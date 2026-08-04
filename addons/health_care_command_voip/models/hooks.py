# -*- coding: utf-8 -*-
"""Live VoIP → Care Command ingestion hook.

This is the one ingestion seam Phase 1 could not ship: ``health_voip24h`` did
not install on Odoo 19, so ``voip.call.log`` was absent from the registry and
an ``_inherit`` on it would have crashed registry load. Now that VoIP is
O19-compatible and installed, this bridge module supplies the create-hook,
mirroring the Phase-1 hooks in ``health_care_command/models/hooks.py`` exactly:

- call super() FIRST — the VoIP module's behaviour is sacrosanct;
- feed Care Command inside ``try/except`` so a bug here can NEVER break a VoIP
  webhook / CDR sync;
- run the guarded body inside ``cr.savepoint()`` so a database-level error
  (e.g. a concurrent double-delivery) leaves the host transaction intact
  rather than aborting every later statement (§5.55, MANDATORY).

No host field is written; we only read the freshly-created call row and upsert
our own ``care.conversation``.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Incoming call_types where the customer reached out but we never talked to
# them → treat as a callback-due "missed call" (Phase 3, deliverable 4).
# `answered` (and `internal`) stay event-only.
_MISSED_LIKE = ("missed", "abandoned", "busy", "failed", "voicemail")


class VoipCallLogHook(models.Model):
    _inherit = "voip.call.log"

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        for log in logs:
            try:
                with self.env.cr.savepoint():
                    self._care_ingest_call(log)
            except Exception:
                _logger.exception(
                    "care_command: voip.call.log ingest failed (log %s)", log.id)
        return logs

    def _care_ingest_call(self, log):
        Care = self.env["care.conversation"]
        # The CUSTOMER's number keys the conversation: caller for incoming,
        # called for outgoing (caller_number on an outgoing CDR is our trunk —
        # anchoring on it would collapse every outbound call into one
        # conversation on the clinic's own number).
        customer_number = (
            log.called_number_normalized if log.direction == "outgoing"
            else log.caller_number_normalized
        )
        anchor = {
            "partner_id": log.partner_id.id or False,
            "lead_id": log.lead_id.id or False,
            "phone_normalized": Care._safe_phone(customer_number),
        }
        if not anchor["phone_normalized"]:
            # `_safe_phone` refuses anything normalize_vn_phone cannot parse —
            # an international caller, a short code — and that used to drop the
            # whole call. The RAW number is still a number somebody can ring
            # back, so fall back to it before giving up (client requirement 2).
            raw = (log.called_number if log.direction == "outgoing"
                   else log.caller_number)
            anchor["phone_normalized"] = (raw or "").strip()[:32] or False

        if not any(anchor.values()):
            # A withheld/anonymous caller: no number at all, so there is
            # genuinely nothing to key a conversation on. It still goes on the
            # Unrouted queue — a missed call from a hidden number is exactly
            # the kind of contact that used to vanish.
            if "care.contact.capture" in self.env:
                self.env["care.contact.capture"]._capture(
                    "unmatched_call", "call",
                    peer_hint=log.caller_number or log.called_number,
                    body=log.call_type or "",
                    external_event_id="voip.call.log:%s" % log.id,
                    occurred_at=log.call_date)
            return

        if log.direction == "outgoing":
            # we called them → waiting on the customer; the upsert's waiting
            # branch clears any missed_call_unhandled + zeroes unread
            signal = {
                "channel": "call",
                "inbound": False,
                "event_at": log.call_date,
                "set_status": "waiting",
                "unread": "zero",
            }
        elif log.direction == "incoming" and log.call_type in _MISSED_LIKE:
            # they tried to reach us and didn't get through → callback due.
            # missed/abandoned + busy/failed/voicemail (Phase 3): in every one
            # of these the customer rang and we did not talk to them.
            signal = {
                "channel": "call",
                "inbound": True,
                "event_at": log.call_date,
                "set_status": "needs_reply",
                "missed_call": True,
                "unread": "keep",
            }
        else:
            # answered incoming (or internal) → event-only; an answered call is
            # NOT awaiting a reply, so DON'T invent a status change on an
            # existing conversation (new ones fall back to the model default)
            signal = {
                "channel": "call",
                "inbound": log.direction == "incoming",
                "event_at": log.call_date,
                "unread": "keep",
            }
        Care._find_or_create_for(anchor, signal)
