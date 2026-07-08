# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, HttpCase, tagged


def _fixture(env):
    """Conventions §6 fixtures. Patient needs catchment_province_id +
    primary_facility_id; facility timezone pinned so wall-clock assertions
    are deterministic.

    vietuat carries live availability-matrix data for the real provinces, so
    we create a FRESH isolated province + facility (unique code) and pin the
    test staff to it. Province-scoped live rows are then excluded by the slot
    proposer's province filter, keeping the seeded slots identifiable."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    suffix = uuid.uuid4().hex[:6].upper()
    province = env['health.catchment.province'].create(
        {'name': 'SB Province %s' % suffix, 'code': 'SBP%s' % suffix})
    facility = Facility.create({
        'name': 'SB Facility %s' % suffix, 'code': 'SBF%s' % suffix,
        'street': '1 SB Street', 'city': 'Test City',
        'phone': '02838000000',
        'timezone': 'Asia/Ho_Chi_Minh',
        'catchment_province_id': province.id,
    })
    patient = Partner.create({
        'name': 'Le Van Benh',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'mobile': '0912345678',
    })
    staff_user = env['res.users'].create({
        'name': 'SB Staff User',
        'login': 'sb_staff_%s' % uuid.uuid4().hex[:8],
        'email': 'sb_staff_%s@example.com' % uuid.uuid4().hex[:6],
    })
    staff = env['hr.employee'].create(
        {'name': 'Tran Thi Hoa', 'user_id': staff_user.id,
         'staff_catchment_province_id': province.id})
    product = env['product.product'].search(
        [('sale_ok', '=', True), ('type', '=', 'service')], limit=1)
    if not product:
        product = env['product.product'].create(
            {'name': 'SB Service', 'type': 'service', 'list_price': 100.0,
             'sale_ok': True})
    return province, facility, patient, staff, product


@tagged('post_install', '-at_install')
class SelfBookingBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient,
         cls.staff, cls.product) = _fixture(cls.env)
        if not cls.env.user.employee_id:
            cls.env['hr.employee'].create(
                {'name': 'SB Admin Employee', 'user_id': cls.env.user.id})
            cls.env.user.invalidate_recordset()
        Stage = cls.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('health_messaging.enabled', 'True')
        ICP.set_param('health_messaging.dry_run', 'True')
        ICP.set_param('health_self_booking.zns_template_invite', 'SBTPL')
        ICP.set_param('health_self_booking.fallback_service_product_id', '')
        ICP.set_param('health_self_booking.auto_invite_after_completion', 'False')
        # Snapshot a wide slot window so a seeded slot is never truncated out
        # by any null-catchment live rows that also match the isolated patient.
        ICP.set_param('health_self_booking.slot_count', '100')
        ICP.set_param('health_self_booking.horizon_days', '20')

    # -- helpers ------------------------------------------------------------
    def _make_matrix(self, staff=None, day_offset=1, start=8.5):
        day = fields.Date.today() + timedelta(days=day_offset)
        return self.env['health.staff.availability.matrix'].create({
            'staff_id': (staff or self.staff).id,
            'availability_date': day,
            'start_time': start,
            'end_time': start + 3.0,
            'status': 'available',
            'capacity': 2,
        })

    def _make_package(self, service_type='home_visit', total=5, consumed=0):
        return self.env['health.service.package'].create({
            'name': 'SB Package',
            'patient_id': self.patient.id,
            'service_type': service_type,
            'total_services': total,
            'consumed_services': consumed,
            'package_price': 500.0,
            'state': 'active',
        })

    def _make_completed_fso_with_quote(self):
        """A booked+completed FSO carrying a quote line (A3 branch 2 source)."""
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() - timedelta(days=2),
            'scheduled_duration': 120,
            'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        fso.action_start_service()
        self.env['health.clinical.note'].create(
            {'order_id': fso.id, 'clinical_notes': 'done'})
        fso.action_complete_service()
        return fso

    def _invite(self, raise_if_no_source=False):
        return self.env['health.selfbook.invite']._get_or_create_invite(
            self.patient, raise_if_no_source=raise_if_no_source)

    def _slot_index_for(self, invite, staff, day_offset=1, start=8.5):
        """Find the snapshot index of a slot for a specific staff/day/time.

        vietuat carries live availability-matrix rows (some with a null
        catchment that match every patient), so slot 0 is not necessarily the
        one this test seeded — locate our own slot explicitly."""
        day = (fields.Date.today() + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        for idx, s in enumerate(invite.slots_json or []):
            if (s['staff_id'] == staff.id and s['date'] == day
                    and abs(s['start_time'] - start) < 0.01):
                return idx
        return None

    def _rows(self):
        return self.env['health.outbound.message'].search([
            ('purpose', '=', 'selfbook_invite'),
            ('partner_id', '=', self.patient.id)])


# =====================================================================
# 1 — Invite idempotency
# =====================================================================
@tagged('post_install', '-at_install')
class TestIdempotency(SelfBookingBase):

    def test_two_sends_one_invite_one_row_same_token(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        Invite = self.env['health.selfbook.invite']
        first = Invite.send_invite_for_patient(self.patient)
        second = Invite.send_invite_for_patient(self.patient)
        self.assertEqual(first, second)
        self.assertEqual(first.token, second.token)
        self.assertEqual(Invite.search_count(
            [('patient_id', '=', self.patient.id)]), 1)
        self.assertEqual(len(self._rows()), 1)
        self.assertEqual(first.outbound_message_id.state, 'simulated')


# =====================================================================
# 2 — A3 precedence
# =====================================================================
@tagged('post_install', '-at_install')
class TestSourcePrecedence(SelfBookingBase):

    def test_active_package_wins(self):
        self._make_matrix()
        pkg = self._make_package()
        # Also give a completed FSO — the package must still take precedence.
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.assertEqual(invite.package_id, pkg)
        self.assertFalse(invite.service_product_id)

    def test_last_fso_product_when_no_package(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.assertFalse(invite.package_id)
        self.assertEqual(invite.service_product_id, self.product)

    def test_no_source_empty_fallback_button_raises_auto_skips(self):
        # No package, no completed FSO, empty fallback param.
        with self.assertRaises(UserError):
            self.env['health.selfbook.invite'].send_invite_for_patient(
                self.patient, raise_if_no_source=True)
        # Auto path (raise_if_no_source=False) silently skips.
        invite = self.env['health.selfbook.invite'].send_invite_for_patient(
            self.patient, raise_if_no_source=False)
        self.assertFalse(invite)
        self.assertEqual(self.env['health.selfbook.invite'].search_count(
            [('patient_id', '=', self.patient.id)]), 0)

    def test_config_fallback_product_used(self):
        self._make_matrix()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.fallback_service_product_id', str(self.product.id))
        invite = self._invite()
        self.assertEqual(invite.service_product_id, self.product)
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.fallback_service_product_id', '')


# =====================================================================
# 3 — Accept books (product path + package path)
# =====================================================================
@tagged('post_install', '-at_install')
class TestAccept(SelfBookingBase):

    def test_accept_product_path_creates_confirmed_fso_with_quote(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.assertTrue(invite.slots_json)
        idx = self._slot_index_for(invite, self.staff)
        self.assertIsNotNone(idx)
        res = invite.accept_slot(idx)
        self.assertTrue(res['ok'])
        fso = res['fso']
        self.assertEqual(invite.state, 'booked')
        self.assertEqual(invite.fso_id, fso)
        self.assertIn(fso.state, ('confirmed', 'assigned'))
        # Slot staff assigned as lead.
        lead = self.env['health.staff.assignment'].search([
            ('fso_id', '=', fso.id), ('assignment_role', '=', 'lead')])
        self.assertEqual(lead.staff_id, self.staff)
        # Quote line with the product present.
        self.assertTrue(fso.sale_order_id)
        self.assertIn(self.product, fso.sale_order_id.order_line.product_id)
        # Matrix slot booked for the staff on that date.
        self.assertTrue(self.env['health.staff.availability.matrix'].search_count([
            ('fso_id', '=', fso.id), ('status', '=', 'booked')]))

    def test_accept_package_path_consumes_service_no_quote(self):
        self._make_matrix()
        pkg = self._make_package(total=5, consumed=1)
        invite = self._invite()
        self.assertEqual(invite.package_id, pkg)
        idx = self._slot_index_for(invite, self.staff)
        self.assertIsNotNone(idx)
        res = invite.accept_slot(idx)
        self.assertTrue(res['ok'])
        fso = res['fso']
        self.assertIn(fso.state, ('confirmed', 'assigned'))
        # No quote line on the package path.
        self.assertFalse(fso.sale_order_id)
        # One service consumed by the reservation.
        pkg.invalidate_recordset(['consumed_services'])
        self.assertEqual(pkg.consumed_services, 2)


# =====================================================================
# 4 — Double-accept race -> exactly one FSO
# =====================================================================
@tagged('post_install', '-at_install')
class TestDoubleAccept(SelfBookingBase):

    def test_second_accept_is_noop(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        idx = self._slot_index_for(invite, self.staff)
        self.assertIsNotNone(idx)
        res1 = invite.accept_slot(idx)
        self.assertTrue(res1['ok'])
        first_fso = res1['fso']
        res2 = invite.accept_slot(idx)
        self.assertFalse(res2['ok'])
        self.assertEqual(res2['reason'], 'already_booked')
        self.assertEqual(res2['fso'], first_fso)
        # Exactly one FSO created from this invite.
        self.assertEqual(invite.fso_id, first_fso)


# =====================================================================
# 7 — Booked page wall-clock (02:00 UTC + Asia/Ho_Chi_Minh -> 09:00)
# =====================================================================
@tagged('post_install', '-at_install')
class TestBookedPageContext(SelfBookingBase):

    def test_booked_context_wall_clock(self):
        self._make_matrix(start=15.5)  # 15:30 local Asia/Ho_Chi_Minh -> 08:30 UTC
        self._make_completed_fso_with_quote()
        invite = self._invite()
        idx = self._slot_index_for(invite, self.staff, start=15.5)
        self.assertIsNotNone(idx)
        res = invite.accept_slot(idx)
        self.assertTrue(res['ok'])
        ctx = invite._page_context()
        self.assertEqual(ctx['mode'], 'booked')
        self.assertTrue(ctx['time_window'].startswith('15:30'))
        # Scheduled datetime stored as naive UTC (15:30 +07 -> 08:30).
        self.assertEqual(res['fso'].scheduled_datetime.hour, 8)
        self.assertEqual(res['fso'].scheduled_datetime.minute, 30)


# =====================================================================
# 8 — Messaging rails (dry_run / empty template / enabled=False)
# =====================================================================
@tagged('post_install', '-at_install')
class TestRails(SelfBookingBase):

    def test_dry_run_simulates(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        msg = invite._send_invite_zns()
        self.assertEqual(msg.state, 'simulated')

    def test_empty_template_creates_no_row(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.zns_template_invite', '')
        msg = invite._send_invite_zns()
        self.assertFalse(msg)
        self.assertEqual(len(self._rows()), 0)
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.zns_template_invite', 'SBTPL')

    def test_disabled_marks_skipped(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_messaging.enabled', 'False')
        msg = invite._send_invite_zns()
        self.assertEqual(msg.state, 'skipped')
        self.env['ir.config_parameter'].sudo().set_param(
            'health_messaging.enabled', 'True')


# =====================================================================
# 9 — Auto-invite after completion (default off; on; failure-resilient)
# =====================================================================
@tagged('post_install', '-at_install')
class TestAutoInvite(SelfBookingBase):

    def test_default_off_creates_nothing(self):
        self._make_matrix()
        self._make_completed_fso_with_quote()  # completes with auto OFF
        self.assertEqual(self.env['health.selfbook.invite'].search_count(
            [('patient_id', '=', self.patient.id)]), 0)

    def test_on_creates_invite_and_row(self):
        self._make_matrix()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.auto_invite_after_completion', 'True')
        self._make_completed_fso_with_quote()
        invites = self.env['health.selfbook.invite'].search(
            [('patient_id', '=', self.patient.id)])
        self.assertEqual(len(invites), 1)
        self.assertEqual(len(self._rows()), 1)
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.auto_invite_after_completion', 'False')

    def test_send_failure_does_not_block_completion(self):
        self._make_matrix()
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.auto_invite_after_completion', 'True')

        def boom(self):
            raise ValueError('ZNS exploded')

        with patch.object(
                type(self.env['health.selfbook.invite']), '_send_invite_zns', boom):
            fso = self._make_completed_fso_with_quote()
        self.assertIn(fso.state, ('completed', 'completed_pending_invoice'))
        self.env['ir.config_parameter'].sudo().set_param(
            'health_self_booking.auto_invite_after_completion', 'False')


# =====================================================================
# 10 — Preferred staff sorts first within the same date
# =====================================================================
@tagged('post_install', '-at_install')
class TestPreferredStaff(SelfBookingBase):

    def test_preferred_staff_slot_first_within_date(self):
        staff_user = self.env['res.users'].create({
            'name': 'SB Pref User',
            'login': 'sb_pref_%s' % uuid.uuid4().hex[:8],
            'email': 'sb_pref_%s@example.com' % uuid.uuid4().hex[:6],
        })
        pref_staff = self.env['hr.employee'].create(
            {'name': 'Pham Thi Mai', 'user_id': staff_user.id,
             'staff_catchment_province_id': self.province.id})
        # Same date: default staff earlier (08:00), preferred later (15:30 —
        # a distinctive time unlikely to collide with live matrix rows).
        self._make_matrix(staff=self.staff, day_offset=1, start=8.0)
        self._make_matrix(staff=pref_staff, day_offset=1, start=15.5)
        self.patient.preferred_staff_id = pref_staff
        self._make_completed_fso_with_quote()
        invite = self._invite()
        # Within OUR seeded date the preferred staff's slot sorts first despite
        # its later time (vietuat carries other live slots on other dates).
        day = (fields.Date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        my_date = [s for s in (invite.slots_json or []) if s['date'] == day]
        self.assertTrue(my_date)
        self.assertEqual(my_date[0]['staff_id'], pref_staff.id)


# =====================================================================
# 11 — Zero feasible slots -> invite still created, call-us body
# =====================================================================
@tagged('post_install', '-at_install')
class TestZeroSlots(SelfBookingBase):

    def test_no_slots_still_creates_invite_and_call_us_page(self):
        # The invite is created even when no feasible slot exists; the page
        # renders a call-us body rather than a dead end. vietuat carries live
        # matrix rows, so force the zero-slot condition on the snapshot to test
        # the render path deterministically.
        self._make_completed_fso_with_quote()
        invite = self._invite()
        self.assertTrue(invite)
        invite.slots_json = []
        ctx = invite._page_context()
        self.assertEqual(ctx['mode'], 'sent')
        self.assertEqual(ctx['slots'], [])
        self.assertTrue(ctx['facility_phone'])


# =====================================================================
# 5 + 6 — Public routes (POST-only pin; neutral render through HTTP)
# =====================================================================
@tagged('post_install', '-at_install')
class TestPublicRoutes(HttpCase):

    def setUp(self):
        super().setUp()
        (self.province, self.facility, self.patient,
         self.staff, self.product) = _fixture(self.env)
        if not self.env.user.employee_id:
            self.env['hr.employee'].create(
                {'name': 'SB Http Emp', 'user_id': self.env.user.id})
        Stage = self.env['health.fieldservice.stage']
        for state in ('confirmed', 'assigned', 'in_progress', 'completed'):
            if not Stage.search([('state', '=', state), ('active', '=', True)], limit=1):
                Stage.create({'name': state.title(), 'state': state})
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('health_self_booking.zns_template_invite', '')

    def _seed_sent_invite(self):
        self.env['health.staff.availability.matrix'].create({
            'staff_id': self.staff.id,
            'availability_date': fields.Date.today() + timedelta(days=1),
            'start_time': 9.0, 'end_time': 12.0,
            'status': 'available', 'capacity': 2,
        })
        # A completed FSO so the invite has a bookable source.
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() - timedelta(days=2),
            'scheduled_duration': 120, 'service_type': 'home_visit',
        })
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {'product_id': self.product.id,
                                   'product_uom_qty': 1, 'price_unit': 100.0})],
        })
        fso.sale_order_id = so.id
        fso.action_assign_staff_to_fso(self.staff.id, assignment_role='lead')
        fso.action_confirm_booking()
        fso.action_start_service()
        self.env['health.clinical.note'].create(
            {'order_id': fso.id, 'clinical_notes': 'done'})
        fso.action_complete_service()
        return self.env['health.selfbook.invite']._get_or_create_invite(self.patient)

    def test_valid_sent_page_and_neutral_variants(self):
        invite = self._seed_sent_invite()
        # Valid sent page -> 200 with the slot page.
        resp = self.url_open('/booking/self/%s' % invite.token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Viet Uc Health', resp.text)

        # Bogus token -> neutral body.
        bogus = self.url_open('/booking/self/deadbeefdeadbeef')
        self.assertEqual(bogus.status_code, 200)
        self.assertIn('không còn hiệu lực', bogus.text)

        # Expired token -> neutral (assert through the render path).
        invite.expires_at = fields.Datetime.now() - timedelta(hours=1)
        expired = self.url_open('/booking/self/%s' % invite.token)
        self.assertEqual(expired.status_code, 200)
        self.assertIn('không còn hiệu lực', expired.text)

        # Revoked token -> neutral.
        invite.write({'expires_at': fields.Datetime.now() + timedelta(days=1),
                      'state': 'revoked'})
        revoked = self.url_open('/booking/self/%s' % invite.token)
        self.assertEqual(revoked.status_code, 200)
        self.assertIn('không còn hiệu lực', revoked.text)

    def test_accept_route_rejects_get(self):
        invite = self._seed_sent_invite()
        # POST-only: a GET on the accept route is 405.
        resp = self.url_open('/booking/self/%s/accept/0' % invite.token)
        self.assertEqual(resp.status_code, 405)
