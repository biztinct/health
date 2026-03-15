# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'
    
    # Optional Insurance Claim linkage (kept in invoicing to avoid base dependency)
    insurance_claim_id = fields.Many2one(
        'account.move',
        string='Insurance Claim Invoice',
        domain="[('move_type', '=', 'out_invoice'), ('partner_id', '=', patient_id), ('has_insurance_claim', '=', True)]",
        help='Link to an invoice that carries insurance claim data for this service order.'
    )
    
    # Enhanced Invoice Integration
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        help='Invoice generated for this service order',
        copy=False
    )
    
    is_invoiced = fields.Boolean(
        'Invoiced',
        default=False,
        help='Whether this FSO has been invoiced'
    )
    
    payment_transaction_ids = fields.One2many(
        'health.payment.transaction',
        'fso_id',
        string='Payment Transactions',
        help='Payment transactions for this service order'
    )
    
    payment_transaction_count = fields.Integer(
        'Payment Count',
        compute='_compute_payment_count',
        help='Number of payment transactions'
    )
    
    total_paid_amount = fields.Monetary(
        'Total Paid',
        currency_field='currency_id',
        compute='_compute_payment_summary',
        help='Total amount paid for this service'
    )
    
    outstanding_amount = fields.Monetary(
        'Outstanding Amount',
        currency_field='currency_id',
        compute='_compute_payment_summary',
        help='Outstanding amount if invoice exists'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Prepaid Package Integration (REPLACING health.prepaid.service model)
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package',
        domain="[('patient_id', '=', patient_id), ('state', '=', 'active'), ('remaining_services', '>', 0)]",
        help='Prepaid service package to consume from (if any)'
    )
    
    is_package_service = fields.Boolean(
        'Package Service',
        compute='_compute_is_package_service',
        store=True,
        help='True if this FSO consumes from a prepaid package'
    )
    
    package_consumption_quantity = fields.Integer(
        'Services Consumed',
        default=1,
        help='Number of services consumed from the package (default: 1)'
    )
    
    package_service_value = fields.Monetary(
        'Package Service Value',
        currency_field='currency_id',
        compute='_compute_package_service_value',
        store=True,
        help='Value of services consumed from package'
    )
    
    # Legacy field for backward compatibility (will be removed)
    prepaid_consumption_ids = fields.One2many(
        'health.prepaid.service',
        'fso_id',
        string='Prepaid Consumptions (DEPRECATED)',
        help='Legacy prepaid service consumptions - use package_id instead'
    )
    
    @api.depends('package_id')
    def _compute_is_package_service(self):
        for fso in self:
            fso.is_package_service = bool(fso.package_id)
    
    @api.depends('package_id', 'package_consumption_quantity')
    def _compute_package_service_value(self):
        for fso in self:
            if fso.package_id and fso.package_consumption_quantity:
                fso.package_service_value = fso.package_id.price_per_service * fso.package_consumption_quantity
            else:
                fso.package_service_value = 0.0
    
    @api.depends('payment_transaction_ids')
    def _compute_payment_count(self):
        for fso in self:
            fso.payment_transaction_count = len(fso.payment_transaction_ids)
    
    @api.depends('invoice_id', 'payment_transaction_ids')
    def _compute_payment_summary(self):
        for fso in self:
            fso.total_paid_amount = sum(fso.payment_transaction_ids.mapped('amount'))
            
            if fso.invoice_id:
                fso.outstanding_amount = fso.invoice_id.amount_residual
            else:
                fso.outstanding_amount = 0.0
    
    # Enhanced FSO Completion Workflow
    def action_complete_service_with_payment(self):
        """Complete service and launch payment collection workflow.
        If all services are prepaid (invoice fully paid or package covers it),
        skip the payment wizard and complete directly with a notification.
        """
        self.ensure_one()

        if self.state != 'in_progress':
            raise UserError(_('Only services in progress can be completed.'))
        
        # Check if fully prepaid
        is_fully_paid = False
        prepaid_message = ''
        
        # Case 1: Invoice exists and is fully paid
        if self.invoice_id and self.invoice_id.payment_state in ('paid', 'in_payment'):
            is_fully_paid = True
            prepaid_message = _(
                'All services have been prepaid via invoice %s. '
                'Service completed successfully.'
            ) % self.invoice_id.name
        
        # Case 2: Service package covers this booking
        elif self.is_package_service and self.package_id:
            is_fully_paid = True
            prepaid_message = _(
                'This service is covered by package "%s" (%d remaining). '
                'Service completed successfully.'
            ) % (self.package_id.name, self.package_id.remaining_services)
        
        if is_fully_paid:
            # Complete the service directly without payment wizard
            self.action_complete_service()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Service Completed - Prepaid'),
                    'message': prepaid_message,
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        
        if self.is_invoiced:
            raise UserError(_('This service has already been invoiced.'))
        
        # Launch nurse payment collection wizard
        return {
            'name': _('Complete Service - Payment Collection'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.nurse.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_prepay_quote(self):
        """Prepay the quote: create invoice from sale order and open payment registration."""
        self.ensure_one()
        
        if not self.sale_order_id:
            raise UserError(_('No quote exists for this booking. Please create a quote first.'))
        
        if not self.sale_order_id.order_line:
            raise UserError(_('The quote has no line items. Please add services to the quote first.'))
        
        # Step 1: Confirm the sale order if still in draft/sent
        if self.sale_order_id.state in ('draft', 'sent'):
            self.sale_order_id.action_confirm()
        
        # Step 2: Create invoice from confirmed sale order if not already invoiced
        if not self.invoice_id:
            # Create invoice directly from sale order lines (full amount, not delivered qty)
            invoices = self.sale_order_id._create_invoices(final=True)
            
            if invoices:
                invoice = invoices[0]
                # Post (validate) the invoice
                invoice.action_post()
                # Link to FSO
                self.write({
                    'invoice_id': invoice.id,
                    'is_invoiced': True,
                })
            else:
                raise UserError(_('Could not create invoice from the quote.'))
        
        invoice = self.invoice_id
        
        # Step 3: Check if already fully paid
        if invoice.payment_state in ('paid', 'in_payment'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Already Paid'),
                    'message': _('Invoice %s is already fully paid.') % invoice.name,
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Step 4: Open payment registration wizard with clean context
        # Must NOT inherit parent context which has active_model='health.fieldservice.order'
        # The wizard's default_get needs active_model='account.move' with the invoice IDs
        ctx = {
            'active_model': 'account.move',
            'active_ids': [invoice.id],
            'active_id': invoice.id,
            'dont_redirect_to_payments': True,
        }
        return {
            'name': _('Register Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
    
    def action_view_payment_transactions(self):
        """View payment transactions for this FSO"""
        self.ensure_one()
        
        return {
            'name': _('Payment Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'domain': [('fso_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {
                'default_fso_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_view_invoice(self):
        """View invoice for this FSO"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_('No invoice has been created for this service order.'))
        
        return {
            'name': _('Service Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_manual_invoice(self):
        """Create invoice manually (alternative to nurse workflow)"""
        self.ensure_one()
        
        if self.is_invoiced:
            raise UserError(_('This service has already been invoiced.'))
        
        # Calculate service amount
        amount = 0.0
        if self.appointment_type_id:
            amount += self.appointment_type_id.price or 0.0
        elif self.base_price:
            amount += self.base_price
        else:
            # Default amount if no specific pricing found
            amount = 100.0  # Default service amount
        
        # Create invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_origin': f'FSO: {self.name}',
            'invoice_line_ids': [(0, 0, {
                'name': f'{dict(self._fields["service_type"].selection).get(self.service_type, "Healthcare Service")} - {self.name}',
                'quantity': 1,
                'price_unit': amount,
                'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            })],
        })
        
        # Link invoice to FSO
        self.write({
            'invoice_id': invoice.id,
            'is_invoiced': True,
        })
        
        return {
            'name': _('Service Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # Package helpers (moved from health_fieldservice)
    # -------------------------------------------------------------------------
    def _reserve_package_service(self):
        """Reserve services from the package on booking confirmation."""
        self.ensure_one()
        if not self.package_id:
            return False

        quantity_to_reserve = self.package_consumption_quantity or 1
        self.package_id.consumed_services += quantity_to_reserve

        try:
            self.package_id.message_post(
                body=_(
                    '<p><strong>Service Reserved</strong></p>'
                    '<ul>'
                    '<li><strong>Booking:</strong> %s</li>'
                    '<li><strong>Patient:</strong> %s</li>'
                    '<li><strong>Services Reserved:</strong> %d</li>'
                    '<li><strong>Services Remaining:</strong> %d</li>'
                    '</ul>'
                ) % (
                    self.name,
                    self.patient_id.name if self.patient_id else 'N/A',
                    quantity_to_reserve,
                    self.package_id.remaining_services
                ),
                subject=_('Service Reserved - %s') % self.name,
                message_type='notification'
            )
        except Exception as e:
            _logger.warning('Could not log package reservation for FSO %s: %s', self.name, str(e))

        return True

    def _release_package_service(self):
        """Release reserved services if booking is cancelled."""
        self.ensure_one()
        if not self.package_id:
            return False

        quantity_to_release = self.package_consumption_quantity or 1
        self.package_id.consumed_services -= quantity_to_release
        if self.package_id.consumed_services < 0:
            self.package_id.consumed_services = 0

        if self.package_id.state == 'exhausted':
            self.package_id.state = 'active'

        try:
            self.package_id.message_post(
                body=_(
                    '<p><strong>Service Released (Booking Cancelled)</strong></p>'
                    '<ul>'
                    '<li><strong>Booking:</strong> %s</li>'
                    '<li><strong>Patient:</strong> %s</li>'
                    '<li><strong>Services Released:</strong> %d</li>'
                    '<li><strong>Services Remaining:</strong> %d</li>'
                    '</ul>'
                ) % (
                    self.name,
                    self.patient_id.name if self.patient_id else 'N/A',
                    quantity_to_release,
                    self.package_id.remaining_services
                ),
                subject=_('Service Released - %s') % self.name,
                message_type='notification'
            )
        except Exception as e:
            _logger.warning('Could not log package release for FSO %s: %s', self.name, str(e))

        return True

    # -------------------------------------------------------------------------
    # Overrides to re-enable package workflows
    # -------------------------------------------------------------------------
    def _check_confirmation_requirements(self):
        """
        Allow confirmation with either a quote (with lines) or a valid package.
        """
        self.ensure_one()
        has_quote_with_items = (
            self.sale_order_id and
            self.sale_order_id.order_line and
            len(self.sale_order_id.order_line) > 0
        )

        if has_quote_with_items:
            return True, None

        if self.package_id:
            required_quantity = self.package_consumption_quantity or 1
            if self.package_id.remaining_services < required_quantity:
                error_msg = _(
                    'Cannot confirm booking: Package "%s" does not have sufficient remaining services.\n'
                    'Required: %d service(s)\n'
                    'Available: %d service(s)\n\n'
                    'Please select a different package or create a quote instead.'
                ) % (self.package_id.name, required_quantity, self.package_id.remaining_services)
                return False, error_msg
            return True, None

        error_msg = _(
            'Booking cannot be confirmed. You must complete ONE of the following:\n'
            '• Create a Quote with at least one service/product line item\n'
            '• Select a prepaid Service Package'
        )
        return False, error_msg

    def action_confirm_booking(self):
        """Confirm booking, allowing package-based reservations."""
        res = super().action_confirm_booking()
        for order in self:
            if order.package_id:
                order._reserve_package_service()
        return res

    def cancel_with_reason(self, cancellation_reason_id, cancellation_notes):
        """Release package services if booking is cancelled."""
        for order in self:
            if order.package_id:
                order._release_package_service()
        return super().cancel_with_reason(cancellation_reason_id, cancellation_notes)

    def action_complete_service(self):
        """Allow completion when payment is prepaid via package."""
        self.ensure_one()

        if not self.clinical_notes_submitted:
            raise UserError(_(
                'Clinical notes are required before completing the service.\n\n'
                'Please fill in at least one of the following:\n'
                '• Clinical Notes\n'
                '• Treatment Performed'
            ))

        if not self.invoice_submitted and not self.package_id:
            raise UserError(_(
                'Invoice or Quote is required before completing the service.\n\n'
                'Alternatively, a service package must be assigned if payment is prepaid.'
            ))

        if self._check_invoice_creation_permission():
            completed_stage = self.env['health.fieldservice.stage'].search([
                ('state', '=', 'completed'),
                ('active', '=', True)
            ], order='sequence', limit=1)

            if not completed_stage:
                _logger.warning('No Completed stage found')

            self.write({
                'stage_id': completed_stage.id if completed_stage else False,
                'state': 'completed',
                'actual_end_datetime': fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Service Completed'),
                    'message': _('Service marked as completed. Create invoice and process payment when ready.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            completion_note = f'Completed by part-time staff ({self.lead_staff_id.name if self.lead_staff_id else "staff"}) - requires Operations invoicing'

            completed_pending_stage = self.env['health.fieldservice.stage'].search([
                ('state', '=', 'completed_pending_invoice'),
                ('active', '=', True)
            ], order='sequence', limit=1)

            if not completed_pending_stage:
                _logger.warning('No Completed-Pending Invoice stage found')
                completed_pending_stage = self.env['health.fieldservice.stage'].search([
                    ('state', '=', 'completed'),
                    ('active', '=', True)
                ], order='sequence', limit=1)

            self.write({
                'stage_id': completed_pending_stage.id if completed_pending_stage else False,
                'state': 'completed_pending_invoice',
                'actual_end_datetime': fields.Datetime.now(),
                'completion_notes': completion_note,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Service Completed'),
                    'message': _('Service completed successfully. Invoice has been created during quote verification.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
    
    # Package Service Consumption Methods
    def action_consume_package_service(self):
        """Consume services from package when FSO is completed"""
        self.ensure_one()
        
        if not self.package_id:
            return False
        
        if self.package_consumption_quantity <= 0:
            return False
        
        if self.package_id.remaining_services < self.package_consumption_quantity:
            raise UserError(_(
                'Cannot consume %d service(s) from package "%s". Only %d service(s) remaining.\n\n'
                'This may have happened because other field service orders completed and consumed '
                'services from the same package. This validation is performed to ensure accurate '
                'package tracking. Please contact operations management if this is unexpected.'
            ) % (self.package_consumption_quantity, self.package_id.name, self.package_id.remaining_services))
        
        # Consume services from package (direct consumption without separate model)
        self.package_id.consumed_services += self.package_consumption_quantity
        
        # Check if package is exhausted
        if self.package_id.remaining_services == 0:
            self.package_id.state = 'exhausted'
            try:
                self.package_id.message_post(
                    body=f"Package exhausted by FSO {self.name} - all {self.package_id.total_services} services consumed.",
                    subject="Package Services Exhausted"
                )
            except Exception:
                pass  # Silently fail - no email notifications required
        else:
            try:
                self.package_id.message_post(
                    body=f"FSO {self.name} consumed {self.package_consumption_quantity} service(s). "
                         f"{self.package_id.remaining_services} services remaining.",
                    subject="Package Service Consumed"
                )
            except Exception:
                pass  # Silently fail - no email notifications required

        # Record consumption in FSO message
        try:
            self.message_post(
                body=f"Consumed {self.package_consumption_quantity} service(s) from package '{self.package_id.name}'. "
                     f"Service value: {self.package_service_value:,.0f} {self.currency_id.symbol}",
                subject="Package Service Consumed"
            )
        except Exception:
            pass  # Silently fail - no email notifications required
        
        return True
    
    @api.onchange('package_id')
    def _onchange_package_id(self):
        """Auto-fill service details when package is selected"""
        if self.package_id:
            # Auto-set service type if it matches
            if self.package_id.service_type in dict(self._fields.get('service_type', fields.Selection([])).selection):
                self.service_type = self.package_id.service_type
    
    def write(self, vals):
        """Override write to handle package services"""
        result = super().write(vals)

        # NOTE: Package services are now reserved at booking confirmation time (via _reserve_package_service)
        # We do NOT consume them again at completion to avoid double-consumption.
        # The reservation that happens at booking confirmation is sufficient to manage package inventory.

        return result

    def action_open_service_package_wizard(self):
        """Open the Service Package selection wizard."""
        self.ensure_one()
        if not self.patient_id:
            raise UserError(_('Please set a client before selecting a service package.'))

        return {
            'name': _('Select Service Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.service.package.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fso_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
        }
