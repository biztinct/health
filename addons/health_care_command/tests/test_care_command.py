# -*- coding: utf-8 -*-
"""Care Command tests — Phase 1 (T1–T17) + Phase 2 (T18/T19 zalo send repair,
T23 airtight claim, T24 workspace search, T25 capped payload).

Phase-2 bridge tests T20–T22 live in health_care_command_voip (that module
only loads when VoIP is installed, which is the only place voip.call.log
exists). T18/T19 exercise the zalo.message send path and live here (rather than
in a new health_zalo test module) because this suite already carries the
zalo.config / conversation / message fixtures — no extra test-tag needed.

TransactionCase only (no HttpCase → --no-http stays). Assertions key on
codes/ids/enum values, never display strings (ledger §5.32/§5.50).
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

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

    def _flush_tracking(self):
        """mail tracking messages post at precommit (Odoo 17+); a
        TransactionCase never commits, so flush the callbacks explicitly."""
        self.env.flush_all()
        self.env.cr.precommit.run()

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
        # Phase 5: counts read channel_effective (traffic ?? declared), so the
        # authoritative mirror must too — a declared-only lead lands in these.
        for ch in active_channels:
            total = self.Care.sudo().search_count([
                ("company_id", "=", self.company.id),
                ("status", "!=", "closed"), ("channel_effective", "=", ch)])
            needs = self.Care.sudo().search_count([
                ("company_id", "=", self.company.id),
                ("status", "=", "needs_reply"), ("channel_effective", "=", ch)])
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
        # a plain chatter note on an unrelated record must NOT touch care_command.
        # No side_effect: the hook's own try/except would swallow a raise and
        # the test would pass even without the guard — assert the mock instead.
        with patch.object(type(self.Care), "_find_or_create_for") as upsert_mock:
            self.patient.message_post(body="just an internal note",
                                      message_type="comment",
                                      subtype_xmlid="mail.mt_note")
        upsert_mock.assert_not_called()
        after = self.Care.search_count([])
        self.assertEqual(before, after, "no conversation created for a chatter note")

    # ======================================================================
    # T18 — zalo send repair: SUCCESS path (Phase 2, §5.2)
    # ======================================================================
    def test_18_zalo_send_success(self):
        # The real send seam is get_api_client(env) → ZaloAPIClient, whose only
        # HTTP touchpoint is requests.request inside _make_request. Mock that +
        # the token retrieval; nothing hits the network. Proves the wiring the
        # unregistered-model bug (§5.54) had broken.
        zc = self._zalo_conv(name="send18")
        msg = self.env["zalo.message"].create({
            "conversation_id": zc.id, "direction": "outgoing",
            "message_type": "text", "text": "xin chào", "state": "draft"})
        resp = MagicMock(status_code=200, text='{"message_id": "zm_18"}')
        resp.json.return_value = {"message_id": "zm_18"}
        with patch.object(type(self.env["zalo.config"]), "get_valid_token",
                          return_value="tok"), \
                patch("requests.request", return_value=resp) as req, \
                patch.object(type(self.env["zalo.conversation"]),
                             "update_last_message") as ulm:
            msg.action_send_message()
        self.assertTrue(req.called, "the real API path issued the HTTP request")
        self.assertTrue(ulm.called, "conversation.update_last_message was called")
        # state is set on the cache by the success branch
        self.assertEqual(msg.state, "sent")
        self.assertEqual(msg.zalo_message_id, "zm_18")

    # ======================================================================
    # T19 — zalo send repair: FAILURE path + test_connection reaches the API
    # ======================================================================
    def test_19_zalo_send_failure(self):
        zc = self._zalo_conv(name="send19")
        msg = self.env["zalo.message"].create({
            "conversation_id": zc.id, "direction": "outgoing",
            "message_type": "text", "text": "fail", "state": "draft"})
        resp = MagicMock(status_code=400, text='{"message": "bad token"}')
        resp.json.return_value = {"message": "bad token"}
        raised = False
        # manual try/except (NOT assertRaises) so the state='failed' write is not
        # rolled back by the assertRaises savepoint (§5.8); read from cache.
        with patch.object(type(self.env["zalo.config"]), "get_valid_token",
                          return_value="tok"), \
                patch("requests.request", return_value=resp):
            try:
                msg.action_send_message()
            except UserError:
                raised = True
        self.assertTrue(raised, "a non-200 send raises UserError")
        self.assertEqual(msg.state, "failed")
        self.assertTrue(msg.error_message)

        # action_test_connection must reach get_oa_profile without KeyError
        # (the pre-fix `self.env['zalo.api.client']` lookup raised before this).
        config = zc.config_id
        config.write({"access_token": "tok", "state": "draft"})
        resp2 = MagicMock(status_code=200, text='{"name": "Test OA"}')
        resp2.json.return_value = {"name": "Test OA"}
        with patch.object(type(config), "get_valid_token", return_value="tok"), \
                patch("requests.request", return_value=resp2):
            config.action_test_connection()
        self.assertEqual(config.state, "connected")

    # ======================================================================
    # T23 — airtight claim (Phase 2, review LOW-6)
    # ======================================================================
    def test_23_claim_airtight(self):
        conv = self.Care._find_or_create_for(
            {"phone_normalized": "0912345623"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        # fresh → claimed True, and the owner_id change (tracking=True) logs to
        # chatter. mail tracking messages post in the PRECOMMIT phase (Odoo
        # 17+), which a TransactionCase never reaches — flush it explicitly
        # (the canonical flush_tracking pattern) before counting messages.
        self._flush_tracking()
        conv.invalidate_recordset()
        msgs_before = len(conv.message_ids)
        res = self.Care.with_user(self.crm_user).action_claim(conv.id)
        self.assertTrue(res["claimed"])
        self._flush_tracking()
        conv.invalidate_recordset()
        self.assertEqual(conv.owner_id.id, self.crm_user.id)
        self.assertGreater(len(conv.message_ids), msgs_before,
                           "owner change recorded in chatter (tracking)")
        # pre-owned → lost-race path: no exception, reports the current owner
        res2 = self.Care.with_user(self.crm_user2).action_claim(conv.id)
        self.assertFalse(res2["claimed"])
        self.assertEqual(res2["owner"]["id"], self.crm_user.id)
        conv.invalidate_recordset()
        self.assertEqual(conv.owner_id.id, self.crm_user.id, "owner unchanged")

    # ======================================================================
    # T24 — workspace search (Phase 2, review LOW-9 + §5.4)
    # ======================================================================
    def test_24_workspace_search(self):
        lead = self.env["crm.lead"].create({
            "name": "Zqwlead Special", "phone": "0912340001"})
        convL = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        convP = self.Care._find_or_create_for(
            {"phone_normalized": "0912340002"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        convE = self.Care._find_or_create_for(
            {"email_normalized": "findme@example.com", "partner_id": self.patientB.id},
            {"channel": "email", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        U = self.Care.with_user(self.crm_user)

        # Phase 5: the default surface is attention-first (activity only), which
        # hides lead-anchored/dormant rows. Search correctness is what this test
        # asserts, so query across the full set (view="all").
        def ids(**kw):
            kw.setdefault("view", "all")
            return [c["id"] for c in U.get_workspace_data(**kw)["conversations"]]

        # by lead name
        self.assertIn(convL.id, ids(query="Zqwlead"))
        self.assertNotIn(convP.id, ids(query="Zqwlead"))
        # by phone
        self.assertIn(convP.id, ids(query="0912340002"))
        # by email
        self.assertIn(convE.id, ids(query="findme@"))
        # empty query = unfiltered (all three present)
        allids = ids(query="")
        for c in (convL, convP, convE):
            self.assertIn(c.id, allids)
        # still company-scoped even with a query hit
        other = self.Care.sudo().create({
            "phone_normalized": "0912340003", "company_id": self.company2.id,
            "status": "needs_reply"})
        self.assertNotIn(other.id, ids(query="0912340003"))

    # ======================================================================
    # T25 — capped payload: honest cap + exact counts (Phase 2, §5.4)
    # ======================================================================
    def test_25_capped_payload(self):
        cap = self.Care.WORKSPACE_CAP
        vals = [{
            "phone_normalized": "09%08d" % i,
            "company_id": self.company.id,
            "status": "needs_reply",
        } for i in range(cap + 1)]
        self.Care.sudo().create(vals)
        # Phase 5: these dormant rows carry no channel activity, so the cap must
        # be exercised over the full set (view="all"); the attention default
        # would hide them and the cap would never trip.
        data = self.Care.with_user(self.crm_user).get_workspace_data(view="all")
        self.assertTrue(data["capped"], "over-cap payload is flagged capped")
        self.assertGreaterEqual(data["total"], cap + 1)
        self.assertLessEqual(len(data["conversations"]), cap,
                             "tile/list payload is truncated to the cap")
        # counts are EXACT (read_group over the whole set, not the capped list)
        total_open = self.Care.sudo().search_count([
            ("company_id", "=", self.company.id), ("status", "!=", "closed")])
        self.assertEqual(data["channel_counts"]["all"]["total"], total_open)

    # ======================================================================
    # T26 — reply templates: manager-only CRUD + channel-filtered service
    # ======================================================================
    def test_26_reply_templates(self):
        Tpl = self.env["care.reply.template"]
        t_any = Tpl.create({"name": "T Any", "body": "any body", "channel": "any"})
        t_zalo = Tpl.create({"name": "T Zalo", "body": "zalo body", "channel": "zalo"})
        t_email = Tpl.create({"name": "T Email", "body": "email body", "channel": "email"})
        # a plain CRM user cannot create (perm_create=0 → AccessError)
        with self.assertRaises(AccessError):
            Tpl.with_user(self.crm_user).create(
                {"name": "nope", "body": "x", "channel": "any"})
        # a zalo conversation sees any + zalo, never email
        zc = self._zalo_conv(name="tpl26")
        self._zalo_msg(zc)
        conv = self._convs_for_zalo(zc)
        self.assertEqual(conv.channel_primary, "zalo")
        got = self.Care.with_user(self.crm_user).get_reply_templates(conv.id)
        ids = {t["id"] for t in got}
        self.assertIn(t_any.id, ids)
        self.assertIn(t_zalo.id, ids)
        self.assertNotIn(t_email.id, ids)
        # company-scoped: a template in the other company is absent
        other = Tpl.sudo().create({
            "name": "other co tpl", "body": "x", "channel": "any",
            "company_id": self.company2.id})
        self.assertNotIn(other.id, {t["id"] for t in
                         self.Care.with_user(self.crm_user).get_reply_templates(conv.id)})
        # inactive template is excluded
        t_any.active = False
        self.assertNotIn(t_any.id, {t["id"] for t in
                         self.Care.with_user(self.crm_user).get_reply_templates(conv.id)})

    # ======================================================================
    # T27 — watchlist match on inbound Zalo (case-insensitive, +15, no dup)
    # ======================================================================
    def test_27_watchlist_zalo(self):
        self.env["care.watch.phrase"].create({"phrase": "đau ngực"})
        zc = self._zalo_conv(name="watch27")
        self._zalo_msg(zc, text="Bố tôi bị ĐAU NGỰC từ sáng nay")
        conv = self._convs_for_zalo(zc)
        self.assertTrue(conv.watch_flag)
        self.assertIn("đau ngực", (conv.watch_terms or "").lower())
        # the +15 watch term: clearing the flag drops the score by exactly 15
        with_watch = conv.urgency_score
        conv.watch_flag = False
        self.assertEqual(with_watch - conv.urgency_score, 15)
        # a clean inbound message never flags
        zc2 = self._zalo_conv(name="watch27b")
        self._zalo_msg(zc2, text="chào chị em muốn hỏi giá dịch vụ")
        conv2 = self._convs_for_zalo(zc2)
        self.assertFalse(conv2.watch_flag)
        self.assertFalse(conv2.watch_terms)
        # replaying the same phrase does not duplicate the stored term
        self._zalo_msg(zc, text="vẫn còn đau ngực nhiều")
        conv.invalidate_recordset()
        terms = [t.strip() for t in (conv.watch_terms or "").split(",") if t.strip()]
        self.assertEqual(terms.count("đau ngực"), 1)

    # ======================================================================
    # T28 — watchlist match on inbound email; chatter NOTE never scanned
    # ======================================================================
    def test_28_watchlist_email(self):
        self.env["care.watch.phrase"].create({"phrase": "khó thở"})
        lead = self.env["crm.lead"].create({
            "name": "w28", "email_from": "w28@example.com"})
        self.env["mail.message"].create({
            "model": "crm.lead", "res_id": lead.id, "message_type": "email",
            "email_from": "w28@example.com", "subject": "Mẹ tôi KHÓ THỞ",
            "body": "<p>xin tư vấn giúp</p>", "date": fields.Datetime.now()})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertTrue(conv.watch_flag)
        self.assertIn("khó thở", (conv.watch_terms or "").lower())
        # a plain chatter note (T17 guard) is never ingested, never scanned
        with patch.object(type(self.Care), "_match_watchlist") as mm:
            self.patient.message_post(
                body="đau ngực khó thở — ghi chú nội bộ",
                message_type="comment", subtype_xmlid="mail.mt_note")
        mm.assert_not_called()

    # ======================================================================
    # T29 — watchlist flag + terms clear when status leaves needs_reply
    # ======================================================================
    def test_29_watchlist_clears(self):
        self.env["care.watch.phrase"].create({"phrase": "chảy máu"})
        zc = self._zalo_conv(name="w29")
        self._zalo_msg(zc, text="bị chảy máu nhiều")
        conv = self._convs_for_zalo(zc)
        self.assertTrue(conv.watch_flag)
        self.assertTrue(conv.watch_terms)
        # an outgoing reply → status waiting → flag + terms cleared (mirrors
        # the missed-call clearing). Mock the broken upstream send (§5.54).
        with patch.object(type(self.env["zalo.message"]),
                          "action_send_message", return_value=None):
            self.Care.action_send_zalo(conv.id, "điều dưỡng đến ngay ạ")
        conv.invalidate_recordset()
        self.assertEqual(conv.status, "waiting")
        self.assertFalse(conv.watch_flag)
        self.assertFalse(conv.watch_terms)

    # ======================================================================
    # T31 — reminder schedules a todo activity on the anchor, gated
    # ======================================================================
    def test_31_reminder(self):
        Act = self.env["mail.activity"]
        lead = self.env["crm.lead"].create({"name": "rem31", "phone": "0912345631"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        before = Act.search_count(
            [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)])
        res = self.Care.action_reminder(conv.id, 3, "gọi lại tuần sau")
        self.assertTrue(res["ok"])
        acts = Act.search([("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)])
        self.assertEqual(len(acts) - before, 1)
        self.assertEqual(acts.sorted("id")[-1].date_deadline,
                         fields.Date.context_today(self.env.user) + timedelta(days=3))
        # partner-only conversation → activity lands on the partner
        pconv = self.Care._find_or_create_for(
            {"partner_id": self.patientB.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        self.Care.action_reminder(pconv.id, 1, None)
        self.assertTrue(Act.search_count(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.patientB.id)]))
        # gated: a plain (non-CRM) user is denied
        with self.assertRaises(AccessError):
            self.Care.with_user(self.plain_user).action_reminder(conv.id, 1, None)

    # ======================================================================
    # T32 — consent action: partner-scoped act_window (soft dependency)
    # ======================================================================
    def test_32_consent_action(self):
        if "health.consent" not in self.env:
            self.skipTest("health.consent not installed — soft dependency")
        conv = self.Care._find_or_create_for(
            {"partner_id": self.patient.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        action = self.Care.action_consent(conv.id)
        self.assertEqual(action["res_model"], "health.consent")
        # health.consent's patient field is client_id (NOT partner_id)
        self.assertIn(("client_id", "=", self.patient.id), action["domain"])
        # no partner anchor → clean UserError
        nore = self.Care._find_or_create_for(
            {"phone_normalized": "0912345632"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        with self.assertRaises(UserError):
            self.Care.action_consent(nore.id)

    # ======================================================================
    # Phase 5 — Surface Truth. Helpers.
    # ======================================================================
    def _open_domain(self, user=None):
        companies = (user or self.env.user).company_ids or self.company
        return [("company_id", "in", companies.ids), ("status", "!=", "closed")]

    @staticmethod
    def _row(data, cid):
        return next((c for c in data["conversations"] if c["id"] == cid), None)

    # ======================================================================
    # T39 — declared channel derivation from mode_of_contact (no faked traffic)
    # ======================================================================
    def test_39_declared_derivation(self):
        lead = self.env["crm.lead"].create({
            "name": "fb39", "phone": "0912345639", "mode_of_contact": "facebook"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertTrue(conv)
        self.assertEqual(conv.channel_declared, "fb")
        self.assertEqual(conv.channel_effective, "fb")
        self.assertFalse(conv.channel_primary, "a lead never sets traffic")
        self.assertFalse(conv.has_channel_activity, "declared is not activity")
        # walk_in has no mapped channel → all three channel fields falsy
        wlead = self.env["crm.lead"].create({
            "name": "walk39", "phone": "0912345699", "mode_of_contact": "walk_in"})
        wconv = self.Care.search([("lead_id", "=", wlead.id)], limit=1)
        self.assertTrue(wconv)
        self.assertFalse(wconv.channel_declared)
        self.assertFalse(wconv.channel_effective)
        self.assertFalse(wconv.channel_primary)
        self.assertFalse(wconv.has_channel_activity)

    # ======================================================================
    # T40 — traffic wins over a declaration; declared never overwritten
    # ======================================================================
    def test_40_traffic_wins(self):
        lead = self.env["crm.lead"].create({
            "name": "fb40", "phone": "0912345640", "mode_of_contact": "facebook"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertEqual(conv.channel_declared, "fb")
        self.assertEqual(conv.channel_effective, "fb")
        # a real zalo inbound lands on the same lead conversation
        self.Care._find_or_create_for(
            {"lead_id": lead.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        conv.invalidate_recordset()
        self.assertEqual(conv.channel_primary, "zalo")
        self.assertEqual(conv.channel_effective, "zalo", "traffic wins")
        self.assertTrue(conv.has_channel_activity)
        self.assertEqual(conv.channel_declared, "fb", "declaration is preserved")

    # ======================================================================
    # T41 — view domains: attention vs leads vs all; leads_count shape
    # ======================================================================
    def test_41_view_domains(self):
        U = self.Care.with_user(self.crm_user)
        # a traffic conversation (has activity) …
        traffic = self.Care._find_or_create_for(
            {"phone_normalized": "0912340041"},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        # … and a declared-only lead (no activity)
        lead = self.env["crm.lead"].create({
            "name": "lead41", "phone": "0912340042", "mode_of_contact": "website"})
        lconv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertTrue(lconv and not lconv.has_channel_activity)

        def ids(**kw):
            return [c["id"] for c in U.get_workspace_data(**kw)["conversations"]]

        # default = attention → only the traffic one
        self.assertIn(traffic.id, ids())
        self.assertNotIn(lconv.id, ids())
        # leads → only the lead
        self.assertNotIn(traffic.id, ids(view="leads"))
        self.assertIn(lconv.id, ids(view="leads"))
        # all → both
        allids = ids(view="all")
        self.assertIn(traffic.id, allids)
        self.assertIn(lconv.id, allids)
        # unknown value behaves as attention
        self.assertNotIn(lconv.id, ids(view="bogus"))
        self.assertIn(traffic.id, ids(view="bogus"))
        # leads_count mirrors an authoritative search over the leads domain
        data = U.get_workspace_data()
        leads_dom = self._open_domain(self.crm_user) + [("has_channel_activity", "=", False)]
        self.assertEqual(data["leads_count"]["total"],
                         self.Care.sudo().search_count(leads_dom))
        self.assertEqual(data["leads_count"]["needs"],
                         self.Care.sudo().search_count(
                             leads_dom + [("status", "=", "needs_reply")]))
        self.assertGreaterEqual(data["leads_count"]["total"], 1)
        self.assertEqual(data["view"], "attention", "server echoes the view")

    # ======================================================================
    # T42 — channel filter reads channel_effective (declared lead is filterable)
    # ======================================================================
    def test_42_filter_on_effective(self):
        U = self.Care.with_user(self.crm_user)
        lead = self.env["crm.lead"].create({
            "name": "fb42", "phone": "0912340043", "mode_of_contact": "facebook"})
        lconv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        # declared-only → visible under the leads/all view, filtered by fb
        ids = [c["id"] for c in U.get_workspace_data(view="all", channel="fb")["conversations"]]
        self.assertIn(lconv.id, ids)
        data = U.get_workspace_data()
        self.assertGreaterEqual(data["channel_counts"]["fb"]["total"], 1,
                                "counts read channel_effective")

    # ======================================================================
    # T43 — payload contract: active_channels, 8-key counts, channel_live
    # ======================================================================
    def test_43_payload_contract(self):
        U = self.Care.with_user(self.crm_user)
        lead = self.env["crm.lead"].create({
            "name": "fb43", "phone": "0912340044", "mode_of_contact": "facebook"})
        lconv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        data = U.get_workspace_data(view="all")
        expected = ("zalo", "call", "email", "zns",
                    "whatsapp", "fb", "telegram", "webchat")
        self.assertEqual(set(data["active_channels"]), set(expected))
        for ch in expected:
            self.assertIn(ch, data["channel_counts"])
        self.assertEqual(data["view"], "all")
        row = self._row(data, lconv.id)
        self.assertTrue(row)
        self.assertEqual(row["channel"], "fb")
        self.assertFalse(row["channel_live"], "declared-only is not live")
        # once real traffic lands, channel_live flips true
        self.Care._find_or_create_for(
            {"lead_id": lead.id},
            {"channel": "zalo", "inbound": True, "set_status": "needs_reply",
             "event_at": fields.Datetime.now()})
        data2 = U.get_workspace_data()  # now in attention
        row2 = self._row(data2, lconv.id)
        self.assertTrue(row2)
        self.assertTrue(row2["channel_live"])

    # ======================================================================
    # T44 — backfill: derives declared + sets activity flag; idempotent
    # ======================================================================
    def test_44_backfill(self):
        # legacy lead-anchored conversation with NO declared channel yet
        llead = self.env["crm.lead"].create({
            "name": "bf44", "phone": "0912340045", "mode_of_contact": "zalo"})
        lconv = self.Care.search([("lead_id", "=", llead.id)], limit=1)
        lconv.write({"channel_declared": False})  # simulate a pre-Phase-5 row
        # legacy traffic conversation flagged has_channel_activity=False
        tconv = self.Care.sudo().create({
            "phone_normalized": "0912340046", "company_id": self.company.id,
            "status": "needs_reply", "channel_primary": "zalo",
            "has_channel_activity": False})
        res = self.Care._backfill_channel_truth()
        lconv.invalidate_recordset()
        tconv.invalidate_recordset()
        self.assertEqual(lconv.channel_declared, "zalo", "derived from mode_of_contact")
        self.assertEqual(lconv.channel_effective, "zalo")
        self.assertTrue(tconv.has_channel_activity, "traffic → activity flag set")
        self.assertGreaterEqual(res["activity_set"], 1)
        self.assertGreaterEqual(res["declared"].get("zalo", 0), 1)
        # idempotent: a second run writes nothing new
        res2 = self.Care._backfill_channel_truth()
        self.assertEqual(res2["activity_set"], 0)
        self.assertFalse(res2["declared"])

    # ======================================================================
    # T45 — reply templates key off channel_effective (declared-zalo → zalo)
    # ======================================================================
    def test_45_templates_via_effective(self):
        Tpl = self.env["care.reply.template"]
        t_any = Tpl.create({"name": "T45 Any", "body": "b", "channel": "any"})
        t_zalo = Tpl.create({"name": "T45 Zalo", "body": "b", "channel": "zalo"})
        t_email = Tpl.create({"name": "T45 Email", "body": "b", "channel": "email"})
        lead = self.env["crm.lead"].create({
            "name": "tpl45", "phone": "0912340047", "mode_of_contact": "zalo"})
        conv = self.Care.search([("lead_id", "=", lead.id)], limit=1)
        self.assertFalse(conv.channel_primary)
        self.assertEqual(conv.channel_effective, "zalo")
        got = {t["id"] for t in
               self.Care.with_user(self.crm_user).get_reply_templates(conv.id)}
        self.assertIn(t_any.id, got)
        self.assertIn(t_zalo.id, got)
        self.assertNotIn(t_email.id, got)

    # ======================================================================
    # T46 — cap honesty is per-view (leads set capped independent of attention)
    # ======================================================================
    def test_46_cap_per_view(self):
        # pin a tiny cap for this test only (§5.32-style hygiene)
        model_cls = type(self.Care)
        orig = model_cls.WORKSPACE_CAP
        model_cls.WORKSPACE_CAP = 3
        self.addCleanup(setattr, model_cls, "WORKSPACE_CAP", orig)
        # create > cap dormant leads (no channel activity)
        self.Care.sudo().create([{
            "phone_normalized": "0912%06d" % (460000 + i),
            "company_id": self.company.id, "status": "needs_reply",
            "has_channel_activity": False,
        } for i in range(model_cls.WORKSPACE_CAP + 2)])
        U = self.Care.with_user(self.crm_user)
        leads = U.get_workspace_data(view="leads")
        self.assertTrue(leads["capped"], "leads view flags capped")
        self.assertLessEqual(len(leads["conversations"]), model_cls.WORKSPACE_CAP)
        leads_total = self.Care.sudo().search_count(
            self._open_domain(self.crm_user) + [("has_channel_activity", "=", False)])
        self.assertEqual(leads["total"], leads_total, "per-view total is honest")
