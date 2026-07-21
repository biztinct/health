# -*- coding: utf-8 -*-
"""``care.ai.assist`` — the OPTIONAL AI layer over Care Command.

Philosophy (handover §1, binding): AI is a *configuration, not a feature of the
core*. This module lives entirely OUTSIDE ``health_care_command`` — it composes
from the core's public service seams (``_ensure_access`` / ``_guarded`` /
``_detail_timeline``) and NEVER edits it. Everything here is:

- **OFF until a manager turns it on** (``care_ai_enabled`` default False),
- **Ollama-first** — a cloud provider is refused unless ``care_ai_allow_cloud``
  is explicitly on (the health_ai_coding cloud-refusal gate, cloned),
- **redacted** — the partner's AND lead's name/phone/email are stripped from
  every timeline text before it reaches the model (the ai_coding ``_redact``,
  generalised to two identity sources); the SAME redacted string is what we log,
- **never a send path** — every output lands in the editable composer or a
  labeled card; the only send remains the existing human one.

No clinical content ever enters a prompt: the context is the care_command
timeline (non-clinical by design) + status/booking facts only.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# System prompts (VN-first, plain) — handover §5.1. Fixed; never tuned from UI.
_DRAFT_SYSTEM = (
    "Bạn soạn một câu trả lời tiếng Việt ngắn gọn, lịch sự cho nhân viên "
    "chăm sóc/bán hàng của một dịch vụ chăm sóc tại nhà. Chỉ dùng các dữ kiện "
    "hội thoại được cung cấp. Nếu thiếu thông tin, hãy hỏi MỘT câu làm rõ. "
    "Không bịa giá, thời gian hay lời khuyên y tế. Chỉ xuất ra nội dung câu "
    "trả lời.\n"
    "You draft a short, polite Vietnamese reply for a home-care service's "
    "sales/care agent. Use only the provided conversation facts. If information "
    "is missing, ask one clarifying question. Never invent prices, times, or "
    "medical advice. Output the reply text only."
)
_BRIEF_SYSTEM = (
    "Tóm tắt hội thoại này cho một nhân viên tiếp nhận. Viết 3-5 gạch đầu dòng "
    "tiếng Việt ngắn: ai (chỉ vai trò, tên đã được ẩn), họ muốn gì, tình trạng "
    "hiện tại, việc cần làm tiếp theo. Chỉ nêu dữ kiện.\n"
    "Summarize this conversation for an agent taking over. 3-5 short Vietnamese "
    "bullets: who (role only, names are redacted), what they want, current "
    "state, what to do next. Facts only."
)

_MAX_CONTEXT_CHARS = 4000
_MAX_TIMELINE_EVENTS = 15
_TAG = {"out": "OUT", "in": "IN", "internal": "NOTE"}


class CareAiAssist(models.AbstractModel):
    """Stateless service layer. No table, no ACL of its own — every entry point
    borrows the core's group gate + company scope, so a non-CRM user or a
    cross-company id is refused exactly as it is in Care Command itself."""
    _name = "care.ai.assist"
    _description = "Care Command AI Assist"

    # ------------------------------------------------------------------
    # Config (read params DIRECTLY — ir.config_parameter ormcache is
    # per-worker, §5.48; never cache).
    # ------------------------------------------------------------------
    @api.model
    def _cfg(self, key):
        return self.env["ir.config_parameter"].sudo().get_param(
            "health_care_command_ai.%s" % key)

    @api.model
    def _cfg_bool(self, key, default=False):
        raw = self._cfg(key)
        if raw is None or raw is False or raw == "":
            return default
        return str(raw).lower() in ("1", "true", "yes")

    @api.model
    def _provider(self):
        """The configured bi.ai.provider, or an empty recordset."""
        raw = self._cfg("provider_id")
        if raw:
            try:
                provider = self.env["bi.ai.provider"].browse(int(raw)).exists()
                if provider:
                    return provider
            except (TypeError, ValueError):
                pass
        return self.env["bi.ai.provider"]

    @api.model
    def _gate(self):
        """The runtime gate (handover §5.2), used by every service AND ai_flags.

        Returns ``(enabled, provider)``: enabled = master on AND a provider
        exists AND it is usable AND (it is Ollama OR cloud is allowed)."""
        if not self._cfg_bool("enabled"):
            return False, self.env["bi.ai.provider"]
        provider = self._provider()
        if not provider or not provider._is_usable():
            return False, provider
        if provider.provider != "ollama" and not self._cfg_bool("allow_cloud"):
            _logger.info(
                "care_ai: provider %s is not Ollama and allow_cloud is off — "
                "refusing to call a cloud model.", provider.name)
            return False, provider
        return True, provider

    # ------------------------------------------------------------------
    # Public services (group-gated + company-scoped via the CORE seams)
    # ------------------------------------------------------------------
    @api.model
    def ai_flags(self):
        """{enabled, drafts, brief, provider_name} — drives ALL AI DOM. With the
        master off (or the module's gate failing) every flag is False, so the
        OWL patch renders zero AI affordances (AI OFF == Phase 3 exactly)."""
        self.env["care.conversation"]._ensure_access()
        enabled, provider = self._gate()
        return {
            "enabled": enabled,
            "drafts": enabled and self._cfg_bool("drafts", default=True),
            "brief": enabled and self._cfg_bool("brief", default=True),
            "provider_name": provider.name if provider else "",
        }

    @api.model
    def ai_draft_reply(self, conv_id):
        """Return ``{text}`` — a suggested reply for the composer. NEVER sends,
        NEVER posts: the only writes on this path are the audit log row."""
        rec = self.env["care.conversation"]._guarded(conv_id)  # gate + scope
        enabled, provider = self._gate()
        if not enabled or not self._cfg_bool("drafts", default=True):
            raise UserError(_("AI drafting is not enabled."))
        prompt = self._ai_context(rec)
        text = self._complete(provider, "draft", rec, _DRAFT_SYSTEM, prompt)
        return {"text": (text or "").strip()}

    @api.model
    def ai_brief(self, conv_id):
        """Return ``{bullets, stamp}`` — a 3-5 bullet takeover summary. On-demand
        only (cost + surprise control); never automatic."""
        rec = self.env["care.conversation"]._guarded(conv_id)
        enabled, provider = self._gate()
        if not enabled or not self._cfg_bool("brief", default=True):
            raise UserError(_("AI briefing is not enabled."))
        prompt = self._ai_context(rec)
        text = self._complete(provider, "brief", rec, _BRIEF_SYSTEM, prompt)
        return {
            "bullets": self._to_bullets(text),
            "stamp": _("Generated just now by %s", provider.name),
        }

    # ------------------------------------------------------------------
    # Completion + audit (the ONE place _complete is called)
    # ------------------------------------------------------------------
    def _complete(self, provider, capability, rec, system, prompt):
        """Call the provider, audit the call, surface a clean UserError on any
        failure. An AI failure must NEVER block manual work (handover §4).

        NB: the redacted-prompt local is named ``prompt``, NOT ``context`` —
        Odoo's ``_()`` sniffs the caller frame for a local named ``context``
        expecting a context *dict* to read ``lang`` off; a plain string there
        raises ``AttributeError: 'str' object has no attribute 'get'`` (§5.60)."""
        started = fields.Datetime.now()
        try:
            raw = provider._complete(system, prompt, force_json=False)
        except Exception as exc:  # noqa: BLE001 — any provider error → clean msg
            _logger.warning("care_ai %s failed (conv %s): %s",
                            capability, rec.id, exc)
            # No partial audit row that claims success (handover T38).
            raise UserError(_("AI is unavailable — continue manually."))
        duration = int((fields.Datetime.now() - started).total_seconds() * 1000)
        # Audit: capability + conv + provider + duration only. NEVER any content
        # (the redacted context is not persisted here — no content beyond the
        # redacted string rule, and we keep even that out of the audit row).
        self.env["bi.audit.log"].sudo().log(
            "ai_request", record=rec,
            payload={"capability": capability, "conv_id": rec.id,
                     "provider": provider.name, "duration_ms": duration})
        return raw

    @staticmethod
    def _to_bullets(text):
        """Split the model's plain-text answer into clean bullet strings."""
        bullets = []
        for line in (text or "").splitlines():
            line = line.strip()
            # strip a leading bullet/number marker
            line = re.sub(r"^[\-\*•–—\d\.\)\s]+", "", line).strip()
            if line:
                bullets.append(line)
        return bullets[:5]

    # ------------------------------------------------------------------
    # Redacted, non-clinical context builder (handover §5.3)
    # ------------------------------------------------------------------
    def _ai_context(self, rec):
        """Last ~15 timeline events → IN/OUT/NOTE lines + status/channel/booking
        facts, then redacted. No ids, no phone/email, no raw HTML."""
        timeline = rec.sudo()._detail_timeline()[-_MAX_TIMELINE_EVENTS:]
        lines = []
        for e in timeline:
            kind = e.get("kind") or ""
            if kind == "booking":
                body = "%s (%s)" % (e.get("service") or "booking",
                                    e.get("state") or "")
            elif kind == "call":
                body = "call %s" % (e.get("call_type") or "")
            else:
                body = e.get("text") or e.get("subject") or ""
            if not body:
                continue
            tag = _TAG.get(e.get("direction"), kind.upper() or "EVENT")
            lines.append("%s: %s" % (tag, body))

        facts = ["Channel: %s" % (rec.channel_primary or "unknown"),
                 "Status: %s" % (rec.status or "")]
        if rec.next_booking_at:
            facts.append("Next booking: %s"
                         % fields.Date.to_string(rec.next_booking_at.date()))
        stage = getattr(rec.lead_id, "stage_id", False) if rec.lead_id else False
        if stage:
            facts.append("Lead stage: %s" % stage.name)

        prompt = "HỘI THOẠI / CONVERSATION:\n%s\n\nDỮ KIỆN / FACTS:\n%s" % (
            "\n".join(lines) or "(no messages yet)", "\n".join(facts))
        prompt = self._redact(prompt, rec)
        if len(prompt) > _MAX_CONTEXT_CHARS:
            prompt = prompt[:_MAX_CONTEXT_CHARS]
        return prompt

    @api.model
    def _redact(self, text, rec):
        """Pseudonymise: strip BOTH the partner's and the lead's identity values
        (name/phone/mobile/email) + the conversation's own normalized phone/email
        from the text; collapse whitespace. The ai_coding ``_redact`` shape,
        generalised to two identity sources. Longest values first so a name
        inside another value is not half-replaced."""
        if not text:
            return ""
        result = text
        pairs = []
        names = []

        def add(val, token):
            v = (val or "")
            v = v.strip() if isinstance(v, str) else ""
            if v and len(v) >= 2:
                pairs.append((v, token))

        for src in (rec.partner_id, rec.lead_id):
            if not src:
                continue
            add(getattr(src, "email", None) or getattr(src, "email_from", None),
                "[EMAIL]")
            for pf in ("phone", "mobile"):
                add(getattr(src, pf, None), "[SĐT]")
            nm = (getattr(src, "name", None) or getattr(src, "contact_name", None)
                  or getattr(src, "partner_name", None))
            add(nm, "[BN]")
            if nm:
                names.append(nm)
        add(rec.email_normalized, "[EMAIL]")
        add(rec.phone_normalized, "[SĐT]")

        pairs.sort(key=lambda kv: len(kv[0]), reverse=True)
        for needle, token in pairs:
            result = re.sub(re.escape(needle), token, result, flags=re.IGNORECASE)
        # each name token >= 3 chars, to catch partial mentions
        for nm in names:
            for tok in re.split(r"\s+", nm.strip()):
                if len(tok) >= 3:
                    result = re.sub(r"\b%s\b" % re.escape(tok), "[BN]",
                                    result, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", result).strip()
