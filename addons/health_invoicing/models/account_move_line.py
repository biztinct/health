# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import date


class HealthcareMoveLine(models.Model):
    """
    Extend account.move.line with healthcare AR-specific computed fields
    for the Accounts Receivable dashboard.
    """
    _inherit = 'account.move.line'

    # Archive support — inherits from parent move
    active = fields.Boolean(related='move_id.active', store=True)

    # --- Related fields for AR view ---

    partner_phone = fields.Char(
        related='partner_id.phone',
        string='Phone',
        readonly=True,
        store=False,
    )

    facility_id = fields.Many2one(
        related='move_id.fieldservice_order_id.facility_id',
        string='Facility',
        readonly=True,
        store=False,
    )

    catchment_province_id = fields.Many2one(
        related='move_id.catchment_province_id',
        string='Catchment Area',
        readonly=True,
        store=True,
    )

    # --- Computed fields ---

    aging_days = fields.Integer(
        string='Aging (Days)',
        compute='_compute_aging_days',
        store=False,
        help='Number of days past due date. Negative = not yet due.',
    )

    amount_paid = fields.Monetary(
        string='Paid Amount',
        compute='_compute_amount_paid',
        currency_field='company_currency_id',
        store=False,
        help='Total amount minus outstanding residual',
    )

    @api.depends('date_maturity')
    def _compute_aging_days(self):
        today = date.today()
        for line in self:
            if line.date_maturity:
                line.aging_days = (today - line.date_maturity).days
            else:
                line.aging_days = 0

    @api.depends('balance', 'amount_residual')
    def _compute_amount_paid(self):
        for line in self:
            line.amount_paid = abs(line.balance) - abs(line.amount_residual)
