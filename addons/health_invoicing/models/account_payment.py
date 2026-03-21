# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class HealthcarePayment(models.Model):
    """
    Healthcare Payment extending standard Odoo account.payment functionality
    Inherits from account.payment to leverage all standard payment features
    """
    _inherit = 'account.payment'

    # Basic healthcare fields only - test if this resolves the '_unknown' error
    healthcare_payment_type = fields.Selection([
        ('patient_direct', 'Direct Patient Payment'),
        ('insurance_primary', 'Primary Insurance Payment'),
        ('insurance_secondary', 'Secondary Insurance Payment'),
        ('government_subsidy', 'Government Healthcare Subsidy'),
        ('corporate_account', 'Corporate Healthcare Account'),
        ('installment', 'Installment Payment'),
        ('deposit', 'Service Deposit'),
        ('refund', 'Service Refund'),
    ], string='Healthcare Payment Type', help='Type of healthcare payment')
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain="[('is_patient', '=', True)]",
        help='client making or benefiting from this payment'
    )
    
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        help='Booking this payment is for'
    )
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        help='Healthcare appointment this payment is for'
    )
    
    health_transaction_id = fields.Many2one(
        'health.payment.transaction',
        string='Healthcare Transaction',
        help='Related healthcare payment transaction',
        copy=False
    )

    @api.model
    def create(self, vals):
        """Override create to handle basic healthcare payment automation"""
        result = super().create(vals)
        # Auto-populate AR Transaction Log for payments created directly as posted
        for payment in result:
            if payment.state == 'posted':
                try:
                    self.env['health.ar.transaction.log']._create_from_payment(payment)
                except Exception:
                    pass  # Don't block payment if log creation fails
        return result

    def action_post(self):
        """Override action_post to log payments to AR Transaction Log."""
        result = super().action_post()
        for payment in self:
            if payment.state == 'posted':
                try:
                    self.env['health.ar.transaction.log']._create_from_payment(payment)
                except Exception:
                    pass  # Don't block payment if log creation fails
        return result