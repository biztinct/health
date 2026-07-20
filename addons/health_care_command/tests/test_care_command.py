# -*- coding: utf-8 -*-
"""Care Command Phase 1 tests (handover §9, T1–T17).

TransactionCase only (no HttpCase → --no-http stays). Assertions key on
codes/ids/enum values, never display strings (ledger §5.32/§5.50).
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_care_command.hooks import post_init_hook


@tagged("post_install", "-at_install")
class TestCareCommand(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Care = env["care.conversation"]
        cls.company = env.company
        cls.company2 = env["res.company"].create({"name": "CC Other Co"})

        cls.province = env["health.catchment.province"].create({"name": "CC Prov"})
        cls.facility = env["health.facility"].create({
            "name": "CC Facility", "code": "CCFAC", "street": "1 St",
            "city": "Hà Nội", "catchment_province_id": cls.province.id})
        cls.patient = env["res.partner"].create({
            "name": "Nguyễn Văn Care", "is_patient": True,
            "patient_code": "KH-CC01",
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})
        cls.patientB = env["res.partner"].create({
            "name": "Trần Thị B", "is_patient": True,
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})

        # Reuse the live active Zalo config if one exists (vietuat has one and
        # only ONE active config per company is allowed); else create an
        # inactive fixture config so conversations/messages can be seeded.
        cls.zconfig = env["zalo.config"].get_active_config() or env["zalo.config"].create({
            "name": "CC Zalo", "app_id": "app1", "app_secret": "s",
            "oa_id": "oa1", "active": False})
        # health_voip24h is optional and does NOT install on Odoo 19, so the
        # voip.call.log model is absent on vietuat — gate every voip fixture.
        cls.has_voip = "voip.call.log" in env
        cls.vconfig = env["voip.config"].create({
            "name": "CC VoIP", "api_key": "k", "api_secret": "s",
            "account_id": "acc1"}) if cls.has_voip else False

        cls.crm_user = cls._mk_user("cc_crm_u", ["health_crm.group_health_crm_user"])
        cls.crm_user2 = cls._mk_user("cc_crm_u2", ["health_crm.group_health_crm_user"])
        cls.crm_mgr = cls._mk_user("cc_crm_mgr", ["health_crm.group_health_crm_manager"])
        cls.plain_user = cls._mk_user("cc_plain", [])

        # The default test user is the superuser, which is NOT a member of the
        # CRM group (has_group checks real membership, not su) — grant it so the
        # service-method tests that run in the default env pass the gate.
        env.user.sudo().write({
            "group_ids": [(4, env.ref("health_crm.group_health_crm_manager").id)]})

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
    def _zalo_conv(self, phone=False, partner=False, name="Zalo User"):
        return self.env["zalo.conversation"].create({
            "zalo_user_id": "zu_%s" % (phone or name),
            "zalo_user_name": name,
            "zalo_phone_number": phone or False,
            "partner_id": partner.id if partner else False,
            "config_id": self.zconfig.id,
            "unread_count": 0,
        })

    def _zalo_msg(self, conv, direction="incoming", text="hi"):
        return self.env["zalo.message"].create({
            "conversation_id": conv.id, "direction": direction,
            "message_type": "text", "text": text,
            "sent_date": fields.Datetime.now(),
            "state": "sent" if direction == "outgoing" else "delivered"})

    def _call(self, phone, call_type="missed", direction="incoming", partner=False):
        return self.env["voip.call.log"].create({
            "call_id": "call_%s_%s" % (phone, call_type),
            "voip_config_id": self.vconfig.id,
            "direction": direction, "call_type": call_type,
            "caller_number": phone,
            "call_date": fields.Datetime.now(),
            "partner_id": partner.id if partner else False,
            "talk_duration_seconds": 0 if call_type == "missed" else 30})

    def _fso(self, patient, when):
        return self.env["health.fieldservice.order"].create({
            "patient_id": patient.id, "facility_id": self.facility.id,
            "scheduled_datetime": when})

    def _convs_for_zalo(self, zconv):
        return self.Care.search([("zalo_conversation_id", "=", zconv.id)])

    # ======================================================================
    # T1 — upsert idempotency
    # ======================================================================
    def test_01_upsert_idempotency(self):
        zc = self._zalo_conv(name="idem")
        self._zalo_msg(zc)  # hook creates the conversation
        convs = self._convs_for_zalo(zc)
        self.assertEqual(len(convs), 1)
        unread0 = convs.unread_count
        # fire the SAME logical inbound event again → SET semantics, no double bump
        self.Care._find_or_create_for(
            {"zalo_conversation_id": zc.id},
            {"channel": "zalo", "inbound": True,
             "event_at": fields.Datetime.now(), "set_status": "needs_reply",
             "unread": max(1, zc.unread_count or 0)})
        convs = self._convs_for_zalo(zc)
        self.assertEqual(len(convs), 1, "no duplicate conversation on replay")
        self.assertEqual(convs.unread_count, unread0, "no double unread bump")

    # ======================================================================
    # T2 — anchor precedence (fill zalo anchor, keep partner)
    # ======================================================================
    def test_02_anchor_precedence(self):
        phone = "0912345602"
        conv = self.Care._find_or_create_for(
            {"phone_normalized": phone, "partner_id": self.patient.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        zc = self._zalo_conv(phone=phone, partner=self.patient, name="prec")
        self._zalo_msg(zc)  # anchor: zalo_conv + partner + phone
        # matched the phone conversation, filled the zalo anchor
        same = self.Care.search([("phone_normalized", "=", phone)])
        self.assertEqual(len(same), 1)
        self.assertEqual(same.id, conv.id)
        self.assertEqual(same.zalo_conversation_id.id, zc.id)
        self.assertEqual(same.partner_id.id, self.patient.id)

    # ======================================================================
    # T3 — partner fill-not-overwrite on conflict
    # ======================================================================
    def test_03_partner_not_overwritten(self):
        phone = "0912345603"
        conv = self.Care._find_or_create_for(
            {"phone_normalized": phone, "partner_id": self.patient.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        # a later signal claims a DIFFERENT partner for the same phone
        self.Care._find_or_create_for(
            {"phone_normalized": phone, "partner_id": self.patientB.id},
            {"channel": "call", "inbound": True,
             "event_at": fields.Datetime.now()})
        conv.invalidate_recordset()
        self.assertEqual(conv.partner_id.id, self.patient.id,
                         "existing partner is never overwritten")

    # ======================================================================
    # T4 — status machine
    # ======================================================================
    def test_04_status_machine(self):
        zc = self._zalo_conv(name="statemach")
        self._zalo_msg(zc, direction="incoming")
        conv = self._convs_for_zalo(zc)
        self.assertEqual(conv.status, "needs_reply")
        self.assertGreater(conv.unread_count, 0)
        # outgoing send → waiting + unread 0. NB: the real send path
        # (zalo.message.action_send_message) references self.env['zalo.api.client'],
        # which is NOT a registered model on this codebase (plain ZaloAPIClient
        # class) — it KeyErrors, so we mock the send method itself.
        with patch.object(type(self.env["zalo.message"]),
                          "action_send_message", return_value=None):
            self.Care.action_send_zalo(conv.id, "reply")
        conv.invalidate_recordset()
        self.assertEqual(conv.status, "waiting")
        self.assertEqual(conv.unread_count, 0)
        # missed call → needs_reply (only when voip is installed)
        if self.has_voip:
            self._call("0912345640", call_type="missed")
            mc = self.Care.search([("phone_normalized", "=", "0912345640")])
            self.assertEqual(mc.status, "needs_reply")
            self.assertTrue(mc.missed_call_unhandled)

    # ======================================================================
    # T5 — urgency tiers
    # ======================================================================
    def test_05_urgency(self):
        # booking in 12h + needs_reply ≥ 60
        conv = self.Care._find_or_create_for(
            {"partner_id": self.patient.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        self._fso(self.patient, fields.Datetime.now() + timedelta(hours=12))
        conv.invalidate_recordset()
        self.assertGreaterEqual(conv.urgency_score, 60)
        self.assertEqual(conv._urgency_tier(), "large")
        # waiting-only < 30
        w = self.Care._find_or_create_for(
            {"phone_normalized": "0912345605"},
            {"channel": "zalo", "inbound": False, "set_status": "waiting",
             "event_at": fields.Datetime.now(), "unread": "zero"})
        self.assertLess(w.urgency_score, 30)
        # junk = 0
        jl = self.env["crm.lead"].create({"name": "junk5", "phone": "0912345650"})
        jconv = self.Care.search([("lead_id", "=", jl.id)], limit=1)
        # action_mark_spam() commits, which is forbidden inside a test cursor —
        # neutralise the commit for the duration of the call.
        with patch.object(self.env.cr, "commit"):
            self.Care.action_set_status(jconv.id, "junk_suspect")
        jconv.invalidate_recordset()
        self.assertEqual(jconv.urgency_score, 0)

    # ======================================================================
    # T6 — claim race
    # ======================================================================
    def test_06_claim_race(self):
        conv = self.Care._find_or_create_for(
            {"phone_normalized": "0912345606"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        r1 = self.Care.with_user(self.crm_user).action_claim(conv.id)
        self.assertTrue(r1["claimed"])
        r2 = self.Care.with_user(self.crm_user2).action_claim(conv.id)
        self.assertFalse(r2["claimed"])
        self.assertEqual(r2["owner"]["id"], self.crm_user.id)
        conv.invalidate_recordset()
        self.assertEqual(conv.owner_id.id, self.crm_user.id)

    # ======================================================================
    # T7 — take-over (manager only)
    # ======================================================================
    def test_07_take_over(self):
        conv = self.Care._find_or_create_for(
            {"phone_normalized": "0912345607"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        self.Care.with_user(self.crm_user).action_claim(conv.id)
        with self.assertRaises(AccessError):
            self.Care.with_user(self.crm_user2).action_take_over(conv.id)
        res = self.Care.with_user(self.crm_mgr).action_take_over(conv.id)
        self.assertTrue(res["claimed"])
        conv.invalidate_recordset()
        self.assertEqual(conv.owner_id.id, self.crm_mgr.id)

    # ======================================================================
    # T8 — junk marks the lead spam
    # ======================================================================
    def test_08_junk_marks_lead_spam(self):
        lead = self.env["crm.lead"].create({"name": "spam8", "phone": "0912345608"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertTrue(conv)
        with patch.object(self.env.cr, "commit"):  # action_mark_spam commits
            self.Care.action_set_status(conv.id, "junk_suspect")
        lead.invalidate_recordset()
        self.assertEqual(lead.contact_status, "spam")
        self.assertTrue(lead.is_spam_caller)

    # ======================================================================
    # T9 — timeline merge, no clinical keys
    # ======================================================================
    def test_09_timeline_merge(self):
        zc = self._zalo_conv(phone="0912345609", partner=self.patient, name="tl")
        self._zalo_msg(zc, text="msg one")
        self._zalo_msg(zc, text="msg two")
        # inbound email on the partner → email card (voip absent on O19)
        self.env["mail.message"].create({
            "model": "res.partner", "res_id": self.patient.id,
            "message_type": "email", "email_from": "tl9@example.com",
            "subject": "hello", "body": "<p>hi there</p>",
            "date": fields.Datetime.now()})
        self._fso(self.patient, fields.Datetime.now() + timedelta(days=1))
        if self.has_voip:
            self._call("0912345609", call_type="missed", partner=self.patient)
        conv = self._convs_for_zalo(zc)
        detail = self.Care.get_conversation_detail(conv.id)
        tl = detail["timeline"]
        kinds = {e["kind"] for e in tl}
        self.assertIn("zalo", kinds)
        self.assertIn("email", kinds)
        self.assertIn("booking", kinds)
        if self.has_voip:
            self.assertIn("call", kinds)
        self.assertGreaterEqual(len(tl), 4)
        # sorted ascending
        ts = [e["ts"] for e in tl]
        self.assertEqual(ts, sorted(ts))
        # NO clinical keys anywhere in the payload
        banned = {"diagnosis", "clinical_notes", "news2", "vitals", "risk",
                  "alert_level", "is_abnormal"}
        for e in tl:
            self.assertFalse(banned & set(e.keys()))

    # ======================================================================
    # T10 — scoping (group + company)
    # ======================================================================
    def test_10_scoping(self):
        with self.assertRaises(AccessError):
            self.Care.with_user(self.plain_user).get_workspace_data()
        # other-company conversation is absent
        other = self.Care.sudo().create({
            "phone_normalized": "0912345610", "company_id": self.company2.id,
            "status": "needs_reply"})
        data = self.Care.with_user(self.crm_user).get_workspace_data()
        ids = [c["id"] for c in data["conversations"]]
        self.assertNotIn(other.id, ids)

    # ======================================================================
    # T11 — zalo send path
    # ======================================================================
    def test_11_zalo_send(self):
        zc = self._zalo_conv(name="send11")
        self._zalo_msg(zc)
        conv = self._convs_for_zalo(zc)
        with patch.object(type(self.env["zalo.message"]),
                          "action_send_message", return_value=None) as mock:
            self.Care.action_send_zalo(conv.id, "outbound text")
        self.assertTrue(mock.called)
        out = self.env["zalo.message"].search([
            ("conversation_id", "=", zc.id), ("direction", "=", "outgoing")])
        self.assertTrue(out)
        conv.invalidate_recordset()
        self.assertEqual(conv.status, "waiting")

    # ======================================================================
    # T12 — backfill idempotent
    # ======================================================================
    def test_12_backfill_idempotent(self):
        # seed a couple of sources the backfill will pick up
        self._zalo_conv(phone="0912345612", name="bf").write(
            {"last_message_date": fields.Datetime.now()})
        self.env["crm.lead"].create({"name": "bf12", "phone": "0912345662",
                                      "contact_status": "lead"})
        post_init_hook(self.env)
        n1 = self.Care.search_count([])
        post_init_hook(self.env)
        n2 = self.Care.search_count([])
        self.assertEqual(n1, n2, "re-running backfill creates nothing new")

    # ======================================================================
    # T13 — hook isolation
    # ======================================================================
    def test_13_hook_isolation(self):
        zc = self._zalo_conv(name="iso")
        with patch.object(type(self.Care), "_find_or_create_for",
                          side_effect=RuntimeError("boom")):
            # the zalo.message create must still succeed despite the raising hook
            msg = self._zalo_msg(zc)
        self.assertTrue(msg.exists())

    # ======================================================================
    # T14 — channel counts
    # ======================================================================
    def test_14_channel_counts(self):
        # seed one of each active channel, including email
        self._zalo_msg(self._zalo_conv(name="cc_z"))
        if self.has_voip:
            self._call("0912345614", call_type="missed")
        lead = self.env["crm.lead"].create({"name": "cc_e14"})  # no phone/email → no lead conv
        self.env["mail.message"].create({
            "model": "crm.lead", "res_id": lead.id, "message_type": "email",
            "email_from": "cust14@example.com", "subject": "hi",
            "body": "<p>hello</p>", "date": fields.Datetime.now()})
        data = self.Care.with_user(self.crm_user).get_workspace_data()
        counts = data["channel_counts"]
        # counts mirror an authoritative search per channel (robust vs other fixtures)
        active_channels = ("zalo", "email") + (("call",) if self.has_voip else ())
        for ch in active_channels:
            total = self.Care.sudo().search_count([
                ("company_id", "=", self.company.id),
                ("status", "!=", "closed"), ("channel_primary", "=", ch)])
            needs = self.Care.sudo().search_count([
                ("company_id", "=", self.company.id),
                ("status", "=", "needs_reply"), ("channel_primary", "=", ch)])
            self.assertEqual(counts[ch]["total"], total)
            self.assertEqual(counts[ch]["needs"], needs)
        self.assertGreaterEqual(counts["email"]["total"], 1)

    # ======================================================================
    # T15 — email ingestion
    # ======================================================================
    def test_15_email_ingestion(self):
        lead = self.env["crm.lead"].create({"name": "email15"})  # no phone/email anchor
        self.assertFalse(self.Care.search([("lead_id", "=", lead.id)]))
        self.env["mail.message"].create({
            "model": "crm.lead", "res_id": lead.id, "message_type": "email",
            "email_from": "Cust15@Example.com", "subject": "Q",
            "body": "<p>rehab?</p>", "date": fields.Datetime.now()})
        conv = self.Care.search([("lead_id", "=", lead.id)])
        self.assertEqual(len(conv), 1)
        self.assertEqual(conv.channel_primary, "email")
        self.assertEqual(conv.status, "needs_reply")
        self.assertEqual(conv.email_normalized, "cust15@example.com")
        # gateway retry: a second email row on the same lead → still one conversation
        self.env["mail.message"].create({
            "model": "crm.lead", "res_id": lead.id, "message_type": "email",
            "email_from": "Cust15@Example.com", "subject": "Q2",
            "body": "<p>again</p>", "date": fields.Datetime.now()})
        self.assertEqual(len(self.Care.search([("lead_id", "=", lead.id)])), 1)

    # ======================================================================
    # T16 — email reply
    # ======================================================================
    def test_16_email_reply(self):
        lead = self.env["crm.lead"].create({
            "name": "reply16", "email_from": "reply16@example.com"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertTrue(conv)
        before = self.env["mail.message"].search_count([
            ("model", "=", "crm.lead"), ("res_id", "=", lead.id),
            ("message_type", "=", "comment")])
        self.Care.action_send_email(conv.id, "Here is our reply")
        posted = self.env["mail.message"].search([
            ("model", "=", "crm.lead"), ("res_id", "=", lead.id),
            ("message_type", "=", "comment")])
        self.assertEqual(len(posted) - 0, before + 1)
        last = posted.sorted("id")[-1]
        self.assertIn("Here is our reply", last.body)
        recipients = last.partner_ids.mapped("email")
        self.assertIn("reply16@example.com", [e and e.lower() for e in recipients])
        conv.invalidate_recordset()
        self.assertEqual(conv.status, "waiting")
        # no recipient email → clean UserError, no post
        nore = self.Care._find_or_create_for(
            {"phone_normalized": "0912345616"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        with self.assertRaises(UserError):
            self.Care.action_send_email(nore.id, "no recipient")

    # ======================================================================
    # T17 — hot-path guard
    # ======================================================================
    def test_17_hot_path_guard(self):
        before = self.Care.search_count([])
        # a plain chatter note on an unrelated record must NOT touch care_command
        with patch.object(type(self.Care), "_find_or_create_for",
                          side_effect=RuntimeError("must not be called")):
            self.patient.message_post(body="just an internal note",
                                      message_type="comment",
                                      subtype_xmlid="mail.mt_note")
        after = self.Care.search_count([])
        self.assertEqual(before, after, "no conversation created for a chatter note")
