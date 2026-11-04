# -*- coding: utf-8 -*-
"""UAT 2026-11-04, round 3 item 3: every posted invoice showed the raw error
"'account.move' object has no attribute 'patient_id'" as its Tax Submission
and MISA Sync error. The client is the booking's client, else the partner.
Nothing may be sent anywhere from a test: the simulator stays on (and then
nothing is recorded as submitted), MISA has no address, and the test runner
refuses outside calls anyway."""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTaxMisaPatient(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('vietnamese_tax.red_invoice_enabled', 'True')
        ICP.set_param('vietnamese_tax.use_mock_api', 'True')
        ICP.set_param('misa.api_url', '')
        ICP.set_param('misa.api_token', '')
        cls.partner = cls.env['res.partner'].create({'name': 'UAT Tax Probe Client'})
        cls.product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1) \
            or cls.env['product.product'].create({'name': 'UAT Tax Probe Service', 'type': 'service'})

    def _posted(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, [])]})],
        })
        move.action_post()
        return move

    def test_1_posting_leaves_no_program_error(self):
        move = self._posted()
        for text in (move.tax_submission_error, move.misa_sync_error):
            self.assertFalse(text and 'patient_id' in text, text)
        self.assertNotEqual(move.tax_authority_submission_status, 'error')
        self.assertNotEqual(move.misa_sync_status, 'sync_error')

    def test_2_simulator_never_records_a_submission(self):
        move = self._posted()
        self.assertEqual(move.tax_authority_submission_status, 'draft')
        self.assertFalse(move.tax_submission_reference)

    def test_3_data_builders_name_the_client(self):
        move = self._posted()
        self.assertEqual(move._health_patient(), self.partner)
        self.assertEqual(move._prepare_tax_authority_data()['healthcare_service']['patient_id'], self.partner.id)
        self.assertEqual(move._prepare_misa_data()['HealthcareService']['PatientID'], self.partner.id)
