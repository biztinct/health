# -*- coding: utf-8 -*-
"""The two extension seams `health_web_leads` opened, filled in for Google Ads.

This module never re-implements the handler and never patches its dict in
place: `_lead_extra_vals` and `_touchpoint_extra_vals` are named, overridable
methods with empty defaults, and everything Google-specific lives here.

Two rails run through every line below:

* **R1 — company never comes from the payload.** Account and campaign lookups
  are domained on `self.env.company`, which the API gateway set from the
  credential the relay authenticated with. A `customer_id` in a submission is
  an attribution HINT; it can never reach across companies.
* **R2 — the first touch is immutable.** `_lead_extra_vals` runs from
  `_create_lead` only; `_merge` never calls it. A Google follow-up on an
  organic enquiry appends a touchpoint and leaves the enquiry's first source
  exactly where it was.
"""
import logging

from odoo import models

from odoo.addons.health_web_leads.models.web_lead_service import _sub

from ..services import attribution

_logger = logging.getLogger(__name__)


class WebLeadServiceGoogleAds(models.AbstractModel):
    _inherit = 'web.lead.service'

    # ------------------------------------------------------------------
    # The seams
    # ------------------------------------------------------------------
    def _lead_extra_vals(self, payload, catchment, city_source):
        vals = super()._lead_extra_vals(payload, catchment, city_source)
        google = self._google_ads_vals(payload)
        if not google:
            return vals
        vals = dict(vals, **google)
        if google.get('google_ads_match_status') == 'conflict':
            # OR, never assignment: the base builder has already decided
            # whether this enquiry needs review for its own reasons, and a
            # conflict can only ADD a reason. The key is returned ONLY for a
            # conflict, so `vals.update()` in `_create_lead` can never clear
            # an existing True.
            vals['web_needs_review'] = True
        return vals

    def _touchpoint_extra_vals(self, lead, payload, catchment, city_source):
        vals = super()._touchpoint_extra_vals(lead, payload, catchment,
                                              city_source)
        google = self._google_ads_vals(payload)
        if not google:
            return vals
        vals = dict(vals, **google)
        # GA1 always writes `website`: the time on this row is the website's
        # `submitted_at`. Nothing in this phase reads a provider clock.
        vals['google_ads_time_basis'] = 'website'
        return vals

    # ------------------------------------------------------------------
    # Classification + resolution
    # ------------------------------------------------------------------
    def _google_ads_vals(self, payload):
        """Shared by both seams. Returns {} when the touch is not Google Ads."""
        if not isinstance(payload, dict):
            return {}
        utm, clicks = _sub(payload, 'utm'), _sub(payload, 'click_ids')
        is_ads, hint = attribution.classify(utm, clicks)
        if not is_ads:
            return {}
        ids = attribution.extract_ids(payload)
        account, status = self._google_ads_resolve_account(ids)
        if hint == 'conflict':
            # The click id is the stronger evidence, so the touch IS Google
            # Ads — but the declared UTM strings are never rewritten (design
            # §6.1). The disagreement is recorded, not resolved.
            status = 'conflict'
        return {
            'google_ads_origin': 'website',
            'google_ads_match_status': status,
            'google_ads_account_id': account.id if account else False,
            'google_ads_customer_id': ids['customer_id'] or False,
            'google_ads_campaign_id': ids['campaign_id'] or False,
            'google_ads_adgroup_id': ids['adgroup_id'] or False,
            'google_ads_creative_id': ids['creative_id'] or False,
            'google_ads_asset_group_id': ids['asset_group_id'] or False,
        }

    def _google_ads_resolve_account(self, ids):
        """Design §6.2 order, COMPANY-SCOPED.

        Explicit validated customer id within the company; otherwise a UNIQUE
        configured campaign mapping within the company; otherwise unmatched.
        **Never the first of several** — an ambiguous campaign id resolves to
        unmatched, because guessing an account here would misattribute spend
        with no way for anyone to notice.

        Why `sudo()`: the relay's service user has no ACL on these two models
        and needs none. The search is pinned to `self.env.company`, which the
        gateway set from the credential the request authenticated with
        (`health_web_leads/controllers/web_leads.py` — `request.update_env`),
        so elevation here widens nothing.
        """
        Account = self.env['google.ads.account'].sudo()
        company = self.env.company
        if ids.get('customer_id'):
            account = Account.search(
                [('company_id', '=', company.id),
                 ('customer_id', '=', ids['customer_id'])], limit=1)
            if account:
                return account, 'matched'
        if ids.get('campaign_id'):
            rows = self.env['google.ads.campaign'].sudo().search(
                [('company_id', '=', company.id),
                 ('external_campaign_id', '=', ids['campaign_id'])], limit=2)
            if len(rows) == 1:
                return rows.account_id, 'matched'
            if len(rows) > 1:
                _logger.info(
                    'google_ads: campaign id %s is mapped on more than one '
                    'account in company %s — left unmatched',
                    ids['campaign_id'], company.id)
        return Account.browse(), 'unmatched'
