# -*- coding: utf-8 -*-
"""Chat-originated leads inherit their attribution (client requirement 3).

The client's ask — *"capture the GCLID for google and equivalents for Facebook
and Zalo, so we can feed back actual contacts to the algorithms"* — only pays
off at the moment a conversation becomes a LEAD. That is the conversion the ad
platforms want back, and until now it was the exact moment the attribution was
thrown away: ``care.conversation.action_create_lead`` wrote name, phone, email
and partner, and nothing else. A lead created from a Messenger thread that
started on a Click-to-Messenger ad was indistinguishable from a walk-in.

This override lives in health_web_leads rather than in Care Command because
this is the module that owns ``crm.lead.gclid`` and ``health.lead.touchpoint``
— and because health_care_command must not grow a dependency on it (nothing
depends on health_web_leads; ledger §5.71).

Everything here follows the shipped W1 policy rather than inventing a second
one: source and medium are find-or-create, campaign is **find-only** (an
advertiser-supplied campaign string is attacker-controllable input and blanket
auto-create is a record-explosion vector — web_lead_service.py:313-339).
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Copied onto the lead as its FIRST touch, frozen at creation — the same rule
# the web-form path uses. Only fields that exist on crm.lead.
_LEAD_ATTRIBUTION_FIELDS = (
    'gclid', 'wbraid', 'gbraid', 'fbclid',
    'utm_content', 'utm_term',
    'web_landing_url', 'web_submit_page_url', 'web_referrer_url',
)


class CareConversationAttribution(models.Model):
    _inherit = 'care.conversation'

    @api.model
    def action_create_lead(self, conv_id):
        """Create the lead, then give it the conversation's attribution."""
        result = super().action_create_lead(conv_id)
        try:
            with self.env.cr.savepoint():
                self.browse(conv_id)._apply_conversation_attribution()
        except Exception:  # noqa: BLE001 — never cost the operator the lead
            _logger.exception(
                'web_leads: attribution copy failed for conversation %s',
                conv_id)
        return result

    def _apply_conversation_attribution(self):
        """Move first-touch attribution from the conversation onto its lead."""
        self.ensure_one()
        rec = self.sudo()
        lead = rec.lead_id
        if not lead:
            return False
        Touch = self.env['health.lead.touchpoint'].sudo()
        touch = Touch.search([('conversation_id', '=', rec.id)],
                             order='occurred_at asc, id asc', limit=1)
        if not touch:
            return False

        vals = {}
        for field in _LEAD_ATTRIBUTION_FIELDS:
            value = touch[field] if field in touch._fields else None
            # Fill-never-overwrite: if the lead already carries a click id it
            # came from somewhere with a better claim (a web form the same
            # person also submitted), and first touch wins.
            if value and field in lead._fields and not lead[field]:
                vals[field] = value

        # The UTM vocabulary, through the shipped policy.
        Service = self.env['web.lead.service'].sudo()
        utm_ids = Service._utm_ids({
            'source': touch.utm_source,
            'medium': touch.utm_medium,
            'campaign': touch.utm_campaign,
        })
        for field, value in (utm_ids or {}).items():
            if value and not lead[field]:
                vals[field] = value

        # The account's own defaults, when the event carried nothing. This is
        # what attributes a phone call — which can never carry a click id — to
        # the number that was dialled.
        conn = rec.channel_connection_id if 'channel_connection_id' \
            in rec._fields else None
        if conn:
            if conn.utm_source_id and not lead.source_id:
                vals['source_id'] = conn.utm_source_id.id
            if conn.utm_medium_id and not lead.medium_id:
                vals['medium_id'] = conn.utm_medium_id.id
            if conn.campaign_id and not lead.campaign_id:
                vals['campaign_id'] = conn.campaign_id.id

        if vals:
            lead.sudo().write(vals)
        # The touch now belongs to the lead as well: the offline-conversion
        # export reads `lead_id`, and re-pointing it here is what makes a
        # chat-originated conversion exportable at all.
        if not touch.lead_id:
            touch.write({'lead_id': lead.id})
        return True
