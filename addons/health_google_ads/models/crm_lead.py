# -*- coding: utf-8 -*-
"""Google Ads first-touch snapshot on ``crm.lead``.

These fields describe the FIRST enquiry and nothing else. A later Google touch
on the same person appends a touchpoint; it never turns an organic first
source into a paid one (design §5.3). That is why every one of these columns
is written exactly once, by `_create_lead`, and never by `_merge`.

``google_ads_influenced`` is the other half of that rule made searchable: it
is a non-stored, search-only compute over the touchpoints, so "Google Ads
influenced" and "First source Google Ads" are two genuinely different
questions rather than the same filter wearing two names.
"""
from odoo import _, api, fields, models

GOOGLE_ADS_ORIGIN_SELECTION = [
    ('website', 'Website'),
    ('native_form', 'Google lead form'),
]

GOOGLE_ADS_MATCH_SELECTION = [
    ('matched', 'Matched'),
    ('unmatched', 'Unmatched'),
    ('conflict', 'Conflict'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    google_ads_account_id = fields.Many2one(
        'google.ads.account', string='Google Ads Account',
        index=True, ondelete='set null', check_company=True,
        help='Which of your advertising accounts this enquiry was matched to. '
             'Empty means the enquiry looked like a Google ad click but could '
             'not be matched to a configured account.')
    google_ads_customer_id = fields.Char(
        string='Google Ads Customer ID', size=10,
        help='The ten-digit advertising account number the ad carried. It is '
             'a hint about where the click came from, never a permission.')
    google_ads_campaign_id = fields.Char(
        string='Google Campaign ID',
        help='The campaign number exactly as Google sent it, kept as text so '
             'the digits cannot change.')
    google_ads_adgroup_id = fields.Char(string='Google Ad Group ID')
    google_ads_creative_id = fields.Char(string='Google Ad ID')
    google_ads_asset_group_id = fields.Char(string='Google Asset Group ID')

    google_ads_origin = fields.Selection(
        GOOGLE_ADS_ORIGIN_SELECTION, string='Google Ads Origin', index=True,
        help='How a Google Ads enquiry reached us. Empty on every enquiry '
             'that did not come from a Google ad.')
    google_ads_match_status = fields.Selection(
        GOOGLE_ADS_MATCH_SELECTION, string='Google Ads Match',
        help='Matched: we know which advertising account it came from. '
             'Unmatched: it came from a Google ad we have no account set up '
             'for. Conflict: the enquiry carried a Google click but said it '
             'came from somewhere else — worth a look.')

    google_ads_influenced = fields.Boolean(
        string='Google Ads influenced', compute='_compute_google_ads_influenced',
        search='_search_google_ads_influenced',
        help='True when ANY touch behind this enquiry came from a Google ad, '
             'even if the first one did not.')

    @api.depends('web_touchpoint_ids.google_ads_origin')
    def _compute_google_ads_influenced(self):
        for lead in self:
            lead.google_ads_influenced = any(
                touch.google_ads_origin for touch in lead.web_touchpoint_ids)

    def _search_google_ads_influenced(self, operator, value):
        """Search-only: the filter is the point, the column is not.

        **Ledger §5.13, measured live on the master rather than assumed:**
        `('google_ads_influenced', '=', True)` never reaches this method in
        that shape. Odoo 19's domain optimizer rewrites it to
        `('in', OrderedSet([True]))` — an `OrderedSet`, which is neither a
        `list` nor a `bool`, so a check like `value == [True]` or
        `value in (True, 1)` reads False and the filter silently returns the
        EXACT COMPLEMENT of what was asked for. The truthiness is therefore
        read by iterating, and the negation is a single XOR against the
        operator. (The filter listed 298 unrelated enquiries and excluded the
        one Google-influenced one; both halves of that symptom come from this
        one line.)

        The lead ids are resolved HERE rather than handed back as a
        `web_touchpoint_ids.google_ads_origin` traversal: an explicit id list
        is deterministic and cheap (there is one row per enquiry touch, not
        one per message).

        `sudo()` on the touchpoint read leaks nothing: the ids only narrow the
        outer `crm.lead` search, which still applies the reader's own record
        rules.
        """
        if operator in ('in', 'not in'):
            # A generic iterable — never index it, never compare it to a list.
            wanted = any(bool(item) for item in value)
            negate = operator == 'not in'
        else:
            wanted = bool(value)
            negate = operator in ('!=', '<>')
        positive = wanted != negate
        touched = self.env['health.lead.touchpoint'].sudo().search([
            ('google_ads_origin', '!=', False),
            ('lead_id', '!=', False),
        ])
        lead_ids = list(set(touched.mapped('lead_id').ids))
        return [('id', 'in' if positive else 'not in', lead_ids)]

    google_ads_source_line = fields.Char(
        string='Google Ads', compute='_compute_google_ads_source_line',
        help='What the advertising click said, in one line. Empty when the '
             'enquiry did not come from a Google ad.')

    @api.depends('google_ads_origin', 'google_ads_campaign_id',
                 'google_ads_match_status')
    def _compute_google_ads_source_line(self):
        """One readable line for the Lead-Hub source modal.

        A view attribute cannot call a method, so this is a field. Spelled-out
        labels rather than `dict(SELECTION)`: a Selection label is a model
        term and `_(variable)` would never be extracted at all.
        """
        labels = {
            'matched': _('matched to an account'),
            'unmatched': _('no matching account'),
            'conflict': _('conflicting source — needs a look'),
        }
        for lead in self:
            if not lead.google_ads_origin:
                lead.google_ads_source_line = ''
                continue
            lead.google_ads_source_line = _(
                'Google Ads: %(campaign)s · %(match)s',
                campaign=lead.google_ads_campaign_id or _('campaign unknown'),
                match=labels.get(lead.google_ads_match_status,
                                 _('no matching account')))
