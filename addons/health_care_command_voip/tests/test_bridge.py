# -*- coding: utf-8 -*-
"""Care Command VoIP bridge tests (handover §6, T21–T22).

TransactionCase only (no HttpCase). Asserts key on codes/ids/enum values,
never display strings (ledger §5.32/§5.50). This module only loads when
health_voip24h is installed, so voip.call.log is guaranteed present here.
"""

from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCareCommandVoipBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Care = env["care.conversation"]
        cls.company = env.company

        cls.province = env["health.catchment.province"].create({"name": "VB Prov"})
        cls.facility = env["health.facility"].create({
            "name": "VB Facility", "code": "VBFAC", "street": "1 St",
            "city": "Hà Nội", "catchment_province_id": cls.province.id})
        cls.patient = env["res.partner"].create({
            "name": "Nguyễn Văn Bridge", "is_patient": True,
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})
        cls.patientB = env["res.partner"].create({
            "name": "Trần Thị Bridge", "is_patient": True,
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})
        cls.patientC = env["res.partner"].create({
            "name": "Lê Văn Bridge", "is_patient": True,
            "catchment_province_id": cls.province.id,
            "primary_facility_id": cls.facility.id})

        cls.vconfig = env["voip.config"].create({
            "name": "VB VoIP", "api_key": "k", "api_secret": "s",
            "account_id": "acc1"})

        # get_conversation_detail is group-gated; the default test user (uid 1)
        # is NOT a CRM group member (has_group checks real membership, not su),
        # so grant it — mirrors the care_command suite's setUpClass.
        env.user.sudo().write({
            "group_ids": [(4, env.ref("health_crm.group_health_crm_manager").id)]})

        # ...and the catchment scope, for the same reason one rung down.
        # `care.conversation._scope_domain` filters every service method by
        # catchment area: a user who is not an owner sees only their own area
        # plus the conversations that resolve to no area at all. These fixture
        # patients all carry `cls.province`, while uid 1 on this deployment
        # has no area and is not an owner — so `get_conversation_detail`
        # answered "Conversation not found" for a conversation the test had
        # just created. Pre-existing, and invisible until this module was next
        # run with tests. The engine is right and the fixture was
        # under-specified (§5.62: fix the test, not the engine), so give the
        # test user the same area as its patients — which is what a real
        # operator would have.
        env.user.sudo().write({"catchment_province_id": cls.province.id})

    def _call(self, phone, call_type="missed", direction="incoming", partner=False):
        return self.env["voip.call.log"].create({
            "call_id": "vb_%s_%s_%s" % (phone, call_type, direction),
            "voip_config_id": self.vconfig.id,
            "direction": direction, "call_type": call_type,
            # the CUSTOMER is the caller on incoming, the callee on outgoing;
            # the other side is the clinic trunk
            "caller_number": phone if direction == "incoming" else "02873001234",
            "called_number": phone if direction == "outgoing" else "02873001234",
            "call_date": fields.Datetime.now(),
            "partner_id": partner.id if partner else False,
            "talk_duration_seconds": 0 if call_type == "missed" else 30})

    def _conv_for_partner(self, partner):
        return self.Care.search([("partner_id", "=", partner.id)], limit=1)

    # ======================================================================
    # T20 — health_voip24h installs on Odoo 19 (the category_id → privilege_id fix)
    # ======================================================================
    def test_20_voip_installed(self):
        # Both security groups exist and carry privilege_id — the modern O19
        # replacement for the removed res.groups.category_id (§4.2).
        guser = self.env.ref("health_voip24h.group_voip_user")
        gmgr = self.env.ref("health_voip24h.group_voip_manager")
        self.assertTrue(guser.privilege_id, "group_voip_user has a privilege_id")
        self.assertTrue(gmgr.privilege_id, "group_voip_manager has a privilege_id")
        # smoke-create a voip.call.log (proves the model loaded cleanly on O19)
        log = self._call("0912345620", call_type="answered", direction="incoming")
        self.assertTrue(log.exists())

    # ======================================================================
    # T21 — live call ingestion (missed / answered / outgoing)
    # ======================================================================
    def test_21_call_ingestion(self):
        # -- missed incoming → needs_reply + missed flag + the +10 urgency term
        self._call("0912345621", call_type="missed",
                   direction="incoming", partner=self.patient)
        conv = self._conv_for_partner(self.patient)
        self.assertEqual(len(conv), 1, "one conversation created for the call")
        self.assertEqual(conv.channel_primary, "call")
        self.assertEqual(conv.status, "needs_reply")
        self.assertTrue(conv.missed_call_unhandled)
        # needs_reply (+40) + missed-call (+10); call_date=now so no stale term
        self.assertGreaterEqual(conv.urgency_score, 50)

        # -- answered incoming → status of an existing conversation UNTOUCHED
        convw = self.Care._find_or_create_for(
            {"partner_id": self.patientC.id},
            {"channel": "zalo", "inbound": False, "set_status": "waiting",
             "event_at": fields.Datetime.now(), "unread": "zero"})
        self.assertEqual(convw.status, "waiting")
        self._call("0912345622", call_type="answered",
                   direction="incoming", partner=self.patientC)
        convw.invalidate_recordset()
        self.assertEqual(convw.status, "waiting",
                         "an answered call must not invent a status change")
        detail = self.Care.get_conversation_detail(convw.id)
        self.assertIn("call", {e["kind"] for e in detail["timeline"]},
                      "answered call appears on the timeline")

        # -- outgoing → waiting + missed flag cleared
        missed = self._call("0912345623", call_type="missed",
                            direction="incoming", partner=self.patientB)
        convo = self._conv_for_partner(self.patientB)
        self.assertTrue(convo.missed_call_unhandled)
        self._call("0912345623", call_type="answered",
                   direction="outgoing", partner=self.patientB)
        convo.invalidate_recordset()
        self.assertEqual(convo.status, "waiting")
        self.assertFalse(convo.missed_call_unhandled,
                         "calling back clears the missed-call flag")

        # -- outgoing with no partner/lead → anchors on the CALLED number
        # (the customer), never the trunk caller_number
        self._call("0912345624", call_type="answered", direction="outgoing")
        convn = self.Care.search([("phone_normalized", "=", "0912345624")])
        self.assertEqual(len(convn), 1,
                         "outgoing call anchors on the customer's number")
        self.assertEqual(convn.status, "waiting")
        trunk = self.Care.search([("phone_normalized", "=", "02873001234")])
        self.assertFalse(trunk, "no conversation keyed to the clinic trunk")

    # ======================================================================
    # T30 — busy / failed / voicemail incoming count as missed-like (Phase 3)
    # ======================================================================
    def test_30_missed_like_signals(self):
        # the customer tried to reach us and didn't get through → needs_reply
        # + missed-call flag, exactly like a plain missed/abandoned call
        for ct, phone, patient in (
                ("busy", "0912345630", self.patient),
                ("voicemail", "0912345631", self.patientB),
                ("failed", "0912345632", self.patientC)):
            self._call(phone, call_type=ct, direction="incoming", partner=patient)
            conv = self._conv_for_partner(patient)
            self.assertEqual(len(conv), 1, "one conversation for %s" % ct)
            self.assertEqual(conv.channel_primary, "call")
            self.assertEqual(conv.status, "needs_reply", "%s → needs_reply" % ct)
            self.assertTrue(conv.missed_call_unhandled, "%s sets missed flag" % ct)

    # ======================================================================
    # T22 — hook exception isolation (savepoint in force, mirrors T13)
    # ======================================================================
    def test_22_hook_isolation(self):
        with patch.object(type(self.Care), "_find_or_create_for",
                          side_effect=RuntimeError("boom")):
            # the voip.call.log create must still succeed despite the raising hook
            log = self._call("0912345629", call_type="missed",
                             direction="incoming", partner=self.patient)
        self.assertTrue(log.exists())
        # and no conversation leaked from the failed ingest
        self.assertFalse(self._conv_for_partner(self.patient))

    # ======================================================================
    # T23 — the CMS left menu's Phone block
    #
    # The Phone app's backend menu is only reachable through the app grid, and
    # the clinic's users do not have it. These rows ARE the phone, so a typo in
    # an action xml-id is not a cosmetic defect: it is a menu row that throws
    # when somebody clicks it mid-call. Asserted on xml-ids and structure, not
    # on labels (ledger §5.32/§5.50).
    # ======================================================================
    LEAVES = (
        ("item_phone_callbacks", "health_voip24h.action_voip_callbacks"),
        ("item_phone_calls", "health_voip24h.action_voip_call_session"),
        ("item_phone_records", "health_voip24h.action_voip_call_log"),
        ("item_phone_recordings", "health_voip24h.action_voip_call_recording"),
        ("item_phone_extensions", "health_voip24h.action_voip_extension"),
        ("item_phone_settings", "health_voip24h.action_voip_config"),
    )

    def test_23_phone_sidebar_block_exists(self):
        parent = self.env.ref("health_care_command_voip.item_phone")
        self.assertTrue(parent.active)
        self.assertFalse(parent.parent_id, "the block is a top-level accordion")
        self.assertFalse(
            parent.action_xmlid,
            "a parent that navigates cannot also expand (cms_sidebar.js:124)")
        self.assertEqual(
            parent.section_id,
            self.env.ref("health_cms_sidebar.section_crm"))

    #: The two SET-UP screens live in Settings › Connections on the
    #: consolidated menu (MENU M2, `health_cms_ia`); the other four stay the
    #: Phone tab's.
    SETUP_LEAVES = ("item_phone_extensions", "item_phone_settings")

    def test_24_phone_sidebar_leaves_open_real_actions(self):
        parent = self.env.ref("health_care_command_voip.item_phone")
        connections = self.env.ref("health_cms_ia.parent_admin_connections",
                                   raise_if_not_found=False)
        for item_id, action_xmlid in self.LEAVES:
            item = self.env.ref("health_care_command_voip.%s" % item_id)
            if item_id in self.SETUP_LEAVES:
                self.assertEqual(item.section_id,
                                 self.env.ref("health_cms_sidebar.section_admin"),
                                 item_id)
                self.assertIn(item.parent_id, (connections, parent) if connections
                              else (parent, self.env["cms.sidebar.item"]), item_id)
            else:
                self.assertEqual(item.parent_id, parent, item_id)
            self.assertEqual(item.action_xmlid, action_xmlid, item_id)
            # The whole point: the action it names must actually exist.
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            self.assertTrue(action, "%s points at a missing action" % item_id)

    def test_25_phone_sidebar_is_in_the_match_keys(self):
        """Navigating to a phone screen must keep the CMS shell around."""
        keys = self.env["cms.sidebar.item"].get_match_keys()
        for _item_id, action_xmlid in self.LEAVES:
            self.assertIn(action_xmlid, keys["xmlids"], action_xmlid)
        self.assertIn("voip.call.session", keys["models"])
