# -*- coding: utf-8 -*-
"""Care Command — the thin work-item spine.

One ``care.conversation`` per person-ish anchor. It NEVER stores message
bodies; it references source records (Zalo conversation, VoIP calls, the
lead/partner that carries email chatter) and maintains just enough state
(status, owner, unread, timestamps, urgency) to drive the triage wall and
the messenger list. The merged timeline is composed read-time in
``get_conversation_detail`` from the live source rows.

All ingestion (from the additive hooks in ``hooks.py``) goes through
``_find_or_create_for`` and runs ``sudo()`` — the hooks fire as whatever
user/webhook produced the source row, but maintaining this cross-user
work-index is engine-internal bookkeeping. Ownership/visibility for the
USER-facing service methods is enforced separately by an explicit group
gate + company scope on every public method (§6).
"""

import logging
from datetime import datetime, timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from odoo.addons.health_base.models.phone_utils import normalize_vn_phone

_logger = logging.getLogger(__name__)

CRM_USER_GROUP = "health_crm.group_health_crm_user"
CRM_MANAGER_GROUP = "health_crm.group_health_crm_manager"

# Bus-notified field set (§6.5)
_BUS_FIELDS = {"status", "owner_id", "unread_count", "last_event_at"}


class CareConversation(models.Model):
    _name = "care.conversation"
    _description = "Care Command Conversation (work item)"
    _inherit = ["mail.thread"]
    _order = "urgency_score desc, last_event_at desc"

    # --- anchors -------------------------------------------------------
    partner_id = fields.Many2one(
        "res.partner", string="Contact", index=True, ondelete="set null"
    )
    lead_id = fields.Many2one(
        "crm.lead", string="Lead", index=True, ondelete="set null"
    )
    zalo_conversation_id = fields.Many2one(
        "zalo.conversation", string="Zalo Conversation", index=True,
        ondelete="set null",
    )
    phone_normalized = fields.Char(string="Phone", index=True)
    email_normalized = fields.Char(string="Email", index=True)

    # --- display / routing --------------------------------------------
    display_name_c = fields.Char(
        string="Name", compute="_compute_display_name_c", store=True,
    )
    channel_primary = fields.Selection(
        [("zalo", "Zalo"), ("call", "Calls"), ("email", "Email"), ("zns", "ZNS")],
        string="Last Inbound Channel",
    )
    status = fields.Selection(
        [
            ("needs_reply", "Needs reply"),
            ("waiting", "Waiting"),
            ("junk_suspect", "Junk?"),
            ("closed", "Closed"),
        ],
        default="needs_reply",
        required=True,
        tracking=True,
        index=True,
    )

    # --- ownership -----------------------------------------------------
    owner_id = fields.Many2one(
        "res.users", string="Owner", index=True, tracking=True
    )
    claimed_at = fields.Datetime(string="Claimed At")

    # --- counters / timing --------------------------------------------
    unread_count = fields.Integer(default=0)
    # Set (not incremented) by the missed-call hook; cleared when the
    # conversation leaves needs_reply. Feeds the +10 urgency term
    # deterministically without a time-dependent stored compute.
    missed_call_unhandled = fields.Boolean(default=False)
    last_inbound_at = fields.Datetime(string="Last Inbound")
    last_event_at = fields.Datetime(string="Last Event", index=True)
    next_booking_at = fields.Datetime(string="Next Booking")

    urgency_score = fields.Integer(
        compute="_compute_urgency_score", store=True, index=True,
    )

    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # DB constraints
    # ------------------------------------------------------------------
    def init(self):
        # §5.1 gotcha: _sql_constraints aren't materialised; a partial unique
        # index is the only reliable uniqueness contract on zalo_conversation_id.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                care_conversation_zalo_conv_uniq
            ON care_conversation (zalo_conversation_id)
            WHERE zalo_conversation_id IS NOT NULL
            """
        )

    @api.constrains(
        "partner_id", "lead_id", "zalo_conversation_id",
        "phone_normalized", "email_normalized",
    )
    def _check_anchor(self):
        for rec in self:
            if not (
                rec.partner_id or rec.lead_id or rec.zalo_conversation_id
                or rec.phone_normalized or rec.email_normalized
            ):
                raise UserError(_(
                    "A Care Command conversation needs at least one anchor "
                    "(contact, lead, Zalo conversation, phone or email)."
                ))

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends(
        "partner_id", "partner_id.name",
        "lead_id", "lead_id.contact_name", "lead_id.partner_name", "lead_id.name",
        "zalo_conversation_id.zalo_user_name",
        "email_normalized", "phone_normalized",
    )
    def _compute_display_name_c(self):
        for rec in self:
            name = False
            if rec.partner_id:
                name = rec.partner_id.name
            if not name and rec.lead_id:
                name = (
                    rec.lead_id.contact_name or rec.lead_id.partner_name
                    or rec.lead_id.name
                )
            if not name and rec.zalo_conversation_id:
                name = rec.zalo_conversation_id.zalo_user_name
            if not name:
                name = rec.email_normalized or rec.phone_normalized
            rec.display_name_c = name or _("Unknown contact")

    @api.depends(
        "status", "next_booking_at", "unread_count",
        "last_inbound_at", "missed_call_unhandled",
    )
    def _compute_urgency_score(self):
        """Deterministic triage score (§5.3). Time terms (booking-within-24h,
        hours-since-last-inbound) are evaluated at write time; every hook and
        the 60s wall refresh re-reads the stored value, so mild staleness is
        acceptable and the score never depends on an un-stored 'now'."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.status == "junk_suspect":
                rec.urgency_score = 0
                continue
            score = 0
            if rec.status == "needs_reply":
                score += 40
            if rec.next_booking_at and rec.next_booking_at >= now \
                    and rec.next_booking_at <= now + timedelta(hours=24):
                score += 30
            if rec.unread_count > 0:
                score += 15
            if rec.missed_call_unhandled:
                score += 10
            if rec.status == "needs_reply" and rec.last_inbound_at:
                hours = (now - rec.last_inbound_at).total_seconds() / 3600.0
                score += min(20, max(0, int(hours)))
            rec.urgency_score = score

    # ------------------------------------------------------------------
    # Bus (§6.5)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._bus_send_update()
        return records

    def write(self, vals):
        res = super().write(vals)
        if _BUS_FIELDS & set(vals):
            for rec in self:
                rec._bus_send_update()
        return res

    def _bus_send_update(self):
        """Clone of health_zalo message_handler bus pattern
        (services/message_handler.py:256)."""
        self.ensure_one()
        try:
            channel = "care_command_%s" % self.company_id.id
            self.env["bus.bus"]._sendone(
                channel,
                "care.conversation/update",
                {
                    "id": self.id,
                    "status": self.status,
                    "owner_id": self.owner_id.id or False,
                    "unread": self.unread_count,
                    "urgency": self.urgency_score,
                },
            )
        except Exception:  # never let a bus hiccup break a write/hook
            _logger.exception("care_command: bus notify failed for %s", self.id)

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @api.model
    def _safe_phone(self, value):
        """normalize_vn_phone raises on garbage (ledger §5.15) — inbound
        external data is routinely garbage, so fall back to falsy."""
        if not value:
            return False
        try:
            return normalize_vn_phone(value)
        except Exception:
            return False

    @api.model
    def _safe_email(self, value):
        if not value or "@" not in value:
            return False
        return value.strip().lower()

    # ------------------------------------------------------------------
    # Idempotent upsert (§5.2) — always runs sudo (engine bookkeeping)
    # ------------------------------------------------------------------
    @api.model
    def _find_or_create_for(self, anchor, signal):
        """anchor: identity dict (zalo_conversation_id / partner_id / lead_id /
        phone_normalized / email_normalized). signal: event dict
        (channel, inbound, event_at, set_status, unread, missed_call).

        SET semantics for unread (never increment) → firing the same source
        event twice is idempotent: one record, no double state bump (T1)."""
        Conv = self.sudo()
        company = self.env.company
        anchor = {k: v for k, v in (anchor or {}).items() if v}

        # --- find by precedence (company-scoped) -----------------------
        domain_base = [("company_id", "=", company.id)]
        rec = Conv.browse()
        for key in ("zalo_conversation_id", "partner_id", "lead_id",
                    "phone_normalized", "email_normalized"):
            if anchor.get(key):
                rec = Conv.search(domain_base + [(key, "=", anchor[key])], limit=1)
                if rec:
                    break

        event_at = signal.get("event_at") or fields.Datetime.now()
        inbound = signal.get("inbound", False)
        channel = signal.get("channel")

        if not rec:
            vals = dict(anchor)
            vals["company_id"] = company.id
            vals["last_event_at"] = event_at
            if channel:
                vals["channel_primary"] = channel
            if inbound:
                vals["last_inbound_at"] = event_at
            vals["status"] = signal.get("set_status") or "needs_reply"
            vals["unread_count"] = self._resolve_unread(signal, 0)
            vals["missed_call_unhandled"] = signal.get("missed_call", False)
            return Conv.create(vals)

        # --- update existing -------------------------------------------
        upd = {}
        # fill-not-overwrite anchors (identity changes are human decisions)
        for key in ("partner_id", "lead_id"):
            new = anchor.get(key)
            if new:
                cur = rec[key].id
                if not cur:
                    upd[key] = new
                elif cur != new:
                    _logger.warning(
                        "care_command: conflicting %s on conversation %s "
                        "(have %s, signal %s) — keeping existing",
                        key, rec.id, cur, new,
                    )
        for key in ("zalo_conversation_id", "phone_normalized", "email_normalized"):
            if anchor.get(key) and not rec[key]:
                upd[key] = anchor[key]

        if not rec.last_event_at or event_at >= rec.last_event_at:
            upd["last_event_at"] = event_at
        if channel:
            upd["channel_primary"] = channel
        if inbound:
            if not rec.last_inbound_at or event_at >= rec.last_inbound_at:
                upd["last_inbound_at"] = event_at
        if signal.get("set_status"):
            upd["status"] = signal["set_status"]
        if signal.get("missed_call"):
            upd["missed_call_unhandled"] = True
        upd["unread_count"] = self._resolve_unread(signal, rec.unread_count)
        # clear the missed-call term once we're no longer waiting on a reply
        target_status = upd.get("status", rec.status)
        if target_status in ("waiting", "closed"):
            upd["missed_call_unhandled"] = False
            if target_status == "waiting":
                upd["unread_count"] = 0

        rec.write(upd)
        return rec

    @api.model
    def _resolve_unread(self, signal, current):
        """SET (idempotent) unread from the signal."""
        u = signal.get("unread")
        if u == "zero":
            return 0
        if u == "keep":
            return current
        if isinstance(u, int):
            return max(current, u)  # never shrink on an inbound bump
        return current

    def _sync_next_booking(self):
        """Recompute next_booking_at from the partner's next non-cancelled FSO
        (§5.4 fso hook). sudo: reading the patient's bookings is engine
        bookkeeping, not a user-scoped read."""
        FSO = self.env["health.fieldservice.order"].sudo()
        now = fields.Datetime.now()
        for rec in self:
            if not rec.partner_id:
                if rec.next_booking_at:
                    rec.write({"next_booking_at": False})
                continue
            fso = FSO.search(
                [
                    ("patient_id", "=", rec.partner_id.id),
                    ("state", "not in", ("cancelled", "closed")),
                    ("scheduled_datetime", ">=", now),
                ],
                order="scheduled_datetime asc", limit=1,
            )
            new = fso.scheduled_datetime if fso else False
            if new != rec.next_booking_at:
                rec.write({"next_booking_at": new})

    # ==================================================================
    # SERVICE LAYER (user-facing, called from OWL via orm.call)
    # ==================================================================
    @api.model
    def _ensure_access(self):
        if not self.env.user.has_group(CRM_USER_GROUP):
            raise AccessError(_("Care Command is restricted to CRM staff."))

    def _is_manager(self):
        return self.env.user.has_group(CRM_MANAGER_GROUP)

    @api.model
    def _company_domain(self):
        return [("company_id", "in", self.env.companies.ids)]

    @staticmethod
    def _initials(name):
        parts = [p for p in (name or "").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def _urgency_tier(self):
        self.ensure_one()
        s = self.urgency_score
        if self.status in ("waiting", "junk_suspect"):
            return "small"
        if s >= 60:
            return "large"
        if s >= 30:
            return "medium"
        return "small"

    # --- 6.1 workspace payload ----------------------------------------
    # Tile/list payload cap (review LOW-9). Past this the wall is truncated to
    # the most urgent WORKSPACE_CAP rows (ordered by _order); the counts below
    # are still EXACT (read_group over the whole open set), and the payload
    # carries {"capped": true, "total": N} so the UI never lies about coverage
    # (same honesty rule as the PWA cache-hygiene phase).
    WORKSPACE_CAP = 400

    @api.model
    def get_workspace_data(self, channel=None, mine_only=False, query=None):
        self._ensure_access()
        uid = self.env.user.id
        open_domain = self._company_domain() + [("status", "!=", "closed")]

        # --- tile/list payload (filtered, capped, ordered by _order) ------
        list_domain = list(open_domain)
        if channel:
            list_domain.append(("channel_primary", "=", channel))
        if mine_only:
            # "Mine" = my actionable board: what I own PLUS what's unclaimed and
            # up for grabs (matches the POC, which never shows an empty wall).
            list_domain += ["|", ("owner_id", "=", uid), ("owner_id", "=", False)]
        q = (query or "").strip()
        if q:
            # search box over name / phone / email / lead name, on top of the
            # company + status + channel/mine scope (server-side, §5.4)
            list_domain += [
                "|", "|", "|",
                ("display_name_c", "ilike", q),
                ("phone_normalized", "ilike", q),
                ("email_normalized", "ilike", q),
                ("lead_id.name", "ilike", q),
            ]
        total_matching = self.sudo().search_count(list_domain)
        convs = self.sudo().search(list_domain, limit=self.WORKSPACE_CAP)  # _order
        conversations = [c._workspace_row() for c in convs]

        # --- channel counts via read_group (one query each, not ORM loops) -
        counts = {ch: {"total": 0, "needs": 0} for ch in ("zalo", "call", "email", "zns")}
        for channel_val, cnt in self.sudo()._read_group(
                open_domain, ["channel_primary"], ["__count"]):
            if channel_val in counts:
                counts[channel_val]["total"] = cnt
        for channel_val, cnt in self.sudo()._read_group(
                open_domain + [("status", "=", "needs_reply")],
                ["channel_primary"], ["__count"]):
            if channel_val in counts:
                counts[channel_val]["needs"] = cnt
        counts["all"] = {
            "total": self.sudo().search_count(open_domain),
            "needs": self.sudo().search_count(
                open_domain + [("status", "=", "needs_reply")]),
        }

        # --- team dock strip via read_group (per owner: open + needs) ------
        team_by_id = {}
        for owner, cnt in self.sudo()._read_group(
                open_domain + [("owner_id", "!=", False)],
                ["owner_id"], ["__count"]):
            team_by_id[owner.id] = {
                "id": owner.id, "name": owner.name,
                "initials": self._initials(owner.name),
                "open": cnt, "needs": 0,
            }
        for owner, cnt in self.sudo()._read_group(
                open_domain + [("owner_id", "!=", False),
                               ("status", "=", "needs_reply")],
                ["owner_id"], ["__count"]):
            if owner.id in team_by_id:
                team_by_id[owner.id]["needs"] = cnt
        team = sorted(team_by_id.values(), key=lambda t: t["needs"], reverse=True)

        return {
            "conversations": conversations,
            "capped": total_matching > self.WORKSPACE_CAP,
            "total": total_matching,
            "channel_counts": counts,
            "team": team,
            "me": {
                "id": uid,
                "name": self.env.user.name,
                "initials": self._initials(self.env.user.name),
                "is_manager": self._is_manager(),
            },
            "company_id": self.env.company.id,
        }

    def _workspace_row(self):
        self.ensure_one()
        name = self.display_name_c
        chips = []
        if self.partner_id and self.partner_id.is_patient and self.partner_id.patient_code:
            chips.append({"kind": "client", "label": self.partner_id.patient_code})
        if self.lead_id and self.lead_id.contact_status:
            chips.append({"kind": "lead", "label": self.lead_id.contact_status})
        if self.status == "needs_reply" and not self.owner_id:
            chips.append({"kind": "new", "label": _("New")})
        if self.status == "junk_suspect":
            chips.append({"kind": "junk", "label": _("Junk?")})
        return {
            "id": self.id,
            "name": name,
            "initials": self._initials(name),
            "chips": chips,
            # NULL channel = a lead/contact not yet reached on any channel;
            # render neutral, never a misleading channel glyph.
            "channel": self.channel_primary or "none",
            "status": self.status,
            "owner": {
                "id": self.owner_id.id,
                "name": self.owner_id.name,
                "initials": self._initials(self.owner_id.name),
            } if self.owner_id else False,
            "unread": self.unread_count,
            "urgency": self.urgency_score,
            "tier": self._urgency_tier(),
            "reason": self._reason_line(),
            "snippet": self._snippet(),
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else False,
        }

    def _reason_line(self):
        self.ensure_one()
        now = fields.Datetime.now()
        if self.next_booking_at and now <= self.next_booking_at <= now + timedelta(hours=24):
            hrs = max(1, int((self.next_booking_at - now).total_seconds() / 3600))
            return {"text": _("Booking in %sh") % hrs, "hot": True}
        if self.missed_call_unhandled:
            return {"text": _("Missed call — callback due"), "hot": True}
        if self.status == "needs_reply" and not self.owner_id and self.lead_id:
            return {"text": _("New lead · first message"), "hot": False}
        if self.status == "waiting":
            return {"text": _("Waiting on customer"), "hot": False}
        if self.status == "needs_reply":
            return {"text": _("Needs reply"), "hot": True}
        if self.status == "junk_suspect":
            return {"text": _("Marked as junk"), "hot": False}
        return {"text": _("Open"), "hot": False}

    def _snippet(self):
        self.ensure_one()
        if self.channel_primary == "call":
            return _("Missed call · rang recently") if self.missed_call_unhandled \
                else _("Call logged")
        if self.zalo_conversation_id:
            msg = self.env["zalo.message"].sudo().search(
                [("conversation_id", "=", self.zalo_conversation_id.id),
                 ("direction", "=", "incoming")],
                order="sent_date desc", limit=1,
            )
            if msg and msg.text:
                return msg.text[:120]
        if self.channel_primary == "email" and (self.lead_id or self.partner_id):
            model, rid = ("crm.lead", self.lead_id.id) if self.lead_id \
                else ("res.partner", self.partner_id.id)
            m = self.env["mail.message"].sudo().search(
                [("model", "=", model), ("res_id", "=", rid),
                 ("message_type", "=", "email")],
                order="date desc", limit=1,
            )
            if m:
                body = html2plaintext(m.body or "")
                return (m.subject or body or "")[:120]
        return ""

    # --- 6.2 conversation detail --------------------------------------
    @api.model
    def get_conversation_detail(self, conv_id):
        self._ensure_access()
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        return {
            "id": rec.id,
            "header": rec._detail_header(),
            "timeline": rec._detail_timeline(),
            "context": rec._detail_context(),
            "capabilities": {
                "can_reply_zalo": bool(rec.zalo_conversation_id),
                "can_reply_email": bool(rec._recipient_email()),
            },
            "channel_primary": rec.channel_primary or "none",
        }

    def _detail_header(self):
        self.ensure_one()
        row = self._workspace_row()
        relation = False
        # relation line via health.client.relation (representative → client)
        Rel = self.env["health.client.relation"].sudo()
        if self.partner_id:
            as_rep = Rel.search([("representative_id", "=", self.partner_id.id)], limit=1)
            if as_rep:
                role = dict(Rel._fields["role"].selection).get(as_rep.role, as_rep.role)
                relation = _("%(role)s of %(client)s") % {
                    "role": role, "client": as_rep.client_id.name,
                }
        return {
            "name": row["name"],
            "initials": row["initials"],
            "chips": row["chips"],
            "channel": row["channel"],
            "status": self.status,
            "owner": row["owner"],
            "relation": relation,
            "is_client": bool(self.partner_id and self.partner_id.is_patient),
            "has_lead": bool(self.lead_id),
            "phone": self.phone_normalized or (self.partner_id.phone if self.partner_id else False)
            or (self.lead_id.phone if self.lead_id else False) or False,
        }

    def _detail_timeline(self):
        """Read-time merge of channel events (§6.2). No storage, no clinical
        content — channel messages / calls / emails / booking lifecycle only."""
        self.ensure_one()
        events = []

        # Zalo messages (both directions)
        if self.zalo_conversation_id:
            for m in self.env["zalo.message"].sudo().search(
                [("conversation_id", "=", self.zalo_conversation_id.id)],
                order="sent_date asc",
            ):
                events.append({
                    "kind": "zalo",
                    "direction": "out" if m.direction == "outgoing" else "in",
                    "text": m.text or "[%s]" % (m.message_type or "message"),
                    "ts": m.sent_date.isoformat() if m.sent_date else False,
                    "delivery": m.state,
                })

        # VoIP calls (optional module — guard: voip is not installed on O19 yet)
        call_domain = []
        if self.partner_id:
            call_domain = [("partner_id", "=", self.partner_id.id)]
        elif self.lead_id:
            call_domain = [("lead_id", "=", self.lead_id.id)]
        elif self.phone_normalized:
            call_domain = [("caller_number_normalized", "=", self.phone_normalized)]
        if call_domain and "voip.call.log" in self.env:
            calls = self.env["voip.call.log"].sudo()
            for c in calls.search(call_domain, order="call_date asc", limit=100):
                events.append({
                    "kind": "call",
                    "direction": "out" if c.direction == "outgoing" else "in",
                    "call_type": c.call_type,
                    "duration": c.talk_duration_seconds or c.duration_seconds or 0,
                    "has_recording": c.has_recording,
                    "ts": c.call_date.isoformat() if c.call_date else False,
                })

        # Email cards (inbound emails + our posted replies) via mail.message
        model, rid = self._mail_target()
        if model:
            # comments are only real outbound replies (mt_comment) — internal
            # notes (mt_note) on the lead/partner must never render as a
            # message the customer received
            mt_comment_id = self.env.ref("mail.mt_comment").id
            for m in self.env["mail.message"].sudo().search(
                [("model", "=", model), ("res_id", "=", rid),
                 "|", ("message_type", "=", "email"),
                 "&", ("message_type", "=", "comment"),
                 ("subtype_id", "=", mt_comment_id)],
                order="date asc", limit=100,
            ):
                # direction rule (§4): email = inbound; comment authored by an
                # internal user = our outgoing reply
                is_out = bool(m.author_id and m.author_id.user_ids)
                if m.message_type == "email":
                    is_out = False
                events.append({
                    "kind": "email",
                    "direction": "out" if is_out else "in",
                    "subject": m.subject or "",
                    "text": html2plaintext(m.body or "")[:300],
                    "ts": m.date.isoformat() if m.date else False,
                })

        # health_messaging outbound rows (read-only, optional module) (§6.4)
        if "health.outbound_message" in self.env and self.partner_id:
            try:
                for om in self.env["health.outbound_message"].sudo().search(
                    [("partner_id", "=", self.partner_id.id)],
                    order="create_date asc", limit=50,
                ):
                    events.append({
                        "kind": "zns",
                        "direction": "out",
                        "text": getattr(om, "message_type", "") or _("Notification"),
                        "ts": om.create_date.isoformat() if om.create_date else False,
                    })
            except Exception:
                _logger.exception("care_command: outbound_message read failed")

        # FSO lifecycle within the timeline window
        if self.partner_id:
            for fso in self.env["health.fieldservice.order"].sudo().search(
                [("patient_id", "=", self.partner_id.id)],
                order="scheduled_datetime asc", limit=20,
            ):
                events.append({
                    "kind": "booking",
                    "state": fso.state,
                    "service": self._fso_service_label(fso),
                    "ts": (fso.scheduled_datetime.isoformat()
                           if fso.scheduled_datetime else
                           (fso.create_date.isoformat() if fso.create_date else False)),
                })

        # internal notes logged on THIS conversation (§7.5 Note)
        for m in self.env["mail.message"].sudo().search(
            [("model", "=", "care.conversation"), ("res_id", "=", self.id),
             ("message_type", "=", "comment")],
            order="date asc", limit=50,
        ):
            body = html2plaintext(m.body or "")
            if body:
                events.append({
                    "kind": "note",
                    "direction": "internal",
                    "text": body[:300],
                    "ts": m.date.isoformat() if m.date else False,
                })

        events = [e for e in events if e.get("ts")]
        events.sort(key=lambda e: e["ts"])
        return events[-100:]

    @staticmethod
    def _fso_service_label(fso):
        try:
            return fso._get_service_type_label() if hasattr(fso, "_get_service_type_label") \
                else (fso.service_type or "")
        except Exception:
            return fso.service_type or ""

    def _detail_context(self):
        self.ensure_one()
        ctx = {}
        p = self.partner_id
        if p:
            block = {"patient_code": p.patient_code or ""}
            age = getattr(p, "age", 0)
            if age:
                block["age"] = age
            area = p.named_area or (p.catchment_province_id.name if p.catchment_province_id else "")
            if area:
                block["area"] = area
            ctx["patient"] = block

            # relations
            Rel = self.env["health.client.relation"].sudo()
            rels = Rel.search(
                ["|", ("client_id", "=", p.id), ("representative_id", "=", p.id)],
                limit=10,
            )
            ctx["relations"] = [{
                "role": dict(Rel._fields["role"].selection).get(r.role, r.role),
                "client": r.client_id.name,
                "representative": r.representative_id.name,
                "is_primary": r.is_primary,
            } for r in rels]

            # bookings: next 1 + last 3 + lifetime count
            FSO = self.env["health.fieldservice.order"].sudo()
            now = fields.Datetime.now()
            nxt = FSO.search(
                [("patient_id", "=", p.id), ("state", "not in", ("cancelled", "closed")),
                 ("scheduled_datetime", ">=", now)],
                order="scheduled_datetime asc", limit=1,
            )
            last = FSO.search(
                [("patient_id", "=", p.id), ("scheduled_datetime", "<", now)],
                order="scheduled_datetime desc", limit=3,
            )
            ctx["bookings"] = {
                "next": self._fso_brief(nxt) if nxt else False,
                "recent": [self._fso_brief(f) for f in last],
                "lifetime": FSO.search_count([("patient_id", "=", p.id)]),
            }
        if self.lead_id:
            ctx["lead"] = {
                "contact_status": self.lead_id.contact_status or "",
                "code": getattr(self.lead_id, "unique_contact_code", "") or "",
            }
        return ctx

    def _fso_brief(self, fso):
        return {
            "service": self._fso_service_label(fso),
            "scheduled": fso.scheduled_datetime.isoformat() if fso.scheduled_datetime else False,
            "state": fso.state,
        }

    # ------------------------------------------------------------------
    # 6.3 Claim / ownership
    # ------------------------------------------------------------------
    @api.model
    def action_claim(self, conv_id):
        self._ensure_access()
        uid = self.env.user.id
        rec = self.sudo().search(
            self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            return {"claimed": False, "owner": False}
        # Airtight claim (review LOW-6): lock the row ONLY if it is still
        # unowned. `FOR UPDATE SKIP LOCKED` means a concurrent claimer that
        # already holds the lock makes us fall straight through to the
        # "already claimed" branch instead of blocking — one owner wins, the
        # loser gets a clean payload, no exception. Flush first so the raw
        # SELECT sees any pending in-transaction owner write (§5.9).
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT id FROM care_conversation "
            "WHERE id = %s AND owner_id IS NULL FOR UPDATE SKIP LOCKED",
            (rec.id,),
        )
        if not self.env.cr.fetchone():
            # lost the race, already owned, or locked — report the current owner
            rec.invalidate_recordset(["owner_id"])
            return {
                "claimed": False,
                "owner": {
                    "id": rec.owner_id.id, "name": rec.owner_id.name,
                    "initials": self._initials(rec.owner_id.name),
                } if rec.owner_id else False,
            }
        # won the lock — write via the ORM so chatter/tracking is preserved
        rec.write({"owner_id": uid, "claimed_at": fields.Datetime.now()})
        return {"claimed": True, "owner": {
            "id": uid, "name": self.env.user.name,
            "initials": self._initials(self.env.user.name)}}

    @api.model
    def action_release(self, conv_id):
        self._ensure_access()
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        if rec.owner_id.id != self.env.user.id and not self._is_manager():
            raise AccessError(_("Only the owner or a manager can release this conversation."))
        rec.write({"owner_id": False, "claimed_at": False})
        return {"released": True}

    @api.model
    def action_take_over(self, conv_id):
        self._ensure_access()
        if not self._is_manager():
            raise AccessError(_("Only a CRM manager can take over an owned conversation."))
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        rec.write({"owner_id": self.env.user.id, "claimed_at": fields.Datetime.now()})
        return {"claimed": True, "owner": {
            "id": self.env.user.id, "name": self.env.user.name,
            "initials": self._initials(self.env.user.name)}}

    @api.model
    def action_set_status(self, conv_id, status):
        self._ensure_access()
        if status not in ("needs_reply", "junk_suspect", "closed"):
            raise UserError(_("Unsupported status."))
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        rec.write({"status": status})
        if status == "junk_suspect" and rec.lead_id:
            # reuse the CRM spam path (crm_lead.py:1933)
            rec.lead_id.sudo().action_mark_spam()
        return {"status": status}

    # ------------------------------------------------------------------
    # 6.4 Outbound replies
    # ------------------------------------------------------------------
    @api.model
    def action_send_zalo(self, conv_id, text):
        self._ensure_access()
        text = (text or "").strip()
        if not text:
            raise UserError(_("Message is empty."))
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec or not rec.zalo_conversation_id:
            raise UserError(_("This conversation has no Zalo channel."))
        msg = self.env["zalo.message"].sudo().create({
            "conversation_id": rec.zalo_conversation_id.id,
            "direction": "outgoing",
            "message_type": "text",
            "text": text,
            "state": "draft",
        })
        # existing send path (zalo_message.py:152); errors propagate to the UI
        msg.action_send_message()
        rec.write({"status": "waiting", "unread_count": 0,
                   "last_event_at": fields.Datetime.now()})
        return {
            "kind": "zalo", "direction": "out", "text": text,
            "ts": (msg.sent_date or fields.Datetime.now()).isoformat(),
            "delivery": msg.state,
        }

    def _mail_target(self):
        """(model, res_id) that carries the email thread — lead first."""
        self.ensure_one()
        if self.lead_id:
            return "crm.lead", self.lead_id.id
        if self.partner_id:
            return "res.partner", self.partner_id.id
        return False, False

    def _recipient_email(self):
        self.ensure_one()
        if self.lead_id and self.lead_id.email_from:
            return self.lead_id.email_from.strip()
        if self.partner_id and self.partner_id.email:
            return self.partner_id.email.strip()
        if self.email_normalized:
            return self.email_normalized
        return False

    @api.model
    def action_send_email(self, conv_id, text):
        self._ensure_access()
        text = (text or "").strip()
        if not text:
            raise UserError(_("Message is empty."))
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        model, rid = rec._mail_target()
        recipient = rec._recipient_email()
        if not model or not recipient:
            raise UserError(_("This conversation has no email recipient."))
        record = self.env[model].sudo().browse(rid)
        # Ensure a recipient partner exists so Odoo actually sends the email —
        # and that its address IS the one the guard validated (an anchored
        # partner whose email differs from the lead's must not silently win).
        partner = rec.partner_id
        if partner and (partner.email or "").strip().lower() != recipient.lower():
            partner = partner.browse()
        if not partner:
            partner = self.env["res.partner"].sudo().search(
                [("email", "=ilike", recipient)], limit=1)
        if not partner:
            partner = self.env["res.partner"].sudo().create({
                "name": recipient, "email": recipient,
            })
        body = Markup("<p>%s</p>") % text  # escape user text; keep <p> raw
        # message_post raises verbatim if no outgoing mail server — do not swallow
        record.message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=[partner.id],
        )
        rec.write({"status": "waiting", "unread_count": 0,
                   "last_event_at": fields.Datetime.now()})
        return {
            "kind": "email", "direction": "out", "subject": "",
            "text": text, "ts": fields.Datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # 7.5 Header action strip — thin passthroughs to existing CRM flows.
    # Each is group-gated; the ones that return an action dict are run by
    # the client via doAction(). No behaviour is duplicated — we reuse the
    # verified crm.lead / ops_quick_booking seams (§4).
    # ------------------------------------------------------------------
    def _guarded(self, conv_id):
        self._ensure_access()
        rec = self.sudo().search(self._company_domain() + [("id", "=", conv_id)], limit=1)
        if not rec:
            raise UserError(_("Conversation not found."))
        return rec

    @api.model
    def action_book(self, conv_id):
        rec = self._guarded(conv_id)
        if rec.lead_id:
            return rec.lead_id.sudo().action_convert_to_booking()  # crm_lead.py:1701
        if rec.partner_id and rec.partner_id.is_patient:
            return {
                "type": "ir.actions.client",
                "tag": "ops_quick_booking",
                "name": _("Quick Booking"),
                "target": "current",
                "context": {"active_id": rec.partner_id.id,
                            "default_patient_id": rec.partner_id.id,
                            "active_center": "crm_center"},
            }
        raise UserError(_("No client or lead on this conversation to book."))

    @api.model
    def action_open_client(self, conv_id):
        """Promote a non-client anchor: open the booking flow, which
        de-dups/creates the res.partner client on save."""
        rec = self._guarded(conv_id)
        ctx = {"active_center": "crm_center"}
        if rec.lead_id:
            ctx["default_lead_id"] = rec.lead_id.id
        return {
            "type": "ir.actions.client",
            "tag": "ops_quick_booking",
            "name": _("New Client"),
            "target": "current",
            "context": ctx,
        }

    @api.model
    def action_callback(self, conv_id):
        rec = self._guarded(conv_id)
        target = rec.lead_id or rec.partner_id
        if not target:
            raise UserError(_("No lead or contact to schedule a callback on."))
        today = fields.Date.context_today(self.env.user)
        try:
            target.sudo().activity_schedule(
                "mail.mail_activity_data_call",
                date_deadline=today,
                summary=_("Callback — Care Command"),
                user_id=self.env.user.id,
            )
        except Exception:
            # fall back to a generic activity type if the call type is absent
            target.sudo().activity_schedule(
                date_deadline=today, summary=_("Callback — Care Command"),
                user_id=self.env.user.id)
        return {"ok": True, "message": _("Callback scheduled for today.")}

    @api.model
    def action_add_note(self, conv_id, text):
        rec = self._guarded(conv_id)
        text = (text or "").strip()
        if not text:
            raise UserError(_("The note is empty."))
        rec.message_post(body=Markup("<p>%s</p>") % text,
                         message_type="comment", subtype_xmlid="mail.mt_note")
        return {"ok": True, "message": _("Internal note logged.")}

    @api.model
    def action_log(self, conv_id):
        rec = self._guarded(conv_id)
        if not rec.lead_id:
            raise UserError(_("Only a lead-anchored conversation can be logged."))
        return rec.lead_id.sudo().action_log_as_lead()  # crm_lead.py:1966

    @api.model
    def action_create_lead(self, conv_id):
        rec = self._guarded(conv_id)
        if rec.lead_id:
            raise UserError(_("This conversation already has a lead."))
        vals = {"name": rec.display_name_c or _("Care Command lead"),
                "contact_status": "lead"}
        if rec.phone_normalized:
            vals["phone"] = rec.phone_normalized
        if rec.email_normalized:
            vals["email_from"] = rec.email_normalized
        if rec.partner_id:
            vals["partner_id"] = rec.partner_id.id
        lead = self.env["crm.lead"].sudo().create(vals)
        rec.write({"lead_id": lead.id})
        return {"ok": True, "message": _("Lead created and linked.")}

    @api.model
    def action_escalate(self, conv_id):
        rec = self._guarded(conv_id)
        if not rec.lead_id:
            raise UserError(_("Escalation needs a lead anchor."))
        return rec.lead_id.sudo().action_escalate_contact()  # crm_lead.py:2137
