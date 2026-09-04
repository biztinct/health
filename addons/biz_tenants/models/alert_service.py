# -*- coding: utf-8 -*-
"""Noticing, saying so, and admitting it in public.

THE SHAPE OF THIS FILE, and it is the same shape as the rollout before it:
every judgement is next door in `alert_rules.py`, pure and tested. What is left
here is the three things that can only be done on a live machine — measure it,
try to tell somebody, and write a file the web server hands out.

RAIL R1 IS UNTOUCHED. Nothing in this file writes to a customer's system. The
readings are reads: our own cached health fields, one request per customer
through this machine's own web port, read-only SQL on the blank system, the
machine's log, memory and disk. The one thing this phase writes anywhere new is
a static file on this machine.

⚠ AND THE THING THAT MAKES THIS PHASE WHAT IT IS: THERE IS NO OUTGOING MAIL
ACCOUNT ON THIS PLATFORM, AND NONE IS BEING CREATED. So the ALERTS SCREEN is
not the fallback — it is the channel. Everything that would have been sent is
built, is honest about not having been sent, and is readable by anybody who
opens the platform. `channel_state` stays `dark`, `spoken_at` stays empty
(ledger F40), and the "Send a test email" button answers in one plain sentence
rather than with a stack trace or a lie.
"""
import logging
import os
import re
import shutil
from datetime import datetime, timedelta

import odoo
from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common
from .alert_rules import (
    ALERT_KINDS, BACKUP_MIN_FILES, DEFAULT_THRESHOLDS, KIND_ICON, KIND_LABEL,
    SEVERITY_WORD, capacity_verdict, digest_headline, digest_lines,
    readings_to_alerts, reconcile, render_status_page, should_notify,
    status_state, worst_severity,
)
from .rollout_rules import CUSTOMER_RINGS, DEFAULT_TZ, say_window, to_local
from .sync_rules import log_lines_by_database

_logger = logging.getLogger(__name__)

#: How far back each sweep looks in the machine's log.
ALERT_WINDOW_MIN = 15
#: How long a problem that is over stays on the public page as an incident.
#: ⚠ THIS IS WHY VALIDATION ALERTS MUST BE DELETED AND NOT RESOLVED (F41).
INCIDENT_DAYS = 7

EMAIL_RE = re.compile(r'^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$')

#: The threshold settings, `biz_tenants.alert_<name>` -> the name the rules use.
THRESHOLD_KEYS = ('disk_free_pct', 'mem_available_mb', 'backup_stale_hours',
                  'cert_days', 'error_lines')


class BizTenantsAlerts(models.AbstractModel):
    """The alerting, capacity and public-page half of the cockpit."""
    _inherit = 'biz.tenants'

    # =====================================================================
    #  SETTINGS
    # =====================================================================
    def _alert_thresholds(self):
        """Every number the rules judge by: the defaults, then the settings."""
        out = dict(DEFAULT_THRESHOLDS)
        for name in THRESHOLD_KEYS:
            raw = common.param_row(self.env, 'biz_tenants.alert_%s' % name)
            if raw in ('', None):
                continue
            try:
                out[name] = float(raw) if '.' in str(raw) else int(raw)
            except (TypeError, ValueError):
                _logger.warning("biz_tenants: the threshold %s is not a number "
                                "(%r) — using the default.", name, raw)
        return out

    def _alert_recipients(self):
        """Who WOULD be told. The setting if there is one, otherwise every
        platform administrator with an address.

        Falling back to the administrators rather than to a written-down
        address means a platform nobody has configured still knows who to
        reach — which is the state in which that matters most.
        """
        raw = common.param_row(self.env, common.P_ALERT_TO) or ''
        picked = [e.strip() for e in re.split(r'[,;\s]+', raw) if e.strip()]
        if picked:
            return [e for e in picked if EMAIL_RE.match(e)]
        out = []
        for u in self.env['res.users'].sudo().search([
                ('active', '=', True), ('share', '=', False),
                ('email', '!=', False)]):
            if u.has_group('base.group_system') and EMAIL_RE.match(u.email or ''):
                if u.email not in out:
                    out.append(u.email)
        return out

    # =====================================================================
    #  THE CHANNEL — BUILT, AND HONESTLY DARK
    # =====================================================================
    def _mail_capability(self):
        """Can this platform send anything at all? `(bool, plain reason)`.

        ⚠ THE OLD SHAPE OF THIS CHECK WAS A LIE BY OMISSION (ledger F5): it
        asked whether an outgoing mail server RECORD existed, which was true on
        a platform where a thousand messages sat in the failed pile. What is
        asked here is whether there is an account AND a sender address, because
        without the second the framework refuses to send and files the message
        under "exception", where nobody looks.
        """
        server = self.env['ir.mail_server'].sudo().search([], limit=1)
        icp = self.env['ir.config_parameter'].sudo()
        sender = (icp.get_param('mail.default.from') or '').strip()
        if not server and not sender:
            return False, ("There is no outgoing mail account on this platform "
                           "yet, so nothing can be sent to anybody.")
        if not server:
            return False, ("There is a sender address but no outgoing mail "
                           "account, so nothing can actually leave this "
                           "machine.")
        if not sender:
            return False, ("There is an outgoing mail account but no sender "
                           "address, so every message would be refused and "
                           "filed away unsent.")
        return True, ''

    def _send_alert_mail(self, subject, body_text, recipients=None):
        """Build the message, ask whether it can go, and say what happened.

        Returns `(state, reason)` where state is `dark`, `sent` or `failed`.

        ⚠ IT NEVER RAISES AND IT NEVER QUEUES A MESSAGE THAT CANNOT GO. A
        thousand and thirty-four messages already sit unsent on this platform;
        adding to that pile every fifteen minutes would be the same mistake
        with a bigger number. When there is nothing to send WITH, the answer is
        `dark` and the reason is a sentence a person can act on.

        ⚠ AND UNDER A TEST RUN IT DOES NOT EVEN BUILD ONE (ledger F67). The
        suite's own attempts to send wrote five ERROR lines per run into the
        very log the rollout's health gate reads, so a test run could fail the
        next rollout.
        """
        if odoo.tools.config['test_enable']:
            return 'dark', "This is a test run, so nothing was sent."
        can, why = self._mail_capability()
        to = recipients if recipients is not None else self._alert_recipients()
        to = [e for e in (to or []) if EMAIL_RE.match(e or '')]
        if not can:
            return 'dark', why
        if not to:
            return 'dark', ("There is nobody to send platform alerts to. Add "
                            "an address in the alert settings, or give the "
                            "platform administrator an email address.")
        sender = (self.env['ir.config_parameter'].sudo()
                  .get_param('mail.default.from') or '').strip()
        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_text,
                'email_from': sender,        # ALWAYS explicit — ledger F5
                'email_to': ','.join(to),
                'auto_delete': False,
            })
            mail.send(raise_exception=True)
            mail.invalidate_recordset(['state', 'failure_reason'])
            if mail.state != 'sent':
                return 'failed', (mail.failure_reason or
                                  "The message was refused and nobody has it.")
        except Exception as exc:                             # noqa: BLE001
            _logger.error("biz_tenants: a platform message failed: %s", exc)
            return 'failed', str(exc).strip().split('\n')[0][:240]
        return 'sent', ''

    # =====================================================================
    #  WHAT WOULD HAVE BEEN SENT — built, and readable on screen
    # =====================================================================
    def _alert_message(self, alerts, reminder=False):
        """The message a group of problems would go out as. `(subject, body)`.

        ⚠ THE SEVERITY FLOOR (ledger F68). A group whose worst member is only
        `info` is announced "For information" and NOTHING LOUDER. Telling
        somebody that something "needs their attention" when it does not is
        crying wolf about the one thing that must never be scrolled past.
        """
        rows = [a for a in alerts]
        if not rows:
            return None
        worst = worst_severity([{'severity': a.severity} for a in rows])
        word = SEVERITY_WORD.get(worst, "Worth a look")
        brand = common.brand(self.env) or "The platform"
        if reminder:
            subject = ("[%s] Still open: %s" % (brand, rows[0].subject)
                       if len(rows) == 1
                       else "[%s] Still open: %d things" % (brand, len(rows)))
            intro = ("This is a reminder. Nothing here is new, and none of it "
                     "has cleared on its own.")
        elif len(rows) == 1:
            subject = '[%s] %s: %s' % (brand, word, rows[0].subject)
            intro = ("One thing worth knowing." if worst == 'info'
                     else "One new thing needs you.")
        else:
            subject = '[%s] %s: %d new things' % (brand, word, len(rows))
            intro = ("%d things worth knowing." % len(rows) if worst == 'info'
                     else "%d new things need you." % len(rows))
        blocks = []
        for a in rows:
            where = (' · %s' % a.tenant_id.name) if a.tenant_id else ''
            blocks.append('%s%s\n%s\n%s'
                          % (a.subject, where,
                             SEVERITY_WORD.get(a.severity, ''),
                             a.body_text or ''))
        return subject, '%s\n\n%s' % (intro, '\n\n'.join(blocks))

    # =====================================================================
    #  READINGS — reads only, rail R1
    # =====================================================================
    def _memory_reading(self):
        """What this machine has. /proc, and NOT the registry cache.

        ⚠ THE REGISTRY CACHE IS NOT A BOUND ON THIS MACHINE (ledger F6). It is
        sized from `limit_memory_soft`, so asked how many customers fit it
        would answer with a number in the hundreds on a machine with room for
        two.
        """
        out = {'total_mb': 0, 'available_mb': None}
        try:
            with open('/proc/meminfo', encoding='utf-8') as fh:
                for line in fh:
                    if line.startswith('MemTotal:'):
                        out['total_mb'] = int(int(line.split()[1]) / 1024)
                    elif line.startswith('MemAvailable:'):
                        out['available_mb'] = int(int(line.split()[1]) / 1024)
        except OSError:
            pass
        return out

    def _disk_reading(self):
        try:
            du = shutil.disk_usage('/')
            return {'free_pct': int(du.free * 100 / du.total),
                    'free_gb': round(du.free / (1024.0 ** 3), 1),
                    'total_gb': round(du.total / (1024.0 ** 3), 1)}
        except OSError:
            return {}

    def _log_error_counts(self, dbnames, since):
        """Error lines per system since a moment — ONE PASS over the log.

        ⚠ Ledger F39. The health gate reads a twenty-megabyte tail to answer
        about one system, which is right for a rollout. This sweep asks about
        every live customer plus the platform's own system every quarter of an
        hour, and one pass per customer would be twenty megabytes of reading
        per customer per sweep on a machine with two gigabytes of memory.
        """
        wanted = list(dbnames or ())
        if not wanted:
            return {}
        lines = self._log_tail_lines()
        if lines is None:
            return {db: {'errors': [], 'ignored': []} for db in wanted}
        stamp = (since.strftime('%Y-%m-%d %H:%M:%S')
                 if isinstance(since, datetime) else str(since or ''))
        return log_lines_by_database(lines, wanted, stamp,
                                     common.health_ignore(self.env))

    def _status_dir(self):
        return (common.param(self.env, common.P_STATUS_DIR) or '').strip()

    def _status_file(self):
        folder = self._status_dir()
        return os.path.join(folder, 'index.html') if folder else ''

    def _status_reading(self):
        folder, path = self._status_dir(), self._status_file()
        if not folder:
            return {'writable': False, 'age_min': None,
                    'reason': "Nobody has said where the public page should be "
                              "written."}
        if not os.path.isdir(folder):
            return {'writable': False, 'age_min': None,
                    'reason': "The folder %s does not exist." % folder}
        if not os.access(folder, os.W_OK):
            return {'writable': False, 'age_min': None,
                    'reason': "The folder %s cannot be written by this "
                              "application." % folder}
        age = None
        if os.path.exists(path):
            age = int((datetime.now().timestamp()
                       - os.path.getmtime(path)) / 60)
        return {'writable': True, 'age_min': age, 'reason': ''}

    def _gather_readings(self, window_minutes=ALERT_WINDOW_MIN):
        """Everything the rules need, measured. READS ONLY.

        Nothing here opens a customer's system: the health fields are the cache
        the hourly job keeps, the site check is one request through this
        machine's own web port, and the only query that leaves this database is
        a count of scheduled jobs on the blank system.
        """
        now = fields.Datetime.now()
        since = now - timedelta(minutes=window_minutes)
        live = self._tenants().search([('state', '=', 'live')])
        counts = self._log_error_counts(
            [t.slug for t in live] + [self.env.cr.dbname], since)
        Backup = self.env['biz.tenant.backup'].sudo()
        rows = []
        for t in live:
            code, _ms = self._probe(self._tenant_host(t.slug))
            last = Backup.search([('tenant_id', '=', t.id)],
                                 order='taken_at desc, id desc', limit=1)
            days_left = None
            if t.cert_expires_on:
                days_left = (t.cert_expires_on - fields.Date.today()).days
            rows.append({
                'id': t.id, 'name': t.name, 'slug': t.slug, 'state': t.state,
                'health': 'ok' if code == 200 else 'down',
                'last_backup_at': t.last_backup_at or None,
                'last_backup_failed': bool(last and last.state == 'failed'),
                # F59/H70 again, read back rather than assumed: a copy whose
                # attachments archive holds fewer files than a blank system does
                # is not a copy anybody could restore from.
                'last_backup_small': bool(
                    last and last.state == 'done'
                    and 0 < (last.filestore_files or 0) < BACKUP_MIN_FILES),
                'cert_state': t.cert_state or 'none',
                'cert_days_left': days_left,
                'error_lines': len(counts.get(t.slug, {}).get('errors', [])),
                'release_state': t.release_state,
                'behind_count': t.behind_count,
                'stale_count': t.stale_count,
            })

        can_send, why = self._mail_capability()
        roll = self.env['biz.rollout'].sudo().search(
            [('state', 'in', ('rehearsing', 'running', 'waiting', 'paused'))],
            order='id desc', limit=1)
        return {
            'now': now,
            'tenants': rows,
            'disk': self._disk_reading(),
            'memory': self._memory_reading(),
            'capacity': self._capacity(),
            'mail': {'can_send': can_send, 'reason': why},
            'rollout': ({'state': roll.state, 'release': roll.release_id.name,
                         'reason': (roll.note or '').split('\n')[0]}
                        if roll else {}),
            'status_page': self._status_reading(),
            # ⚠ GATHERED AND DELIBERATELY NOT ALERTED ON (ledger F39). This
            # machine logs its own test runs, so a rule about the platform's
            # own error count would have to be written against that noise
            # first — and a rule written against noise is a rule nobody trusts.
            'master_errors': len(
                counts.get(self.env.cr.dbname, {}).get('errors', [])),
        }

    # =====================================================================
    #  THE SWEEP
    # =====================================================================
    @api.model
    def _cron_alerts(self):
        """Every fifteen minutes: look, compare with what we knew, then speak.

        THE ORDER MATTERS. Reconciling BEFORE speaking means a problem that
        cleared between two sweeps stops being reminded about in the same run
        that says it is over, and the public page written at the end is written
        from the reconciled truth rather than from the raw readings.
        """
        now = fields.Datetime.now()
        Alert = self.env['biz.alert'].sudo()
        try:
            readings = self._gather_readings()
        except Exception:                                    # noqa: BLE001
            _logger.exception("biz_tenants: the alert sweep could not take its "
                              "readings")
            return
        fresh = readings_to_alerts(readings, self._alert_thresholds())
        known = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        to_create, to_bump, to_resolve = reconcile(known.as_dict(), fresh, now)

        created = Alert.browse()
        for vals in to_create:
            created |= Alert.create({
                'key': vals['key'], 'kind': vals['kind'],
                'severity': vals['severity'], 'subject': vals['title'],
                'body_text': vals['text'],
                'tenant_id': vals.get('tenant_id') or False,
                'first_seen': now, 'last_seen': now, 'count': 1,
                'state': 'open', 'channel_state': 'dark',
            })
        for aid, vals in to_bump:
            Alert.browse(aid).write(vals)
        closing = Alert.browse(to_resolve)
        if closing:
            closing.write({'state': 'resolved', 'resolved_at': now,
                           'resolution': "The platform checked again and it "
                                         "had cleared."})
        self.env.cr.commit()

        crit_h, warn_h = common.alert_intervals(self.env)
        reminders = Alert.browse()
        for a in Alert.search([('state', '=', 'open')]):
            if a in created:
                continue
            if should_notify(a.as_dict()[0], now, crit_h, warn_h):
                reminders |= a
        self._speak(created, reminders, now)
        try:
            self._write_status_page()
        except Exception:                                    # noqa: BLE001
            _logger.exception("biz_tenants: the public page could not be "
                              "written")
        self.env.cr.commit()

    def _speak(self, created, reminders, now):
        """At most two messages per sweep, never one per problem.

        ⚠ THE STAMP IS ONLY WRITTEN WHEN THE MESSAGE ACTUALLY WENT (ledger
        F40). If a send fails — or, as today, never happens at all — and this
        stamped anyway, the problem would fall silent for two hours on the
        strength of a message nobody received. With the channel dark, every
        alert keeps `channel_state = dark` and an empty `spoken_at`, and the
        reason is written on the record so the screen can say it out loud.
        """
        for group, reminder in ((created, False), (reminders, True)):
            if not group:
                continue
            made = self._alert_message(group, reminder=reminder)
            if not made:
                continue
            state, reason = self._send_alert_mail(made[0], made[1])
            if state == 'sent':
                for a in group:
                    a.write({'spoken_at': now, 'spoken_severity': a.severity,
                             'channel_state': 'sent', 'channel_reason': ''})
            else:
                group.write({'channel_state': state, 'channel_reason': reason})

    @api.model
    def _cron_alert_digest(self):
        """One short summary a day, whether or not anything is wrong.

        THE EMPTY ONE IS THE POINT. A channel that only ever speaks when
        something is broken is a channel nobody can tell apart from a broken
        channel. Today nothing is sent at all, and the summary is written down
        here where the Alerts screen shows it — which is the same promise kept
        with the only channel there is.
        """
        now = fields.Datetime.now()
        rows = self.env['biz.alert'].sudo().search(
            [('state', 'in', ('open', 'acknowledged'))])
        live = self._tenants().search_count([('state', '=', 'live')])
        data = rows.as_dict()
        heading, intro = digest_headline(data, live)
        lines = digest_lines(data, now)
        brand = common.brand(self.env) or "The platform"
        subject = '[%s] Morning summary — %s' % (brand, heading.lower())
        body = '%s\n\n%s' % (intro, '\n'.join(lines) if lines
                             else "Nothing is open.")
        state, reason = self._send_alert_mail(subject, body)
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_tenants.digest_last',
            '%s|%s|%s' % (now.strftime('%Y-%m-%d %H:%M:%S'), state, reason))
        return {'state': state, 'reason': reason, 'heading': heading,
                'intro': intro, 'lines': lines}

    @api.model
    def _cron_status_page(self):
        try:
            self._write_status_page()
        except Exception:                                    # noqa: BLE001
            _logger.exception("biz_tenants: the public page could not be "
                              "written")

    # =====================================================================
    #  CAPACITY
    # =====================================================================
    def _capacity(self):
        mem = self._memory_reading()
        live = self._tenants().search_count([('state', '=', 'live')])
        return capacity_verdict(mem['total_mb'], mem['available_mb'], live,
                                common.tenant_cost_mb(self.env),
                                common.capacity_reserve_mb(self.env))

    @api.model
    def capacity_check(self):
        """What the fleet screen shows and the new-customer wizard asks."""
        self._require_platform_admin()
        return self._capacity()

    def _capacity_gate(self):
        """THE REFUSAL, and it names the setting and the way out.

        This replaces the raw memory floor the first version of provisioning
        carried. The floor asked "is there 400 MB free" — a fair question with
        no relationship to how much of that a customer would need. This asks
        the question that matters: is there room for ONE MORE, given what one
        is allowed and what has to stay free for the rest of the machine.
        """
        cap = self._capacity()
        if cap['level'] != 'full':
            return cap
        raise UserError(self.env._(
            "There is no room on this machine for another customer.\n\n"
            "%(reason)s\n\n"
            "Nothing is broken and nobody is affected. What to do next: remove "
            "any practice copies, which each hold a whole system's worth of "
            "memory — or make the machine bigger. The one-page guide for that "
            "is docs/SAAS_RESIZE_RUNBOOK.md. If you believe a customer costs "
            "less than the %(cost)s MB this platform allows for one, that "
            "figure is a setting (%(key)s) and can be re-weighed.",
            reason=cap['reason'], cost=cap['cost_per_tenant_mb'],
            key=common.P_TENANT_COST))

    # =====================================================================
    #  THE PUBLIC PAGE
    # =====================================================================
    def _status_tz(self):
        """Whose clock the public page speaks in.

        ⚠ THE PAGE HAS NO READER TO ASK WHAT TIME IT IS (ledger F38). A
        customer's own bar renders its window in the browser that is drawing
        it; a file on disk cannot, so the window has to be SAID in a named zone
        or it is a lie by omission — a window typed as 22:34 appeared to the
        world as 12:34 the first time this was got wrong.
        """
        picked = (common.param_row(self.env, common.P_STATUS_TZ) or '').strip()
        if picked:
            return picked
        try:
            tz = self.env.company.partner_id.tz
        except Exception:                                    # noqa: BLE001
            tz = ''
        return tz or DEFAULT_TZ

    def _public_notices(self):
        """The messages on customers' own bars, said once and named nowhere.

        The same announcement sent to five customers is five mirrors of ONE
        message, so it is de-duplicated on its text — otherwise the public page
        would repeat one maintenance window five times and read like five
        separate outages. AND THE CUSTOMER IS NEVER NAMED: what leaves here is
        the sentence and the window, nothing else.
        """
        now = fields.Datetime.now()
        tz = self._status_tz()
        local_now = to_local(now, tz)
        seen, out = set(), []
        for t in self._tenants().search([('state', '=', 'live')]):
            text = (t.notice or '').strip()
            if not text:
                continue
            if t.notice_to and t.notice_to <= now:
                continue
            if text in seen:
                continue
            seen.add(text)
            window = ''
            if t.notice_from:
                window = say_window(to_local(t.notice_from, tz),
                                    to_local(t.notice_to, tz), local_now, tz)
                # "their time" is the customer's phrase and is meaningless on a
                # public page: this one speaks the platform's own clock, named.
                window = window.replace(' · their time · ', ' · ')
            out.append({'kind': t.notice_kind or 'info', 'text': text,
                        'range': window})
        return out

    def _status_inputs(self):
        now = fields.Datetime.now()
        tz = self._status_tz()
        Alert = self.env['biz.alert'].sudo()
        opens = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        since = now - timedelta(days=INCIDENT_DAYS)
        closed = Alert.search([('state', '=', 'resolved'),
                               ('severity', '=', 'critical'),
                               ('resolved_at', '>=', since)])
        incidents = []
        for a in closed:
            mins = 0
            if a.first_seen and a.resolved_at:
                mins = int((a.resolved_at - a.first_seen).total_seconds() / 60)
            incidents.append({'kind': a.kind, 'minutes': mins,
                              'ended': a.resolved_at})
        incidents.sort(key=lambda i: str(i['ended'] or ''), reverse=True)
        roll = self.env['biz.rollout'].sudo().search(
            [('state', 'in', ('rehearsing', 'running', 'waiting'))], limit=1)
        maintenance = bool(roll and roll.ring in CUSTOMER_RINGS)
        local = to_local(now, tz)
        state = status_state(
            opens.as_dict(), self._public_notices(), incidents[:12], now,
            maintenance=maintenance,
            updated_at=local.strftime('%Y-%m-%d %H:%M') if local else '',
            tz=tz)
        # The absolute instant, so the reader's own browser can tell how old the
        # page is whatever zone either of them happens to be in.
        state['updated_iso'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        return state

    def _write_status_page(self):
        """Write the page the web server hands out, atomically.

        Temp file plus a rename, because a reader arriving mid-write must get
        the OLD page rather than half of the new one — the whole promise of
        this file is that it is there when nothing else is.

        ⚠ A FILE WRITTEN BY A MODEL IS NOT ROLLED BACK BY A TEST (ledger F44).
        The suite runs against an invented fleet inside a transaction that is
        thrown away — but this write is not in that transaction, so a run on
        the live platform once PUBLISHED a page built from customers that do
        not exist. Every caller is covered HERE rather than in each test,
        because the callers are the two buttons, two scheduled jobs and every
        message sent or cleared, and the next one will be written by somebody
        who has not read this comment.
        """
        path = self._status_file()
        if odoo.tools.config['test_enable']:
            return {'ok': True, 'path': path, 'skipped': 'test run'}
        if not path:
            return {'ok': False, 'path': '',
                    'reason': "Nobody has said where the public page should be "
                              "written."}
        folder = os.path.dirname(path)
        state = self._status_inputs()
        page = render_status_page(state, common.brand(self.env),
                                  self._status_tz())
        tmp = path + '.tmp'
        try:
            os.makedirs(folder, exist_ok=True)
            with open(tmp, 'w', encoding='utf-8') as fh:
                fh.write(page)
            os.replace(tmp, path)
        except OSError as exc:
            _logger.warning("biz_tenants: could not write %s: %s", path, exc)
            return {'ok': False, 'reason': str(exc), 'path': path}
        return {'ok': True, 'path': path, 'level': state['level'],
                'bytes': len(page)}

    def _refresh_status_page_quietly(self):
        """Rewrite the page, and NEVER let that break what called it.

        Sending a message to a customer must not fail because a folder on this
        machine is missing. The missing folder is an alert of its own, raised by
        the sweep, which is the right place for it.
        """
        try:
            return self._write_status_page()
        except Exception:                                    # noqa: BLE001
            _logger.exception("biz_tenants: the public page could not be "
                              "written")
            return {'ok': False}

    @api.model
    def status_page_refresh(self):
        self._require_platform_admin()
        return self._write_status_page()

    @api.model
    def status_page_preview(self):
        """The page as it stands, for a screenshot and for a test."""
        self._require_platform_admin()
        return render_status_page(self._status_inputs(),
                                  common.brand(self.env), self._status_tz())

    def _status_url(self):
        apex = self._apex()
        return 'https://%s/status' % apex if apex else ''

    def _status_served(self):
        """Is the WEB SERVER really handing the file out? Asked of it, not of us.

        ⚠ THE PROOF IS TWO HEADERS. A file handed out from disk carries
        `Last-Modified` and an `ETag`; a page built by this application carries
        neither. That is how this tells "the web server served the file" from
        "the application answered that address" — and the whole point of the
        page is that it keeps working when the application does not.
        """
        import socket
        import ssl
        host = self._apex()
        if not host:
            return {'code': 0, 'server_file': False, 'error': 'no address set'}
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection(('127.0.0.1', 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as tls:
                    tls.sendall(
                        ("GET /status HTTP/1.1\r\nHost: %s\r\n"
                         "User-Agent: platform-status-check\r\n"
                         "Connection: close\r\n\r\n" % host).encode())
                    chunks, got = [], 0
                    while got < 8192:
                        part = tls.recv(4096)
                        if not part:
                            break
                        chunks.append(part)
                        got += len(part)
            raw = b''.join(chunks).decode('utf-8', 'replace')
            head, _sep, body = raw.partition('\r\n\r\n')
            first = head.split('\r\n')[0] if head else ''
            parts = first.split()
            code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            low = head.lower()
            return {
                'code': code,
                'server_file': 'last-modified:' in low or 'etag:' in low,
                'is_status': 'status</title>' in body.lower(),
            }
        except Exception as exc:                             # noqa: BLE001
            return {'code': 0, 'error': str(exc)[:160], 'server_file': False,
                    'is_status': False}

    # =====================================================================
    #  THE PLATFORM CHECKS — and F42: THE CARD DOES NOT HIDE ITSELF
    # =====================================================================
    def platform_checks(self):
        """Three rows about the platform itself, always shown.

        ⚠ IT DOES NOT HIDE ITSELF WHEN EVERYTHING IS GREEN (ledger F42). The
        card that went away the moment its checks passed took the "Send a test
        email" button with it — and that button is wanted on a good day too,
        because a good day is exactly when nobody finds out the channel is
        broken.
        """
        can_send, why = self._mail_capability()
        reading = self._status_reading()
        served = self._status_served()
        age = reading.get('age_min')
        fresh = (age is not None
                 and age < DEFAULT_THRESHOLDS['status_page_minutes'])
        cap = self._capacity()

        if reading.get('writable') is False:
            status_hint = ('%s Create it on the machine and let this '
                           'application write to it.' % reading.get('reason'))
        elif age is None:
            status_hint = ("The page has never been written. Press Refresh — it "
                           "is rewritten every five minutes and after every "
                           "check.")
        elif not fresh:
            status_hint = ("The page is %d minutes old, so it would tell "
                           "somebody something stale. Check the scheduled jobs "
                           "are running." % age)
        elif served.get('code') != 200:
            status_hint = ("The file is there but %s does not hand it out (%s). "
                           "The web server needs the /status location — see the "
                           "status-page section of docs/SAAS_RUNBOOK.md."
                           % (self._status_url(),
                              served.get('error')
                              or 'it answered %s' % served.get('code')))
        elif not served.get('server_file'):
            status_hint = ("Something is answering that address, but not from "
                           "disk — which means it would go down with the "
                           "application it is supposed to report on.")
        else:
            status_hint = ("Handed out from disk by the web server, and %d "
                           "minutes old." % (age or 0))

        return [
            {
                'key': 'mail',
                'label': "Somebody can be told",
                'ok': can_send,
                'hint': (why + " Everything that would have been sent is on "
                               "this screen instead, and nothing is lost."
                         if not can_send else
                         "Messages can leave this machine. Press \"Send a test "
                         "email\" to prove it end to end."),
                'action': 'mail_test',
                'action_label': "Send a test email",
            },
            {
                'key': 'status_page',
                'label': "The public page",
                'ok': bool(fresh and served.get('code') == 200
                           and served.get('server_file')),
                'hint': status_hint,
                'link': self._status_url(),
                'link_label': "Open the page",
            },
            {
                'key': 'capacity',
                'label': "Room for another customer",
                'ok': cap['level'] != 'full',
                'hint': cap['reason'],
            },
        ]

    # =====================================================================
    #  THE ALERTS SCREEN — the second hero, and today the ONLY channel
    # =====================================================================
    @api.model
    def alerts_data(self, mark_seen=True):
        """Everything the Alerts screen draws.

        "SINCE YOU WERE LAST HERE" IS NOT DECORATION. With nothing being
        emailed, this screen is how the owner finds out that anything happened
        at all, so the first thing it has to answer is "what is new to ME".
        """
        self._require_platform_admin()
        Alert = self.env['biz.alert'].sudo()
        now = fields.Datetime.now()
        seen_raw = common.param_row(self.env, common.P_ALERTS_SEEN) or ''
        seen_at = None
        if seen_raw:
            try:
                seen_at = fields.Datetime.to_datetime(seen_raw)
            except (TypeError, ValueError):
                seen_at = None

        opens = Alert.search([('state', 'in', ('open', 'acknowledged'))])
        history = Alert.search([('state', '=', 'resolved'),
                                ('resolved_at', '>=', now - timedelta(days=30))],
                               order='resolved_at desc', limit=100)

        def brief(a):
            row = a.as_dict()[0]
            row['since'] = self._stamp(a.first_seen) or ''
            row['seen'] = self._stamp(a.last_seen) or ''
            row['ended'] = self._stamp(a.resolved_at) or ''
            row['age'] = self._age_words(a.first_seen, a.resolved_at or now)
            row['spoken'] = self._stamp(a.spoken_at) or ''
            row['is_new'] = bool(seen_at and a.first_seen
                                 and a.first_seen > seen_at)
            for key in ('first_seen', 'last_seen', 'spoken_at', 'resolved_at'):
                row.pop(key, None)
            return row

        rows = [brief(a) for a in opens]
        crit_h, warn_h = common.alert_intervals(self.env)
        can_send, why = self._mail_capability()
        data = opens.as_dict()
        heading, intro = digest_headline(
            data, self._tenants().search_count([('state', '=', 'live')]))
        out = {
            'critical': [r for r in rows if r['severity'] == 'critical'
                         and r['state'] == 'open'],
            'warning': [r for r in rows if r['severity'] == 'warning'
                        and r['state'] == 'open'],
            'info': [r for r in rows if r['severity'] == 'info'
                     and r['state'] == 'open'],
            'acknowledged': [r for r in rows if r['state'] == 'acknowledged'],
            'history': [brief(a) for a in history],
            'open_count': len(rows),
            'critical_count': len([r for r in rows
                                   if r['severity'] == 'critical'
                                   and r['state'] == 'open']),
            'new_count': len([r for r in rows if r['is_new']]),
            'seen_at': self._stamp(seen_at) if seen_at else '',
            'digest': {'heading': heading, 'intro': intro,
                       'lines': digest_lines(data, now)},
            'channel': {'can_send': can_send, 'reason': why,
                        'recipients': self._alert_recipients()},
            'intervals': {'critical': crit_h, 'warning': warn_h},
            'checked_at': self._stamp(now),
            'status_url': self._status_url(),
            'checks': self.platform_checks(),
            'kinds': [{'key': k, 'label': KIND_LABEL.get(k, k),
                       'icon': KIND_ICON.get(k, 'alert')} for k in ALERT_KINDS],
        }
        if mark_seen:
            self.env['ir.config_parameter'].sudo().set_param(
                common.P_ALERTS_SEEN, now.strftime('%Y-%m-%d %H:%M:%S'))
        return out

    @staticmethod
    def _age_words(start, end):
        if not start or not end:
            return ''
        mins = int((end - start).total_seconds() / 60)
        if mins < 60:
            return "%d min" % max(1, mins)
        if mins < 60 * 48:
            return "%d h" % int(round(mins / 60.0))
        return "%d days" % int(round(mins / 1440.0))

    @api.model
    def alert_banner(self):
        """The one line the fleet screen carries when something is urgent.

        Generalised from the one alert that could never email itself: with no
        mail account at all, EVERY alert is in that position, so the banner is
        about all of them.
        """
        self._require_platform_admin()
        Alert = self.env['biz.alert'].sudo()
        crit = Alert.search([('state', '=', 'open'),
                             ('severity', '=', 'critical')], order='first_seen')
        opens = Alert.search_count([('state', 'in', ('open', 'acknowledged'))])
        if not crit:
            return {'level': '', 'text': '', 'open': opens}
        first = crit[0]
        return {
            'level': 'critical',
            'count': len(crit),
            'open': opens,
            'text': (first.subject if len(crit) == 1
                     else "%s, and %d more" % (first.subject, len(crit) - 1)),
            'dark': first.channel_state == 'dark',
        }

    @api.model
    def alert_ack(self, alert_id):
        self._require_platform_admin()
        rec = self.env['biz.alert'].sudo().browse(int(alert_id)).exists()
        if not rec:
            raise UserError(self.env._("That alert is no longer there."))
        rec.write({'state': 'acknowledged', 'acknowledged_by': self.env.uid,
                   'acknowledged_at': fields.Datetime.now()})
        self._refresh_status_page_quietly()
        return self.alerts_data(mark_seen=False)

    @api.model
    def alert_resolve(self, alert_id, reason=''):
        self._require_platform_admin()
        rec = self.env['biz.alert'].sudo().browse(int(alert_id)).exists()
        if not rec:
            raise UserError(self.env._("That alert is no longer there."))
        rec.write({'state': 'resolved', 'resolved_at': fields.Datetime.now(),
                   'resolution': (reason or '').strip()[:240]
                   or "Closed by hand."})
        self._refresh_status_page_quietly()
        return self.alerts_data(mark_seen=False)

    @api.model
    def alert_delete(self, alert_id):
        """Remove an alert altogether, rather than closing it.

        ⚠ THIS IS NOT THE SAME BUTTON AS "IT IS OVER" (ledger F41). A RESOLVED
        urgent alert becomes an incident on the PUBLIC page for seven days,
        which is right for something that really happened and wrong for one
        raised while somebody was testing the alarm. Anything raised on purpose
        during a check has to be DELETED, or the platform advertises an
        incident that never happened.
        """
        self._require_platform_admin()
        rec = self.env['biz.alert'].sudo().browse(int(alert_id)).exists()
        if not rec:
            raise UserError(self.env._("That alert is no longer there."))
        rec.unlink()
        self._refresh_status_page_quietly()
        return self.alerts_data(mark_seen=False)

    @api.model
    def alert_check_now(self):
        """Run the sweep by hand. The same code the scheduled job runs."""
        self._require_platform_admin()
        self._cron_alerts()
        return self.alerts_data(mark_seen=False)

    @api.model
    def mail_test(self):
        """Prove the channel — or say, in one plain sentence, why there is none.

        ⚠ NEVER A STACK TRACE AND NEVER A LIE. On this platform today the
        honest answer is that no outgoing mail account exists, so nothing can
        be sent; the button says exactly that and says what to do about it.
        """
        self._require_platform_admin()
        can, why = self._mail_capability()
        if not can:
            return {
                'ok': False, 'state': 'dark', 'to': self._alert_recipients(),
                'message': (
                    "%s Connect one under Settings → Technical → Email →"
                    " Outgoing Mail Servers, set a sender address, and press "
                    "this again.\n\nNothing is lost in the meantime: "
                    "everything the platform would have sent is written down "
                    "on this screen." % why),
            }
        to = self._alert_recipients()
        if not to:
            return {'ok': False, 'state': 'dark', 'to': [],
                    'message': ("There is an outgoing mail account, but nobody "
                                "to send to. Add an address in the alert "
                                "settings, or give the platform administrator "
                                "an email address, and press this again.")}
        brand = common.brand(self.env) or "the platform"
        state, reason = self._send_alert_mail(
            '[%s] Test message from your platform' % brand,
            "If you are reading this, the platform can reach you. Real alerts "
            "arrive the same way, within fifteen minutes of something going "
            "wrong, and each one says what to do next.", recipients=to)
        if state == 'sent':
            return {'ok': True, 'state': state, 'to': to,
                    'message': "Sent to %s. It has left this machine — check "
                               "the inbox." % ', '.join(to)}
        return {'ok': False, 'state': state, 'to': to,
                'message': reason or "It could not be sent."}

    @api.model
    def alert_settings(self):
        """What the alert settings dialog opens holding."""
        self._require_platform_admin()
        th = self._alert_thresholds()
        crit_h, warn_h = common.alert_intervals(self.env)
        cap = self._capacity()
        return {
            'alert_to': common.param_row(self.env, common.P_ALERT_TO) or '',
            'default_recipients': self._alert_recipients(),
            'interval_critical': crit_h,
            'interval_warning': warn_h,
            'thresholds': {k: th[k] for k in THRESHOLD_KEYS},
            'tenant_cost_mb': cap['cost_per_tenant_mb'],
            'reserve_mb': cap['reserve_mb'],
            'status_tz': self._status_tz(),
            'status_dir': self._status_dir(),
            'health_ignore': common.param_row(
                self.env, common.P_HEALTH_IGNORE) or '',
            'capacity': cap,
            # SAID ON THE SCREEN, because it is the difference between a policy
            # and a measurement and somebody will otherwise read the first as
            # the second (ledger F34).
            'cost_note': (
                "This is a POLICY, not a measurement. Opening one real "
                "customer's system on this machine was measured at about 11 MB "
                "across the three processes that serve it — but that is the "
                "system sitting still. Sessions, screens already drawn, and "
                "a customer actually working in it are the rest, and none of "
                "them can be measured while nobody is using it. So this "
                "number is the "
                "measurement plus a deliberate allowance, and it is here to be "
                "re-weighed as customers arrive."),
        }

    @api.model
    def alert_settings_save(self, vals):
        """Save them, refusing anything that would silence the alarm.

        Every refusal names the field and says what a good answer looks like. A
        settings screen that saves nonsense is a settings screen that turns the
        alarm off without telling anybody.
        """
        self._require_platform_admin()
        vals = vals or {}
        icp = self.env['ir.config_parameter'].sudo()
        raw = (vals.get('alert_to') or '').strip()
        picked = [e.strip() for e in re.split(r'[,;\s]+', raw) if e.strip()]
        bad = [e for e in picked if not EMAIL_RE.match(e)]
        if bad:
            raise UserError(self.env._(
                "This does not look like an email address: %s",
                ', '.join(bad)))
        icp.set_param(common.P_ALERT_TO, ', '.join(picked))

        def num(name, lo, hi, label):
            got = vals.get(name)
            if got in (None, ''):
                return None
            try:
                val = float(got)
            except (TypeError, ValueError):
                raise UserError(self.env._("%(label)s has to be a number.",
                                           label=label))
            if not lo <= val <= hi:
                raise UserError(self.env._(
                    "%(label)s has to be between %(lo)s and %(hi)s.",
                    label=label, lo=lo, hi=hi))
            return val

        for name, key, lo, hi, label in (
                ('interval_critical', common.P_ALERT_EVERY_CRITICAL, 0, 168,
                 "The reminder for urgent problems"),
                ('interval_warning', common.P_ALERT_EVERY_WARNING, 0, 168,
                 "The reminder for smaller problems"),
                ('tenant_cost_mb', common.P_TENANT_COST, 1, 4096,
                 "The memory one customer is allowed"),
                ('reserve_mb', common.P_CAPACITY_RESERVE, 0, 8192,
                 "The memory kept back for the rest of the machine")):
            val = num(name, lo, hi, label)
            if val is not None:
                icp.set_param(key, str(int(val) if val == int(val) else val))

        limits = {
            'disk_free_pct': (1, 90, "The disk warning level"),
            'mem_available_mb': (32, 8192, "The memory warning level"),
            'backup_stale_hours': (1, 720, "How old a copy may get"),
            'cert_days': (1, 90, "The certificate warning"),
            'error_lines': (1, 500, "Errors before the platform says something"),
        }
        th = vals.get('thresholds') or {}
        for name, (lo, hi, label) in limits.items():
            if name not in th:
                continue
            got = th.get(name)
            if got in (None, ''):
                icp.set_param('biz_tenants.alert_%s' % name, '')
                continue
            try:
                val = float(got)
            except (TypeError, ValueError):
                raise UserError(self.env._("%(label)s has to be a number.",
                                           label=label))
            if not lo <= val <= hi:
                raise UserError(self.env._(
                    "%(label)s has to be between %(lo)s and %(hi)s.",
                    label=label, lo=lo, hi=hi))
            icp.set_param('biz_tenants.alert_%s' % name,
                          str(int(val) if val == int(val) else val))

        if 'status_tz' in vals:
            icp.set_param(common.P_STATUS_TZ, (vals.get('status_tz') or '').strip())
        if 'health_ignore' in vals:
            icp.set_param(common.P_HEALTH_IGNORE,
                          (vals.get('health_ignore') or '').strip())
        return self.alert_settings()
