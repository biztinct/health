# -*- coding: utf-8 -*-
"""``google.ads.campaign`` — the campaign mapping table.

In GA1 every row is entered by hand: it is how an operator says "campaign
12345678901234567 in Google is this campaign here, serving this area", which
is the second (and only other) way an enquiry can be matched to an account
when the ad's final-URL suffix carried no customer id.

From GA3 the sync also writes rows here: a campaign Google answers for is
upserted with `source='provider'`, Google's own name, status and type, and a
`last_seen_at`. A row somebody typed in by hand is flipped to `provider` the
first time Google answers for it, because Google's spelling is the one everyone
else will recognise. A campaign that DISAPPEARS from Google is never deleted —
it still explains the spend already in the cache.

The `*_30d` rollups are a stored summary of the daily cache and the report
view, refreshed by the sync and never typed.

`external_campaign_id` is a **string**, always. Google's ids exceed
JavaScript's safe integer range, and one `int()` anywhere in the chain
silently rounds an id to a different campaign.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import format_amount

from ..services import attribution
from .google_ads_account import OPERATOR_GROUPS


class GoogleAdsCampaign(models.Model):
    _name = 'google.ads.campaign'
    _description = 'Google Ads Campaign'
    _order = 'account_id, name, id'

    account_id = fields.Many2one(
        'google.ads.account', string='Advertising Account',
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='account_id.company_id',
        store=True, index=True)

    external_campaign_id = fields.Char(
        string='Campaign ID in Google', required=True,
        help='The campaign ID exactly as Google shows it — digits only. It is '
             'kept as text on purpose: these numbers are too large for some '
             'systems to hold as numbers without changing them.')
    name = fields.Char(string='Campaign Name', required=True)
    status = fields.Char(string='Status in Google', readonly=True)
    advertising_channel_type = fields.Char(
        string='Campaign Type', readonly=True)

    utm_campaign_id = fields.Many2one(
        'utm.campaign', string='Campaign',
        help='The campaign already set up in this system that this Google '
             'campaign corresponds to. It is only ever chosen from the '
             'existing list — nothing here creates one.')
    catchment_id = fields.Many2one(
        'health.catchment.province', string='Area')

    source = fields.Selection(
        [('manual', 'Entered by hand'), ('provider', 'From Google')],
        string='Where this row came from', default='manual', required=True)
    last_seen_at = fields.Datetime(string='Last Seen in Google', readonly=True)

    status_label = fields.Char(
        string='Status', compute='_compute_status_label',
        help='What Google says about this campaign right now, in plain words.')

    # -- The 30-day rollups (GA3) ------------------------------------------
    # Stored and refreshed by the sync, never typed: they are a SUMMARY of the
    # daily cache and the report view, and a figure somebody can type over is a
    # figure nobody can trust. Every one of them names the window it covers.
    currency_id = fields.Many2one(
        'res.currency', string='Currency', related='account_id.currency_id',
        readonly=True)
    window_from = fields.Date(string='Figures From', readonly=True)
    window_to = fields.Date(string='Figures To', readonly=True)
    spend_30d = fields.Monetary(
        string='Spend (30 days)', currency_field='currency_id', readonly=True)
    clicks_30d = fields.Integer(string='Clicks (30 days)', readonly=True)
    impressions_30d = fields.Integer(
        string='Impressions (30 days)', readonly=True)
    conversions_30d = fields.Float(
        string='Google Conversions (30 days)', readonly=True,
        help='What Google counts. It uses different rules from the enquiry '
             'count beside it and need not agree.')
    new_enquiries_30d = fields.Integer(
        string='New Enquiries (30 days)', readonly=True,
        help='Enquiries this system opened because of this campaign. A '
             'submission added to an enquiry that already existed is not '
             'counted here.')
    submissions_30d = fields.Integer(
        string='Form Submissions (30 days)', readonly=True,
        help='Every accepted form submission from this campaign, including '
             'the ones added to an enquiry that already existed.')
    cost_per_new_enquiry_30d = fields.Float(
        string='Cost per New Enquiry (30 days)', readonly=True,
        help='Spend divided by new enquiries, worked out from this system\'s '
             'own enquiry count — not from Google\'s conversion count.')
    cost_per_new_enquiry_display = fields.Char(
        string='Cost per New Enquiry',
        compute='_compute_cost_per_new_enquiry_display',
        help='A dash means no new enquiry was opened in the window, so there '
             'is nothing to divide by.')

    @api.depends('status')
    def _compute_status_label(self):
        """Google's own enum in words a clinic reads.

        Spelled out one `_()` per entry rather than built from a variable:
        `_(some_variable)` is invisible to the catalogue extractor and would
        ship untranslatable.
        """
        for row in self:
            status = (row.status or '').upper()
            if status == 'ENABLED':
                row.status_label = _('Running')
            elif status == 'PAUSED':
                row.status_label = _('Paused')
            elif status == 'REMOVED':
                row.status_label = _('Removed')
            else:
                row.status_label = _('Unknown')

    @api.depends('spend_30d', 'new_enquiries_30d', 'cost_per_new_enquiry_30d',
                 'currency_id')
    def _compute_cost_per_new_enquiry_display(self):
        for row in self:
            if not row.new_enquiries_30d:
                # An em dash, not "0": zero cost per enquiry would read as
                # "these enquiries were free", which is the opposite of what a
                # zero denominator means.
                row.cost_per_new_enquiry_display = '—'
                continue
            amount = row.cost_per_new_enquiry_30d or 0.0
            currency = row.currency_id
            row.cost_per_new_enquiry_display = (
                format_amount(self.env, amount, currency) if currency
                else '%.2f' % amount)

    @api.constrains('external_campaign_id')
    def _check_external_campaign_id(self):
        for row in self:
            raw = row.external_campaign_id
            if raw and attribution.norm_provider_id(raw) != raw:
                raise ValidationError(_(
                    'A Google campaign ID is digits only, with no spaces — '
                    '"%s" is not one.', raw))

    def _check_operator(self):
        if self.env.su or any(self.env.user.has_group(group)
                              for group in OPERATOR_GROUPS):
            return
        raise AccessError(_(
            'Only a system administrator, a CRM manager, a clinic '
            'administrator or an owner may set up Google Ads campaigns.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_operator()
        records = super().create(vals_list)
        # Ledger §5.2 — `@api.constrains` does not fire on create for fields
        # absent from vals.
        records._check_external_campaign_id()
        return records

    def write(self, values):
        self._check_operator()
        return super().write(values)

    def unlink(self):
        self._check_operator()
        return super().unlink()

    def init(self):
        init = getattr(super(), 'init', None)
        if callable(init):
            init()
        # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS google_ads_campaign_account_ext_uidx
            ON google_ads_campaign (account_id, external_campaign_id)
        """)
