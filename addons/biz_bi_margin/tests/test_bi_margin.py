# -*- coding: utf-8 -*-
"""Tests for biz_bi_margin — the bi_margin_visit view math + hook idempotency.

The view is created by the post_init hook at install, so it already exists in
the test DB. View rows are read straight through the cursor; per ledger §9 we
``flush_all()`` before every SELECT so ORM writes reach the tables the view
reads.
"""
import uuid
from datetime import date, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class MarginBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Province = cls.env['health.catchment.province']
        Facility = cls.env['health.facility']
        cls.province = Province.search([], limit=1) or Province.create(
            {'name': 'Margin Province', 'code': 'MGP'})
        cls.facility = Facility.search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = Facility.create({
                'name': 'Margin Facility', 'code': 'MGF',
                'timezone': 'Asia/Ho_Chi_Minh',
                'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Margin Patient', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id})
        # Own taxless product so a sale-order line's amount_total equals the
        # price exactly (sale.order.line has no tax_id field in Odoo 19).
        cls.product = cls.env['product.product'].create({
            'name': 'Margin Service', 'type': 'service', 'list_price': 100.0,
            'taxes_id': [(6, 0, [])]})
        cls._set_cfg(default_hourly_cost_vnd=45000, monthly_hours=208,
                     cost_per_km_vnd=3000)

    @classmethod
    def _set_cfg(cls, **kw):
        icp = cls.env['ir.config_parameter'].sudo()
        for key, val in kw.items():
            icp.set_param('health_bi_margin.%s' % key, str(val))

    # -- fixtures ----------------------------------------------------------
    def _staff(self, wage=0):
        user = self.env['res.users'].create({
            'name': 'Margin Staff', 'login': 'mstaff_%s' % uuid.uuid4().hex[:8],
            'email': 'mstaff_%s@example.com' % uuid.uuid4().hex[:6]})
        emp = self.env['hr.employee'].create(
            {'name': 'Margin Emp', 'user_id': user.id})
        if wage:
            version = self.env['hr.version'].search(
                [('employee_id', '=', emp.id)], limit=1)
            version.write({'wage': wage,
                           'contract_date_start': date.today() - timedelta(30)})
        return emp

    def _fso(self, nurse=None, service_type='home_visit', state='completed',
             travel_km=0, travel_min=0, commission_pct=0,
             scheduled_duration=60, actual_minutes=None):
        vals = {
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': scheduled_duration,
            'service_type': service_type,
        }
        if nurse:
            vals['primary_nurse_id'] = nurse.id
        fso = self.env['health.fieldservice.order'].create(vals)
        write = {'state': state, 'travel_distance': travel_km,
                 'travel_time_minutes': travel_min,
                 'commission_percentage': commission_pct}
        if actual_minutes is not None:
            start = fields.Datetime.now()
            write['actual_start_datetime'] = start
            write['actual_end_datetime'] = start + timedelta(minutes=actual_minutes)
        fso.with_context(skip_travel_recompute=True).write(write)
        return fso

    def _revenue(self, fso, amount):
        so = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'fso_id': fso.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1,
                'price_unit': amount})]})
        so.order_line.tax_ids = [(6, 0, [])]   # ensure no fiscal-position tax
        fso.sale_order_id = so.id
        return so

    def _attendance(self, fso, emp, minutes, start=None):
        start = start or (fields.Datetime.now() - timedelta(minutes=minutes + 5))
        return self.env['hr.attendance'].create({
            'employee_id': emp.id, 'fso_id': fso.id,
            'attendance_source': 'pwa_visit',
            'check_in': start, 'check_out': start + timedelta(minutes=minutes)})

    def _row(self, fso_id):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT * FROM bi_margin_visit WHERE fso_id = %s", (fso_id,))
        cols = [d[0] for d in self.env.cr.description]
        row = self.env.cr.fetchone()
        return dict(zip(cols, row)) if row else None

    @staticmethod
    def _f(row, key):
        return float(row[key]) if row[key] is not None else None


# =====================================================================
# 1 — View math (the worked example from the handover)
# =====================================================================
@tagged('post_install', '-at_install')
class TestViewMath(MarginBase):

    def test_full_margin_calculation(self):
        staff = self._staff(wage=8320000)   # 8,320,000 / 208 = 40,000/h
        fso = self._fso(nurse=staff, travel_km=10, travel_min=30,
                        commission_pct=10)
        self._revenue(fso, 500000)          # commission 10% → 50,000
        self._attendance(fso, staff, 120)   # 2h × 40,000 = 80,000
        row = self._row(fso.id)
        self.assertTrue(row)
        self.assertEqual(row['labor_source'], 'attendance')
        self.assertAlmostEqual(self._f(row, 'revenue_total_vnd'), 500000, 0)
        self.assertAlmostEqual(self._f(row, 'labor_cost_vnd'), 80000, 0)
        self.assertAlmostEqual(self._f(row, 'travel_cost_vnd'), 50000, 0)
        self.assertAlmostEqual(self._f(row, 'commission_vnd'), 50000, 0)
        self.assertAlmostEqual(self._f(row, 'cost_total_vnd'), 180000, 0)
        self.assertAlmostEqual(self._f(row, 'margin_vnd'), 320000, 0)
        self.assertAlmostEqual(self._f(row, 'margin_pct'), 64.0, 1)


# =====================================================================
# 2 — Fallback chain + default rate
# =====================================================================
@tagged('post_install', '-at_install')
class TestFallback(MarginBase):

    def test_actuals_fallback_and_default_rate(self):
        staff = self._staff(wage=0)   # no wage → default 45,000/h
        fso = self._fso(nurse=staff, actual_minutes=120)   # no attendance
        self._revenue(fso, 300000)
        row = self._row(fso.id)
        self.assertEqual(row['labor_source'], 'actuals')
        self.assertAlmostEqual(self._f(row, 'labor_minutes'), 120, 0)
        # 2h × 45,000 default
        self.assertAlmostEqual(self._f(row, 'labor_cost_vnd'), 90000, 0)

    def test_scheduled_fallback(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff, scheduled_duration=90)  # no att, no actuals
        self._revenue(fso, 300000)
        row = self._row(fso.id)
        self.assertEqual(row['labor_source'], 'scheduled')
        self.assertAlmostEqual(self._f(row, 'labor_minutes'), 90, 0)
        self.assertAlmostEqual(self._f(row, 'labor_cost_vnd'), 67500, 0)


# =====================================================================
# 3 — Package revenue
# =====================================================================
@tagged('post_install', '-at_install')
class TestPackageRevenue(MarginBase):

    def test_package_visit_revenue_source(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff)
        pkg = self.env['health.service.package'].create({
            'name': 'Margin Package', 'patient_id': self.patient.id,
            'service_type': 'home_visit', 'total_services': 1,
            'package_price': 250000, 'price_per_service': 250000})
        fso.write({'package_ids': [(6, 0, [pkg.id])],
                   'package_consumption_quantity': 1})
        row = self._row(fso.id)
        self.assertEqual(row['revenue_source'], 'package')
        self.assertAlmostEqual(self._f(row, 'revenue_service_vnd'), 250000, 0)


# =====================================================================
# 4 — Zero revenue → NULL margin %
# =====================================================================
@tagged('post_install', '-at_install')
class TestZeroRevenue(MarginBase):

    def test_zero_revenue_margin_pct_null(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff)   # no revenue
        row = self._row(fso.id)
        self.assertAlmostEqual(self._f(row, 'revenue_total_vnd'), 0, 0)
        self.assertIsNone(row['margin_pct'])   # no division by zero


# =====================================================================
# 5 — Scope + multi-staff
# =====================================================================
@tagged('post_install', '-at_install')
class TestScopeAndMultiStaff(MarginBase):

    def test_non_completed_absent(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff, state='confirmed')
        self.assertIsNone(self._row(fso.id))

    def test_multi_staff_sums_attendance(self):
        s1 = self._staff(wage=8320000)   # 40,000/h
        s2 = self._staff(wage=4160000)   # 20,000/h
        fso = self._fso(nurse=s1)
        self._revenue(fso, 1000000)
        self._attendance(fso, s1, 60)    # 1h × 40,000 = 40,000
        self._attendance(fso, s2, 60,
                         start=fields.Datetime.now() - timedelta(hours=5))
        row = self._row(fso.id)
        self.assertEqual(row['labor_source'], 'attendance')
        self.assertAlmostEqual(self._f(row, 'labor_minutes'), 120, 0)
        # 40,000 (s1) + 20,000 (s2) = 60,000
        self.assertAlmostEqual(self._f(row, 'labor_cost_vnd'), 60000, 0)


# =====================================================================
# 6 — Hook idempotency
# =====================================================================
@tagged('post_install', '-at_install')
class TestHookIdempotency(MarginBase):

    def test_rerun_seeder_no_duplicates(self):
        from odoo.addons.biz_bi_margin.hooks import MarginSeeder
        MarginSeeder(self.env).run()
        datasets = self.env['bi.dataset'].search([('name', '=', 'Visit Margin')])
        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets.state, 'published')
        dashboards = self.env['bi.dashboard'].search(
            [('name', '=', 'Visit Margin')])
        self.assertEqual(len(dashboards), 1)
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(
            'biz_bi_margin.seeded'), '1')
        # silver view exists (published) — a bare select must not raise.
        self.env.cr.execute(
            "SELECT 1 FROM %s LIMIT 0" % datasets._silver_view_name())


# =====================================================================
# 7 & 8 — Config: live reflect + junk safety
# =====================================================================
@tagged('post_install', '-at_install')
class TestConfig(MarginBase):

    def test_config_change_reflects_without_republish(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff, travel_km=10)
        self._revenue(fso, 500000)
        before = self._f(self._row(fso.id), 'travel_cost_vnd')
        self.assertAlmostEqual(before, 30000, 0)     # 10 × 3000
        self._set_cfg(cost_per_km_vnd=9000)
        after = self._f(self._row(fso.id), 'travel_cost_vnd')
        self.assertAlmostEqual(after, 90000, 0)      # 10 × 9000, no republish

    def test_junk_config_falls_back_to_default(self):
        staff = self._staff(wage=0)
        fso = self._fso(nurse=staff, travel_km=10)
        self._revenue(fso, 500000)
        self._set_cfg(cost_per_km_vnd='not-a-number')
        row = self._row(fso.id)   # must not raise
        self.assertAlmostEqual(self._f(row, 'travel_cost_vnd'), 30000, 0)
