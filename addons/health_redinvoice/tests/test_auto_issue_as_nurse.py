# -*- coding: utf-8 -*-
"""UAT 2026-11-04, round 4 item 1 (MB-10): an invoice posted from the nurse app
(by the nurse's own user) was never sent as an e-invoice — creating the
e-invoice request needed rights a nurse does not have, and the failure was
only a log line. The automatic issue now runs as a system step (the nurse is
still the recorded user) and a failure is written on the invoice.

The provider is NEVER called: `requests.post` and the sign-in are mocked."""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_redinvoice.models import account_move as red_mod

NURSE_GROUPS = ('base.group_user,health_base.group_healthcare_nurse,'
                'account.group_account_invoice')


class _Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = text if text is not None else ('{}' if payload is None else 'x')

    def json(self):
        return self._payload


@tagged('post_install', '-at_install')
class TestAutoIssueAsNurse(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('vietnamese_tax.red_invoice_enabled', 'True')
        ICP.set_param('health_redinvoice.auto_issue', 'True')
        ICP.set_param('vietnamese_tax.use_mock_api', 'True')
        company = cls.env.company
        company.write({'red_supplier_tax_code': '0101010101',
                       'red_invoice_api_base': 'http://example.invalid/api'})
        cls.nurse = new_test_user(cls.env, login='redinv_nurse', groups=NURSE_GROUPS)
        cls.partner = cls.env['res.partner'].create({'name': 'Red Invoice Probe Client'})
        cls.product = cls.env['product.product'].search([('sale_ok', '=', True)], limit=1) \
            or cls.env['product.product'].create({'name': 'Red Invoice Probe', 'type': 'service'})

    def _draft(self):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': 1, 'price_unit': 500000.0,
                'tax_ids': [(6, 0, [])]})],
        })

    def _post_as_nurse(self, move, response=None, side_effect=None):
        post = patch.object(red_mod.requests, 'post',
                            return_value=response, side_effect=side_effect)
        auth = patch.object(type(self.env['account.move']), '_redinvoice_auth_cookies',
                            lambda self_: ({}, {}))
        dl = patch.object(type(self.env['account.move']), '_redinvoice_download',
                          lambda self_, file_type='ZIP': None)
        with post as mocked, auth, dl:
            move.with_user(self.nurse).action_post()
        return mocked

    def test_1_nurse_posting_issues_the_e_invoice(self):
        move = self._draft()
        ok = _Resp(200, {'result': {'invoiceNo': 'C26TAA1', 'reservationCode': 'R1',
                                    'transactionID': 'T1'}})
        mocked = self._post_as_nurse(move, response=ok)
        self.assertTrue(mocked.called, 'the (mocked) provider was asked')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.red_invoice_state, 'issued', move.red_invoice_last_error)
        self.assertEqual(move.red_invoice_no, 'C26TAA1')
        req = move.sudo().red_invoice_request_ids
        self.assertEqual(len(req), 1, 'one e-invoice request recorded')
        self.assertEqual(req.create_uid, self.nurse, 'the nurse stays the recorded user')

    def test_2_provider_refusal_is_written_on_the_invoice(self):
        move = self._draft()
        self._post_as_nurse(move, response=_Resp(500, text='Service unavailable'))
        self.assertEqual(move.red_invoice_state, 'failed')
        self.assertIn('Service unavailable', move.red_invoice_last_error)

    def test_3_an_unexpected_failure_is_readable_not_only_logged(self):
        move = self._draft()
        boom = patch.object(type(self.env['account.move']), '_redinvoice_issue',
                            side_effect=RuntimeError('provider sign-in expired'))
        with boom:
            move.with_user(self.nurse).action_post()
        self.assertEqual(move.state, 'posted', 'posting is never blocked')
        self.assertEqual(move.red_invoice_state, 'failed')
        self.assertIn('could not be sent automatically', move.red_invoice_last_error)
        self.assertIn('provider sign-in expired', move.red_invoice_last_error)

    def test_4_nurses_get_no_general_access_to_e_invoice_records(self):
        with self.assertRaises(AccessError):
            self.env['redinvoice.request'].with_user(self.nurse).search([])
