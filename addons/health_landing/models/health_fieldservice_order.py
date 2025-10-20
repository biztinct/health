# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFieldserviceOrderDashboard(models.Model):
    """
    Extend FSO model with hub-and-spoke dashboard fields and actions
    """
    _inherit = 'health.fieldservice.order'

    # ============================================================================
    # DASHBOARD SPOKE STATE COMPUTED FIELDS
    # ============================================================================

    # Stage Indicators (active when FSO is in that stage)
    show_draft_indicator = fields.Boolean(
        'Show Draft Indicator',
        compute='_compute_spoke_states',
        help='True when FSO is in Draft stage'
    )

    show_booked_indicator = fields.Boolean(
        'Show Booked Indicator',
        compute='_compute_spoke_states',
        help='True when FSO is in Booked/Confirmed stage'
    )

    show_assigned_indicator = fields.Boolean(
        'Show Assigned Indicator',
        compute='_compute_spoke_states',
        help='True when FSO is in Assigned stage'
    )

    show_in_progress_indicator = fields.Boolean(
        'Show In Progress Indicator',
        compute='_compute_spoke_states',
        help='True when FSO is in In Progress stage'
    )

    show_completed_indicator = fields.Boolean(
        'Show Completed Indicator',
        compute='_compute_spoke_states',
        help='True when FSO is in Completed stage'
    )

    # Conditional Action Indicators (arrows blink when condition is met)
    show_clinical_notes_arrow = fields.Boolean(
        'Show Clinical Notes Arrow',
        compute='_compute_spoke_states',
        help='Blinks when service is in progress or clinical notes not yet filled'
    )

    show_invoice_arrow = fields.Boolean(
        'Show Invoice Arrow',
        compute='_compute_spoke_states',
        help='Blinks when clinical notes are filled but invoice not yet created'
    )

    show_pay_now_arrow = fields.Boolean(
        'Show Pay Now Arrow',
        compute='_compute_spoke_states',
        help='Blinks when service is in In Progress stage and ready for payment'
    )

    show_pay_later_arrow = fields.Boolean(
        'Show Pay Later Arrow',
        compute='_compute_spoke_states',
        help='Blinks when service is in In Progress stage and payment can be deferred'
    )

    show_collect_cash_arrow = fields.Boolean(
        'Show Collect Cash Arrow',
        compute='_compute_spoke_states',
        help='Blinks when cash payment was collected by nurse and needs OM pickup'
    )

    show_payment_received_arrow = fields.Boolean(
        'Show Payment Received Arrow',
        compute='_compute_spoke_states',
        help='Blinks when Pay Later was selected and payment needs to be received'
    )

    # Payment tracking fields
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('pay_later', 'Pay Later'),
    ], string='Payment Method', tracking=True, help='Method of payment selected')

    cash_collected_by_nurse = fields.Boolean(
        'Cash Collected by Nurse',
        default=False,
        help='True when nurse has collected cash from patient'
    )

    cash_received_by_om = fields.Boolean(
        'Cash Received by OM',
        default=False,
        help='True when Operations Manager has received cash from nurse'
    )

    payment_received_date = fields.Datetime(
        'Payment Received Date',
        help='Date when payment was received'
    )

    @api.depends('state', 'stage_id', 'clinical_notes_submitted', 'invoice_submitted',
                 'payment_method', 'cash_collected_by_nurse', 'cash_received_by_om')
    def _compute_spoke_states(self):
        """Compute all spoke indicator states for dashboard"""
        for fso in self:
            # Stage Indicators (show as active when in that stage)
            fso.show_draft_indicator = (fso.state == 'draft')
            fso.show_booked_indicator = (fso.state == 'confirmed')
            fso.show_assigned_indicator = (fso.state == 'assigned')
            fso.show_in_progress_indicator = (fso.state == 'in_progress')
            fso.show_completed_indicator = (fso.state in ['completed', 'completed_pending_invoice', 'closed'])

            # Clinical Notes Arrow - blinks when:
            # - Service is in progress, OR
            # - Clinical notes not yet submitted
            fso.show_clinical_notes_arrow = (
                fso.state == 'in_progress' or
                (fso.state in ['in_progress', 'completed', 'completed_pending_invoice'] and not fso.clinical_notes_submitted)
            )

            # Invoice Arrow - blinks when:
            # - Clinical notes are submitted, AND
            # - Invoice not yet submitted
            fso.show_invoice_arrow = (
                fso.clinical_notes_submitted and
                not fso.invoice_submitted
            )

            # Pay Now/Pay Later Arrows - blink when:
            # - Service is in In Progress stage, AND
            # - Clinical notes are submitted, AND
            # - Invoice exists (ready for payment)
            ready_for_payment = (
                fso.state == 'in_progress' and
                fso.clinical_notes_submitted and
                (fso.invoice_submitted or fso.sale_order_id)
            )
            fso.show_pay_now_arrow = ready_for_payment
            fso.show_pay_later_arrow = ready_for_payment

            # Collect Cash Arrow - blinks when:
            # - Payment method is cash, AND
            # - Cash collected by nurse, AND
            # - Cash NOT yet received by OM
            fso.show_collect_cash_arrow = (
                fso.payment_method == 'cash' and
                fso.cash_collected_by_nurse and
                not fso.cash_received_by_om
            )

            # Payment Received Arrow - blinks when:
            # - Payment method is Pay Later, AND
            # - Payment not yet received
            fso.show_payment_received_arrow = (
                fso.payment_method == 'pay_later' and
                not fso.payment_received_date
            )

    # ============================================================================
    # DASHBOARD ACTION METHODS
    # ============================================================================

    def action_open_fso_dashboard(self):
        """Open FSO Hub-and-Spoke Dashboard"""
        self.ensure_one()

        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing.fso_hub_spoke_action',
            'params': {
                'fso_id': self.id,
                'fso_name': self.name,
            }
        }

    def action_open_clinical_notes_wizard(self):
        """Open clinical notes wizard for viewing/editing"""
        self.ensure_one()

        return {
            'name': _('Clinical Notes - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'health.fso.clinical.notes.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
            }
        }

    def action_open_invoice_wizard(self):
        """Open invoice display/creation wizard"""
        self.ensure_one()

        return {
            'name': _('Invoice Details - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'health.fso.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
            }
        }

    def action_open_cash_collection_wizard(self):
        """Open cash collection wizard for Operations Manager"""
        self.ensure_one()

        # Validate that cash was collected by nurse
        if not self.cash_collected_by_nurse:
            raise UserError(_('Cash has not been collected from patient yet. Please collect cash from patient first.'))

        if self.cash_received_by_om:
            raise UserError(_('Cash has already been received by Operations Manager.'))

        return {
            'name': _('Collect Cash from Nurse - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'health.fso.cash.collection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
            }
        }
