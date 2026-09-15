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
from datetime import timedelta
from urllib.parse import urlencode

import psycopg2
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.health_api_gateway.controllers.gateway import ApiError
from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_care_command_channels.services.redact import redact
from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP,
)

from ..services import attribution
from ..services import google_ads_client as gads
from ..services.google_ads_client import GoogleAdsClient, GoogleAdsError

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
    # GA2 — the reporting grant. Every one of these is written by the
    # sign-in / selection code and by nothing else; a form that could set
    # `access_token_enc` or `customer_id`'s manager would be a form that can
    # forge a connection.
    'access_token_enc', 'refresh_token_enc', 'token_expires_at',
    'token_scope', 'authorized_by', 'authorized_at',
    'reporting_error_redacted', 'login_customer_id',
    # GA3 — the sync queue. A form that could set `sync_requested_at` or move
    # `backfill_cursor` would be a form that can make this system ask Google
    # for anything it likes; both are written by the buttons through
    # `_internal()` and by the scheduled job.
    'sync_requested_at', 'backfill_until', 'backfill_cursor',
)

# Advisory-lock class key for reporting-token refresh. "gads" in hex, chosen
# so it is recognisable in `pg_locks` and distinct from the channels'
# 0x63686E6C ("chnl").
REPORTING_LOCK_CLASS = 0x67616473
TOKEN_SKEW_SECONDS = 60

# Which error codes describe a manager-level refusal rather than a lost
# sign-in. Kept as a constant so the message map and the state machine cannot
# drift apart.
RECONNECT_STATES = ('action_required',)

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

    # -- The reporting grant (GA2) -----------------------------------------
    # `groups='base.group_system'` on the two token columns: a clinic operator
    # may CONNECT a Google account and may DISCONNECT it, and may never read
    # the material that connection is made of.
    access_token_enc = fields.Text(
        string='Access Token (stored)', groups='base.group_system')
    refresh_token_enc = fields.Text(
        string='Long-lived Permission (stored)', groups='base.group_system')
    token_expires_at = fields.Datetime(
        string='Access Token Expires', readonly=True)
    token_scope = fields.Char(string='Granted Permissions', readonly=True)
    authorized_by = fields.Many2one(
        'res.users', string='Signed in by', readonly=True)
    authorized_at = fields.Datetime(string='Signed in on', readonly=True)
    has_reporting_grant = fields.Boolean(
        string='Google Account Connected', compute='_compute_has_grant',
        help='Whether this system still holds permission to read this '
             'advertising account.')
    reporting_error_redacted = fields.Char(
        string='Reporting Message', readonly=True,
        help='What went wrong the last time this system talked to Google, in '
             'plain words. Never a password or a token.')

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

    @api.depends('refresh_token_enc')
    def _compute_has_grant(self):
        # Through sudo(): the source column is group-restricted, and the
        # batched fetch would otherwise raise for the clinic operator this
        # flag exists to inform (the channel_platform_app precedent).
        for account in self:
            account.has_reporting_grant = bool(account.sudo().refresh_token_enc)

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

    def _check_company_scope(self):
        """An operator acts only on their OWN clinic's advertising account.

        The company record rule already hides another company's rows from a
        read, so this mostly fires on a hand-built RPC that browses an id it
        should not have — which is precisely the caller a view attribute does
        nothing about.
        """
        if self.env.su:
            return
        allowed = self.env.user.company_ids
        for account in self:
            if account.company_id and account.company_id not in allowed:
                raise AccessError(_(
                    'This advertising account belongs to another clinic.'))

    def _internal(self):
        """The recordset evidence is written through.

        Both halves are required by `_internal_write_allowed`: the context
        flag says "this write came from the code that measured the thing",
        and the elevation says "and it was not forged by an RPC that happened
        to know the key".
        """
        return self.sudo().with_context(**{INTERNAL_CTX: True})

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
    # Campaign reporting (GA2) — sign in, choose an account, prove access
    # ==================================================================
    def _reporting_messages(self):
        """Every provider failure, in words a clinic operator can act on.

        Spelled out one `_()` per entry rather than built from a variable:
        `_(some_variable)` is invisible to the catalogue extractor and would
        ship untranslatable (the same reason the card's label maps are
        written out).
        """
        return {
            'no_grant': _('This system has no permission to read Google Ads '
                          'for this account yet. Press Connect Google '
                          'account.'),
            'invalid_grant': _('Google no longer accepts this sign-in. Press '
                               'Reconnect.'),
            'OAUTH_TOKEN_INVALID': _('Google no longer accepts this sign-in. '
                                     'Press Reconnect.'),
            'NOT_ADS_USER': _('The Google account you signed in with has no '
                              'Google Ads access. Sign in with the account '
                              'that manages the ads.'),
            'no_refresh_token': _(
                'Google did not return a long-lived permission. Remove this '
                'system from the Google account\'s third-party access list '
                'and sign in again.'),
            'scope_missing': _('The sign-in did not include permission to '
                               'read advertising accounts. Sign in again and '
                               'leave the Google Ads permission ticked.'),
            'oauth_exchange': _('Signing in with Google did not finish. Try '
                                'again.'),
            'exchange_malformed': _('Google sent back an answer this system '
                                    'could not use. Try again.'),
            'not_configured': _('The Google Ads application has not been set '
                                'up by the platform operator yet.'),
            'USER_PERMISSION_DENIED': _(
                'The Google account you signed in with cannot read that '
                'advertising account. Ask whoever manages the ads to give it '
                'access.'),
            'DEVELOPER_TOKEN_NOT_APPROVED': _(
                'Google has not approved this system for reading advertising '
                'accounts yet.'),
            'CUSTOMER_NOT_ENABLED': _('That advertising account is not active '
                                      'in Google Ads.'),
            'customer_not_enabled': _('That advertising account is not active '
                                      'in Google Ads.'),
            'not_an_advertiser': _('That is a manager account, not an '
                                   'advertising account. Choose one of the '
                                   'accounts underneath it.'),
            'customer_mismatch': _('Google answered about a different '
                                   'advertising account. Try again.'),
            'bad_customer_id': _('A Google Ads account number is ten digits. '
                                 'Check the number and try again.'),
            'busy': _('Another sign-in for this account is in progress. Try '
                      'again in a moment.'),
            'too_many_pages': _('There are more advertising accounts than '
                                'this system will read in one go. Tell the '
                                'platform operator.'),
            'network': _('This system could not reach Google. Try again in a '
                         'few minutes.'),
        }

    def _reporting_message_for(self, code):
        return self._reporting_messages().get(code) or _(
            'Google refused this request. Try again, and tell the platform '
            'operator if it keeps happening.')

    def _reporting_message(self, err):
        return self._reporting_message_for(getattr(err, 'code', None))

    def _reporting_failure(self, err):
        """Record one provider failure and answer the caller.

        Two shapes, deliberately:

        * ``needs_reconnect`` — the grant itself is gone, and the account must
          END UP in ``action_required`` whatever the caller does next. A
          `UserError` would roll that write back with itself (ledger §5.65),
          so this branch RETURNS a sticky warning instead: the state persists
          and the operator still sees the message.
        * anything else — nothing durable has changed, so the honest answer is
          the exception. The evidence write ahead of it is best-effort; an
          RPC's rollback takes it with the error, and that is stated rather
          than papered over.

        Nothing about the website capability is touched in either branch
        (rail R6): a lost reporting grant is not a lost website connector.
        """
        self.ensure_one()
        message = self._reporting_message(err)
        vals = {
            'last_error_code': (getattr(err, 'code', None) or 'error')[:64],
            'reporting_error_redacted': message[:255],
        }
        if getattr(err, 'needs_reconnect', False):
            vals['reporting_state'] = 'action_required'
        self._internal().write(vals)
        if getattr(err, 'needs_reconnect', False):
            return self._with_reload(self._notify(
                _('Google Ads: reconnect needed'), message, kind='warning'))
        detail = getattr(err, 'detail_redacted', False)
        raise UserError('%s\n\n%s' % (message, detail) if detail else message)

    def _google_client(self):
        self.ensure_one()
        return GoogleAdsClient(self.env, self)

    # ------------------------------------------------------------------
    def _reporting_access_token(self):
        """A valid access token for this account, refreshing under a lock.

        Advisory xact lock (never FOR UPDATE — ledger §5.74): two workers that
        both find the token expired serialise here; the loser re-reads after
        the winner's write is visible on ITS cursor, which under REPEATABLE
        READ it is not — so the loser may refresh a second time. That is
        harmless: Google refresh tokens are reusable and a second access token
        is just as valid. What the lock prevents is the thundering-herd of N
        parallel refreshes, not correctness.

        The rotated token is written on the SAME cursor, deliberately: a
        fresh-cursor persist is right for a SINGLE-USE rotating credential
        (Zalo) and wrong here — the surrounding transaction writes this row
        again straight afterwards, which is exactly the serialisation failure
        of ledger §5.181.
        """
        self.ensure_one()
        rec = self.sudo()
        now = fields.Datetime.now()
        if rec.access_token_enc and rec.token_expires_at \
                and rec.token_expires_at > now + timedelta(
                    seconds=TOKEN_SKEW_SECONDS):
            return channel_crypto.decrypt(self.env, rec.access_token_enc)
        if not rec.refresh_token_enc:
            raise GoogleAdsError('no_grant', needs_reconnect=True)
        self.env.flush_all()
        try:
            # The savepoint is not in the handover's kernel and is not
            # decoration: a lock timeout ABORTS the PostgreSQL transaction, so
            # without it the caller's `except` block inherits a transaction in
            # which every later statement fails with "current transaction is
            # aborted" — including the evidence write that explains the
            # failure. Rolling back to the savepoint restores a usable
            # transaction; a RELEASE on the happy path hands the lock up to
            # the parent, so the mutual exclusion is unchanged.
            with self.env.cr.savepoint():
                self.env.cr.execute("SET LOCAL lock_timeout = '5s'")
                self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)',
                                    (REPORTING_LOCK_CLASS, rec.id))
        except psycopg2.errors.LockNotAvailable as exc:
            raise GoogleAdsError('busy', retryable=True) from exc
        rec.invalidate_recordset(['access_token_enc', 'token_expires_at'])
        if rec.access_token_enc and rec.token_expires_at \
                and rec.token_expires_at > now + timedelta(
                    seconds=TOKEN_SKEW_SECONDS):
            return channel_crypto.decrypt(self.env, rec.access_token_enc)
        config = self.env['google.ads.platform.config']._active()
        if not config or not config._ready():
            raise GoogleAdsError('not_configured')
        body = gads._http_post_form(gads.TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': channel_crypto.decrypt(
                self.env, rec.refresh_token_enc),
            'client_id': config.client_id,
            'client_secret': config._get_client_secret(),
        })
        body = body if isinstance(body, dict) else {}
        access = body.get('access_token')
        if not access:
            raise GoogleAdsError('refresh_malformed', retryable=True)
        try:
            expires_in = int(body.get('expires_in') or 3600)
        except (TypeError, ValueError):
            expires_in = 3600
        vals = {
            'access_token_enc': channel_crypto.encrypt(self.env, access),
            'token_expires_at': now + timedelta(seconds=expires_in),
        }
        if body.get('refresh_token'):
            # Google rarely rotates; keep ours when the answer omits one.
            vals['refresh_token_enc'] = channel_crypto.encrypt(
                self.env, body['refresh_token'])
        rec._internal().write(vals)
        return access

    # ------------------------------------------------------------------
    def _provider_vals(self, info):
        """What Google says about an advertising account, as field values.

        An unknown currency code leaves the field empty and says so in the
        chatter — this module creates no currency records (design §5.1: the
        money vocabulary belongs to accounting, not to an ad platform).
        """
        self.ensure_one()
        currency = self.env['res.currency'].with_context(
            active_test=False).search(
                [('name', '=', info.get('currency') or '')], limit=1)
        return {
            'provider_name': (info.get('name') or '')[:255],
            'currency_id': currency.id or False,
            'account_timezone': (info.get('time_zone') or '')[:64],
            'last_error_code': False,
            'reporting_error_redacted': False,
        }

    def _validate_reporting_access(self, customer_id, login_customer_id=None):
        """Prove this sign-in can READ that advertising account, right now.

        An id typed into a form establishes nothing (design §7.1): the only
        evidence that counts is Google answering for that exact customer, as
        a non-manager, enabled.
        """
        self.ensure_one()
        info = self._google_client().get_customer(
            customer_id, login_customer_id=login_customer_id or None)
        if not info or not info.get('id'):
            raise GoogleAdsError('customer_mismatch')
        if info['id'] != attribution.norm_customer_id(customer_id):
            raise GoogleAdsError('customer_mismatch')
        if info.get('manager'):
            raise GoogleAdsError('not_an_advertiser')
        if (info.get('status') or '') != 'ENABLED':
            raise GoogleAdsError('customer_not_enabled')
        return info

    def _discover_reporting_candidates(self):
        """Every advertising account this sign-in could report on.

        The directly accessible list is NOT the whole picture: a clinic whose
        ads are run through an agency sees only the manager account, and the
        advertising accounts hang underneath it. Managers are walked one level
        of the API down and their children tagged with the manager id, which
        is what has to travel in `login-customer-id` on every later call.
        """
        self.ensure_one()
        client = self._google_client()
        direct, children = {}, {}
        for customer_id in client.list_accessible_customers():
            info = client.get_customer(customer_id)
            if not info or not info.get('id'):
                continue
            if info.get('manager'):
                for child in client.list_customer_children(customer_id):
                    child = dict(child, login_customer_id=customer_id)
                    children.setdefault(child['id'], child)
            else:
                direct.setdefault(info['id'],
                                  dict(info, login_customer_id=False))
        # Children first, then the direct entries on top: an account we can
        # read without a manager context is the simpler binding of the two.
        out = dict(children)
        out.update(direct)
        return list(out.values())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_start_reporting_oauth(self):
        """Send the operator to Google to sign in."""
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        config = self.env['google.ads.platform.config']._active()
        if not config or not config._ready():
            raise UserError(_(
                'The Google Ads application has not been set up by the '
                'platform operator yet.'))
        redirect_uri = config.redirect_uri or ''
        if not redirect_uri.startswith('https://'):
            raise UserError(_(
                'Signing in with Google needs this system to be reached at a '
                'secure web address (one starting with https). Ask the '
                'platform operator to set it.'))
        session = self.env['google.ads.oauth.session'].create_for(self)
        if self.reporting_state != 'connected':
            # A RECONNECT keeps the working state until it succeeds.
            self._internal().write({
                'reporting_state': 'authorizing',
                'last_error_code': False,
                'reporting_error_redacted': False,
            })
        params = {
            'client_id': config.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': gads.SCOPE,
            'access_type': 'offline',
            # Both are required for a refresh token to come back at all; a
            # re-consent without them returns an hour of access and nothing
            # durable.
            'prompt': 'consent',
            'include_granted_scopes': 'false',
            'state': session['state'],
            'code_challenge': session['code_challenge'],
            'code_challenge_method': session['code_challenge_method'],
        }
        return {
            'type': 'ir.actions.act_url',
            'url': '%s?%s' % (gads.AUTH_URL, urlencode(params)),
            'target': 'self',
        }

    def action_reconnect_reporting(self):
        """Same handshake, different word on the button."""
        return self.action_start_reporting_oauth()

    def action_list_reporting_accounts(self):
        """Ask Google what this sign-in can read, and offer the choice."""
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        if not self.has_reporting_grant:
            raise UserError(_(
                'Connect a Google account first — there is nothing to list '
                'until someone has signed in.'))
        try:
            candidates = self._discover_reporting_candidates()
        except GoogleAdsError as err:
            return self._reporting_failure(err)
        wizard = self.env['google.ads.account.select'].create({
            'account_id': self.id,
            'line_ids': [(0, 0, {
                'customer_id': entry.get('id') or '',
                'login_customer_id': entry.get('login_customer_id') or '',
                'name': entry.get('name') or '',
                'currency': entry.get('currency') or '',
                'time_zone': entry.get('time_zone') or '',
                'status': entry.get('status') or '',
                'is_manager': bool(entry.get('manager')),
                'test_account': bool(entry.get('test_account')),
            }) for entry in candidates],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Choose the advertising account'),
            'res_model': 'google.ads.account.select',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_select_reporting_account(self, customer_id,
                                        login_customer_id=None):
        """Bind this record to ONE advertising account, after proving access."""
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        cid = attribution.norm_customer_id(customer_id)
        if not cid:
            raise UserError(_(
                'A Google Ads account number is ten digits. Check the number '
                'and try again.'))
        login = attribution.norm_customer_id(login_customer_id) \
            if login_customer_id else False
        if login_customer_id and not login:
            raise UserError(_(
                'A Google Ads manager account number is ten digits. Check the '
                'number and try again.'))
        # A customer id binds to ONE record on this database. The message
        # deliberately names NOBODY: which other clinic advertises as that
        # customer is not this operator's business (rail R5).
        clash = self.sudo().with_context(active_test=False).search(
            [('customer_id', '=', cid), ('id', '!=', self.id)], limit=1)
        if clash:
            raise UserError(_(
                'That advertising account is already set up on this system. '
                'Open the entry it is already on instead of adding it twice.'))
        try:
            info = self._validate_reporting_access(cid, login)
        except GoogleAdsError as err:
            return self._reporting_failure(err)
        vals = dict(self._provider_vals(info),
                    customer_id=cid,
                    login_customer_id=login or False,
                    reporting_state='connected')
        self._internal().write(vals)
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Advertising account %(name)s (%(customer)s) connected for '
            'reporting by %(user)s.',
            name=info.get('name') or cid, customer=cid,
            user=self.env.user.name))
        message = _('This system can now read campaign figures for %s. '
                    'Nothing in Google Ads is ever changed.',
                    info.get('name') or cid)
        if not vals.get('currency_id') and info.get('currency'):
            message = '%s\n\n%s' % (message, _(
                'The account currency (%s) is not one this system knows, so '
                'spend will be shown without a currency until someone adds '
                'it.', info.get('currency')))
        return self._with_reload(self._notify(
            _('Google Ads: reporting connected'), message))

    def action_disconnect_reporting(self):
        """Drop OUR copy of the permission. Nothing else changes.

        No revoke call to Google, deliberately (design §7.1): the same Google
        grant may also back the clinic's mailbox, and revoking it here would
        silently disconnect an integration this screen knows nothing about.
        Campaign figures already cached, the website connector, the enquiries
        and the account number all stay exactly where they are.
        """
        self.ensure_one()
        self._check_operator()
        self._check_company_scope()
        self._internal().write({
            'access_token_enc': False,
            'refresh_token_enc': False,
            'token_expires_at': False,
            'token_scope': False,
            'reporting_state': 'not_connected',
            'last_error_code': False,
            'reporting_error_redacted': False,
        })
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Campaign reporting disconnected by %s. Website enquiries are '
            'unaffected.', self.env.user.name))
        return self._with_reload(self._notify(
            _('Google Ads: reporting disconnected'),
            _('This system no longer reads anything from Google Ads. '
              'Website enquiries keep arriving as before.')))

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
            'authorizing': _('Sign-in started'),
            'select_account': _('Choose the advertising account'),
            'syncing': _('Syncing…'),
            'connected': _('Connected'),
            'action_required': _('Action required — reconnect'),
            'paused': _('Paused'),
        }
        reporting_tones = {'connected': 'ok', 'action_required': 'warn',
                           'paused': 'off', 'not_connected': 'off',
                           'authorizing': 'info', 'select_account': 'info',
                           'syncing': 'info'}

        last_lead = max(
            [a.website_last_lead_at for a in accounts if a.website_last_lead_at]
            or [False])
        last_sync = max(
            [a.last_sync_success_at for a in accounts if a.last_sync_success_at]
            or [False])

        # Zero versus unknown (rail R8). A successful run that read nothing is
        # a ZERO and the line says when it happened; a FAILED run leaves the
        # earlier time in place and says the last attempt failed beside it —
        # never a silent stale number, and never a zero that looks like a fact.
        reporting_line = _('Reporting updated: %s') % (
            fields.Datetime.to_string(last_sync) if last_sync
            else _('Not synced'))
        newest_run = self.env['google.ads.sync.run'].sudo().search(
            [('account_id', 'in', accounts.ids)], order='id desc', limit=1
        ) if accounts else self.env['google.ads.sync.run'].browse()
        if newest_run and newest_run.state == 'failed':
            reporting_line = '%s · %s' % (reporting_line, _(
                'last attempt failed (%s)', newest_run.error_code or '-'))

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
                reporting_line,
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
