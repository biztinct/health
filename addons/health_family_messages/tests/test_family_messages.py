# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, HttpCase, tagged

REPLY_PURPOSE = 'family_message_reply'


def _fixture(env):
    """Conventions §6 fixtures (cloned from health_family_link). Patient needs
    catchment_province_id; the relation needs a DISTINCT representative."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create(
            {'name': 'FM Province', 'code': 'FMP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'FM Facility', 'code': 'FMF',
            'street': '1 FM Street', 'city': 'Test City',
            'phone': '02838000000', 'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'FM Patient', 'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id, 'mobile': '0912345678',
    })
    representative = Partner.create({
        'name': 'Nguyen Van Con', 'is_representative': True,
        'mobile': '0987654321',
    })
    staff_user = env['res.users'].create({
        'name': 'FM Nurse User',
        'login': 'fm_nurse_%s' % uuid.uuid4().hex[:8],
        'email': 'fm_nurse_%s@example.com' % uuid.uuid4().hex[:6],
    })
    staff = env['hr.employee'].create(
        {'name': 'Tran Thi Hoa', 'user_id': staff_user.id})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
    if not product:
        product = env['product.product'].create(
            {'name': 'FM Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, patient, representative, staff, product


@tagged('post_install', '-at_install')
class FamilyMessagesBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.representative,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'FM Admin Employee', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        Stage = cls.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('health_messaging.enabled', 'True')
        ICP.set_param('health_messaging.dry_run', 'True')
        ICP.set_param('health_family_messages.enabled', 'True')
        ICP.set_param('health_family_messages.max_per_hour', '10')
        cls.Thread = cls.env['health.family.thread']
        cls.Message = cls.env['health.family.message']

    # -- helpers -----------------------------------------------------------
    def _relation(self, opt_in=True):
        return self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': self.representative.id,
            'role': 'caregiver', 'relationship_type': 'child',
            'receives_visit_updates': opt_in, 'can_receive_medical_info': True,
        })

    def _grant_data_sharing(self):
        consent = self.env['health.consent'].create({
            'client_id': self.patient.id, 'consent_type': 'data_sharing',
            'method': 'verbal', 'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today(),
        })
        consent.action_grant()
        return consent

    def _make_fso(self, scheduled=None):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': scheduled or (
                fields.Datetime.now() + timedelta(days=1)),
            'scheduled_duration': 120, 'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.booking_timezone = 'Asia/Ho_Chi_Minh'
        return fso

    def _confirm(self, fso):
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        return fso

    def _thread(self, relation=None):
        relation = relation or self._relation()
        return self.Thread._get_or_create(self.patient, relation)


# =====================================================================
# 1 — Thread uniqueness
# =====================================================================
@tagged('post_install', '-at_install')
class TestThreadUniqueness(FamilyMessagesBase):

    def test_second_thread_for_pair_refused(self):
        relation = self._relation()
        self.Thread.create({'patient_id': self.patient.id,
                            'relation_id': relation.id})
        with self.assertRaises(UserError):
            self.Thread.create({'patient_id': self.patient.id,
                               'relation_id': relation.id})

    def test_get_or_create_idempotent(self):
        relation = self._relation()
        t1 = self.Thread._get_or_create(self.patient, relation)
        t2 = self.Thread._get_or_create(self.patient, relation)
        self.assertEqual(t1, t2)


# =====================================================================
# 2 — Dual-field crypto
# =====================================================================
@tagged('post_install', '-at_install')
class TestCrypto(FamilyMessagesBase):

    def test_body_stored_encrypted_read_plaintext(self):
        thread = self._thread()
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'in',
            'body': 'Mum had a bad night', 'author_label': 'Con gái'})
        # Stored column carries the enc$1$ token; plaintext round-trips.
        self.env.cr.execute(
            'SELECT body_enc FROM health_family_message WHERE id = %s', (msg.id,))
        raw = self.env.cr.fetchone()[0]
        self.assertTrue(raw.startswith('enc$1$'))
        self.assertEqual(msg.body, 'Mum had a bad night')


# =====================================================================
# 3 — Append-only
# =====================================================================
@tagged('post_install', '-at_install')
class TestAppendOnly(FamilyMessagesBase):

    def _ops_user(self):
        return self.env['res.users'].create({
            'name': 'FM Ops', 'login': 'fm_ops_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_operations_manager').id])],
            'catchment_province_id': self.province.id,
        })

    def test_edit_body_raises(self):
        thread = self._thread()
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'in', 'body': 'original'})
        with self.assertRaises(UserError):
            msg.body = 'tampered'

    def test_unlink_as_ops_raises(self):
        thread = self._thread()
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'in', 'body': 'keep me'})
        ops = self._ops_user()
        with self.assertRaises(UserError):
            msg.with_user(ops).unlink()

    def test_read_flag_flip_allowed(self):
        thread = self._thread()
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'in', 'body': 'hi'})
        msg.read_by_ops = True
        self.assertTrue(msg.read_by_ops)


# =====================================================================
# 5 — Rate limit (per-thread rolling hour cap)
# =====================================================================
@tagged('post_install', '-at_install')
class TestRateLimit(FamilyMessagesBase):

    def test_eleventh_send_refused(self):
        thread = self._thread()
        for i in range(10):
            self.assertTrue(
                thread.post_family_message('msg %s' % i, fso=None))
        refused = thread.post_family_message('one too many', fso=None)
        self.assertFalse(refused)
        self.assertEqual(self.Message.search_count([
            ('thread_id', '=', thread.id), ('direction', '=', 'in')]), 10)


# =====================================================================
# 6 — Length cap + HTML strip
# =====================================================================
@tagged('post_install', '-at_install')
class TestSanitization(FamilyMessagesBase):

    def test_over_length_refused(self):
        thread = self._thread()
        with self.assertRaises(ValidationError):
            self.Message.create({
                'thread_id': thread.id, 'direction': 'in',
                'body': 'a' * 3000})

    def test_html_stripped_to_plain(self):
        thread = self._thread()
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'in',
            'body': '<script>alert(1)</script>Hello'})
        self.assertNotIn('<script>', msg.body or '')
        self.assertIn('Hello', msg.body)


# =====================================================================
# 7 — Notify on inbound (best-effort legs)
# =====================================================================
@tagged('post_install', '-at_install')
class TestNotify(FamilyMessagesBase):

    def _manager_user(self):
        mgr_user = self.env['res.users'].create({
            'name': 'FM Manager', 'login': 'fm_mgr_%s' % uuid.uuid4().hex[:8],
            'email': 'fm_mgr_%s@example.com' % uuid.uuid4().hex[:6],
        })
        mgr_emp = self.env['hr.employee'].create(
            {'name': 'FM Manager Emp', 'user_id': mgr_user.id})
        self.facility.facility_manager_id = mgr_emp.id
        return mgr_user

    def test_bell_rows_and_activity_created(self):
        mgr_user = self._manager_user()
        relation = self._relation()
        fso = self._make_fso()
        self._confirm(fso)
        fso.primary_nurse_id = self.staff.id
        thread = self.Thread._get_or_create(self.patient, relation)
        msg = thread.post_family_message('Please call me', fso=fso)
        self.assertTrue(msg)
        Notif = self.env['health.pwa.staff.notification']
        self.assertEqual(Notif.search_count([
            ('user_id', '=', self.staff.user_id.id),
            ('notification_type', '=', 'family_message')]), 1)
        self.assertEqual(Notif.search_count([
            ('user_id', '=', mgr_user.id),
            ('notification_type', '=', 'family_message')]), 1)
        self.assertTrue(fso.activity_ids.filtered(
            lambda a: 'family' in (a.summary or '').lower()))

    def test_push_failure_does_not_block_message(self):
        self._manager_user()
        relation = self._relation()
        fso = self._make_fso()
        self._confirm(fso)
        fso.primary_nurse_id = self.staff.id
        thread = self.Thread._get_or_create(self.patient, relation)
        boom = MagicMock()
        boom.send_push_notification.side_effect = ValueError('push down')
        with patch.object(type(self.env['health.pwa.config']),
                          'get_push_config', return_value=boom):
            msg = thread.post_family_message('still delivered', fso=fso)
        self.assertTrue(msg)
        self.assertEqual(msg.direction, 'in')


# =====================================================================
# 8 / 11 — Reply flow + rails matrix for the new purpose
# =====================================================================
@tagged('post_install', '-at_install')
class TestReplyFlow(FamilyMessagesBase):

    def _ops_user(self):
        return self.env['res.users'].create({
            'name': 'FM Ops2', 'login': 'fm_ops2_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_operations_manager').id])],
            'catchment_province_id': self.province.id,
        })

    def _out_rows(self, thread):
        return self.env['health.outbound.message'].search([
            ('purpose', '=', REPLY_PURPOSE),
            ('partner_id', '=', self.representative.id)])

    def test_reply_creates_out_message_and_simulated_ping(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', 'FAMREPLYTPL')
        relation = self._relation()
        fso = self._make_fso()
        self._confirm(fso)
        thread = self.Thread._get_or_create(self.patient, relation)
        ops = self._ops_user()
        thread.with_user(ops).write({'reply_text': 'We will visit at 2pm'})
        thread.with_user(ops).action_send_reply()
        out_msg = thread.message_ids.filtered(lambda m: m.direction == 'out')
        self.assertEqual(len(out_msg), 1)
        self.assertEqual(out_msg.body, 'We will visit at 2pm')
        rows = self._out_rows(thread)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'simulated')

    def test_empty_template_creates_no_ping(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', '')
        relation = self._relation()
        thread = self.Thread._get_or_create(self.patient, relation)
        thread.write({'reply_text': 'hello'})
        thread.action_send_reply()
        self.assertEqual(len(self._out_rows(thread)), 0)

    def test_reply_ping_dedup_on_retry(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', 'FAMREPLYTPL')
        relation = self._relation()
        thread = self.Thread._get_or_create(self.patient, relation)
        msg = self.Message.create({
            'thread_id': thread.id, 'direction': 'out', 'body': 'hi',
            'author_user_id': self.env.uid, 'author_label': 'Ops'})
        thread._send_reply_zns(msg)
        thread._send_reply_zns(msg)
        self.assertEqual(len(self._out_rows(thread)), 1)

    def test_rails_disabled_skips(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.zns_template_reply', 'FAMREPLYTPL')
        self.env['ir.config_parameter'].sudo().set_param(
            'health_messaging.enabled', 'False')
        try:
            relation = self._relation()
            thread = self.Thread._get_or_create(self.patient, relation)
            msg = self.Message.create({
                'thread_id': thread.id, 'direction': 'out', 'body': 'hi',
                'author_user_id': self.env.uid, 'author_label': 'Ops'})
            row = thread._send_reply_zns(msg)
            self.assertEqual(row.state, 'skipped')
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'health_messaging.enabled', 'True')


# =====================================================================
# 9 — Access control (non-ops raises; other-facility ops sees nothing)
# =====================================================================
@tagged('post_install', '-at_install')
class TestAccess(FamilyMessagesBase):

    def test_non_ops_user_cannot_read(self):
        thread = self._thread()
        plain = self.env['res.users'].create({
            'name': 'FM Plain', 'login': 'fm_plain_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            thread.with_user(plain).read(['patient_id'])

    def test_other_catchment_ops_sees_nothing(self):
        thread = self._thread()
        ops_here = self.env['res.users'].create({
            'name': 'FM OpsA', 'login': 'fm_opsa_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_operations_manager').id])],
            'catchment_province_id': self.province.id,
        })
        self.assertTrue(self.Thread.with_user(ops_here).search(
            [('id', '=', thread.id)]))
        far_province = self.env['health.catchment.province'].create(
            {'name': 'FM Far', 'code': 'FMFAR'})
        ops_far = self.env['res.users'].create({
            'name': 'FM OpsB', 'login': 'fm_opsb_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('health_base.group_healthcare_operations_manager').id])],
            'catchment_province_id': far_province.id,
        })
        self.assertFalse(self.Thread.with_user(ops_far).search(
            [('id', '=', thread.id)]))


# =====================================================================
# 4 / 10 — Public POST send + GET render (HttpCase; NO --no-http)
# =====================================================================
@tagged('post_install', '-at_install')
class TestPublicMessaging(HttpCase):

    def setUp(self):
        super().setUp()
        (self.province, self.facility, self.patient, self.representative,
         self.staff, self.product) = _fixture(self.env)
        if not self.env.user.employee_id:
            self.env['hr.employee'].create(
                {'name': 'FM Http Emp', 'user_id': self.env.user.id})
        Stage = self.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('health_messaging.enabled', 'True')
        ICP.set_param('health_messaging.dry_run', 'True')
        ICP.set_param('health_family_messages.enabled', 'True')
        ICP.set_param('health_family_messages.max_per_hour', '10')

    def _live_link(self):
        # A fresh patient + representative per scenario so a consent withdrawal
        # or thread in one case never leaks into another (all share one patient
        # otherwise, and check_consent is patient-level).
        patient = self.env['res.partner'].create({
            'name': 'FM Http Patient', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id, 'mobile': '0912345678'})
        representative = self.env['res.partner'].create({
            'name': 'FM Http Rep', 'is_representative': True,
            'mobile': '0987654321'})
        relation = self.env['health.client.relation'].create({
            'client_id': patient.id, 'representative_id': representative.id,
            'role': 'caregiver', 'receives_visit_updates': True,
            'can_receive_medical_info': True,
        })
        consent = self.env['health.consent'].create({
            'client_id': patient.id, 'consent_type': 'data_sharing',
            'method': 'verbal', 'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today(),
        })
        consent.action_grant()
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120, 'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        link = self.env['health.family.link']._get_or_create_link(fso, relation)
        return link, relation, consent, fso

    def _messages(self, link):
        thread = self.env['health.family.thread'].search([
            ('patient_id', '=', link.fso_id.patient_id.id),
            ('relation_id', '=', link.relation_id.id)], limit=1)
        return thread.message_ids if thread else self.env['health.family.message']

    def test_valid_post_creates_inbound_row(self):
        link, relation, consent, fso = self._live_link()
        resp = self.url_open('/family/visit/%s/message' % link.token,
                             data={'body': 'Please send an English speaker'})
        self.assertEqual(resp.status_code, 200)
        msgs = self._messages(link)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs.direction, 'in')
        self.assertEqual(msgs.fso_id, fso)
        self.assertIn('English speaker', msgs.body)

    def test_neutral_and_disabled_paths_create_no_row(self):
        # expired token
        link, relation, consent, fso = self._live_link()
        link.expires_at = fields.Datetime.now() - timedelta(hours=1)
        resp = self.url_open('/family/visit/%s/message' % link.token,
                             data={'body': 'hi'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._messages(link)), 0)

        # revoked token (fresh link)
        link2, rel2, con2, fso2 = self._live_link()
        # reuse the same relation/patient would clash on thread uniqueness; use
        # this link's own state.
        link2.state = 'revoked'
        self.url_open('/family/visit/%s/message' % link2.token,
                      data={'body': 'hi'})
        self.assertEqual(len(self._messages(link2)), 0)

        # master switch off
        link3, rel3, con3, fso3 = self._live_link()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.enabled', 'False')
        self.url_open('/family/visit/%s/message' % link3.token,
                      data={'body': 'hi'})
        self.assertEqual(len(self._messages(link3)), 0)
        self.env['ir.config_parameter'].sudo().set_param(
            'health_family_messages.enabled', 'True')

        # consent withdrawn
        link4, rel4, con4, fso4 = self._live_link()
        con4.withdrawal_reason = 'stop'
        con4.action_withdraw()
        self.url_open('/family/visit/%s/message' % link4.token,
                      data={'body': 'hi'})
        self.assertEqual(len(self._messages(link4)), 0)

    def test_get_renders_thread_and_marks_read(self):
        link, relation, consent, fso = self._live_link()
        thread = self.env['health.family.thread']._get_or_create(
            link.fso_id.patient_id, relation)
        out = self.env['health.family.message'].create({
            'thread_id': thread.id, 'direction': 'out',
            'body': 'We are on our way', 'author_label': 'Ops'})
        resp = self.url_open('/family/visit/%s' % link.token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('We are on our way', resp.text)
        out.invalidate_recordset()
        self.assertTrue(out.read_by_family)
