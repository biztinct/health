# -*- coding: utf-8 -*-
"""UAT 2026-11-04, round 4 item 3: a booking whose invoice was posted from the
nurse app showed "Invoiced" unticked (BK4056 / INV/2026/00025): that path
links the invoice without writing the flag. The flag follows the invoice."""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBookingInvoicedFlag(TransactionCase):

    def test_flag_follows_the_linked_invoice(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('vietnamese_tax.red_invoice_enabled', 'False')  # no e-invoice step here
        facility = self.env['health.facility'].search([('catchment_province_id', '!=', False)], limit=1)
        patient = self.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'Invoiced Flag Probe', 'is_patient': True,
            'catchment_province_id': facility.catchment_province_id.id,
            'primary_facility_id': facility.id})
        fso = self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': facility.id,
            'scheduled_datetime': fields.Datetime.now()})
        self.assertFalse(fso.is_invoiced)
        product = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': patient.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1,
                                         'price_unit': 100.0, 'tax_ids': [(6, 0, [])]})]})
        move.action_post()
        # The nurse-app path: link the posted invoice, nothing else.
        fso.write({'invoice_id': move.id})
        self.assertTrue(fso.is_invoiced, 'a posted invoice ticks "Invoiced"')
        move.button_draft()
        move.button_cancel()
        self.assertFalse(fso.is_invoiced, 'a cancelled invoice does not')
        # The older paths that set the flag by hand still can.
        fso.write({'is_invoiced': True})
        self.assertTrue(fso.is_invoiced)
