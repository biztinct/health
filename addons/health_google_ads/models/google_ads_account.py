# -*- coding: utf-8 -*-
"""``google.ads.account`` — one configured advertising customer per company.

GA1 scope: the record exists, it links to the existing website connector, it
proves the website pipeline with a rollback-only synthetic run, and it feeds
the Channel Connection Center's acquisition card. **No Google API call of any
kind happens in this phase** — `reporting_state` is a field a later phase
drives, and nothing here can move it off `not_connected`.

Three postures are deliberate and load-bearing:

* **Evidence is internal-write-only.** `website_test_*`, `reporting_state`,
  the sync stamps and `native_eligibility` are written by server paths that
  pass `INTERNAL_CTX`, never by a form. There is no manually editable
  "connected" checkbox anywhere, because a checkbox is a claim and this
  screen only shows measurements.
* **Every action gates BEFORE it acts** (`_check_operator`), and only then
  may the body use `sudo()` — a view attribute hides a button, it does not
  stop an RPC.
* **A customer id binds to exactly ONE company on this database**, archived
  rows included. Two companies advertising as the same Google customer would
  duplicate the spend and make ownership ambiguous.
"""
import logging
import uuid

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.health_api_gateway.controllers.gateway import ApiError
from odoo.addons.health_care_command_channels.services.redact import redact
from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP,
)

from ..services import attribution

_logger = logging.getLogger(__name__)

# Who may operate an advertising account. The Channel Center's own gate
# (health_care_command_channels/models/care_channel_connection.py CENTER_GROUPS)
# plus the clinic's own top tiers — the people who own the marketing budget.
OPERATOR_GROUPS = (
    'base.group_system',
    'health_crm.group_health_crm_manager',
    'health_access.group_clinic_admin',
    'health_base.group_healthcare_owner',
    'health_base.group_healthcare_admin',
)

# The context flag a server path sets to write evidence. `su` alone is NOT
# enough (ledger §5.4: uid 1 always runs as su, so an `env.su` test is dead
# code for admin and in tests) — the flag says "this write came from the code
# that measured the thing", and the su/system check says "and it was not
# forged by an RPC that happened to know the key".
INTERNAL_CTX = 'google_ads_internal'

# Written only by a server path that measured something.
EVIDENCE_FIELDS = (
    'website_test_at', 'website_test_kind', 'website_test_summary',
    'reporting_state', 'last_sync_attempt_at', 'last_sync_success_at',
    'last_error_code', 'currency_id', 'account_timezone', 'provider_name',
    'native_eligibility', 'eligibility_checked_at', 'eligibility_reference',
)

REPORTING_STATE_SELECTION = [
    ('not_connected', 'Not connected'),
    ('authorizing', 'Signing in'),
    ('select_account', 'Choose account'),
    ('syncing', 'Syncing'),
    ('connected', 'Connected'),
    ('action_required', 'Action required'),
    ('paused', 'Paused'),
]

WEBSITE_TEST_KIND_SELECTION = [
    ('server', 'Server pipeline check'),
    ('roundtrip', 'Deployed round trip'),
    ('live', 'Real lead'),
]

NATIVE_ELIGIBILITY_SELECTION = [
    ('healthcare_blocked', 'Unavailable for healthcare ads'),
    ('unverified', 'Not verified'),
    ('eligible', 'Eligible (operator-verified)'),
]

WEBSITE_STATUS_SELECTION = [
    ('setup_needed', 'Setup needed'),
    ('ready_for_test', 'Ready for test'),
    ('test_passed', 'Test passed; awaiting live lead'),
    ('receiving', 'Receiving'),
]

OVERALL_STATUS_SELECTION = [
    ('setup_needed', 'Setup needed'),
    ('partial', 'Partially connected'),
    ('connected', 'Connected'),
]

# Google's published policy, checked 2026-09-15: "Advertisements for
# healthcare-related content are not allowed for lead forms."
NATIVE_POLICY_URL = 'https://support.google.com/adspolicy/answer/9472930'

# The ValueTrack substitutions an ad's final-URL suffix carries. `{campaignname}`
# is NOT a Google parameter and must never appear here (design §6.1).
FINAL_URL_SUFFIX_BASE = (
    'utm_source=google&utm_medium=cpc'
    '&h19_gads_campaign_id={campaignid}'
    '&h19_gads_adgroup_id={adgroupid}'
    '&h19_gads_creative_id={creative}'
)

TEST_SUMMARY_CAP = 200


class _WebsiteTestRollback(Exception):
    """Private sentinel raised inside `action_test_website`'s savepoint.

    A synthetic submission must leave NOTHING behind, and the only reliable
    way to undo an ORM write is to make the savepoint roll back — so the happy
    path raises this and the caller catches it immediately outside the `with`
    block. Ledger §5.55: the savepoint, not the `try`, is what keeps the outer
    transaction usable. Cloned from `web.leads.connector._PipelineTestRollback`.
    """


class GoogleAdsAccount(models.Model):
    _name = 'google.ads.account'
    _description = 'Google Ads Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, name, id'

    name = fields.Char(
        string='Name', required=True, default='Google Ads', tracking=True,
        help='What this advertising account is called here. It does not have '
             'to match the name in Google Ads.')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, tracking=True,
        help='The clinic this advertising account belongs to. Enquiries are '
             'only ever matched to an account of the same company.')

    customer_id = fields.Char(
        string='Customer ID', size=10, index=True, tracking=True,
        help='The ten-digit Google Ads customer ID, without hyphens. Leave it '
             'empty while you are only setting up website leads.')
    login_customer_id = fields.Char(
        string='Manager Account ID', size=10,
        help='The manager account ID, optional. Only needed later, when '
             'campaign reporting is connected through a manager account.')

    website_connector_id = fields.Many2one(
        'web.leads.connector', string='Website Connector',
        check_company=True, tracking=True,
        help='The website connection these enquiries arrive through. It must '
             'belong to the same company as this account.')
    default_catchment_id = fields.Many2one(
        'health.catchment.province', string='Default Area',
        help='Only used by an explicit campaign mapping — never inferred from '
             'an ad.')

    # -- Campaign reporting (a later phase drives all of this) -------------
    reporting_state = fields.Selection(
        REPORTING_STATE_SELECTION, string='Campaign Reporting',
        default='not_connected', required=True, tracking=True,
        help='Whether this system can read campaign figures from Google. It '
             'is set by the connection steps, never by hand.')
    currency_id = fields.Many2one(
        'res.currency', string='Account Currency', readonly=True,
        help='Read from Google when reporting is connected.')
    account_timezone = fields.Char(
        string='Account Time Zone', readonly=True,
        help='Read from Google when reporting is connected.')
    provider_name = fields.Char(
        string='Account Name in Google', readonly=True,
        help='Read from Google when reporting is connected.')
    last_sync_attempt_at = fields.Datetime(
        string='Last Sync Attempt', readonly=True)
    last_sync_success_at = fields.Datetime(
        string='Last Successful Sync', readonly=True)
    last_error_code = fields.Char(string='Last Error Code', readonly=True)

    # -- Website-lead evidence ---------------------------------------------
    website_test_at = fields.Datetime(
        string='Last Successful Test', readonly=True,
        help='When the website pipeline was last proven to work. A failed '
             'test never moves it.')
    website_test_kind = fields.Selection(
        WEBSITE_TEST_KIND_SELECTION, string='Test Kind', readonly=True,
        help='What kind of proof this was: a check of this system only, a '
             'full round trip from the website, or a real enquiry.')
    website_test_summary = fields.Char(
        string='Last Test Result', readonly=True,
        help='One line describing what the last test found.')

    website_last_lead_at = fields.Datetime(
        string='Last Website Lead', compute='_compute_website_stats',
        help='When the newest real enquiry matched to this account arrived.')
    website_lead_count = fields.Integer(
        string='Website Enquiries', compute='_compute_website_stats')
    unmatched_lead_count = fields.Integer(
        string='Google enquiries not matched to any account (this company)',
        compute='_compute_unmatched_lead_count')

    # -- Google-hosted lead forms ------------------------------------------
    # Readable by everyone who can open the account (the whole point of the
    # page is that a tenant READS "Unavailable for healthcare ads"), but
    # writable only by a platform administrator — enforced in `write()`
    # below, not by a field-level `groups=`, which would also hide the value
    # from the people it is meant to inform.
    native_eligibility = fields.Selection(
        NATIVE_ELIGIBILITY_SELECTION, string='Google Lead Forms',
        default='healthcare_blocked', readonly=True,
        help='Google does not allow healthcare advertisers to use its own '
             'lead forms. Only a platform administrator can record a '
             'different finding, and only with evidence.')
    eligibility_checked_at = fields.Datetime(
        string='Eligibility Checked', readonly=True)
    eligibility_reference = fields.Char(
        string='Eligibility Reference', readonly=True,
        help='A policy or case reference. Never a person or a credential.')

    # -- Derived headline status -------------------------------------------
    website_status = fields.Selection(
        WEBSITE_STATUS_SELECTION, string='Website Leads',
        compute='_compute_website_status')
    overall_status = fields.Selection(
        OVERALL_STATUS_SELECTION, string='Overall Status',
        compute='_compute_overall_status')

    final_url_suffix = fields.Char(
        string='Final URL Suffix', compute='_compute_final_url_suffix',
        help='Paste this into the campaign\'s Final URL suffix in Google Ads, '
             'after checking what tracking is already there. It contains no '
             'secret of any kind.')

    campaign_ids = fields.One2many(
        'google.ads.campaign', 'account_id', string='Campaigns')

    # ==================================================================
    # Computes
    # ==================================================================
    def _touchpoint_domain(self):
        """Touchpoints this account is the matched source of."""
        self.ensure_one()
        return [('google_ads_account_id', '=', self.id),
                ('google_ads_origin', '!=', False)]

    @api.depends('company_id')
    def _compute_website_stats(self):
        """NON-STORED on purpose (W2.5 D1 precedent): touchpoints are written
        in transactions this record has no `@api.depends` path to — the
        website service creates them as the relay's service user, and a stored
        compute would simply never recompute."""
        Touch = self.env['health.lead.touchpoint'].sudo()
        for account in self:
            if not account._origin.id:
                account.website_last_lead_at = False
                account.website_lead_count = 0
                continue
            domain = account._origin._touchpoint_domain()
            account.website_lead_count = Touch.search_count(domain)
            newest = Touch.search(domain, order='occurred_at desc, id desc',
                                  limit=1)
            account.website_last_lead_at = newest.occurred_at or False

    @api.depends('company_id')
    def _compute_unmatched_lead_count(self):
        """Company-level, shown once. A Google enquiry that matched no account
        belongs to the COMPANY, not to whichever account happens to share the
        website connector — assigning it to every account would be a lie told
        several times over (design §5.1)."""
        Touch = self.env['health.lead.touchpoint'].sudo()
        for account in self:
            company = account.company_id
            account.unmatched_lead_count = Touch.search_count([
                ('company_id', '=', company.id),
                ('google_ads_origin', '!=', False),
                ('google_ads_match_status', '=', 'unmatched'),
            ]) if company else 0

    @api.depends('website_connector_id', 'website_test_at',
                 'website_test_kind', 'website_lead_count')
    def _compute_website_status(self):
        for account in self:
            if not account.website_connector_id:
                account.website_status = 'setup_needed'
            elif account.website_lead_count:
                account.website_status = 'receiving'
            elif account.website_test_at and account.website_test_kind in (
                    'server', 'roundtrip'):
                account.website_status = 'test_passed'
            else:
                account.website_status = 'ready_for_test'

    @api.depends('website_status', 'reporting_state')
    def _compute_overall_status(self):
        for account in self:
            website_ok = account.website_status == 'receiving'
            reporting_ok = account.reporting_state == 'connected'
            if website_ok and reporting_ok:
                account.overall_status = 'connected'
            elif reporting_ok or account.website_status in (
                    'test_passed', 'receiving'):
                account.overall_status = 'partial'
            else:
                account.overall_status = 'setup_needed'

    @api.depends('customer_id')
    def _compute_final_url_suffix(self):
        for account in self:
            suffix = FINAL_URL_SUFFIX_BASE
            if account.customer_id:
                suffix += '&h19_gads_customer_id=%s' % account.customer_id
            account.final_url_suffix = suffix

    # ==================================================================
    # Validation
    # ==================================================================
    @api.constrains('customer_id', 'login_customer_id')
    def _check_customer_id(self):
        for account in self:
            for field_name, label in (('customer_id', _('Customer ID')),
                                      ('login_customer_id',
                                       _('Manager Account ID'))):
                raw = account[field_name]
                if not raw:
                    continue
                if attribution.norm_customer_id(raw) != raw:
                    raise ValidationError(_(
                        '%(label)s must be exactly ten digits, with no '
                        'hyphens or spaces.', label=label))

    @api.constrains('website_connector_id', 'company_id')
    def _check_connector_company(self):
        for account in self:
            connector = account.website_connector_id
            if connector and connector.company_id \
                    and connector.company_id != account.company_id:
                raise ValidationError(_(
                    'The website connector "%(connector)s" belongs to '
                    '%(their)s, but this advertising account belongs to '
                    '%(ours)s.',
                    connector=connector.display_name,
                    their=connector.company_id.display_name,
                    ours=account.company_id.display_name))

    @api.constrains('default_catchment_id')
    def _check_default_catchment(self):
        # Present so a future mapping cannot quietly start inferring a city
        # from an ad. Nothing in GA1 reads this field at capture time.
        return True

    @api.model
    def _assert_customer_free(self, customer, exclude_id=None):
        """A customer id binds to ONE company on this database, archived rows
        included (design §5.1).

        Pre-checked in Python so the message is actionable: **ledger §5.3 — a
        DB unique index fires BEFORE any Python constraint, and its
        IntegrityError poisons the whole transaction**. This must therefore
        run BEFORE `super().create()`, not after it. (Hit live on the first
        GA1 test run, which is exactly the failure §5.3 describes.) The index
        in `init()` stays as the concurrency backstop.
        """
        if not customer:
            return
        domain = [('customer_id', '=', customer)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        clash = self.sudo().with_context(active_test=False).search(
            domain, limit=1)
        if clash:
            raise UserError(_(
                'Customer ID %(customer)s is already used by "%(name)s" '
                '(%(company)s). One Google Ads customer belongs to one '
                'company — open that account instead of creating a '
                'second one.',
                customer=customer, name=clash.name,
                company=clash.company_id.display_name))

    def _check_unique_customer_binding(self, values=None):
        for account in self:
            customer = (values or {}).get('customer_id', account.customer_id)
            self._assert_customer_free(customer, exclude_id=account.id)

    @api.model
    def _assert_no_other_draft(self, company_id, exclude_id=None):
        """One website-only draft per company (design §5.1).

        A draft is an account with no customer id. A second one is almost
        always somebody re-doing the setup rather than adding a real second
        advertising account — and it would silently split the evidence.
        """
        if not company_id:
            return
        domain = [('company_id', '=', company_id),
                  ('customer_id', 'in', (False, ''))]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        clash = self.sudo().search(domain, limit=1)
        if clash:
            raise UserError(_(
                'There is already a Google Ads account without a customer '
                'ID for this company ("%s"). Give that one its customer '
                'ID instead of creating a second draft.', clash.name))

    def _check_single_draft(self, values=None):
        for account in self:
            customer = (values or {}).get('customer_id', account.customer_id)
            company = (values or {}).get('company_id') or account.company_id.id
            if customer or not company:
                continue
            self._assert_no_other_draft(company, exclude_id=account.id)

    # ==================================================================
    # Guarded writes
    # ==================================================================
    def _check_operator(self):
        """Guard by group, then let the body run through `sudo()`.

        The header buttons carry `groups=`, but a view attribute is
        decoration: this is the check a direct RPC has to pass.
        """
        if self.env.su or any(self.env.user.has_group(group)
                              for group in OPERATOR_GROUPS):
            return
        raise AccessError(_(
            'Only a system administrator, a CRM manager, a clinic '
            'administrator or an owner may set up Google Ads.'))

    def _is_platform_admin(self):
        return bool(self.env.su
                    or self.env.user.has_group('base.group_system')
                    or self.env.user._is_admin())

    def _internal_write_allowed(self):
        """Evidence writes need BOTH the context flag and real elevation.

        `su` alone is NOT enough and neither is the flag alone — ledger §5.4
        (uid 1 always runs as su, so an `env.su` test is dead code for admin
        and in every test) crossed with the care_channel_connection posture
        (the flag says "this write came from the code that measured the
        thing").
        """
        return bool(self.env.context.get(INTERNAL_CTX)) \
            and self._is_platform_admin()

    @api.model_create_multi
    def create(self, vals_list):
        self._check_operator()
        internal = self._internal_write_allowed()
        for vals in vals_list:
            if not internal:
                for field_name in EVIDENCE_FIELDS:
                    vals.pop(field_name, None)
            if vals.get('customer_id'):
                # Normalise the display form ('123-456-7890') before anything
                # else sees it; a value that is not ten digits at all is left
                # alone so `_check_customer_id` can name it.
                customer = attribution.norm_customer_id(vals['customer_id'])
                if customer:
                    vals['customer_id'] = customer
            # BEFORE super(), not after: ledger §5.3 — the DB unique index
            # fires first and its IntegrityError poisons the transaction, so
            # the actionable message has to be raised ahead of the INSERT.
            # `@api.constrains` would not fire here either (§5.2).
            self._assert_customer_free(vals.get('customer_id'))
            if not vals.get('customer_id'):
                self._assert_no_other_draft(
                    vals.get('company_id') or self.env.company.id)
        return super().create(vals_list)

    def write(self, values):
        values = dict(values)
        # An archive/unarchive toggle is not an operator action on the
        # evidence — but everything else here is, so gate first.
        self._check_operator()
        if 'native_eligibility' in values and not self._is_platform_admin():
            # The internal context is not a key to this one. Google's policy
            # is not something a tenant may vote itself out of — only a
            # platform administrator records a different finding, with a
            # reference beside it. Loud, not silent: naming this field at all
            # is a decision somebody meant to take.
            raise AccessError(_(
                'Only a platform administrator can change whether Google lead '
                'forms are available, and only against a written policy '
                'finding.'))
        if not self._internal_write_allowed():
            for field_name in EVIDENCE_FIELDS:
                values.pop(field_name, None)
        if values.get('customer_id'):
            normalised = attribution.norm_customer_id(values['customer_id'])
            if normalised:
                values['customer_id'] = normalised
        if not values:
            return True
        if 'customer_id' in values or 'company_id' in values:
            # Same §5.3 ordering as `create`: pre-check, then write.
            self._check_unique_customer_binding(values)
            self._check_single_draft(values)
        return super().write(values)

    def unlink(self):
        if not self._is_platform_admin():
            raise AccessError(_(
                'A Google Ads account is kept for its history. Archive it '
                'instead — only a system administrator can delete one.'))
        return super().unlink()

    def init(self):
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19.
        # DATABASE-WIDE, not per company (design §5.1): one advertising
        # customer must not be bound to two companies. Archived rows keep the
        # binding, which is why there is no `active` clause here.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS google_ads_account_customer_uidx
            ON google_ads_account (customer_id)
            WHERE customer_id IS NOT NULL AND customer_id <> ''
        """)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_test_website(self):
        """Run one synthetic Google-attributed submission through the REAL
        handler, inspect what it produced, and undo it.

        What this proves: the handler classifies a Google click, resolves the
        account the way this company's configuration says it should, and
        writes the identifiers onto both the lead and the touchpoint. What it
        cannot prove: that the WEBSITE actually sends those values — that is a
        round trip through the relay, and the relay does not exist yet. The
        notification says so rather than implying a stronger claim.
        """
        self.ensure_one()
        self._check_operator()
        if not self.website_connector_id:
            raise UserError(_(
                'Link the website connector first — there is nothing to test '
                'the enquiry against until this account knows which website '
                'its enquiries arrive from.'))

        connector = self.website_connector_id.sudo()
        runner = connector.oauth_client_id.user_id
        Service = self.env['web.lead.service']
        Runner = (Service.with_user(runner)
                  if runner and runner.active else Service.sudo())
        Runner = Runner.with_company(self.company_id)

        form_map = Service._json_param(PARAM_FORM_CITY_MAP)
        form_id = str(next(iter(form_map), '') or 'google-ads-test')
        token = uuid.uuid4().hex
        mapping = self.campaign_ids[:1]
        payload = {
            'submission_id': 'gads-test-%s' % token,
            'form_id': form_id,
            'name': 'Kiểm tra Google Ads',
            'phone': '0900000000',
            'utm': {'source': 'google', 'medium': 'cpc',
                    'campaign': 'gads-test'},
            'click_ids': {'gclid': 'TEST-%s' % token},
            'google_ads': {
                'customer_id': self.customer_id or '',
                'campaign_id': mapping.external_campaign_id or '',
            },
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }

        facts, failure = None, None
        try:
            with self.env.cr.savepoint():
                outcome = Runner.process_submission(payload)
                facts = self._inspect_test_outcome(outcome)
                # ALWAYS roll back: a configuration test that leaves an
                # enquiry behind is a test nobody dares run twice.
                raise _WebsiteTestRollback()
        except _WebsiteTestRollback:
            pass
        except ApiError as error:
            failure = str(getattr(error, 'message', error))
        except (UserError, ValidationError) as error:
            failure = str(getattr(error, 'args', [error])[0])
        except Exception as error:  # noqa: BLE001 — report, never 500 a button
            _logger.warning('google_ads: website pipeline test failed',
                            exc_info=True)
            failure = str(error) or type(error).__name__
        # `cr.savepoint()` clears the precommit queue on the way out but NOT
        # the ORM cache, so without this the environment still believes in an
        # enquiry the database has already forgotten.
        self.env.invalidate_all()

        caveat = _(
            'This checks this system only. A full round trip from the website '
            'becomes available once the website connection piece is '
            'installed; until then, the proof that Google\'s own values reach '
            'us is a real enquiry.')

        internal = self.sudo().with_context(**{INTERNAL_CTX: True})
        if failure or not facts:
            reason = failure or _('the test produced nothing to inspect')
            summary = _('FAILED: %s', redact(reason))[:TEST_SUMMARY_CAP]
            internal.write({'website_test_summary': summary})
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Website pipeline test FAILED for %(user)s: %(reason)s',
                user=self.env.user.name, reason=reason))
            return self._notify(_('Google Ads: website test failed'),
                                '%s\n\n%s' % (reason, caveat), kind='warning')

        headline = facts['headline']
        internal.write({
            'website_test_at': fields.Datetime.now(),
            'website_test_kind': 'server',
            'website_test_summary': redact(headline)[:TEST_SUMMARY_CAP],
        })
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Website pipeline test run by %(user)s: %(result)s',
            user=self.env.user.name, result=headline))
        return self._with_reload(self._notify(
            _('Google Ads: website pipeline OK'),
            '\n\n'.join(facts['lines'] + [caveat])))

    def _inspect_test_outcome(self, outcome):
        """Read the synthetic rows BEFORE the savepoint rolls them back.

        Returns a dict with a translated headline and the notification lines,
        or None when there is nothing to read.
        """
        self.ensure_one()
        outcome = outcome or {}
        lead = self.env['crm.lead'].sudo().browse(
            outcome.get('_lead_id') or []).exists()
        if not lead:
            return None
        touch = self.env['health.lead.touchpoint'].sudo().search(
            [('lead_id', '=', lead.id)],
            order='occurred_at desc, id desc', limit=1)

        status = outcome.get('status')
        lines = []
        if status == 'created':
            origin = lead.google_ads_origin
            match = lead.google_ads_match_status
            campaign = lead.google_ads_campaign_id
        else:
            # Merged / duplicate: the LEAD's first touch is older and rightly
            # untouched, so the honest evidence is on the new touchpoint.
            origin = touch.google_ads_origin
            match = touch.google_ads_match_status
            campaign = touch.google_ads_campaign_id

        if origin != 'website':
            return None
        if not (lead.gclid or touch.gclid):
            return None

        matched_account = (lead.google_ads_account_id if status == 'created'
                           else touch.google_ads_account_id)
        if self.customer_id and matched_account != self:
            match = 'unmatched'

        match_labels = {
            'matched': _('matched to this account'),
            'unmatched': _('not matched to any account'),
            'conflict': _('matched, but the enquiry contradicts itself'),
        }
        headline = _(
            'Pipeline OK — a Google ad click on form %(form)s would be '
            'recorded as a Google Ads enquiry, %(match)s. Nothing was saved.',
            form=lead.web_form_id or '-',
            match=match_labels.get(match, match or _('not matched')))
        lines.append(headline)
        if campaign:
            lines.append(_('Campaign ID carried through exactly: %s', campaign))
        if status and status != 'created':
            lines.append(_(
                'The synthetic enquiry resolved to "%s" rather than a new '
                'enquiry — an open enquiry already matches the test phone '
                'number. The pipeline itself worked.', status))
        return {'headline': headline, 'lines': lines, 'match': match}

    def action_view_leads(self):
        """The enquiries this account is the FIRST source of.

        No `sudo()`: the reader's own record rules are exactly what should
        decide which enquiries they see.
        """
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Google Ads leads'),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('google_ads_origin', '!=', False),
                       ('google_ads_account_id', '=', self.id)],
            'context': {'search_default_google_ads_first': 1},
        }
        # Pin the same two views the window action binds. Without this the
        # button falls back to the SHARED opportunity list, which carries
        # `sample="1"` — so an empty result renders ten invented people
        # instead of saying it is empty (found by driving the screen).
        views = []
        for xmlid, mode in (
                ('health_google_ads.view_google_ads_leads_list', 'list'),
                ('health_crm.view_crm_contact_form_crm_center', 'form')):
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view:
                views.append((view.id, mode))
        if len(views) == 2:
            action['views'] = views
        return action

    def action_view_touchpoints(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Google Ads touches'),
            'res_model': 'health.lead.touchpoint',
            'view_mode': 'list,form',
            'domain': [('google_ads_account_id', '=', self.id)],
            'context': {},
        }

    def action_open_connector(self):
        self.ensure_one()
        if not self.website_connector_id:
            raise UserError(_('No website connector is linked yet.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'web.leads.connector',
            'res_id': self.website_connector_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def action_open_setup(self):
        """What the Center card's button opens.

        With exactly one account in the company, open THAT account — the list
        would be a screen with one row on it and one more click to make.
        """
        action = self.env['ir.actions.act_window']._for_xml_id(
            'health_google_ads.action_google_ads_accounts')
        accounts = self.sudo().search(
            [('company_id', '=', self.env.company.id)])
        if len(accounts) == 1:
            action = dict(action, res_id=accounts.id,
                          view_mode='form',
                          views=[(False, 'form')])
        return action

    # ==================================================================
    # The Channel Center card (design §4.1)
    # ==================================================================
    @api.model
    def _center_card_payload(self):
        """The acquisition card for `self.env.company`.

        No group check of its own — `center_overview()` already gated the
        caller. It reads only this company's accounts, through `sudo()` with
        an explicit company domain, and carries NO credential material: there
        is none on this model in GA1, and the test asserts it stays that way.
        """
        company = self.env.company
        accounts = self.sudo().search([('company_id', '=', company.id)])
        rank = {'connected': 2, 'partial': 1, 'setup_needed': 0}
        best = None
        for account in accounts:
            if best is None or rank.get(account.overall_status, 0) > \
                    rank.get(best.overall_status, 0):
                best = account

        state = best.overall_status if best else 'setup_needed'
        chips = {
            'setup_needed': _('Setup needed'),
            'partial': _('Partially connected'),
            'connected': _('Connected'),
        }

        if not accounts:
            resource_line = ''
        elif len(accounts) > 1:
            resource_line = _('%s accounts', len(accounts))
        else:
            account = accounts
            resource_line = ('%s — %s' % (account.name, account.customer_id)
                             if account.customer_id else account.name)

        website_status = best.website_status if best else 'setup_needed'
        website_labels = {
            'receiving': _('Receiving'),
            'test_passed': _('Test passed; awaiting live lead'),
            'ready_for_test': _('Ready for test'),
            'setup_needed': _('Setup needed'),
        }
        website_tones = {'receiving': 'ok', 'test_passed': 'info',
                         'ready_for_test': 'info', 'setup_needed': 'off'}

        reporting_state = best.reporting_state if best else 'not_connected'
        # Spelled out rather than built from the Selection: `_(variable)` is
        # invisible to the catalogue extractor and would ship untranslatable.
        reporting_labels = {
            'not_connected': _('Not connected'),
            'authorizing': _('Signing in'),
            'select_account': _('Choose account'),
            'syncing': _('Syncing'),
            'connected': _('Connected'),
            'action_required': _('Action required'),
            'paused': _('Paused'),
        }
        reporting_tones = {'connected': 'ok', 'action_required': 'warn',
                           'paused': 'off', 'not_connected': 'off'}

        last_lead = max(
            [a.website_last_lead_at for a in accounts if a.website_last_lead_at]
            or [False])
        last_sync = max(
            [a.last_sync_success_at for a in accounts if a.last_sync_success_at]
            or [False])

        return {
            'channel': 'google_ads',
            'kind': 'acquisition',
            'after_key': 'fb',
            'label': _('Google Ads'),
            'tagline': _('Leads from your advertising campaigns'),
            'state': state,
            'state_chip': chips.get(state, state),
            'paused': False,
            'connection_id': False,
            'resource_line': resource_line,
            'last_inbound_at': '',
            'last_outbound_at': '',
            'health_status': '',
            'primary_action': 'open' if accounts else 'connect',
            'primary_label': _('Manage') if accounts else _('Set up Google Ads'),
            'mode': 'external_action',
            'action_xmlid': 'health_google_ads.action_google_ads_accounts',
            'available': True,
            'implemented': True,
            'sendable': False,
            'checks': [],
            'checks_done': 0,
            'checks_total': 0,
            'parent_channel': '',
            'guide_steps': [],
            'accounts': [],
            'multi_account': False,
            'can_add_account': False,
            'capabilities': [
                {'key': 'website',
                 'label': _('Website leads'),
                 'status': website_status,
                 'status_label': website_labels.get(website_status,
                                                    website_status),
                 'tone': website_tones.get(website_status, 'off')},
                {'key': 'reporting',
                 'label': _('Campaign reporting'),
                 'status': reporting_state,
                 'status_label': reporting_labels.get(reporting_state,
                                                      reporting_state),
                 'tone': reporting_tones.get(reporting_state, 'info')},
                {'key': 'native',
                 'label': _('Google lead forms'),
                 'status': 'unavailable',
                 'status_label': _('Unavailable for healthcare ads'),
                 'tone': 'off'},
            ],
            'lines': [
                _('Last website lead: %s') % (
                    fields.Datetime.to_string(last_lead) if last_lead
                    else _('No leads received yet')),
                _('Reporting updated: %s') % (
                    fields.Datetime.to_string(last_sync) if last_sync
                    else _('Not synced')),
            ],
            'notice': '',
            'view_leads_action': 'health_google_ads.action_google_ads_leads',
        }

    # ==================================================================
    # Helpers
    # ==================================================================
    def _with_reload(self, action):
        """Re-open this record behind the notification (W2.5 D4).

        The status fields are non-stored computes, so an action that returns
        only a notification leaves the header showing the state the record was
        in BEFORE the button ran.
        """
        self.ensure_one()
        if isinstance(action, dict) and isinstance(action.get('params'), dict):
            action['params']['next'] = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'current',
            }
        return action

    @staticmethod
    def _notify(title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message,
                       'type': kind, 'sticky': True},
        }
