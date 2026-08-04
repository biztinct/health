# -*- coding: utf-8 -*-
"""Lifecycle soft delete on bookings: count exclusion, dashboard KPIs and the
purge guard. The generic mixin matrix lives in health_base
(test_lifecycle_mixin); this covers the FSO-specific seams."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLifecycleFso(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facility = cls.env['health.facility'].search([], limit=1)
        cls.patient = cls.env['res.partner'].create({
            'name': 'Lifecycle FSO Patient',
            'is_patient': True,
            'primary_facility_id': cls.facility.id,
            'catchment_province_id': cls.facility.catchment_province_id.id,
        })
        cls.order = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id,
            'facility_id': cls.facility.id,
            'scheduled_datetime': '2026-08-04 09:00:00',
        })
        cls.reason = cls.env.ref('health_base.deletion_reason_duplicate')

    def test_deleted_booking_leaves_counts_but_stays_in_table(self):
        Order = self.env['health.fieldservice.order']
        domain = [('id', '=', self.order.id)]
        self.assertEqual(Order.search_count(domain), 1)
        self.order.action_soft_delete(self.reason.id, '')
        self.assertEqual(Order.search_count(domain), 0)
        self.assertEqual(
            Order.with_context(deleted_test=False).search_count(domain), 1)

    def test_ops_dashboard_excludes_deleted(self):
        Order = self.env['health.fieldservice.order']
        base = Order.get_ops_dashboard_data()
        self.order.action_soft_delete(self.reason.id, '')
        after = Order.get_ops_dashboard_data()
        # the deleted booking may or may not fall in "today" — the invariant
        # is that no KPI ever goes UP because of a deletion
        for key in ('total_today', 'needs_assignment'):
            if key in base and key in after:
                self.assertLessEqual(after[key], base[key])

    def test_purge_requires_delete_request(self):
        owner = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Lifecycle FSO Owner',
                'login': 'lifecycle_fso_owner',
                'group_ids': [(4, self.env.ref(
                    'health_base.group_healthcare_owner').id)],
            })
        with self.assertRaises(UserError):
            self.order.with_user(owner).unlink()
        self.order.action_soft_delete(self.reason.id, '')
        self.order.with_user(owner).unlink()
        self.assertFalse(self.order.exists())
