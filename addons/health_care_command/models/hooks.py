# -*- coding: utf-8 -*-
"""Additive ingestion hooks.

Every hook: call super() FIRST (the host module's behaviour is sacrosanct),
then feed Care Command inside a try/except so a bug here can NEVER break a
Zalo webhook, a call log, a lead create or a mail delivery (§5.4, tested by
T13). No host field is written; we only read the freshly-created row and
upsert our own ``care.conversation``.

Each ingest runs inside ``cr.savepoint()``: a database-level error (e.g. the
partial unique index firing on concurrent webhook double-delivery) would
otherwise leave the host transaction aborted even though the exception is
caught, failing every later statement in the host flow.
"""

import logging

from odoo import api, fields, models
from odoo.tools import html2plaintext

from .care_conversation import MODE_TO_CHANNEL

_logger = logging.getLogger(__name__)


class ZaloMessageHook(models.Model):
    _inherit = "zalo.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for msg in messages:
            try:
                with self.env.cr.savepoint():
                    self._care_ingest_zalo(msg)
            except Exception:
                _logger.exception("care_command: zalo.message ingest failed (msg %s)", msg.id)
        return messages

    def _care_ingest_zalo(self, msg):
        conv = msg.conversation_id
        if not conv:
            return
        Care = self.env["care.conversation"]
        anchor = {
            "zalo_conversation_id": conv.id,
            "partner_id": conv.partner_id.id or False,
            "phone_normalized": Care._safe_phone(conv.zalo_phone_number),
        }
        if msg.direction == "incoming":
            Care._find_or_create_for(anchor, {
                "channel": "zalo",
                "inbound": True,
                "event_at": msg.sent_date,
                "set_status": "needs_reply",
                "unread": max(1, conv.unread_count or 0),
                # watchlist runs at ingest, inbound only (§3, deliverable 2)
                "watch_hits": Care._match_watchlist(msg.text),
            })
        else:  # outgoing (sent by us / an agent, incl. via action_send_zalo)
            Care._find_or_create_for(anchor, {
                "channel": "zalo",
                "inbound": False,
                "event_at": msg.sent_date,
                "set_status": "waiting",
                "unread": "zero",
            })


# NOTE: no VoipCallLogHook here. health_voip24h does not install on Odoo 19
# (removed res.groups.category_id), so `voip.call.log` is not in the registry
# and an `_inherit` on it would crash registry load. Live call INGESTION is
# therefore deferred: when VoIP is made O19-compatible and installed, re-add a
# `models.Model(_inherit='voip.call.log')` create-hook mirroring the other
# ingestion hooks (anchors: partner_id/lead_id/caller_number_normalized;
# missed→needs_reply+missed_call). Backfill + timeline already read voip
# defensively via `if 'voip.call.log' in self.env`, so calls surface the
# moment the model exists.


class CrmLeadHook(models.Model):
    _inherit = "crm.lead"

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead in leads:
            try:
                with self.env.cr.savepoint():
                    self._care_ingest_lead(lead)
            except Exception:
                _logger.exception("care_command: crm.lead ingest failed (lead %s)", lead.id)
        return leads

    def _care_ingest_lead(self, lead):
        Care = self.env["care.conversation"]
        phone = Care._safe_phone(lead.phone)
        email = Care._safe_email(lead.email_from)
        if not phone and not email:
            return
        # Derive a DECLARED channel from how the lead said they reached us —
        # never faked as traffic (no `channel` key → channel_primary stays NULL,
        # has_channel_activity stays False). walk_in/unmapped → None → skipped.
        Care._find_or_create_for(
            {"lead_id": lead.id, "phone_normalized": phone, "email_normalized": email},
            {"inbound": True, "event_at": lead.create_date, "set_status": "needs_reply",
             "unread": "keep",
             "declared_channel": MODE_TO_CHANNEL.get(lead.mode_of_contact)},
        )


class MailMessageHook(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        # HOT PATH (§5.4): every chatter note in the system passes through here.
        # Cheap first-line field checks on vals — NO search before the guard.
        for msg, vals in zip(messages, vals_list):
            if vals.get("message_type") != "email":
                continue
            if vals.get("model") not in ("crm.lead", "res.partner"):
                continue
            try:
                with self.env.cr.savepoint():
                    self._care_ingest_email(msg)
            except Exception:
                _logger.exception("care_command: mail.message ingest failed (msg %s)", msg.id)
        return messages

    def _care_ingest_email(self, msg):
        if not msg.res_id:
            return
        Care = self.env["care.conversation"]
        anchor = {}
        if msg.model == "crm.lead":
            anchor["lead_id"] = msg.res_id
        else:
            anchor["partner_id"] = msg.res_id
        anchor["email_normalized"] = Care._safe_email(msg.email_from)
        if not any(anchor.values()):
            return
        Care._find_or_create_for(anchor, {
            "channel": "email",
            "inbound": True,
            "event_at": msg.date or fields.Datetime.now(),
            "set_status": "needs_reply",
            "unread": 1,
            # match against subject + a plaintext preview of the body (§3)
            "watch_hits": Care._match_watchlist(
                msg.subject, html2plaintext(msg.body or "")[:1000]),
        })


class FieldserviceOrderHook(models.Model):
    _inherit = "health.fieldservice.order"

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            try:
                with self.env.cr.savepoint():
                    self._care_sync_booking(order)
            except Exception:
                _logger.exception("care_command: fso create sync failed (fso %s)", order.id)
        return orders

    def write(self, vals):
        res = super().write(vals)
        if "scheduled_datetime" in vals or "state" in vals:
            for order in self:
                try:
                    with self.env.cr.savepoint():
                        self._care_sync_booking(order)
                except Exception:
                    _logger.exception("care_command: fso write sync failed (fso %s)", order.id)
        return res

    def _care_sync_booking(self, order):
        if not order.patient_id:
            return
        convs = self.env["care.conversation"].sudo().search(
            [("partner_id", "=", order.patient_id.id)]
        )
        if convs:
            convs._sync_next_booking()
