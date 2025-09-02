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
        string='Patient',
        domain="[('is_patient', '=', True)]",
        help='Patient making or benefiting from this payment'
    )
    
    fieldservice_order_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        help='Field service order this payment is for'
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
        return super().create(vals)