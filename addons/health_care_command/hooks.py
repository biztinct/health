# -*- coding: utf-8 -*-
"""post_init backfill (§5.5).

Bounded, idempotent seed of ``care.conversation`` from existing channel data
so the wall is not empty on first open. Re-running creates nothing new
(the upsert keys on anchors). Logs a one-line count per channel.
"""

import logging
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    Care = env["care.conversation"]
    now = fields.Datetime.now()
    d30 = now - timedelta(days=30)
    d90 = now - timedelta(days=90)
    counts = {"zalo": 0, "call": 0, "email": 0, "lead": 0}

    def _before():
        return Care.search_count([])

    # --- Zalo: active conversations with recent traffic -----------------
    for conv in env["zalo.conversation"].sudo().search(
        [("state", "=", "active"), ("last_message_date", ">=", d30)]
    ):
        before = _before()
        Care._find_or_create_for(
            {
                "zalo_conversation_id": conv.id,
                "partner_id": conv.partner_id.id or False,
                "phone_normalized": Care._safe_phone(conv.zalo_phone_number),
            },
            {
                "channel": "zalo",
                "inbound": not conv.last_message_from_us,
                "event_at": conv.last_message_date,
                "set_status": "waiting" if conv.last_message_from_us else "needs_reply",
                "unread": max(0, conv.unread_count or 0) or "keep",
            },
        )
        counts["zalo"] += _before() - before

    # --- VoIP: last 30 days, missed incoming first (optional module) -----
    calls = (env["voip.call.log"].sudo().search(
        [("call_date", ">=", d30), ("direction", "in", ("incoming", "outgoing"))],
        order="call_type asc, call_date desc",
    ) if "voip.call.log" in env else env["res.partner"].browse())
    for log in calls:
        anchor = {
            "partner_id": log.partner_id.id or False,
            "lead_id": log.lead_id.id or False,
            "phone_normalized": Care._safe_phone(log.caller_number_normalized),
        }
        if not any(anchor.values()):
            continue
        before = _before()
        signal = {"channel": "call", "inbound": log.direction == "incoming",
                  "event_at": log.call_date, "unread": "keep"}
        if log.direction == "incoming" and log.call_type in ("missed", "abandoned"):
            signal.update(set_status="needs_reply", missed_call=True, unread=1)
        Care._find_or_create_for(anchor, signal)
        counts["call"] += _before() - before

    # --- Email: inbound mail.message on leads/partners, last 30 days -----
    emails = env["mail.message"].sudo().search(
        [("message_type", "=", "email"), ("date", ">=", d30),
         ("model", "in", ("crm.lead", "res.partner")), ("res_id", "!=", False)],
        order="date desc",
    )
    for msg in emails:
        anchor = {"email_normalized": Care._safe_email(msg.email_from)}
        if msg.model == "crm.lead":
            anchor["lead_id"] = msg.res_id
        else:
            anchor["partner_id"] = msg.res_id
        if not any(anchor.values()):
            continue
        before = _before()
        Care._find_or_create_for(anchor, {
            "channel": "email", "inbound": True, "event_at": msg.date,
            "set_status": "needs_reply", "unread": 1})
        counts["email"] += _before() - before

    # --- Leads: active/lead with a phone or email, created <= 90 days ----
    for lead in env["crm.lead"].sudo().search(
        [("contact_status", "in", ("active", "lead")), ("create_date", ">=", d90),
         "|", ("phone", "!=", False), ("email_from", "!=", False)]
    ):
        phone = Care._safe_phone(lead.phone)
        email = Care._safe_email(lead.email_from)
        if not phone and not email:
            continue
        before = _before()
        Care._find_or_create_for(
            {"lead_id": lead.id, "phone_normalized": phone, "email_normalized": email},
            {"inbound": True, "event_at": lead.create_date,
             "set_status": "needs_reply", "unread": "keep"},
        )
        counts["lead"] += _before() - before

    _logger.info(
        "care_command backfill: created zalo=%(zalo)s call=%(call)s "
        "email=%(email)s lead=%(lead)s (total now %(total)s)",
        {**counts, "total": Care.search_count([])},
    )
