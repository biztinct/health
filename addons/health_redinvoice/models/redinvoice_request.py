# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RedInvoiceRequest(models.Model):
    """Tracks outbound Red Invoice API calls and responses."""

    _name = 'redinvoice.request'
    _description = 'Red Invoice Request'
    _order = 'create_date desc'

    name = fields.Char(default='Red Invoice Request', required=True)
    move_id = fields.Many2one('account.move', string='Invoice', ondelete='cascade')
    # account.move already carries a stored catchment (health_invoicing/models/
    # account_move.py:116), so the red-invoice request just follows its invoice.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        related='move_id.catchment_province_id', store=True, index=True,
        readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ], default='pending', tracking=True)
    endpoint = fields.Char(string='Endpoint')
    payload = fields.Text(string='Payload JSON')
    response_code = fields.Char(string='HTTP Code')
    response_body = fields.Text(string='Response Body')
    error_message = fields.Text(string='Error Message')
    retry_count = fields.Integer(default=0)

    def mark_sent(self, code=None, body=None):
        self.write({
            'state': 'sent',
            'response_code': code,
            'response_body': body,
        })

    def mark_success(self, code=None, body=None):
        self.write({
            'state': 'succeeded',
            'response_code': code,
            'response_body': body,
        })

    def mark_failed(self, message, code=None, body=None):
        self.write({
            'state': 'failed',
            'response_code': code,
            'response_body': body,
            'error_message': message,
        })
        _logger.warning("RedInvoice request failed: %s", message)
