# -*- coding: utf-8 -*-
"""Owner ruling 2026-11-04 (UAT video item 14 follow-up): distance is travel.
It feeds the price rules only when staff go to the client; a clinic or online
visit for a client 6+ km away gets NO distance add, the same visit at home
does. Covers both price paths: the booking's quote and the Quick Booking
preview."""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNoTravelDistance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)
        cls.product = cls.env['product.product'].create({
            'name': 'Distance Probe Nursing', 'type': 'service',
            'list_price': 300000, 'sale_ok': True})
        cls.engine = cls.env['advanced.pricing.engine'].create({'name': 'Distance probe'})
        rule = cls.env['advanced.pricing.rule'].create({
            'name': 'Distance probe - 5 to 8 km', 'engine_id': cls.engine.id,
            'applied_on': '0_product_variant', 'product_id': cls.product.id,
            'level': '1', 'sequence': 1,
            'action_type': 'add', 'action_value': 50000, 'action_scope': 'line',
            'distance_min': 5, 'distance_max': 8,
        })
        rule.write({'approval_status': 'approved', 'active': True})
        cls.pricelist = cls.env['product.pricelist'].create({
            'name': 'Distance probe list', 'advanced_engine_id': cls.engine.id})
        cls.patient = cls.env['res.partner'].with_context(
            skip_auto_geocode=True, skip_distance_recompute=True).create({
            'name': 'Distance Probe Client', 'is_patient': True,
            'catchment_province_id': cls.facility.catchment_province_id.id,
            'primary_facility_id': cls.facility.id,
            'specific_property_product_pricelist': cls.pricelist.id,
        })
        cls.patient.with_context(skip_distance_recompute=True).write(
            {'clinic_drive_distance_km': 6.5})

    def _quote_price(self, location):
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=3),
            'service_type': 'home_visit' if location == 'home' else 'clinic_visit',
            'service_location': location,
        })
        fso.travel_distance = 6.5
        quote = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'pricelist_id': self.pricelist.id,
            'fso_id': fso.id})
        quote._compute_fso_fields()
        ctx = quote._pricing_booking_context()
        ctx.update(quantity=1, product_id=self.product.id, base_unit_price=self.product.list_price)
        return ctx['distance'], self.engine.calculate_price(
            self.product.id, 1, self.patient.id, ctx)

    def test_1_quote_clinic_and_online_get_no_distance_add(self):
        for location in ('clinic', 'online'):
            distance, price = self._quote_price(location)
            self.assertEqual(distance, 0, location)
            self.assertEqual(price, 300000, location)

    def test_2_quote_home_visit_keeps_the_distance_add(self):
        distance, price = self._quote_price('home')
        self.assertEqual(distance, 6.5)
        self.assertEqual(price, 350000)

    def _preview(self, location):
        res = self.env['health.fieldservice.order'].preview_quick_booking_pricing({
            'patient_id': self.patient.id,
            'service_type': 'home_visit' if location == 'home' else 'clinic_visit',
            'service_location': location,
            'facility_id': self.facility.id,
            'date': str(fields.Date.today() + timedelta(days=3)),
            'time_hour': 10.0,
            'duration_hours': 1,
            'product_lines': [{'product_id': self.product.id, 'qty': 1}],
        })
        return res['lines'][0]['unit_price'], [f['key'] for f in res.get('factors', [])]

    def test_3_quick_booking_preview_agrees(self):
        price, keys = self._preview('clinic')
        self.assertEqual(price, 300000)
        self.assertNotIn('pin', keys)
        price, keys = self._preview('home')
        self.assertEqual(price, 350000)
        self.assertIn('pin', keys)
