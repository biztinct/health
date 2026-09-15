# -*- coding: utf-8 -*-
"""Google Ads evidence on ``health.lead.touchpoint`` — EVERY touch.

Where `crm.lead` carries the frozen first touch, the touchpoint carries what
each individual enquiry brought with it. A repeat enquiry from an ad therefore
records its own campaign and its own account while the lead's first-touch
fields stay exactly as they were.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .crm_lead import (
    GOOGLE_ADS_MATCH_SELECTION,
    GOOGLE_ADS_ORIGIN_SELECTION,
)

GOOGLE_ADS_TIME_BASIS_SELECTION = [
    ('provider', 'Provider'),
    ('website', 'Website'),
    ('received_fallback', 'Received time'),
]


class HealthLeadTouchpoint(models.Model):
    _inherit = 'health.lead.touchpoint'

    google_ads_account_id = fields.Many2one(
        'google.ads.account', string='Google Ads Account',
        index=True, ondelete='set null',
        help='Which of your advertising accounts this touch was matched to.')
    google_ads_customer_id = fields.Char(
        string='Google Ads Customer ID', size=10)
    google_ads_campaign_id = fields.Char(
        string='Google Campaign ID',
        help='The campaign number exactly as Google sent it, kept as text.')
    google_ads_adgroup_id = fields.Char(string='Google Ad Group ID')
    google_ads_creative_id = fields.Char(string='Google Ad ID')
    google_ads_asset_group_id = fields.Char(string='Google Asset Group ID')

    google_ads_origin = fields.Selection(
        GOOGLE_ADS_ORIGIN_SELECTION, string='Google Ads Origin', index=True,
        help='How this Google Ads touch reached us. Empty on every touch that '
             'did not come from a Google ad.')
    google_ads_match_status = fields.Selection(
        GOOGLE_ADS_MATCH_SELECTION, string='Google Ads Match')
    google_ads_time_basis = fields.Selection(
        GOOGLE_ADS_TIME_BASIS_SELECTION, string='Time Basis',
        help='Whose clock the time on this touch came from. A website '
             'enquiry always says Website.')

    @api.constrains('google_ads_account_id', 'company_id')
    def _check_google_ads_account_company(self):
        """An advertising account may only be named by a touch of its own
        company. `company_id` on the touchpoint is itself computed from the
        lead / conversation anchor, so this is what stops a payload's
        customer id becoming a cross-company reference."""
        for touch in self:
            # sudo on the ACCOUNT read only: the website service user writes
            # these rows and has read-only ACL on the account, and a
            # constraint must not be the thing that decides who may capture a
            # lead. The touch's own company is read as the caller.
            account = touch.google_ads_account_id.sudo()
            if account and touch.company_id \
                    and account.company_id != touch.company_id:
                raise ValidationError(_(
                    'This touch belongs to %(ours)s, but the Google Ads '
                    'account "%(account)s" belongs to %(theirs)s.',
                    ours=touch.company_id.display_name,
                    account=account.name,
                    theirs=account.company_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Ledger §5.2 — `@api.constrains` does not fire on create when none of
        # the constrained fields are in vals, and `company_id` is computed
        # (never in vals), so the check has to be called explicitly.
        records._check_google_ads_account_company()
        return records
