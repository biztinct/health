# -*- coding: utf-8 -*-
"""Care Command AI Assist tests (handover §7, T33-T38).

TransactionCase only (no HttpCase → --no-http stays). EVERY test mocks
``bi.ai.provider._complete`` — no real model call ever leaves the box. Assertions
key on codes/ids/enum values, never display strings (ledger §5.32/§5.50).

Gate matrix, redaction, side-effect-freedom of a draft, the audit row, access
control and the failure path are all proven here; the browser evidence (AI off
== Phase 3, and the on-state affordances) is the reviewer's selective pass.
"""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCareCommandAi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Care = env["care.conversation"]
        cls.AI = env["care.ai.assist"]
        cls.company = env.company
        cls.company2 = env["res.company"].create({"name": "CCAI Other Co"})

        cls.province = env["health.catchment.province"].create({"name": "CCAI Prov"})
        cls.facility = env["health.facility"].create({
            "name": "CCAI Facility", "code": "CCAIFAC", "street": "1 St",
            "city": "Hà Nội", "catchment_province_id": cls.province.id})
        cls.patient = env["res.partner"].create({
            "name": "Nguyễn Văn Redact", "is_patient": True,
            "phone": "0901234567", "email": "redact@example.com",
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})

        cls.crm_user = cls._mk_user("ccai_u", ["health_crm.group_health_crm_user"])
        cls.plain_user = cls._mk_user("ccai_plain", [])

        # default test user is superuser (not a real CRM group member) — grant.
        env.user.sudo().write({
            "group_ids": [(4, env.ref("health_crm.group_health_crm_manager").id)]})

        cls.conv = cls.Care._find_or_create_for(
            {"partner_id": cls.patient.id, "phone_normalized": "0901234567",
             "email_normalized": "redact@example.com"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})

    @classmethod
    def _mk_user(cls, login, group_xmlids):
        env = cls.env
        gids = [env.ref("base.group_user").id]
        for x in group_xmlids:
            gids.append(env.ref(x).id)
        return env["res.users"].create({
            "name": login, "login": login,
            "group_ids": [(6, 0, gids)],
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
            "catchment_province_id": cls.province.id,
        })

    # -- helpers -------------------------------------------------------
    def _mk_provider(self, provider="ollama", with_key=False):
        vals = {
            "name": "CCAI %s" % provider,
            "provider": provider,
            "endpoint": "http://localhost:11434/api/chat",
            "model_name": "qwen2.5",
        }
        if with_key:
            vals["api_key_input"] = "sk-test-key-not-real"
        return self.env["bi.ai.provider"].create(vals)

    def _enable(self, provider, allow_cloud=False, drafts=True, brief=True):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("health_care_command_ai.provider_id", str(provider.id))
        icp.set_param("health_care_command_ai.enabled", "True")
        icp.set_param("health_care_command_ai.allow_cloud",
                      "True" if allow_cloud else "False")
        icp.set_param("health_care_command_ai.drafts",
                      "True" if drafts else "False")
        icp.set_param("health_care_command_ai.brief",
                      "True" if brief else "False")

    # ======================================================================
    # T33 — the runtime gate (master / cloud-refusal / ollama)
    # ======================================================================
    def test_33_gate(self):
        # master OFF (params absent) → disabled + a draft is refused
        self.assertFalse(self.AI.ai_flags()["enabled"])
        with self.assertRaises(UserError):
            self.AI.ai_draft_reply(self.conv.id)

        # master ON + a usable CLOUD provider + allow_cloud OFF → refused
        cloud = self._mk_provider("anthropic", with_key=True)
        self.assertTrue(cloud._is_usable(), "cloud provider with a key is usable")
        self._enable(cloud, allow_cloud=False)
        self.assertFalse(self.AI.ai_flags()["enabled"],
                         "a cloud provider is refused unless cloud is allowed")
        with self.assertRaises(UserError):
            self.AI.ai_draft_reply(self.conv.id)

        # same cloud provider + allow_cloud ON → enabled
        self._enable(cloud, allow_cloud=True)
        self.assertTrue(self.AI.ai_flags()["enabled"])

        # an OLLAMA provider → enabled regardless of allow_cloud
        ollama = self._mk_provider("ollama")
        self._enable(ollama, allow_cloud=False)
        flags = self.AI.ai_flags()
        self.assertTrue(flags["enabled"])
        self.assertEqual(flags["provider_name"], ollama.name)
        self.assertTrue(flags["drafts"] and flags["brief"])

    # ======================================================================
    # T34 — a draft has ZERO side effects beyond the audit log
    # ======================================================================
    def test_34_draft_no_side_effects(self):
        ollama = self._mk_provider("ollama")
        self._enable(ollama)
        Msg = self.env["mail.message"]
        Zalo = self.env["zalo.message"]
        before = (self.conv.status, self.conv.unread_count)
        n_msg, n_zalo = Msg.search_count([]), Zalo.search_count([])

        with patch.object(type(ollama), "_complete",
                          return_value="Chào anh/chị, cảm ơn đã liên hệ.") as mock:
            res = self.AI.ai_draft_reply(self.conv.id)

        self.assertTrue(res["text"], "the draft text is returned")
        self.assertEqual(mock.call_count, 1)
        # force_json must be False for prose (handover §2)
        _sys, _user = mock.call_args.args[0], mock.call_args.args[1]
        self.assertFalse(mock.call_args.kwargs.get("force_json", False))
        self.assertEqual(Msg.search_count([]), n_msg,
                         "a draft posts NO mail.message")
        self.assertEqual(Zalo.search_count([]), n_zalo,
                         "a draft creates NO zalo.message")
        self.conv.invalidate_recordset()
        self.assertEqual((self.conv.status, self.conv.unread_count), before,
                         "a draft changes neither status nor unread")

    # ======================================================================
    # T35 — redaction: partner name/phone/email never reach the prompt
    # ======================================================================
    def test_35_redaction(self):
        ollama = self._mk_provider("ollama")
        self._enable(ollama)
        name, phone, email = "Nguyễn Văn Redact", "0901234567", "redact@example.com"
        # seed the PII into the timeline via a note on the conversation
        self.conv.message_post(
            body="Khách %s, SĐT %s, email %s hỏi lịch hẹn." % (name, phone, email),
            message_type="comment", subtype_xmlid="mail.mt_comment")

        captured = {}

        def fake(provider, system, user_message, force_json=True):
            captured["user"] = user_message
            return "ok"

        with patch.object(type(ollama), "_complete", fake):
            self.AI.ai_draft_reply(self.conv.id)

        user = captured["user"]
        self.assertIn("[BN]", user)
        self.assertIn("[SĐT]", user)
        self.assertIn("[EMAIL]", user)
        self.assertNotIn(phone, user, "raw phone must be redacted")
        self.assertNotIn(email, user, "raw email must be redacted")
        self.assertNotIn(name, user, "raw name must be redacted")

        # -- lead-anchored conversation: contact_name/partner_name carry the
        # person's identity (crm.lead.name is just the required TITLE) — every
        # name field must be redacted independently, not first-truthy
        lead = self.env["crm.lead"].create({
            "name": "Website inquiry #77",
            "contact_name": "Trần Thị LeadRedact",
            "partner_name": "Công ty LeadRedactCo",
            "phone": "0907654321",
        })
        lconv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        if not lconv:
            lconv = self.Care._find_or_create_for(
                {"lead_id": lead.id, "phone_normalized": "0907654321"},
                {"inbound": True, "set_status": "needs_reply",
                 "event_at": fields.Datetime.now()})
        lconv.message_post(
            body="Chị Trần Thị LeadRedact của Công ty LeadRedactCo hỏi giá.",
            message_type="comment", subtype_xmlid="mail.mt_comment")
        with patch.object(type(ollama), "_complete", fake):
            self.AI.ai_draft_reply(lconv.id)
        luser = captured["user"]
        self.assertNotIn("LeadRedact", luser,
                         "lead contact_name must be redacted")
        self.assertNotIn("LeadRedactCo", luser,
                         "lead partner_name must be redacted")
        self.assertIn("[BN]", luser)

    # ======================================================================
    # T36 — brief returns bullets; ONE audit row with capability + provider
    # ======================================================================
    def test_36_brief_audit(self):
        ollama = self._mk_provider("ollama")
        self._enable(ollama)
        Audit = self.env["bi.audit.log"].sudo()
        n = Audit.search_count([("event", "=", "ai_request")])

        with patch.object(type(ollama), "_complete",
                          return_value="- muốn đặt lịch\n- ở Hà Nội\n- gọi lại chiều nay"):
            res = self.AI.ai_brief(self.conv.id)

        self.assertEqual(res["bullets"],
                         ["muốn đặt lịch", "ở Hà Nội", "gọi lại chiều nay"])
        self.assertTrue(res["stamp"])
        self.assertEqual(Audit.search_count([("event", "=", "ai_request")]), n + 1)
        row = Audit.search([("event", "=", "ai_request")], order="id desc", limit=1)
        payload = row.payload_json or {}
        self.assertEqual(payload.get("capability"), "brief")
        self.assertEqual(payload.get("provider"), ollama.name)
        self.assertEqual(payload.get("conv_id"), self.conv.id)
        self.assertIn("duration_ms", payload)
        # no content in the audit payload beyond the (absent) redacted string
        self.assertNotIn("context", payload)
        self.assertNotIn("text", payload)
        self.assertNotIn("prompt", payload)

    # ======================================================================
    # T37 — access: non-CRM user refused; cross-company id not reachable
    # ======================================================================
    def test_37_access(self):
        ollama = self._mk_provider("ollama")
        self._enable(ollama)
        AIu = self.AI.with_user(self.plain_user)
        with self.assertRaises(AccessError):
            AIu.ai_flags()
        with self.assertRaises(AccessError):
            AIu.ai_draft_reply(self.conv.id)
        with self.assertRaises(AccessError):
            AIu.ai_brief(self.conv.id)

        # a company-2 conversation is invisible to a company-1 CRM user
        other = self.Care.sudo().create({
            "phone_normalized": "0912349999", "company_id": self.company2.id,
            "status": "needs_reply"})
        with self.assertRaises(UserError):
            self.AI.with_user(self.crm_user).ai_draft_reply(other.id)

    # ======================================================================
    # T38 — a provider failure surfaces a clean UserError, no partial audit
    # ======================================================================
    def test_38_failure_clean(self):
        ollama = self._mk_provider("ollama")
        self._enable(ollama)
        Audit = self.env["bi.audit.log"].sudo()
        n = Audit.search_count([("event", "=", "ai_request")])

        with patch.object(type(ollama), "_complete",
                          side_effect=RuntimeError("model down")):
            with self.assertRaises(UserError):
                self.AI.ai_draft_reply(self.conv.id)

        self.assertEqual(Audit.search_count([("event", "=", "ai_request")]), n,
                         "a failed call writes NO audit row claiming success")
