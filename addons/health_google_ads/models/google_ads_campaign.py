# -*- coding: utf-8 -*-
"""``google.ads.campaign`` — the campaign mapping table.

In GA1 every row is entered by hand: it is how an operator says "campaign
12345678901234567 in Google is this campaign here, serving this area", which
is the second (and only other) way an enquiry can be matched to an account
when the ad's final-URL suffix carried no customer id.

`external_campaign_id` is a **string**, always. Google's ids exceed
JavaScript's safe integer range, and one `int()` anywhere in the chain
silently rounds an id to a different campaign.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

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
