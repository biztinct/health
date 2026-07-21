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

    def _call(self, phone, call_type="missed", direction="incoming", partner=False):
        return self.env["voip.call.log"].create({
            "call_id": "vb_%s_%s_%s" % (phone, call_type, direction),
            "voip_config_id": self.vconfig.id,
            "direction": direction, "call_type": call_type,
            "caller_number": phone,
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
