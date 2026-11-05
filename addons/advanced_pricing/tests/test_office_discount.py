# -*- coding: utf-8 -*-
"""UAT round 6, item 1 (docs/handovers/uat-video-fixes-2026-11-04.md §8):
Operations Managers / Owners / the CRM booking role give a line Discount % in
the office (booking › View Quote, booking › Pricing › Discounts).

The line must equal the client's 29 Oct quotes: the discount comes off the
catalogue price × qty only, never off a price-rule adjustment —
`qty × base + adjustment − discount% × (qty × base)`:

  TC-05 đd_240  2 × 150,000 + 50,000  − 10% × 300,000 = 320,000
  TC-08 đd_060  3 × 150,000 − 200,000 − 10% × 450,000 = 205,000
  TC-02 bs_040  300,000               − 10% × 300,000 = 270,000
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOfficeDiscount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.pricelist = cls.env['product.pricelist'].create({
            'name': 'Office discount probe list', 'currency_id': vnd.id,
            'discount_on_base_only': True})
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)
        cls.patient = cls.env['res.partner'].with_context(
            skip_auto_geocode=True, skip_distance_recompute=True).create({
            'name': 'Office Discount Client', 'is_patient': True,
            'catchment_province_id': cls.facility.catchment_province_id.id,
            'primary_facility_id': cls.facility.id,
        })
        Product = cls.env['product.product']
        cls.p_240 = Product.create({'name': 'Nursing fee (additional hour) probe',
                                    'type': 'service', 'list_price': 150000})
        cls.p_060 = Product.create({'name': 'Injection probe',
                                    'type': 'service', 'list_price': 150000})
        cls.p_040 = Product.create({'name': 'Ultrasound probe',
                                    'type': 'service', 'list_price': 300000})
        cls.has_reason = 'discount_reason' in cls.env['sale.order.line']._fields

    def _quote(self, with_booking=False):
        vals = {'partner_id': self.patient.id, 'pricelist_id': self.pricelist.id}
        booking = False
        if with_booking:
            booking = self.env['health.fieldservice.order'].create({
                'patient_id': self.patient.id, 'facility_id': self.facility.id,
                'scheduled_datetime': fields.Datetime.now() + timedelta(days=5),
                'service_type': 'clinic_visit', 'service_location': 'clinic',
            })
            vals['fso_id'] = booking.id
        so = self.env['sale.order'].create(vals)
        if booking:
            booking.sale_order_id = so
        return so, booking

    def _line(self, so, product, qty, base, unit):
        line = self.env['sale.order.line'].create({
            'order_id': so.id, 'product_id': product.id, 'product_uom_qty': qty})
        # The engine's result (base + rule adjustment per unit), as stored on
        # the client's quotes S04296 / S04299 / S04293.
        line.write({'base_price': base, 'price_unit': unit})
        return line

    def _discount(self, line, pct):
        vals = {'discount': pct}
        if self.has_reason:
            vals['discount_reason'] = 'Repeat booking discount on base'
        line.write(vals)

    def test_1_tc05_adjustment_kept_whole(self):
        so, _b = self._quote()
        line = self._line(so, self.p_240, 2, 150000, 175000)   # +50,000 rule
        self._discount(line, 10)
        self.assertEqual(round(line.price_subtotal), 320000)
        self.assertEqual(round(so.amount_total), 320000)

    def test_2_tc08_negative_adjustment_kept_whole(self):
        so, _b = self._quote()
        line = self._line(so, self.p_060, 3, 150000, 83333.33)  # −200,000 rule
        self._discount(line, 10)
        self.assertEqual(round(line.price_subtotal), 205000)

    def test_3_tc02_plain_line(self):
        so, _b = self._quote()
        line = self._line(so, self.p_040, 1, 300000, 300000)
        self._discount(line, 10)
        self.assertEqual(round(line.price_subtotal), 270000)
        # The quote keeps the entered percentage (as the client's quotes do).
        self.assertEqual(line.discount, 10)

    def test_4_office_users_may_change_discounts_nurses_may_not(self):
        so, _b = self._quote()
        om = new_test_user(self.env, login='disc_probe_om', groups=(
            'base.group_user,health_base.group_healthcare_operations_manager'))
        nurse = new_test_user(self.env, login='disc_probe_nurse', groups=(
            'base.group_user,health_base.group_healthcare_nurse'))
        (om | nurse).write({'catchment_province_id': self.facility.catchment_province_id.id})
        self.assertTrue(so.with_user(om).health_can_edit_discount)
        self.assertFalse(so.with_user(nurse).health_can_edit_discount)
        # Once invoiced (any invoice not cancelled) the box closes.
        line = self._line(so, self.p_040, 1, 300000, 300000)
        self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.patient.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.p_040.id, 'quantity': 1, 'price_unit': 300000,
                'sale_line_ids': [Command.link(line.id)]})],
        })
        so.invalidate_recordset()
        self.assertFalse(so.with_user(om).health_can_edit_discount)

    def test_5_change_leaves_a_history_note_on_the_booking(self):
        so, booking = self._quote(with_booking=True)
        line = self._line(so, self.p_040, 1, 300000, 300000)
        before = len(booking.message_ids)
        self._discount(line, 10)
        notes = booking.message_ids[:len(booking.message_ids) - before]
        self.assertTrue(any('changed from 0% to 10%' in (m.body or '') for m in notes),
                        [m.body for m in notes])
        # Writing the same value again is not a change: no second note.
        count = len(booking.message_ids)
        self._discount(line, 10)
        self.assertEqual(len(booking.message_ids), count)

    def test_6_booking_pricing_tab_writes_through_to_the_quote(self):
        so, booking = self._quote(with_booking=True)
        line = self._line(so, self.p_240, 2, 150000, 175000)
        vals = {'discount': 10}
        if self.has_reason:
            vals['discount_reason'] = 'Repeat booking discount on base'
        booking.write({'quote_line_ids': [Command.update(line.id, vals)]})
        self.assertEqual(line.discount, 10)
        self.assertEqual(round(line.price_subtotal), 320000)
        self.assertEqual(booking.quote_line_ids, so.order_line)
