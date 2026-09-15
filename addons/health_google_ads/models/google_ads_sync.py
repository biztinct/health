# -*- coding: utf-8 -*-
"""The campaign reporting sync — methods and fields on ``google.ads.account``.

What it does, in one sentence: once a day, and on demand, it reads the last 30
days of campaign names, spend, clicks and Google-reported conversions for one
advertising account into a local cache, and refreshes the per-campaign rollups
the account page shows.

Five postures are load-bearing and each of them is a rail in the handover:

* **Nothing is written to the cache before BOTH fetches have succeeded**, and
  the write happens inside one savepoint (R1). A failed run leaves the previous
  figures exactly where they were and says "last attempt failed" beside them —
  a stale number that admits it is stale beats a zero that looks like a fact.
* **Nothing is ever deleted outside the fetched window** (R2). A campaign that
  has disappeared from Google keeps its row and its `last_seen_at`; only the
  days INSIDE the window Google just answered for are replaced.
* **The window is in the ADVERTISING ACCOUNT's own time zone** (R4), because
  that is the day boundary Google's own figures use.
* **One run per account at a time** (R6), through a PostgreSQL advisory lock —
  never a row lock, which would deadlock against any independent-cursor write
  (ledger §5.74).
* **No HTTP happens in a browser request** (R7). "Sync now" writes a flag and
  nudges the scheduled job; the fetch itself always runs in the job.
"""
import logging
import time
from datetime import date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.google_ads_client import GoogleAdsError
from .google_ads_campaign_day import MICROS_RE

_logger = logging.getLogger(__name__)

# The rolling window: the last 30 account-local calendar days INCLUDING today.
SYNC_WINDOW_DAYS = 30
SYNC_ATTEMPTS = 3
# Waited between attempt 1→2 and 2→3. Never inside a browser request: the only
# caller that retries is the scheduled job.
SYNC_BACKOFF_SECONDS = (2, 8)
# "gasy" in hex — recognisable in `pg_locks`, and distinct from the token
# refresh's REPORTING_LOCK_CLASS (0x67616473, "gads").
SYNC_LOCK_CLASS = 0x67617379
BACKFILL_MAX_DAYS = 365
BACKFILL_WINDOWS_PER_RUN = 3
RUNS_KEPT = 200


def _backoff_sleep(seconds):
    """The only wait in this module, in a plain module-level function.

    A test replaces it with ``patch.object(google_ads_sync, '_backoff_sleep',
    fn)`` — a PLAIN FUNCTION, never ``autospec`` (ledger §5.76). It is never
    reached from a request: `action_sync_now` makes no provider call at all.
    """
    time.sleep(seconds)


class GoogleAdsAccountSync(models.Model):
    _inherit = 'google.ads.account'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    sync_requested_at = fields.Datetime(
        string='Sync Asked For', readonly=True,
        help='When somebody last pressed Sync now. It is cleared as soon as '
             'the figures have been read.')
    backfill_until = fields.Date(
        string='Fetch Back To', readonly=True,
        help='The oldest day still to be fetched. Older days arrive in '
             'batches over the next scheduled runs.')
    backfill_cursor = fields.Date(
        string='Fetched Back To', readonly=True,
        help='The oldest day already fetched. Nothing older than this has '
             'been read yet.')

    campaign_day_count = fields.Integer(
        string='Days of Figures Held', compute='_compute_campaign_day_count')
    unresolved_campaign_count = fields.Integer(
        string='Enquiries with no matching campaign',
        compute='_compute_unresolved_campaign_count',
        help='Google-attributed enquiries on this account whose campaign is '
             'missing or is not one of the campaigns read from Google, so '
             'they appear in no campaign row of the report.')
    sync_run_ids = fields.One2many(
        'google.ads.sync.run', 'account_id', string='Sync History')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('company_id')
    def _compute_campaign_day_count(self):
        Day = self.env['google.ads.campaign.day'].sudo()
        for account in self:
            record = account._origin
            account.campaign_day_count = Day.search_count(
                [('account_id', '=', record.id)]) if record.id else 0

    @api.depends('company_id')
    def _compute_unresolved_campaign_count(self):
        """How many Google-attributed touches this account holds that no
        campaign row explains.

        NON-STORED, like GA1's other touch counters: touchpoints are written by
        the website service in transactions this record has no `@api.depends`
        path to.
        """
        Touch = self.env['health.lead.touchpoint'].sudo()
        for account in self:
            record = account._origin
            if not record.id:
                account.unresolved_campaign_count = 0
                continue
            known = set(record.campaign_ids.mapped('external_campaign_id'))
            rows = Touch.search_read(
                [('google_ads_account_id', '=', record.id),
                 ('google_ads_origin', '!=', False)],
                ['google_ads_campaign_id'])
            account.unresolved_campaign_count = sum(
                1 for row in rows
                if not row['google_ads_campaign_id']
                or row['google_ads_campaign_id'] not in known)

    # ------------------------------------------------------------------
    # The window
    # ------------------------------------------------------------------
    def _sync_zone(self):
        """The advertising account's own IANA zone, or UTC with a warning.

        An unknown zone name must NOT take the sync down: the figures are still
        readable, they are simply counted on UTC days until somebody fixes the
        account.
        """
        self.ensure_one()
        name = (self.account_timezone or '').strip() or 'UTC'
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            _logger.warning(
                'google_ads: advertising account %s reports time zone %r, '
                'which this system does not know — counting days in UTC',
                self.id, name)
            return ZoneInfo('UTC')

    def _sync_today(self):
        self.ensure_one()
        now = fields.Datetime.now().replace(tzinfo=timezone.utc)
        return now.astimezone(self._sync_zone()).date()

    def _sync_window(self, today_local=None):
        """``(date_from, date_to)`` — the last 30 account-local days, today
        included."""
        self.ensure_one()
        if today_local is None:
            today_local = self._sync_today()
        return (today_local - timedelta(days=SYNC_WINDOW_DAYS - 1),
                today_local)

    # ------------------------------------------------------------------
    # The unit of work
    # ------------------------------------------------------------------
    def _sync_reporting(self, kind='scheduled', window=None):
        """Read one account's window into the cache. Never called by a browser.

        Returns the `google.ads.sync.run` row it wrote, or an empty recordset
        when the account was in no state to be read at all.
        """
        self.ensure_one()
        account = self.sudo()
        Run = self.env['google.ads.sync.run'].sudo()
        date_from, date_to = window or account._sync_window()

        # 1. One run per account. An ADVISORY lock, never `FOR UPDATE`: this
        #    transaction writes the account row itself, and a row lock plus any
        #    independent-cursor write of the same row is the self-deadlock of
        #    ledger §5.74. `try` rather than a timeout, so the loser records the
        #    skip instantly instead of waiting out a whole other run.
        self.env.flush_all()
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                            (SYNC_LOCK_CLASS, account.id))
        if not self.env.cr.fetchone()[0]:
            _logger.info('google_ads: account %s is already syncing — skipped',
                         account.id)
            return Run.create({
                'account_id': account.id, 'kind': kind,
                'window_from': date_from, 'window_to': date_to,
                'started_at': fields.Datetime.now(),
                'finished_at': fields.Datetime.now(),
                'state': 'skipped_locked',
            })

        # 2. Nothing to read: no run row either, because nothing was attempted.
        if account.reporting_state not in ('connected', 'syncing') \
                or not account.customer_id:
            return Run.browse()

        now = fields.Datetime.now()
        run = Run.create({
            'account_id': account.id, 'kind': kind,
            'window_from': date_from, 'window_to': date_to,
            'started_at': now, 'state': 'failed', 'attempts': 0,
        })
        account._internal().write({'last_sync_attempt_at': now})

        # 3. Fetch. NOTHING reaches the cache until both calls have answered.
        client = account._google_client()
        login = account.login_customer_id or None
        campaigns = days = None
        error = None
        attempts = 0
        for attempt in range(1, SYNC_ATTEMPTS + 1):
            attempts = attempt
            error = None
            try:
                campaigns = client.list_campaigns(
                    account.customer_id, login_customer_id=login)
                days = client.fetch_campaign_days(
                    account.customer_id, date_from, date_to,
                    login_customer_id=login)
                break
            except GoogleAdsError as err:
                error = err
                if err.needs_reconnect or not err.retryable \
                        or attempt >= SYNC_ATTEMPTS:
                    break
                _backoff_sleep(SYNC_BACKOFF_SECONDS[attempt - 1])
        run.write({'attempts': attempts})

        if error is not None:
            return account._sync_record_failure(run, error)

        # 4. Write. One savepoint over the whole publication, so a failure
        #    anywhere in it leaves the PREVIOUS figures intact (rail R1).
        try:
            with self.env.cr.savepoint():
                counters = account._sync_publish(
                    campaigns, days, date_from, date_to, kind)
                account._internal().write({
                    'last_sync_success_at': fields.Datetime.now(),
                    'last_error_code': False,
                    'reporting_error_redacted': False,
                    'reporting_state': 'connected',
                    'sync_requested_at': False,
                })
                run.write(dict(counters, state='success',
                               finished_at=fields.Datetime.now()))
        except GoogleAdsError as err:
            return account._sync_record_failure(run, err)
        except Exception as err:  # noqa: BLE001 — a job never raises upward
            _logger.exception('google_ads: publishing the window failed for '
                              'account %s', account.id)
            run.write({
                'state': 'failed',
                'error_code': 'publish_failed',
                'detail_redacted': str(err)[:255],
                'finished_at': fields.Datetime.now(),
            })
            return run

        account._sync_prune_runs()
        return run

    # ------------------------------------------------------------------
    def _sync_record_failure(self, run, error):
        """One failed fetch, recorded without touching the cache.

        `needs_reconnect` is its own state: the grant is gone, so there is
        nothing to retry and the account has to say "Action required" until
        somebody signs in again. Every other failure leaves the account
        `connected` — it is the ATTEMPT that failed, not the connection.
        """
        self.ensure_one()
        account = self.sudo()
        code = (getattr(error, 'code', None) or 'error')[:64]
        detail = getattr(error, 'detail_redacted', False) or False
        vals = {
            'error_code': code,
            'detail_redacted': (detail or '')[:255] or False,
            'request_id': (getattr(error, 'request_id', None) or '')[:64]
            or False,
            'finished_at': fields.Datetime.now(),
        }
        if getattr(error, 'needs_reconnect', False):
            vals['state'] = 'skipped_reconnect'
            account._internal().write({
                'reporting_state': 'action_required',
                'last_error_code': code,
                'reporting_error_redacted':
                    account._reporting_message_for(code)[:255],
                'sync_requested_at': False,
            })
        else:
            vals['state'] = 'failed'
            account._internal().write({
                'last_error_code': code,
                'sync_requested_at': False,
            })
        run.write(vals)
        account._sync_prune_runs()
        return run

    def _sync_prune_runs(self):
        """Keep the newest `RUNS_KEPT` runs per account, oldest dropped first."""
        self.ensure_one()
        runs = self.env['google.ads.sync.run'].sudo().search(
            [('account_id', '=', self.id)], order='id desc')
        if len(runs) > RUNS_KEPT:
            runs[RUNS_KEPT:].unlink()

    # ------------------------------------------------------------------
    def _sync_publish(self, campaigns, days, date_from, date_to, kind):
        """Replace the window and refresh the rollups. Runs inside a savepoint.

        Returns the counters the run row records.
        """
        self.ensure_one()
        account = self.sudo()
        now = fields.Datetime.now()
        Campaign = self.env['google.ads.campaign'].sudo()
        Day = self.env['google.ads.campaign.day'].sudo()

        # (a) Campaigns. Upserted, never deleted: a campaign Google no longer
        #     returns still explains the spend already in the cache.
        by_external = {c.external_campaign_id: c
                       for c in account.campaign_ids}
        for entry in campaigns or []:
            external = str(entry.get('id') or '')
            if not external:
                continue
            vals = {
                'name': entry.get('name') or external,
                'status': entry.get('status') or '',
                'advertising_channel_type':
                    entry.get('advertising_channel_type') or '',
                'source': 'provider',
                'last_seen_at': now,
            }
            row = by_external.get(external)
            if row:
                # A row somebody typed in by hand is flipped to `provider` and
                # takes Google's own name: once Google has answered for it,
                # Google's spelling is the one everybody else will recognise.
                row.write(vals)
            else:
                by_external[external] = Campaign.create(dict(
                    vals, account_id=account.id,
                    external_campaign_id=external))

        # (b) Days. The fetched window is REPLACED: revised rows updated in
        #     place, rows Google no longer reports removed, and not one row
        #     outside the window touched (rail R2).
        existing = Day.search([
            ('account_id', '=', account.id),
            ('date', '>=', date_from), ('date', '<=', date_to)])
        by_key = {(row.campaign_id.id, row.date): row for row in existing}
        fetched = set()
        rows_written = 0
        malformed = 0
        unknown = 0
        currency = account.currency_id.id or False
        for entry in days or []:
            campaign = by_external.get(str(entry.get('campaign_id') or ''))
            if not campaign:
                unknown += 1
                continue
            micros = str(entry.get('cost_micros') or '')
            if not MICROS_RE.match(micros):
                # A figure this system cannot store exactly is not stored at
                # all. Counted and reported, never rounded into the total.
                malformed += 1
                continue
            day = entry.get('date')
            if not isinstance(day, date):
                malformed += 1
                continue
            key = (campaign.id, day)
            fetched.add(key)
            vals = {
                'currency_id': currency,
                'impressions': entry.get('impressions') or 0,
                'clicks': entry.get('clicks') or 0,
                'overflow': False,
                'cost_micros': micros,
                'google_conversions': entry.get('conversions') or 0.0,
                'synced_at': now,
            }
            row = by_key.get(key)
            if row:
                row.write(vals)
            else:
                Day.create(dict(vals, account_id=account.id,
                                campaign_id=campaign.id, date=day))
            rows_written += 1

        stale = existing.filtered(
            lambda r: (r.campaign_id.id, r.date) not in fetched)
        rows_removed = len(stale)
        stale.unlink()

        # (c) Rollups. Read back through the report view so ONE definition of
        #     "new enquiry" and "submission" rules everywhere.
        account._sync_refresh_rollups(date_from, date_to, kind)

        detail = []
        if malformed:
            detail.append(_('%s malformed row', malformed)
                          if malformed == 1
                          else _('%s malformed rows', malformed))
        if unknown:
            detail.append(_('%s row for a campaign Google did not list',
                            unknown) if unknown == 1
                          else _('%s rows for campaigns Google did not list',
                                 unknown))
        return {
            'campaigns_seen': len(campaigns or []),
            'rows_written': rows_written,
            'rows_removed': rows_removed,
            'detail_redacted': '; '.join(detail)[:255] or False,
        }

    def _sync_refresh_rollups(self, date_from, date_to, kind='scheduled'):
        """The 30-day figures the account page shows, per campaign.

        A BACKFILL run reads an old window, and "spend over the last 30 days"
        must keep meaning what its name says — so the rollups are always
        computed over the ROLLING window, which for every other kind of run is
        the window just fetched.
        """
        self.ensure_one()
        account = self.sudo()
        if kind == 'backfill':
            date_from, date_to = account._sync_window()
        # The cache was written through the ORM a moment ago and the report is
        # a SQL view: without the flush the view reads the database as it was
        # before this run (ledger §5.9).
        self.env.flush_all()
        Stat = self.env['google.ads.campaign.stat'].sudo()
        totals = {}
        for group in Stat._read_group(
                [('account_id', '=', account.id),
                 ('date', '>=', date_from), ('date', '<=', date_to)],
                groupby=['campaign_id'],
                aggregates=['spend:sum', 'clicks:sum', 'impressions:sum',
                            'google_conversions:sum', 'new_enquiries:sum',
                            'submissions:sum']):
            campaign = group[0]
            totals[campaign.id] = group[1:]
        for campaign in account.campaign_ids:
            spend, clicks, impressions, conversions, new_enquiries, \
                submissions = totals.get(campaign.id, (0.0, 0, 0, 0.0, 0, 0))
            campaign.write({
                'window_from': date_from,
                'window_to': date_to,
                'spend_30d': spend or 0.0,
                'clicks_30d': clicks or 0,
                'impressions_30d': impressions or 0,
                'conversions_30d': conversions or 0.0,
                'new_enquiries_30d': new_enquiries or 0,
                'submissions_30d': submissions or 0,
                'cost_per_new_enquiry_30d': (
                    (spend or 0.0) / new_enquiries) if new_enquiries else 0.0,
            })

    # ==================================================================
    # The scheduled job
    # ==================================================================
    @api.model
    def _cron_sync_reporting(self):
        """Read every connected account, then move the backfill queue on.

        Harmless by default (ledger §5.81): with no connected advertising
        account it makes no provider call of any kind and logs one line saying
        so. Every account is wrapped in its own savepoint, so one clinic's
        Google problem cannot stop another clinic's figures — and the job never
        raises, because a scheduled job that raises is a scheduled job that
        gets switched off.
        """
        accounts = self.sudo().search(
            [('reporting_state', 'in', ('connected', 'syncing'))])
        if not accounts:
            _logger.info('google_ads: reporting sync — no connected '
                         'advertising account, nothing to read')
            return True
        for account in accounts:
            kind = 'scheduled'
            if account.sync_requested_at:
                kind = 'manual' if account.last_sync_success_at else 'initial'
            try:
                with self.env.cr.savepoint():
                    account._sync_reporting(kind)
            except Exception:  # noqa: BLE001 — contained, per account
                _logger.exception(
                    'google_ads: reporting sync failed for account %s',
                    account.id)
        self._cron_run_backfill()
        return True

    @api.model
    def _cron_run_backfill(self):
        """Up to `BACKFILL_WINDOWS_PER_RUN` older windows per account per run.

        Bounded on purpose: a year of history is twelve windows, and asking
        Google for all of them in one go is how an integration gets rate
        limited on the day it is switched on.
        """
        accounts = self.sudo().search([('backfill_until', '!=', False),
                                       ('backfill_cursor', '!=', False)])
        for account in accounts:
            try:
                with self.env.cr.savepoint():
                    account._run_backfill_windows()
            except Exception:  # noqa: BLE001 — contained, per account
                _logger.exception(
                    'google_ads: backfill failed for account %s', account.id)
        return True

    def _run_backfill_windows(self):
        self.ensure_one()
        account = self.sudo()
        for _index in range(BACKFILL_WINDOWS_PER_RUN):
            cursor = account.backfill_cursor
            target = account.backfill_until
            if not cursor or not target or cursor <= target:
                account._internal().write({'backfill_until': False,
                                           'backfill_cursor': False})
                return True
            window_to = cursor - timedelta(days=1)
            window_from = max(window_to - timedelta(days=SYNC_WINDOW_DAYS - 1),
                              target)
            run = account._sync_reporting('backfill',
                                          window=(window_from, window_to))
            if not run or run.state != 'success':
                return False
            account._internal().write({'backfill_cursor': window_from})
            if window_from <= target:
                account._internal().write({'backfill_until': False,
                                           'backfill_cursor': False})
                return True
        return True

    # ==================================================================
    # Buttons
    # ==================================================================
    def _sync_cron(self):
        return self.env.ref(
            'health_google_ads.ir_cron_google_ads_sync_reporting',
            raise_if_not_found=False)

    def _enqueue_sync(self):
        """Ask the scheduled job to read this account, and say so honestly.

        **No provider call happens here** (rail R7). A browser request that
        talks to Google holds a worker for as long as Google feels like taking,
        and a timeout in a button is indistinguishable from a broken account.
        """
        self.ensure_one()
        self._internal().write({
            'sync_requested_at': fields.Datetime.now(),
            'reporting_state': 'syncing',
        })
        cron = self._sync_cron()
        message = _('Sync queued — the numbers refresh within a minute.')
        if cron:
            cron.sudo()._trigger()
            if not cron.sudo().active:
                # A blank template ships with every scheduled job switched off
                # (SaaS runbook §5), and a nudge to a job that is off does
                # nothing at all. Saying so beats a spinner that never ends.
                message = '%s\n\n%s' % (
                    message, _('Scheduled jobs are off on this system, so '
                               'this will not run until they are on.'))
        return message

    def action_sync_now(self):
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        if self.reporting_state == 'syncing' or self.sync_requested_at:
            return self._notify(
                _('Google Ads: already queued'),
                _('A sync is already queued for this advertising account.'),
                kind='warning')
        if self.reporting_state != 'connected':
            raise UserError(_(
                'Connect campaign reporting first — there is nothing to read '
                'until this system has permission to read it.'))
        # The title is the bare channel name on purpose: the body already says
        # "Sync queued", and a title that repeats it reads as a stutter on the
        # screen ("Google Ads: sync queued. Sync queued — …").
        return self._with_reload(self._notify(
            _('Google Ads'), self._enqueue_sync()))

    def action_request_backfill(self):
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        if self.reporting_state not in ('connected', 'syncing'):
            raise UserError(_(
                'Connect campaign reporting first — there is nothing to read '
                'until this system has permission to read it.'))
        wizard = self.env['google.ads.backfill.wizard'].create({
            'account_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fetch older days'),
            'res_model': 'google.ads.backfill.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _scoped_action(self, xmlid, context=None):
        """One of this module's own act_window records, narrowed to this row.

        Always through `_for_xml_id`, NEVER a hand-built dict: the CMS shell
        resolves an opened action against the sidebar leaf's
        `match_action_xmlids`, and an action with no xmlid to match opens
        OUTSIDE the sidebar — the screen loses the whole navigation chrome
        (ledger §5.69/§5.93). Measured in the browser during this phase: the
        sync history opened bare until it was routed through here.
        """
        self.ensure_one()
        self._check_company_scope()
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = [('account_id', '=', self.id)]
        merged = dict(action.get('context') or {}) \
            if isinstance(action.get('context'), dict) else {}
        merged.update(context or {})
        action['context'] = merged
        return action

    def action_open_report(self):
        return self._scoped_action(
            'health_google_ads.action_google_ads_campaign_stat',
            {'search_default_last_30': 1,
             'search_default_group_campaign': 1,
             'search_default_group_currency': 2})

    def action_open_sync_runs(self):
        return self._scoped_action(
            'health_google_ads.action_google_ads_sync_runs')

    def action_open_campaign_days(self):
        return self._scoped_action(
            'health_google_ads.action_google_ads_campaign_days')

    # ------------------------------------------------------------------
    def action_select_reporting_account(self, customer_id,
                                        login_customer_id=None):
        """GA2's binding step, plus the first read.

        The moment a clinic has chosen its advertising account, the honest next
        thing to do is read it: a screen that says "Connected" and shows no
        figures at all invites exactly one question.
        """
        result = super().action_select_reporting_account(
            customer_id, login_customer_id=login_customer_id)
        if self.reporting_state == 'connected':
            self._enqueue_sync()
        return result
