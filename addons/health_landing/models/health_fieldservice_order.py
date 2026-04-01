# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HealthFieldserviceOrderDashboard(models.Model):
    """
    Extend FSO model with hub-and-spoke dashboard fields and actions.

    Each node can be in one of four visual tiers:
      - completed   → step is done (green fill, checkmark badge)
      - active      → the single recommended next step (pulsing, guide arrow)
      - available   → clickable but not the immediate priority
      - locked      → prerequisites not met (greyed, lock icon, tooltip reason)
    """
    _inherit = 'health.fieldservice.order'

    # ============================================================================
    # DASHBOARD SPOKE STATE COMPUTED FIELDS  — 4-tier system
    # ============================================================================

    # --- Stage indicators (kept for the status bar) ---
    show_draft_indicator = fields.Boolean(compute='_compute_spoke_states')
    show_booked_indicator = fields.Boolean(compute='_compute_spoke_states')
    show_assigned_indicator = fields.Boolean(compute='_compute_spoke_states')
    show_in_progress_indicator = fields.Boolean(compute='_compute_spoke_states')
    show_completed_indicator = fields.Boolean(compute='_compute_spoke_states')

    # --- Legacy arrow booleans (still needed for backward compat) ---
    show_clinical_notes_arrow = fields.Boolean(compute='_compute_spoke_states')
    show_invoice_arrow = fields.Boolean(compute='_compute_spoke_states')
    show_pay_now_arrow = fields.Boolean(compute='_compute_spoke_states')
    show_pay_later_arrow = fields.Boolean(compute='_compute_spoke_states')
    show_collect_cash_arrow = fields.Boolean(compute='_compute_spoke_states')
    show_payment_received_arrow = fields.Boolean(compute='_compute_spoke_states')

    # --- 4-tier node states (Selection: completed / active / available / locked) ---
    NODE_STATE_SELECTION = [
        ('completed', 'Completed'),
        ('active', 'Active Next Step'),
        ('available', 'Available'),
        ('locked', 'Locked'),
    ]

    node_state_service_packages = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_quote = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_confirm_booking = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_equipment = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_staff_assignment = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_start_service = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_clinical_notes = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_invoice = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_pay_now = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_pay_later = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_collect_cash = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_payment_received = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')
    node_state_complete_service = fields.Selection(NODE_STATE_SELECTION, compute='_compute_spoke_states')

    # --- Tooltip text per node ---
    node_tip_service_packages = fields.Char(compute='_compute_spoke_states')
    node_tip_quote = fields.Char(compute='_compute_spoke_states')
    node_tip_confirm_booking = fields.Char(compute='_compute_spoke_states')
    node_tip_equipment = fields.Char(compute='_compute_spoke_states')
    node_tip_staff_assignment = fields.Char(compute='_compute_spoke_states')
    node_tip_start_service = fields.Char(compute='_compute_spoke_states')
    node_tip_clinical_notes = fields.Char(compute='_compute_spoke_states')
    node_tip_invoice = fields.Char(compute='_compute_spoke_states')
    node_tip_pay_now = fields.Char(compute='_compute_spoke_states')
    node_tip_pay_later = fields.Char(compute='_compute_spoke_states')
    node_tip_collect_cash = fields.Char(compute='_compute_spoke_states')
    node_tip_payment_received = fields.Char(compute='_compute_spoke_states')
    node_tip_complete_service = fields.Char(compute='_compute_spoke_states')

    # --- Single primary next step id ---
    primary_next_step = fields.Char(compute='_compute_spoke_states')

    # --- Hub color based on current stage ---
    hub_stage_color = fields.Char(compute='_compute_spoke_states')

    # Payment tracking fields
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('pay_later', 'Pay Later'),
    ], string='Payment Method', tracking=True)

    cash_collected_by_nurse = fields.Boolean('Cash Collected by Nurse', default=False)
    cash_received_by_om = fields.Boolean('Cash Received by OM', default=False)
    payment_received_date = fields.Datetime('Payment Received Date')

    # ============================================================================
    # COMPUTE — single method for ALL dashboard fields
    # ============================================================================

    @api.depends('state', 'stage_id', 'clinical_notes_submitted', 'invoice_submitted',
                 'sale_order_id', 'invoice_id',
                 'assigned_equipment_ids', 'assigned_staff_ids',
                 'payment_method', 'cash_collected_by_nurse', 'cash_received_by_om',
                 'payment_status')
    def _compute_spoke_states(self):
        """Compute all spoke indicator states for the 4-tier dashboard."""
        STAGE_ORDER = ['draft', 'confirmed', 'assigned', 'in_progress',
                       'completed', 'completed_pending_invoice', 'closed']

        for fso in self:
            state = fso.state or 'draft'

            # -- helpers --
            past_draft = state != 'draft'
            past_confirmed = state not in ('draft', 'confirmed')
            past_assigned = state not in ('draft', 'confirmed', 'assigned')
            is_in_progress = state == 'in_progress'
            is_completed = state in ('completed', 'completed_pending_invoice', 'closed')
            has_quote = bool(fso.sale_order_id)
            has_invoice = bool(fso.invoice_id)
            notes_done = bool(fso.clinical_notes_submitted)
            invoice_done = has_invoice  # actual invoice exists, not just a quote
            payment_done = fso.payment_status == 'paid'
            has_staff = bool(fso.assigned_staff_ids)
            has_packages = self.env['health.service.package'].search_count(
                [('fso_ids', 'in', [fso.id])], limit=1) > 0
            has_equipment = bool(fso.assigned_equipment_ids)

            # ====== Status bar indicators (unchanged for compat) ======
            fso.show_draft_indicator = (state == 'draft')
            fso.show_booked_indicator = (state == 'confirmed')
            fso.show_assigned_indicator = (state == 'assigned')
            fso.show_in_progress_indicator = is_in_progress
            fso.show_completed_indicator = is_completed

            # ====== legacy arrow booleans ======
            fso.show_clinical_notes_arrow = (
                is_in_progress or
                ((is_in_progress or is_completed) and not notes_done)
            )
            fso.show_invoice_arrow = notes_done and not invoice_done
            ready_for_payment = (
                is_in_progress and notes_done and (invoice_done or has_quote)
            )
            fso.show_pay_now_arrow = ready_for_payment
            fso.show_pay_later_arrow = ready_for_payment
            fso.show_collect_cash_arrow = (
                fso.payment_method == 'cash' and
                fso.cash_collected_by_nurse and
                not fso.cash_received_by_om
            )
            fso.show_payment_received_arrow = (
                fso.payment_method == 'pay_later' and
                not fso.payment_received_date
            )

            # ====== Hub color ======
            hub_colors = {
                'draft': '#94a3b8',
                'confirmed': '#3b82f6',
                'assigned': '#0ea5e9',
                'in_progress': '#f97316',
            }
            fso.hub_stage_color = hub_colors.get(state, '#22c55e')

            # ====== 4-tier node states ======
            # Collector to find the single primary next step
            primary = None  # will be set to the first "active" node id

            def _set(node_id, tier, tip):
                """Helper to set node state, tip, and track primary."""
                nonlocal primary
                setattr(fso, f'node_state_{node_id}', tier)
                setattr(fso, f'node_tip_{node_id}', tip)
                if tier == 'active' and primary is None:
                    primary = node_id

            # ---- Service Packages ----
            pkg_count = self.env['health.service.package'].search_count(
                [('fso_ids', 'in', [fso.id])])
            if pkg_count:
                _set('service_packages', 'completed',
                     _('%d package(s) assigned') % pkg_count)
            else:
                _set('service_packages', 'available',
                     _('View and assign service packages'))

            # ---- Quote ----
            if has_quote:
                _set('quote', 'completed', _('Quote created'))
            elif state == 'draft':
                _set('quote', 'active', _('Create a healthcare quote'))
            else:
                _set('quote', 'available', _('View or create quote'))

            # ---- Confirm Booking ----
            if past_draft:
                _set('confirm_booking', 'completed', _('Booking confirmed'))
            elif has_quote:
                _set('confirm_booking', 'active', _('Confirm the booking'))
            else:
                _set('confirm_booking', 'locked',
                     _('Create a quote first'))

            # ---- Equipment ----
            if has_equipment:
                _set('equipment', 'completed',
                     _('%d equipment item(s) assigned') % len(fso.assigned_equipment_ids))
            else:
                _set('equipment', 'available', _('Assign required equipment'))

            # ---- Staff Assignment ----
            if past_confirmed:
                _set('staff_assignment', 'completed', _('Staff assigned'))
            elif state == 'confirmed':
                _set('staff_assignment', 'active', _('Assign staff to this booking'))
            else:
                _set('staff_assignment', 'locked',
                     _('Confirm booking first'))

            # ---- Start Service ----
            if past_assigned:
                _set('start_service', 'completed', _('Service started'))
            elif state == 'assigned':
                _set('start_service', 'active', _('Start the service delivery'))
            else:
                _set('start_service', 'locked',
                     _('Assign staff first'))

            # ---- Clinical Notes ----
            if notes_done:
                _set('clinical_notes', 'completed', _('Clinical notes submitted'))
            elif is_in_progress:
                _set('clinical_notes', 'active', _('Fill in clinical notes'))
            else:
                _set('clinical_notes', 'locked',
                     _('Start service first'))

            # ---- Complete Service ----
            # Must happen BEFORE payment. Transitions state to completed/completed_pending_invoice.
            is_done = state in ('completed', 'completed_pending_invoice', 'closed')
            if is_done:
                _set('complete_service', 'completed', _('Service completed'))
            elif is_in_progress and notes_done:
                _set('complete_service', 'active', _('Complete service and collect payment'))
            elif is_in_progress:
                _set('complete_service', 'locked',
                     _('Complete clinical notes first'))
            else:
                _set('complete_service', 'locked',
                     _('Start service first'))

            # ---- Invoice ----
            # Invoice is "done" if actual invoice exists OR a quote with items exists
            # (the quote IS the billing artifact in this workflow)
            billing_ready = has_invoice or (has_quote and fso.invoice_submitted)
            if has_invoice:
                _set('invoice', 'completed', _('Invoice created'))
            elif has_quote and fso.invoice_submitted:
                _set('invoice', 'completed', _('Quote ready for invoicing'))
            elif is_done or (is_in_progress and notes_done):
                _set('invoice', 'active' if primary is None else 'available',
                     _('Create a quote'))
            else:
                _set('invoice', 'locked',
                     _('Submit clinical notes first'))

            # ---- Pay Now / Pay Later ----
            # Payment is only available AFTER Complete Service (state = completed/completed_pending_invoice)
            # AND billing exists (invoice or quote)
            pay_method = fso.payment_method
            chose_pay_now = pay_method in ('cash', 'card', 'bank_transfer', False, None)
            chose_pay_later = pay_method == 'pay_later'
            ready_for_payment = is_done and billing_ready

            if payment_done and chose_pay_now:
                _set('pay_now', 'completed', _('Payment received'))
            elif payment_done and chose_pay_later:
                _set('pay_now', 'locked', _('Pay Later was selected'))
            elif chose_pay_now and pay_method:
                # Pay Now was selected but payment not fully done yet
                _set('pay_now', 'completed', _('Payment method: %s') % pay_method)
            elif ready_for_payment and not payment_done:
                _set('pay_now', 'active' if primary is None else 'available',
                     _('Collect immediate payment'))
            elif is_done and not billing_ready:
                _set('pay_now', 'locked', _('Create a quote first'))
            else:
                _set('pay_now', 'locked', _('Complete service first'))

            if payment_done and chose_pay_later:
                _set('pay_later', 'completed', _('Payment received'))
            elif payment_done and chose_pay_now:
                _set('pay_later', 'locked', _('Pay Now was selected'))
            elif chose_pay_now and pay_method:
                # Pay Now was selected, lock Pay Later
                _set('pay_later', 'locked', _('Pay Now was selected'))
            elif chose_pay_later:
                _set('pay_later', 'completed', _('Pay Later selected'))
            elif ready_for_payment and not payment_done:
                _set('pay_later', 'available', _('Defer payment'))
            elif is_done and not billing_ready:
                _set('pay_later', 'locked', _('Create a quote first'))
            else:
                _set('pay_later', 'locked', _('Complete service first'))

            # ---- Collect Cash ----
            if fso.cash_received_by_om:
                _set('collect_cash', 'completed', _('Cash received by OM'))
            elif (fso.payment_method == 'cash' and fso.cash_collected_by_nurse
                  and not fso.cash_received_by_om):
                _set('collect_cash', 'active', _('OM to collect cash from nurse'))
            elif fso.payment_method == 'cash':
                _set('collect_cash', 'available', _('Waiting for nurse to collect cash'))
            else:
                _set('collect_cash', 'locked', _('Cash payment not selected'))

            # ---- Payment Received ----
            if fso.payment_received_date:
                _set('payment_received', 'completed', _('Payment received'))
            elif (fso.payment_method == 'pay_later' and not fso.payment_received_date):
                _set('payment_received', 'active', _('Confirm payment received'))
            elif fso.payment_method == 'pay_later':
                _set('payment_received', 'available', _('Awaiting payment'))
            else:
                _set('payment_received', 'locked', _('Pay Later not selected'))

            # Set the single primary next step
            fso.primary_next_step = primary or ''

    # ============================================================================
    # DASHBOARD ACTION METHODS
    # ============================================================================

    def action_open_fso_dashboard(self):
        """Open FSO Hub-and-Spoke Dashboard"""
        self.ensure_one()

        return {
            'name': _('%s Dashboard') % self.name,
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

        if not self.cash_collected_by_nurse:
            raise UserError(_('Cash has not been collected from patient yet.'))

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
