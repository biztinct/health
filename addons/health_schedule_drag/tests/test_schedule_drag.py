# -*- coding: utf-8 -*-
"""Tests for health_schedule_drag — the reschedule_from_drag gate (handover §3).

Staff availability comes from the legacy working_hours_<weekday> char fields
(a full 00:00-23:59 week makes any daytime target valid); a narrow window is
used for the hard-block case. Times are naive UTC; the base FSO sits at
02:00 UTC = 09:00 Asia/Ho_Chi_Minh.
"""
import uuid
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

BASE = datetime(2026, 8, 3, 2, 0, 0)   # Mon 03 Aug 2026, 02:00 UTC = 09:00 ICT
_DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
         'saturday', 'sunday')


def _iso(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


@tagged('post_install', '-at_install')
class ScheduleDragBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Province = cls.env['health.catchment.province']
        Facility = cls.env['health.facility']
        cls.province = Province.search([], limit=1) or Province.create(
            {'name': 'Drag Province', 'code': 'DRP'})
        cls.facility = Facility.search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = Facility.create({
                'name': 'Drag Facility', 'code': 'DRF',
                'timezone': 'Asia/Ho_Chi_Minh',
                'catchment_province_id': cls.province.id})
        cls.facility2 = Facility.create({
            'name': 'Drag Facility 2', 'code': 'DRF2',
            'street': '2 Drag Street', 'city': 'Test City',
            'phone': '02838000000', 'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Drag Patient', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id, 'mobile': '0912345678'})
        cls.ops = cls._user('health_base.group_healthcare_operations_manager')
        cls.nurse = cls._user('health_base.group_healthcare_nurse')

    @classmethod
    def _user(cls, group_xmlid):
        u = cls.env['res.users'].create({
            'name': 'Drag %s' % group_xmlid.split('_')[-1],
            'login': 'drag_%s' % uuid.uuid4().hex[:10],
            'email': 'drag_%s@example.com' % uuid.uuid4().hex[:6],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref(group_xmlid).id])],
            'catchment_province_id': cls.province.id})
        return u

    def _staff(self, hours='00:00-23:59', facility=None):
        user = self.env['res.users'].create({
            'name': 'Drag Staff', 'login': 'ds_%s' % uuid.uuid4().hex[:10],
            'email': 'ds_%s@example.com' % uuid.uuid4().hex[:6]})
        emp = self.env['hr.employee'].create({
            'name': 'Drag Staff', 'user_id': user.id,
            'healthcare_facility_id': (facility or self.facility).id})
        # working_hours_* char fields are only the FALLBACK —
        # resource_calendar_id (auto-set to the company default calendar)
        # takes precedence in _working_intervals_for, silently ignoring the
        # hours param. Clear it so the requested hours actually apply.
        emp.write({'resource_calendar_id': False})
        emp.write({'working_hours_%s' % d: hours for d in _DAYS})
        return emp

    def _fso(self, when=None, duration=60, state='assigned'):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': when or BASE, 'scheduled_duration': duration,
            'service_type': 'home_visit'})
        fso.booking_timezone = 'Asia/Ho_Chi_Minh'
        fso.state = state
        return fso

    def _assign(self, fso, staff, role='lead'):
        fso.action_assign_staff_to_fso(staff.id, assignment_role=role)
        return self.env['health.staff.assignment'].search(
            [('fso_id', '=', fso.id), ('staff_id', '=', staff.id)], limit=1)

    def _resched(self, assignment, start, end=None, new_staff=0,
                 confirmed=False, mode='day', user=None):
        fso = assignment.fso_id
        end = end or (start + timedelta(minutes=fso.scheduled_duration or 60))
        return self.env['health.staff.assignment'].with_user(
            user or self.ops).reschedule_from_drag(
                assignment.id, _iso(start), _iso(end), new_staff, confirmed, mode)

    def _set_msg_rails(self, enabled=False, dry_run=True, template=''):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('health_messaging.enabled', str(enabled))
        icp.set_param('health_messaging.dry_run', str(dry_run))
        icp.set_param('health_schedule_drag.zns_template_rescheduled', template)


# =====================================================================
# 1 — State matrix
# =====================================================================
@tagged('post_install', '-at_install')
class TestStateGate(ScheduleDragBase):

    def test_non_reschedulable_states_refused(self):
        staff = self._staff()
        for state in ('draft', 'in_progress', 'completed', 'cancelled'):
            fso = self._fso(state='assigned')
            a = self._assign(fso, staff)
            fso.state = state
            res = self._resched(a, BASE + timedelta(hours=2))
            self.assertEqual(res['status'], 'refused', state)
            self.assertEqual(fso.scheduled_datetime, BASE)

    def test_confirmed_and_assigned_proceed(self):
        for state in ('confirmed', 'assigned'):
            staff = self._staff()
            fso = self._fso(state=state)
            a = self._assign(fso, staff)
            fso.state = state
            res = self._resched(a, BASE + timedelta(hours=2))
            self.assertEqual(res['status'], 'ok', state)
            self.assertEqual(fso.scheduled_datetime, BASE + timedelta(hours=2))


# =====================================================================
# 2 — Ops guard
# =====================================================================
@tagged('post_install', '-at_install')
class TestOpsGuard(ScheduleDragBase):

    def test_nurse_refused_even_own_block(self):
        staff = self._staff()
        # make the nurse the assignment's own staff
        staff.user_id = self.nurse
        fso = self._fso()
        a = self._assign(fso, staff)
        res = self._resched(a, BASE + timedelta(hours=2), user=self.nurse)
        self.assertEqual(res['status'], 'refused')
        self.assertEqual(fso.scheduled_datetime, BASE)

    def test_ops_manager_ok(self):
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        res = self._resched(a, BASE + timedelta(hours=2), user=self.ops)
        self.assertEqual(res['status'], 'ok')


# =====================================================================
# 3 — Sibling coherence
# =====================================================================
@tagged('post_install', '-at_install')
class TestSiblingCoherence(ScheduleDragBase):

    def test_two_staff_both_move(self):
        s1 = self._staff()
        s2 = self._staff()
        fso = self._fso()
        a1 = self._assign(fso, s1, role='lead')
        a2 = self._assign(fso, s2, role='support')
        res = self._resched(a1, BASE + timedelta(hours=2))
        self.assertEqual(res['status'], 'ok')
        new = BASE + timedelta(hours=2)
        self.assertEqual(fso.scheduled_datetime, new)
        self.assertEqual(a1.planned_start_time, new)
        self.assertEqual(a2.planned_start_time, new)
        self.assertEqual(a2.staff_id, s2)             # other staff unchanged
        self.assertEqual(a1.assignment_role, 'lead')  # roles unchanged
        self.assertEqual(a2.assignment_role, 'support')


# =====================================================================
# 4 — Duration immunity
# =====================================================================
@tagged('post_install', '-at_install')
class TestDurationImmunity(ScheduleDragBase):

    def test_client_end_ignored(self):
        staff = self._staff()
        fso = self._fso(duration=60)
        a = self._assign(fso, staff)
        start = BASE + timedelta(hours=2)
        # client claims a 3h block (a resize) — server must keep 60 min.
        res = self._resched(a, start, end=start + timedelta(hours=3))
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(fso.scheduled_duration, 60)
        self.assertEqual(fso.scheduled_datetime, start)


# =====================================================================
# 5 — Hard block
# =====================================================================
@tagged('post_install', '-at_install')
class TestHardBlock(ScheduleDragBase):

    def test_outside_hours_refused_nothing_written(self):
        staff = self._staff(hours='08:00-09:00')   # ICT window
        fso = self._fso()
        a = self._assign(fso, staff)
        # 20:00 UTC = 03:00 ICT next day → outside 08:00-09:00.
        res = self._resched(a, datetime(2026, 8, 3, 20, 0, 0))
        self.assertEqual(res['status'], 'refused')
        self.assertEqual(fso.scheduled_datetime, BASE)


# =====================================================================
# 6 — needs_confirm on overlap
# =====================================================================
@tagged('post_install', '-at_install')
class TestNeedsConfirm(ScheduleDragBase):

    def test_overlap_confirm_then_apply(self):
        staff = self._staff()
        target = BASE + timedelta(hours=4)
        # a second booking for the same staff AT the target → overlap
        other = self._fso(when=target)
        self._assign(other, staff)
        fso = self._fso()
        a = self._assign(fso, staff)
        res = self._resched(a, target, confirmed=False)
        self.assertEqual(res['status'], 'needs_confirm')
        self.assertTrue(res['message'])
        self.assertEqual(fso.scheduled_datetime, BASE)   # not yet applied
        res2 = self._resched(a, target, confirmed=True)
        self.assertEqual(res2['status'], 'ok')
        self.assertEqual(fso.scheduled_datetime, target)


# =====================================================================
# 7 — Staff-lane change
# =====================================================================
@tagged('post_install', '-at_install')
class TestStaffChange(ScheduleDragBase):

    def test_staff_swapped_siblings_keep_theirs(self):
        s1 = self._staff()
        s2 = self._staff()
        keeper = self._staff()
        fso = self._fso()
        a1 = self._assign(fso, s1, role='lead')
        a2 = self._assign(fso, keeper, role='support')
        res = self._resched(a1, BASE, new_staff=s2.id)
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(a1.staff_id, s2)
        self.assertEqual(a1.assignment_role, 'lead')
        self.assertEqual(a2.staff_id, keeper)

    def test_cross_facility_refused(self):
        s1 = self._staff()
        far = self._staff(facility=self.facility2)
        fso = self._fso()
        a = self._assign(fso, s1)
        res = self._resched(a, BASE, new_staff=far.id)
        self.assertEqual(res['status'], 'refused')
        self.assertEqual(a.staff_id, s1)


# =====================================================================
# 8 — Matrix release / rebook
# =====================================================================
@tagged('post_install', '-at_install')
class TestMatrix(ScheduleDragBase):

    def _booked(self, fso):
        return self.env['health.staff.availability.matrix'].search(
            [('fso_id', '=', fso.id), ('status', '=', 'booked')])

    def test_prebooked_released_and_rebooked(self):
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        self.env['health.staff.availability.matrix'].book_staff_slot(
            staff.id, BASE, 60, fso_id=fso.id, assignment_id=a.id)
        self.assertEqual(self._booked(fso).start_time, 2.0)   # 02:00 UTC
        self._resched(a, BASE + timedelta(hours=2))
        booked = self._booked(fso)
        self.assertEqual(len(booked), 1)
        self.assertEqual(booked.start_time, 4.0)              # released + rebooked

    def test_zero_matrix_no_op(self):
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        res = self._resched(a, BASE + timedelta(hours=2))     # no prior rows
        self.assertEqual(res['status'], 'ok')                 # release no-ops


# =====================================================================
# 9 & 10 — Rails + timezone
# =====================================================================
@tagged('post_install', '-at_install')
class TestRails(ScheduleDragBase):

    def _rows(self, fso):
        return self.env['health.outbound.message'].sudo().search(
            [('fso_id', '=', fso.id), ('purpose', '=', 'booking_rescheduled')])

    def test_empty_template_no_row(self):
        self._set_msg_rails(enabled=True, dry_run=True, template='')
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        self._resched(a, BASE + timedelta(hours=2))
        self.assertFalse(self._rows(fso))

    def test_dry_run_dedup_and_second_time(self):
        self._set_msg_rails(enabled=True, dry_run=True, template='TPL123')
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        self._resched(a, BASE + timedelta(hours=2))
        rows = self._rows(fso)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.state, 'simulated')
        # re-fire the SAME move → dedup, still one row
        self._resched(a, BASE + timedelta(hours=2), confirmed=True)
        self.assertEqual(len(self._rows(fso)), 1)
        # a genuine second reschedule to a DIFFERENT time → second row
        self._resched(a, BASE + timedelta(hours=3))
        self.assertEqual(len(self._rows(fso)), 2)

    def test_timezone_in_params(self):
        self._set_msg_rails(enabled=True, dry_run=True, template='TPL123')
        staff = self._staff()
        fso = self._fso(when=BASE + timedelta(hours=6))   # start elsewhere
        a = self._assign(fso, staff)
        self._resched(a, datetime(2026, 8, 3, 2, 0, 0))   # 02:00 UTC = 09:00 ICT
        row = self._rows(fso)
        self.assertEqual(row.payload_json.get('new_time'), '09:00')


# =====================================================================
# 11 — Chatter regression pin
# =====================================================================
@tagged('post_install', '-at_install')
class TestChatter(ScheduleDragBase):

    def test_reschedule_leaves_chatter(self):
        staff = self._staff()
        fso = self._fso()
        a = self._assign(fso, staff)
        before = len(fso.message_ids)
        self._resched(a, BASE + timedelta(hours=2))
        self.env.flush_all()
        fso.invalidate_recordset(['message_ids'])
        self.assertGreater(len(fso.message_ids), before)


# =====================================================================
# 12 — The legacy side door is gated (review fix)
# =====================================================================
@tagged('post_install', '-at_install')
class TestLegacyEndpointGated(ScheduleDragBase):

    def test_apply_timeline_change_routes_through_gate(self):
        """The shipped apply_timeline_change had NO guards and wrote
        scheduled_duration; it must now obey the gate: non-ops refused,
        duration immune."""
        staff = self._staff()
        staff.user_id = self.nurse
        fso = self._fso()
        a = self._assign(fso, staff)
        old_dt = fso.scheduled_datetime
        old_dur = fso.scheduled_duration
        target = BASE + timedelta(hours=3)
        # Non-ops caller (the assignment's own nurse) → refused, nothing written.
        res = self.env['health.staff.assignment'].with_user(
            self.nurse).apply_timeline_change(
                a.id, _iso(target), _iso(target + timedelta(hours=5)), 0)
        self.assertFalse(res['ok'])
        self.assertEqual(fso.scheduled_datetime, old_dt)
        self.assertEqual(fso.scheduled_duration, old_dur)
        # Ops caller → applies, but the 5h client end is IGNORED (immunity).
        res2 = self.env['health.staff.assignment'].with_user(
            self.ops).apply_timeline_change(
                a.id, _iso(target), _iso(target + timedelta(hours=5)), 0)
        self.assertTrue(res2['ok'])
        self.assertEqual(fso.scheduled_datetime, target)
        self.assertEqual(fso.scheduled_duration, old_dur)

    def test_sibling_hard_conflict_refused(self):
        """Superseded-flow parity: the whole booking moves, so a sibling
        staff outside HER working hours at the target must hard-refuse even
        though the dragged staff is available."""
        s1 = self._staff()                       # works 00:00-23:59
        s2 = self._staff(hours='08:00-11:00')    # mornings only (ICT)
        fso = self._fso()
        a1 = self._assign(fso, s1, role='lead')
        self._assign(fso, s2, role='support')
        target = BASE + timedelta(hours=5)       # 14:00 ICT — s2 off duty
        res = self._resched(a1, target, confirmed=True)
        self.assertEqual(res['status'], 'refused')
        self.assertIn(s2.name, res['message'])
        self.assertNotEqual(fso.scheduled_datetime, target)
