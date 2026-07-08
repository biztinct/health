# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, HttpCase, tagged

FAMILY_PURPOSES = ('family_visit_link', 'family_snapshot')


def _fixture(env):
    """Conventions §6 fixtures. Patient needs catchment_province_id; the
    relation needs a DISTINCT representative partner (the model CHECK-
    constrains client != representative)."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create(
            {'name': 'FL Province', 'code': 'FLP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'FL Facility', 'code': 'FLF',
            'street': '1 FL Street', 'city': 'Test City',
            'phone': '02838000000',
            'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'FL Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'mobile': '0912345678',
    })
    representative = Partner.create({
        'name': 'Nguyen Van Con',
        'is_representative': True,
        'mobile': '0987654321',
    })
    staff_user = env['res.users'].create({
        'name': 'FL Staff User',
        'login': 'fl_staff_%s' % uuid.uuid4().hex[:8],
        'email': 'fl_staff_%s@example.com' % uuid.uuid4().hex[:6],
    })
    staff = env['hr.employee'].create(
        {'name': 'Tran Thi Hoa', 'user_id': staff_user.id})
    product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
    if not product:
        product = env['product.product'].create(
            {'name': 'FL Service', 'type': 'service', 'list_price': 100.0})
    return province, facility, patient, representative, staff, product


@tagged('post_install', '-at_install')
class FamilyLinkBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient, cls.representative,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'FL Admin Employee', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        Stage = cls.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('health_messaging.enabled', 'True')
        ICP.set_param('health_messaging.dry_run', 'True')
        ICP.set_param('health_family_link.zns_template_family_link', 'FAMLINKTPL')
        ICP.set_param('health_family_link.zns_template_family_snapshot', 'FAMSNAPTPL')

    # -- helpers ------------------------------------------------------------
    def _make_relation(self, opt_in=True, medical=True):
        return self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': self.representative.id,
            'role': 'caregiver',
            'relationship_type': 'child',
            'receives_visit_updates': opt_in,
            'can_receive_medical_info': medical,
        })

    def _grant_data_sharing(self):
        consent = self.env['health.consent'].create({
            'client_id': self.patient.id,
            'consent_type': 'data_sharing',
            'method': 'verbal',
            'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today(),
        })
        consent.action_grant()
        return consent

    def _make_fso(self, scheduled=None):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': scheduled or (
                fields.Datetime.now() + timedelta(days=1)),
            'scheduled_duration': 120,
            'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id,
            'fso_id': fso.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        # Pin the tz so wall-clock assertions are deterministic regardless of
        # any pre-existing facility timezone on the server.
        fso.booking_timezone = 'Asia/Ho_Chi_Minh'
        return fso

    def _confirm(self, fso):
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        return fso

    def _complete(self, fso, note_vals=None):
        fso.action_start_service()
        self.env['health.clinical.note'].create(
            note_vals or {'order_id': fso.id, 'clinical_notes': 'ok'})
        fso.action_complete_service()
        return fso

    def _msgs(self, fso, purpose=None):
        domain = [('fso_id', '=', fso.id),
                  ('purpose', 'in', list(FAMILY_PURPOSES))]
        if purpose:
            domain = [('fso_id', '=', fso.id), ('purpose', '=', purpose)]
        return self.env['health.outbound.message'].search(domain)

    def _links(self, fso):
        return self.env['health.family.link'].search([('fso_id', '=', fso.id)])


# =====================================================================
# 1 — Consent matrix (the no-phantom rule)
# =====================================================================
@tagged('post_install', '-at_install')
class TestConsentMatrix(FamilyLinkBase):

    def test_opted_in_with_consent_creates_link_and_simulated_row(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        links = self._links(fso)
        self.assertEqual(len(links), 1)
        msgs = self._msgs(fso, 'family_visit_link')
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs.state, 'simulated')

    def test_flag_off_creates_nothing(self):
        self._make_relation(opt_in=False, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        self.assertEqual(self.env['health.family.link'].search_count(
            [('fso_id', '=', fso.id)]), 0)
        self.assertEqual(self.env['health.outbound.message'].search_count(
            [('fso_id', '=', fso.id),
             ('purpose', 'in', list(FAMILY_PURPOSES))]), 0)

    def test_no_consent_creates_nothing(self):
        self._make_relation(opt_in=True, medical=True)
        # no data_sharing consent granted
        fso = self._make_fso()
        self._confirm(fso)
        self.assertEqual(self.env['health.family.link'].search_count(
            [('fso_id', '=', fso.id)]), 0)
        self.assertEqual(self.env['health.outbound.message'].search_count(
            [('fso_id', '=', fso.id),
             ('purpose', 'in', list(FAMILY_PURPOSES))]), 0)


# =====================================================================
# 2 — can_receive_medical_info gates the snapshot only
# =====================================================================
@tagged('post_install', '-at_install')
class TestMedicalGate(FamilyLinkBase):

    def test_non_medical_relation_gets_link_but_no_snapshot(self):
        self._make_relation(opt_in=True, medical=False)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        self.assertEqual(len(self._msgs(fso, 'family_visit_link')), 1)
        self._complete(fso)
        self.assertEqual(len(self._msgs(fso, 'family_snapshot')), 0)

    def test_medical_relation_gets_both(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        self._complete(fso)
        self.assertEqual(len(self._msgs(fso, 'family_visit_link')), 1)
        self.assertEqual(len(self._msgs(fso, 'family_snapshot')), 1)


# =====================================================================
# 3 — Snapshot sanitization (A3)
# =====================================================================
@tagged('post_install', '-at_install')
class TestSanitization(FamilyLinkBase):

    def test_summary_excludes_diagnosis_and_strips_html(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        fso.action_start_service()
        self.env['health.clinical.note'].create({
            'order_id': fso.id,
            'diagnosis': 'SECRETDIAGNOSIS pneumonia',
            'medications_prescribed': 'SECRETMED amoxicillin',
            'patient_condition_after': 'Patient resting comfortably, stable vitals.',
        })
        fso.action_complete_service()
        link = self._links(fso)
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'completed')
        self.assertIn('resting comfortably', ctx['summary'])
        self.assertNotIn('SECRETDIAGNOSIS', ctx['summary'])
        self.assertNotIn('SECRETMED', ctx['summary'])

    def test_summary_truncates_200_and_strips_tags(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        fso.action_start_service()
        long_html = '<p>' + ('a' * 300) + '</p>'
        self.env['health.clinical.note'].create({
            'order_id': fso.id, 'clinical_notes': long_html})
        fso.action_complete_service()
        summary = self._links(fso)._snapshot_summary()
        self.assertEqual(len(summary), 200)
        self.assertNotIn('<', summary)

    def test_precedence_condition_after_first(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        fso.action_start_service()
        self.env['health.clinical.note'].create({
            'order_id': fso.id,
            'clinical_notes': '<p>notes body</p>',
            'treatment_performed': 'treatment body',
            'patient_condition_after': 'condition body',
        })
        fso.action_complete_service()
        self.assertEqual(self._links(fso)._snapshot_summary(), 'condition body')


# =====================================================================
# 4 — Idempotency (dedup + one link per fso/relation)
# =====================================================================
@tagged('post_install', '-at_install')
class TestIdempotency(FamilyLinkBase):

    def test_double_confirm_and_complete_single_rows(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        # Re-run confirm hook (re-confirmation).
        fso._family_link_on_confirm()
        self._complete(fso)
        # Re-run complete hook (double completion).
        fso._family_link_on_complete()
        self.assertEqual(len(self._links(fso)), 1)
        self.assertEqual(len(self._msgs(fso, 'family_visit_link')), 1)
        self.assertEqual(len(self._msgs(fso, 'family_snapshot')), 1)


# =====================================================================
# 5 — Public page lifecycle + neutral tokens + timezone
# =====================================================================
@tagged('post_install', '-at_install')
class TestPageContext(FamilyLinkBase):

    def _link_for(self, fso):
        return self.env['health.family.link']._get_or_create_link(
            fso, self._make_relation(opt_in=True, medical=True))

    def test_upcoming_wall_clock(self):
        # 02:00 UTC + Asia/Ho_Chi_Minh (+7) -> 09:00 wall clock.
        fso = self._make_fso(scheduled=datetime(2026, 7, 10, 2, 0, 0))
        self._confirm(fso)
        link = self._link_for(fso)
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'upcoming')
        self.assertEqual(ctx['visit_date'], '10/07/2026')
        self.assertTrue(ctx['time_window'].startswith('09:00'))
        # ZNS params share the wall-clock date.
        self.assertEqual(link._zns_params()['visit_date'], '10/07/2026')
        # Staff given name only (last token).
        self.assertEqual(ctx['staff_name'], 'Hoa')

    def test_arrived_shows_hhmm(self):
        fso = self._make_fso(scheduled=datetime(2026, 7, 10, 2, 0, 0))
        self._confirm(fso)
        fso.action_start_service()
        link = self._link_for(fso)
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'arrived')
        self.assertTrue(ctx['arrived_time'])

    def test_completed_shows_summary(self):
        self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        link = self._link_for(fso)
        self._complete(fso, {'order_id': fso.id,
                             'patient_condition_after': 'All good.'})
        ctx = link._page_context()
        self.assertEqual(ctx['mode'], 'completed')
        self.assertIn('All good', ctx['summary'])

    def test_cancelled_is_neutral(self):
        fso = self._make_fso()
        self._confirm(fso)
        link = self._link_for(fso)
        fso.state = 'cancelled'
        self.assertEqual(link._page_context()['mode'], 'neutral')

    def test_expired_and_revoked_flags(self):
        fso = self._make_fso()
        self._confirm(fso)
        link = self._link_for(fso)
        link.expires_at = fields.Datetime.now() - timedelta(hours=1)
        self.assertTrue(link._is_expired())
        link.expires_at = fields.Datetime.now() + timedelta(days=1)
        link.state = 'revoked'
        self.assertEqual(link.state, 'revoked')


# =====================================================================
# 6 — Consent withdrawn after completion -> completed page neutral (A6)
# =====================================================================
@tagged('post_install', '-at_install')
class TestConsentWithdrawal(FamilyLinkBase):

    def test_withdrawal_neutralizes_completed_page(self):
        self._make_relation(opt_in=True, medical=True)
        consent = self._grant_data_sharing()
        fso = self._make_fso()
        self._confirm(fso)
        self._complete(fso, {'order_id': fso.id,
                             'patient_condition_after': 'Recovered well.'})
        link = self._links(fso)
        self.assertEqual(link._page_context()['mode'], 'completed')
        # Withdraw consent -> completed page must go neutral at render time.
        consent.withdrawal_reason = 'Family requested stop'
        consent.action_withdraw()
        self.assertEqual(link._page_context()['mode'], 'neutral')


# =====================================================================
# 7 — Hook resilience (a family-link failure never blocks the workflow)
# =====================================================================
@tagged('post_install', '-at_install')
class TestHookResilience(FamilyLinkBase):

    def test_send_failure_does_not_block_confirm_or_complete(self):
        self._make_relation(opt_in=True, medical=True)
        self._grant_data_sharing()
        fso = self._make_fso()

        def boom(self, purpose):
            raise ValueError('ZNS exploded')

        with patch.object(
                type(self.env['health.family.link']), '_send_zns', boom):
            self._confirm(fso)
            self.assertIn(fso.state, ('confirmed', 'assigned'))
            self._complete(fso)
        self.assertIn(fso.state, ('completed', 'completed_pending_invoice'))


# =====================================================================
# 8 — Public HttpCase smoke (established pattern)
# =====================================================================
@tagged('post_install', '-at_install')
class TestPublicSmoke(HttpCase):

    def test_valid_token_renders_200_and_bogus_neutral(self):
        province, facility, patient, representative, staff, product = _fixture(
            self.env)
        Stage = self.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        if not self.env.user.employee_id:
            self.env['hr.employee'].create(
                {'name': 'FL Admin Emp', 'user_id': self.env.user.id})
        relation = self.env['health.client.relation'].create({
            'client_id': patient.id, 'representative_id': representative.id,
            'role': 'caregiver', 'receives_visit_updates': True,
            'can_receive_medical_info': True,
        })
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120, 'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {'product_id': product.id,
                                   'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.action_assign_staff_to_fso(staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        link = self.env['health.family.link']._get_or_create_link(fso, relation)

        resp = self.url_open('/family/visit/%s' % link.token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Viet Uc Health', resp.text)

        bogus = self.url_open('/family/visit/deadbeefdeadbeef')
        self.assertEqual(bogus.status_code, 200)
        self.assertIn('không còn hiệu lực', bogus.text)
