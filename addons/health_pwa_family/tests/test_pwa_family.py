# -*- coding: utf-8 -*-
import json
import uuid
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged, new_test_user

UPDATE_PURPOSE = 'family_update'
REPLY_PURPOSE = 'family_message_reply'


def _fixture(env):
    """Conventions §6 fixtures (cloned from health_family_messages)."""
    Partner = env['res.partner']
    Facility = env['health.facility']
    province = env['health.catchment.province'].search([], limit=1) or \
        env['health.catchment.province'].create({'name': 'PF Prov', 'code': 'PFP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'PF Facility', 'code': 'PFF', 'street': '1 PF St',
            'city': 'Test City', 'phone': '02838000000',
            'timezone': 'Asia/Ho_Chi_Minh', 'catchment_province_id': province.id})
    patient = Partner.create({
        'name': 'PF Patient', 'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id, 'mobile': '0912345678'})
    representative = Partner.create({
        'name': 'PF Rep', 'is_representative': True, 'mobile': '0987654321'})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1) or \
        env['product.product'].create(
            {'name': 'PF Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, patient, representative, product


@tagged('post_install', '-at_install')
class PwaFamilyBase(HttpCase):

    def setUp(self):
        super().setUp()
        (self.province, self.facility, self.patient, self.representative,
         self.product) = _fixture(self.env)
        Stage = self.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        # A nurse user (login == password) + linked employee.
        self.nurse = new_test_user(
            self.env, login='pf_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        self.nurse_emp = self.env['hr.employee'].create(
            {'name': 'PF Nurse Emp', 'user_id': self.nurse.id})
        # An admin employee so action_start_service etc. have an employee.
        if not self.env.user.employee_id:
            self.env['hr.employee'].create(
                {'name': 'PF Admin Emp', 'user_id': self.env.user.id})
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('health_messaging.enabled', 'True')
        ICP.set_param('health_messaging.dry_run', 'True')
        ICP.set_param('health_family_messages.enabled', 'True')
        ICP.set_param('health_family_messages.max_per_hour', '10')
        self.fso = self._make_fso(self.patient, assign=True)

    # -- fixture helpers ---------------------------------------------------
    def _make_fso(self, patient, assign=False):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120, 'service_type': 'home_visit'})
        so = self.env['sale.order'].create({
            'partner_id': patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 1, 'price_unit': 100.0})]})
        fso.sale_order_id = so.id
        fso.booking_timezone = 'Asia/Ho_Chi_Minh'
        if assign:
            fso.action_assign_staff_to_fso(self.nurse_emp.id,
                                           assignment_role='lead')
            fso.action_confirm_booking()
        return fso

    def _relation(self, patient=None, opt_in=True):
        return self.env['health.client.relation'].create({
            'client_id': (patient or self.patient).id,
            'representative_id': self.representative.id,
            'role': 'caregiver', 'relationship_type': 'child',
            'receives_visit_updates': opt_in, 'can_receive_medical_info': True})

    def _grant_consent(self, patient=None):
        consent = self.env['health.consent'].create({
            'client_id': (patient or self.patient).id,
            'consent_type': 'data_sharing', 'method': 'verbal',
            'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today()})
        consent.action_grant()
        return consent

    def _thread(self, patient=None, relation=None):
        relation = relation or self._relation(patient)
        return self.env['health.family.thread']._get_or_create(
            patient or self.patient, relation)

    def _auth_nurse(self):
        self.authenticate(self.nurse.login, self.nurse.login)

    def _get(self, order_id):
        return self.url_open(
            '/health_pwa/api/fso/%s/family_messages' % order_id).json()

    def _post(self, order_id, sub, payload):
        return self.url_open(
            '/health_pwa/api/fso/%s/family_messages/%s' % (order_id, sub),
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}).json()

    def _out_msgs(self, thread):
        return thread.message_ids.filtered(lambda m: m.direction == 'out')

    # =================================================================
    # 1 — Scope
    # =================================================================
    def test_assigned_nurse_gets_threads(self):
        self._grant_consent()
        thread = self._thread()
        thread.post_family_message('Mum had a bad night', fso=self.fso)
        self._auth_nurse()
        res = self._get(self.fso.id)
        self.assertTrue(res['success'])
        self.assertTrue(res['data']['enabled'])
        self.assertEqual(len(res['data']['threads']), 1)
        bodies = [m['body'] for m in res['data']['threads'][0]['messages']]
        self.assertIn('Mum had a bad night', bodies)

    def test_unassigned_nurse_empty(self):
        self._grant_consent()
        self._thread()
        other_fso = self._make_fso(self.patient, assign=False)  # nurse NOT assigned
        self._auth_nurse()
        res = self._get(other_fso.id)
        self.assertFalse(res['data']['enabled'])
        self.assertEqual(res['data']['threads'], [])

    def test_non_employee_user_empty(self):
        self._grant_consent()
        self._thread()
        plain = new_test_user(
            self.env, login='pf_plain_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user')
        self.authenticate(plain.login, plain.login)
        res = self._get(self.fso.id)
        self.assertFalse(res['data']['enabled'])

    # =================================================================
    # 2 — Master switch off
    # =================================================================
    def test_master_switch_off(self):
        self._grant_consent()
        thread = self._thread()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.enabled', 'False')
        self._auth_nurse()
        res = self._get(self.fso.id)
        self.assertFalse(res['data']['enabled'])
        reply = self._post(self.fso.id, 'reply',
                           {'thread_id': thread.id, 'body': 'hi'})
        self.assertFalse(reply['success'])
        self.assertEqual(len(self._out_msgs(thread)), 0)

    # =================================================================
    # 3 — Reply POST: out row + read flip + bell clear + ZNS
    # =================================================================
    def test_reply_creates_out_and_clears_bell(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', 'FAMREPLYTPL')
        self._grant_consent()
        thread = self._thread()
        inbound = thread.post_family_message('Please call', fso=self.fso)
        # A family_message bell row for the nurse (as _notify_inbound would make).
        bell = self.env['health.pwa.staff.notification'].sudo().create({
            'user_id': self.nurse.id, 'fso_id': self.fso.id,
            'family_thread_id': thread.id, 'notification_type': 'family_message',
            'message': 'New family message'})
        self._auth_nurse()
        res = self._post(self.fso.id, 'reply',
                         {'thread_id': thread.id, 'body': 'On my way at 2pm'})
        self.assertTrue(res['success'])
        inbound.invalidate_recordset()
        bell.invalidate_recordset()
        thread.invalidate_recordset()
        out = self._out_msgs(thread)
        self.assertEqual(len(out), 1)
        self.assertEqual(out.author_user_id, self.nurse)
        self.assertTrue(inbound.read_by_ops)
        self.assertTrue(bell.is_read)
        rows = self.env['health.outbound.message'].search([
            ('purpose', '=', REPLY_PURPOSE),
            ('partner_id', '=', self.representative.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'simulated')

    def test_reply_empty_template_no_ping(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', '')
        self._grant_consent()
        thread = self._thread()
        self._auth_nurse()
        self._post(self.fso.id, 'reply', {'thread_id': thread.id, 'body': 'hi'})
        rows = self.env['health.outbound.message'].search([
            ('purpose', '=', REPLY_PURPOSE),
            ('partner_id', '=', self.representative.id)])
        self.assertEqual(len(rows), 0)

    # =================================================================
    # 4 — Thread-id spoof
    # =================================================================
    def test_reply_thread_spoof_refused(self):
        self._grant_consent()
        # A thread that belongs to ANOTHER patient.
        other_patient = self.env['res.partner'].create({
            'name': 'PF Other', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id, 'mobile': '0911222333'})
        other_rel = self.env['health.client.relation'].create({
            'client_id': other_patient.id,
            'representative_id': self.representative.id, 'role': 'caregiver',
            'receives_visit_updates': True})
        other_thread = self.env['health.family.thread']._get_or_create(
            other_patient, other_rel)
        self._auth_nurse()
        res = self._post(self.fso.id, 'reply',
                         {'thread_id': other_thread.id, 'body': 'leak'})
        self.assertFalse(res['success'])
        self.assertEqual(len(self._out_msgs(other_thread)), 0)

    # =================================================================
    # 5 — FB-047 update fan-out
    # =================================================================
    def test_fb047_update_fanout(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_pwa_family.zns_template_update', 'FAMUPDTPL')
        self._grant_consent()
        eligible = self._relation(opt_in=True)
        # A second relation that is NOT opted in -> excluded from the fan-out.
        self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': self.env['res.partner'].create(
                {'name': 'PF Rep2', 'is_representative': True,
                 'mobile': '0900111222'}).id,
            'role': 'caregiver', 'receives_visit_updates': False})
        self._auth_nurse()
        res = self._post(self.fso.id, 'update',
                         {'body': 'Ca thăm khám đã hoàn tất tốt đẹp.'})
        self.assertTrue(res['success'])
        self.assertEqual(res['data']['sent'], 1)
        thread = self.env['health.family.thread'].search([
            ('patient_id', '=', self.patient.id),
            ('relation_id', '=', eligible.id)])
        self.assertEqual(len(thread), 1)
        self.assertEqual(len(self._out_msgs(thread)), 1)
        rows = self.env['health.outbound.message'].search([
            ('purpose', '=', UPDATE_PURPOSE), ('fso_id', '=', self.fso.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'simulated')
        # Retry -> the family_update ping deduped (still one outbound row).
        self._post(self.fso.id, 'update', {'body': 'again'})
        rows2 = self.env['health.outbound.message'].search([
            ('purpose', '=', UPDATE_PURPOSE), ('fso_id', '=', self.fso.id)])
        self.assertEqual(len(rows2), 1)

    def test_fb047_zero_eligible_friendly(self):
        # No opted-in relation at all -> friendly refusal, no rows.
        self._grant_consent()
        self._relation(opt_in=False)
        self._auth_nurse()
        res = self._post(self.fso.id, 'update', {'body': 'update text'})
        self.assertTrue(res['success'])
        self.assertEqual(res['data']['sent'], 0)
        self.assertEqual(self.env['health.outbound.message'].search_count([
            ('purpose', '=', UPDATE_PURPOSE), ('fso_id', '=', self.fso.id)]), 0)

    def test_fb047_empty_template_no_row(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_pwa_family.zns_template_update', '')
        self._grant_consent()
        self._relation(opt_in=True)
        self._auth_nurse()
        res = self._post(self.fso.id, 'update', {'body': 'done well'})
        self.assertEqual(res['data']['sent'], 1)
        self.assertEqual(self.env['health.outbound.message'].search_count([
            ('purpose', '=', UPDATE_PURPOSE), ('fso_id', '=', self.fso.id)]), 0)

    # =================================================================
    # 6 — Sanitization via the shared _sanitize_body
    # =================================================================
    def test_over_length_reply_refused(self):
        self._grant_consent()
        thread = self._thread()
        self._auth_nurse()
        res = self._post(self.fso.id, 'reply',
                         {'thread_id': thread.id, 'body': 'a' * 3000})
        self.assertFalse(res['success'])
        self.assertEqual(len(self._out_msgs(thread)), 0)

    def test_html_stripped_in_reply(self):
        self._grant_consent()
        thread = self._thread()
        self._auth_nurse()
        self._post(self.fso.id, 'reply',
                   {'thread_id': thread.id,
                    'body': '<script>alert(1)</script>Xin chào'})
        out = self._out_msgs(thread)
        self.assertEqual(len(out), 1)
        self.assertNotIn('<script>', out.body or '')
        self.assertIn('Xin chào', out.body)

    # =================================================================
    # 9 — Append-only untouched (no endpoint can edit/delete)
    # =================================================================
    def test_append_only_untouched(self):
        self._grant_consent()
        thread = self._thread()
        msg = thread.post_family_message('keep me', fso=self.fso)
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            msg.body = 'tampered'

    # =================================================================
    # Review fixes — route-keyed seam context + closed threads + unread
    # =================================================================
    def test_get_returns_order_context(self):
        # The order screen is offline-first (ledger §31): the panel JS gets
        # the order id/state from THIS endpoint, not the base FSO GET.
        self._grant_consent()
        self._thread()
        self._auth_nurse()
        res = self._get(self.fso.id)
        self.assertEqual(res['data']['order_id'], self.fso.id)
        self.assertEqual(res['data']['order_state'], self.fso.state)

    def test_reply_to_closed_thread_refused(self):
        self._grant_consent()
        thread = self._thread()
        thread.sudo().write({'state': 'closed'})
        self._auth_nurse()
        res = self._post(self.fso.id, 'reply',
                         {'thread_id': thread.id, 'body': 'anyone?'})
        self.assertFalse(res['success'])
        self.assertEqual(len(self._out_msgs(thread)), 0)

    def test_update_skips_closed_thread(self):
        self._grant_consent()
        thread = self._thread()
        thread.sudo().write({'state': 'closed'})
        self._auth_nurse()
        res = self._post(self.fso.id, 'update', {'body': 'All done today.'})
        self.assertTrue(res['success'])
        self.assertEqual(res['data']['sent'], 0)
        self.assertEqual(len(self._out_msgs(thread)), 0)

    def test_update_preserves_unread_state(self):
        # A one-tap update is not the nurse reading the thread — the ops
        # inbox unread count and the bell rows must survive it.
        self._grant_consent()
        thread = self._thread()
        thread.post_family_message('unanswered question', fso=self.fso)
        self.assertEqual(thread.unread_ops_count, 1)
        self._auth_nurse()
        res = self._post(self.fso.id, 'update', {'body': 'Visit went well.'})
        self.assertTrue(res['success'])
        self.assertEqual(res['data']['sent'], 1)
        self.assertEqual(len(self._out_msgs(thread)), 1)
        self.assertEqual(thread.unread_ops_count, 1)
        inbound = thread.message_ids.filtered(lambda m: m.direction == 'in')
        self.assertFalse(inbound.read_by_ops)


# =====================================================================
# 3b — action_send_reply still works after the _post_team_reply refactor
# =====================================================================
@tagged('post_install', '-at_install')
class TestOpsReplyRefactor(HttpCase):

    def setUp(self):
        super().setUp()
        (self.province, self.facility, self.patient, self.representative,
         self.product) = _fixture(self.env)
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.enabled', 'True')

    def test_action_send_reply_thin_wrapper(self):
        relation = self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': self.representative.id, 'role': 'caregiver',
            'receives_visit_updates': True})
        thread = self.env['health.family.thread']._get_or_create(
            self.patient, relation)
        thread.reply_text = 'Ops reply via the thin wrapper'
        thread.action_send_reply()
        out = thread.message_ids.filtered(lambda m: m.direction == 'out')
        self.assertEqual(len(out), 1)
        self.assertEqual(out.body, 'Ops reply via the thin wrapper')
        self.assertFalse(thread.reply_text)


# =====================================================================
# 8 — Shell HttpCase: fammsg assets served at 1.14.0
# =====================================================================
@tagged('post_install', '-at_install')
class TestShellAssets(HttpCase):

    def test_shell_serves_fammsg_at_1_10_0(self):
        user = new_test_user(
            self.env, login='pf_shell_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('fammsg.css?v=1.14.0', body)
        self.assertIn('fammsg.js?v=1.14.0', body)
        self.assertIn('1.14.0', body)
        # Co-resident PWA layers still served after the bump.
        self.assertIn('daystrip.js?v=1.14.0', body)


# =====================================================================
# 9 — health_pwa api_fso_detail scope + sudo (PWA reliability phase §2.3)
#     Lives here (health_pwa has no tests/ dir) because this base already
#     builds an assigned nurse + FSO fixture; conventions §3 authorises
#     placing health_pwa tests in a pin suite.
# =====================================================================
@tagged('post_install', '-at_install')
class TestFsoDetailScope(PwaFamilyBase):

    # The response contract the booking modal + fammsg.js consume — snapshot
    # the key set so a future refactor that drops a key fails loudly.
    EXPECTED_KEYS = {
        'id', 'name', 'patient_name', 'state', 'patient', 'primary_contact',
        'quote_items', 'scheduled_datetime', 'scheduled_duration',
        'confirmation_requirements',
    }

    def _detail(self, order_id):
        return self.url_open('/health_pwa/api/fso/%s' % order_id).json()

    def test_assigned_nurse_gets_detail(self):
        # The assigned nurse has NO catchment / sale.order ACL, yet the
        # scope-check + sudo must still return their own visit (200 + data).
        self._auth_nurse()
        res = self._detail(self.fso.id)
        self.assertTrue(res['success'], res)
        self.assertEqual(res['data']['id'], self.fso.id)
        # Response keys unchanged by the sudo refactor.
        self.assertTrue(
            self.EXPECTED_KEYS.issubset(set(res['data'].keys())),
            'missing keys: %s' % (self.EXPECTED_KEYS - set(res['data'].keys())))

    def test_unassigned_nurse_refused(self):
        # A visit the nurse is NOT assigned to and cannot read by rule → 403.
        other = self._make_fso(self.patient, assign=False)
        self._auth_nurse()
        res = self._detail(other.id)
        self.assertFalse(res['success'], res)
        self.assertIn('error', res)
