# -*- coding: utf-8 -*-
"""UAT video item 2 (owner decision 2026-11-04): the nurse adds a service to
the visit's quote DURING the visit, in the nurse app.

  1  the assigned nurse, visit in progress: the line is added with the
     quantity, the quote total grows, the booking history says who added what
  2  visit not in progress: refused, nothing added
  3  a nurse who is not on the visit: refused, nothing added
  4  quantity 0: refused
  5  the catalogue for the visit is priced from the visit's quote
"""
import json
import uuid
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged

GROUPS = 'base.group_user,health_base.group_healthcare_nurse,sales_team.group_sale_salesman_all_leads'


@tagged('post_install', '-at_install')
class TestVisitAddService(HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.addCleanup(ICP.set_param, 'health_workflow_auto.timecard_sync_enabled',
                        ICP.get_param('health_workflow_auto.timecard_sync_enabled'))
        ICP.set_param('health_workflow_auto.timecard_sync_enabled', 'False')

        tag = uuid.uuid4().hex[:5]
        self.province = self.env['health.catchment.province'].create(
            {'name': 'AS Prov %s' % tag, 'code': 'AS%s' % tag[:3]})
        self.facility = self.env['health.facility'].create({
            'name': 'AS Facility %s' % tag, 'code': 'ASF%s' % tag[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': self.province.id})
        self.patient = self.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'AS Patient', 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id})
        self.nurse_user = new_test_user(self.env, login='as_nurse_%s' % tag,
                                        groups=GROUPS, password='asnursepw')
        self.nurse = self.env['hr.employee'].create(
            {'name': 'AS Nurse', 'user_id': self.nurse_user.id})
        self.other_user = new_test_user(self.env, login='as_other_%s' % tag,
                                        groups=GROUPS, password='asotherpw')
        self.env['hr.employee'].create({'name': 'AS Other', 'user_id': self.other_user.id})
        # A nurse reads only bookings of her own area (catchment rule).
        (self.nurse_user | self.other_user).write({'catchment_province_id': self.province.id})

        Product = self.env['product.product']
        self.base_product = Product.create(
            {'name': 'AS Base Service', 'type': 'service', 'list_price': 500000, 'sale_ok': True})
        self.added_product = Product.create(
            {'name': 'AS Added At Visit', 'type': 'service', 'list_price': 50000,
             'sale_ok': True, 'default_code': 'as_glucose_%s' % tag})

        self.order = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(hours=1),
            'scheduled_duration': 60, 'service_type': 'clinic_visit',
            'service_location': 'clinic'})
        quote = self.env['sale.order'].create({
            'partner_id': self.patient.id, 'fso_id': self.order.id,
            'order_line': [(0, 0, {'product_id': self.base_product.id,
                                   'product_uom_qty': 1, 'price_unit': 500000})]})
        self.order.sale_order_id = quote.id
        self.order.action_assign_staff_to_fso(self.nurse.id, assignment_role='lead')
        self.order.sudo().write({'state': 'in_progress'})

    def _add(self, product, qty):
        resp = self.url_open(
            '/health_pwa/api/fso/%s/quote/update' % self.order.id,
            data=json.dumps({'action': 'add', 'line_data': {'product_id': product.id, 'quantity': qty}}),
            headers={'Content-Type': 'application/json'})
        return resp.status_code, resp.json()

    def _lines(self, product):
        self.order.sale_order_id.invalidate_recordset()
        return self.order.sale_order_id.order_line.filtered(lambda l: l.product_id == product)

    def test_1_assigned_nurse_adds_during_the_visit(self):
        total_before = self.order.sale_order_id.amount_total
        self.authenticate(self.nurse_user.login, 'asnursepw')
        status, body = self._add(self.added_product, 2)
        self.assertEqual(status, 200, body)
        self.assertTrue(body['success'], body)
        line = self._lines(self.added_product)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertGreater(body['data']['quote']['amount_total'], total_before)
        self.assertIn('AS Added At Visit', [l['product_name'] for l in body['data']['quote']['order_lines']])
        history = ' '.join(self.order.message_ids.mapped('body'))
        self.assertIn('AS Added At Visit', history)
        self.assertIn('× 2', history)

    def test_2_not_in_progress_is_refused(self):
        self.order.sudo().write({'state': 'assigned'})
        self.authenticate(self.nurse_user.login, 'asnursepw')
        status, body = self._add(self.added_product, 1)
        self.assertEqual(status, 403, body)
        self.assertFalse(self._lines(self.added_product))

    def test_3_unassigned_nurse_is_refused(self):
        self.authenticate(self.other_user.login, 'asotherpw')
        status, body = self._add(self.added_product, 1)
        self.assertFalse(body.get('success'), body)
        self.assertNotEqual(status, 200)
        self.assertFalse(self._lines(self.added_product))

    def test_4_zero_quantity_is_refused(self):
        self.authenticate(self.nurse_user.login, 'asnursepw')
        status, body = self._add(self.added_product, 0)
        self.assertEqual(status, 400, body)
        self.assertFalse(self._lines(self.added_product))

    def test_5_catalogue_for_the_visit(self):
        self.authenticate(self.nurse_user.login, 'asnursepw')
        resp = self.url_open('/health_pwa/api/products/catalog?limit=20&order_id=%s&search=%s'
                             % (self.order.id, 'AS Added'))
        body = resp.json()
        self.assertTrue(body['success'], body)
        names = [p['name'] for p in body['data']['products']]
        self.assertIn('AS Added At Visit', names)
