# -*- coding: utf-8 -*-

from markupsafe import Markup
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
    
    is_invoice_paid = fields.Boolean(
        'Invoice Paid',
        compute='_compute_is_invoice_paid',
        store=False,
        help='True if the linked invoice is fully paid'
    )
    
    @api.depends('invoice_id', 'invoice_id.payment_state')
    def _compute_is_invoice_paid(self):
        for fso in self:
            fso.is_invoice_paid = (
                fso.invoice_id and
                fso.invoice_id.payment_state in ('paid', 'in_payment')
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
    
    # Prepaid Package Integration — MULTI-PACKAGE (Many2many)
    # Keep package_id as a compatibility alias (computed from package_ids)
    package_ids = fields.Many2many(
        'health.service.package',
        'health_fso_package_rel',
        'fso_id',
        'package_id',
        string='Service Packages',
        domain="[('patient_id', '=', patient_id), ('state', '=', 'active'), ('remaining_services', '>', 0)]",
        help='Prepaid service packages to consume from (1 service consumed from each)'
    )

    # Backward-compatible computed field so existing code/views referencing package_id still work
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package (Primary)',
        compute='_compute_package_id',
        inverse='_inverse_package_id',
        help='Primary service package (first of package_ids). For backward compatibility.'
    )

    @api.depends('package_ids')
    def _compute_package_id(self):
        for fso in self:
            fso.package_id = fso.package_ids[:1]

    def _inverse_package_id(self):
        for fso in self:
            if fso.package_id:
                fso.package_ids = [(6, 0, [fso.package_id.id])]
            else:
                fso.package_ids = [(5, 0, 0)]
    
    is_package_service = fields.Boolean(
        'Package Service',
        compute='_compute_is_package_service',
        store=True,
        help='True if this FSO consumes from prepaid packages'
    )
    
    package_consumption_quantity = fields.Integer(
        'Services Consumed Per Package',
        default=1,
        help='Number of services consumed from EACH package (default: 1)'
    )
    
    package_service_value = fields.Monetary(
        'Package Service Value',
        currency_field='currency_id',
        compute='_compute_package_service_value',
        store=True,
        help='Total value of services consumed from all packages'
    )
    
    # Legacy field for backward compatibility (will be removed)
    prepaid_consumption_ids = fields.One2many(
        'health.prepaid.service',
        'fso_id',
        string='Prepaid Consumptions (DEPRECATED)',
        help='Legacy prepaid service consumptions - use package_ids instead'
    )
    
    @api.depends('package_ids')
    def _compute_is_package_service(self):
        for fso in self:
            fso.is_package_service = bool(fso.package_ids)
    
    @api.depends('package_ids', 'package_consumption_quantity')
    def _compute_package_service_value(self):
        for fso in self:
            if fso.package_ids and fso.package_consumption_quantity:
                total_value = sum(
                    pkg.price_per_service * fso.package_consumption_quantity
                    for pkg in fso.package_ids
                )
                fso.package_service_value = total_value
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
        If all services are prepaid (invoice fully paid or packages cover it),
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
        
        # Case 2: Service packages cover this booking
        elif self.is_package_service and self.package_ids:
            pkg_names = ', '.join(self.package_ids.mapped('name'))
            is_fully_paid = True
            prepaid_message = _(
                'This service is covered by package(s): %s. '
                'Service completed successfully.'
            ) % pkg_names
        
        if is_fully_paid:
            # Complete the service directly without payment wizard
            self.action_complete_service()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Service Completed - Prepaid'),
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
            amount = 100.0
        
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
    # Package helpers — multi-package aware
    # -------------------------------------------------------------------------
    def _reserve_package_service(self, packages=None):
        """Reserve services from the given packages (default: all assigned).
        Called on booking confirmation, and when packages are assigned to an
        already-confirmed booking."""
        self.ensure_one()
        packages = packages if packages is not None else self.package_ids
        if not packages:
            return False

        quantity_per_pkg = self.package_consumption_quantity or 1
        for pkg in packages:
            pkg.consumed_services += quantity_per_pkg
            try:
                pkg.message_post(
                    body=Markup(_(
                        '<p><strong>Service Reserved</strong></p>'
                        '<ul>'
                        '<li><strong>Booking:</strong> %s</li>'
                        '<li><strong>Patient:</strong> %s</li>'
                        '<li><strong>Services Reserved:</strong> %d</li>'
                        '<li><strong>Services Remaining:</strong> %d</li>'
                        '</ul>'
                    )) % (
                        self.name,
                        self.patient_id.name if self.patient_id else 'N/A',
                        quantity_per_pkg,
                        pkg.remaining_services
                    ),
                    subject=_('Service Reserved - %s') % self.name,
                    message_type='notification'
                )
            except Exception as e:
                _logger.warning('Could not log package reservation for FSO %s: %s', self.name, str(e))

        return True

    def _release_package_service(self, packages=None):
        """Release reserved services from the given packages (default: all assigned).
        Called on cancellation, and when packages are unassigned from an
        already-confirmed booking."""
        self.ensure_one()
        packages = packages if packages is not None else self.package_ids
        if not packages:
            return False

        quantity_per_pkg = self.package_consumption_quantity or 1
        for pkg in packages:
            pkg.consumed_services -= quantity_per_pkg
            if pkg.consumed_services < 0:
                pkg.consumed_services = 0

            if pkg.state == 'exhausted':
                pkg.state = 'active'

            try:
                pkg.message_post(
                    body=Markup(_(
                        '<p><strong>Service Released (Booking Cancelled)</strong></p>'
                        '<ul>'
                        '<li><strong>Booking:</strong> %s</li>'
                        '<li><strong>Patient:</strong> %s</li>'
                        '<li><strong>Services Released:</strong> %d</li>'
                        '<li><strong>Services Remaining:</strong> %d</li>'
                        '</ul>'
                    )) % (
                        self.name,
                        self.patient_id.name if self.patient_id else 'N/A',
                        quantity_per_pkg,
                        pkg.remaining_services
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
        Allow confirmation with either a quote (with lines) or valid packages.
        """
        self.ensure_one()
        has_quote_with_items = (
            self.sale_order_id and
            self.sale_order_id.order_line and
            len(self.sale_order_id.order_line) > 0
        )

        if has_quote_with_items:
            return True, None

        if self.package_ids:
            required_quantity = self.package_consumption_quantity or 1
            insufficient = self.package_ids.filtered(
                lambda p: p.remaining_services < required_quantity
            )
            if insufficient:
                names = ', '.join(insufficient.mapped('name'))
                error_msg = _(
                    'Cannot confirm booking: Package(s) "%s" do not have sufficient remaining services.\n'
                    'Required: %d service(s) per package.\n\n'
                    'Please remove insufficient packages or create a quote instead.'
                ) % (names, required_quantity)
                return False, error_msg
            return True, None

        error_msg = _(
            'Booking cannot be confirmed. You must complete ONE of the following:\n'
            '- Create a Quote with at least one service/product line item\n'
            '- Select a prepaid Service Package'
        )
        return False, error_msg

    def action_confirm_booking(self):
        """Confirm booking, allowing package-based reservations."""
        res = super().action_confirm_booking()
        for order in self:
            if order.package_ids:
                order._reserve_package_service()
        return res

    def cancel_with_reason(self, cancellation_reason_id, cancellation_notes):
        """Release package services if booking is cancelled (only if previously confirmed)."""
        for order in self:
            if order.package_ids and order.state in ('confirmed', 'assigned', 'in_progress'):
                order._release_package_service()
        return super().cancel_with_reason(cancellation_reason_id, cancellation_notes)

    def action_complete_service(self):
        """Allow completion when payment is prepaid via packages."""
        self.ensure_one()

        if not self.clinical_notes_submitted:
            raise UserError(_(
                'Clinical notes are required before completing the service.\n\n'
                'Please fill in at least one of the following:\n'
                '- Clinical Notes\n'
                '- Treatment Performed'
            ))

        if not self.invoice_submitted and not self.package_ids:
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
        """Consume services from ALL assigned packages when FSO is completed"""
        self.ensure_one()
        
        if not self.package_ids:
            return False
        
        qty = self.package_consumption_quantity
        if qty <= 0:
            return False
        
        for pkg in self.package_ids:
            if pkg.remaining_services < qty:
                raise UserError(_(
                    'Cannot consume %d service(s) from package "%s". Only %d service(s) remaining.\n\n'
                    'Please contact operations management if this is unexpected.'
                ) % (qty, pkg.name, pkg.remaining_services))
            
            # Consume
            pkg.consumed_services += qty
            
            # Check if exhausted
            if pkg.remaining_services == 0:
                pkg.state = 'exhausted'
                try:
                    pkg.message_post(
                        body=f"Package exhausted by FSO {self.name} - all {pkg.total_services} services consumed.",
                        subject="Package Services Exhausted"
                    )
                except Exception:
                    pass
            else:
                try:
                    pkg.message_post(
                        body=f"FSO {self.name} consumed {qty} service(s). "
                             f"{pkg.remaining_services} services remaining.",
                        subject="Package Service Consumed"
                    )
                except Exception:
                    pass

        # Record consumption in FSO message
        pkg_names = ', '.join(self.package_ids.mapped('name'))
        try:
            self.message_post(
                body=f"Consumed {qty} service(s) from each of: {pkg_names}. "
                     f"Total service value: {self.package_service_value:,.0f} {self.currency_id.symbol}",
                subject="Package Service Consumed"
            )
        except Exception:
            pass
        
        return True
    
    def write(self, vals):
        """Override write to handle package services"""
        result = super().write(vals)

        # NOTE: Package services are now reserved at booking confirmation time (via _reserve_package_service)
        # We do NOT consume them again at completion to avoid double-consumption.

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

    # ── OWL Package Dialog RPC methods ──

    def get_package_dialog_data(self):
        """Return data for the OWL package selection dialog."""
        self.ensure_one()
        existing = []
        packages = self.env['health.service.package'].search([
            ('patient_id', '=', self.patient_id.id),
            ('state', '=', 'active'),
        ])
        current_ids = self.package_ids.ids
        for pkg in packages:
            existing.append({
                'id': pkg.id,
                'name': pkg.name,
                'service_type': pkg.service_type or '',
                'service_type_label': dict(pkg._fields['service_type'].selection).get(pkg.service_type, ''),
                'total_services': pkg.total_services,
                'consumed_services': pkg.consumed_services,
                'remaining_services': pkg.remaining_services,
                'selectable': pkg.remaining_services > 0,
                'selected': pkg.id in current_ids,
            })

        products = []
        package_products = self.env['product.template'].search([
            ('is_healthcare_package', '=', True),
        ])
        for pt in package_products:
            products.append({
                'id': pt.id,
                'name': pt.name,
                'service_count': pt.healthcare_service_count,
                'price': pt.list_price,
                'price_per_service': pt.healthcare_price_per_visit,
                'package_type': pt.healthcare_package_type or '',
                'package_type_label': dict(pt._fields['healthcare_package_type'].selection).get(pt.healthcare_package_type, ''),
            })

        return {
            'patient_name': self.patient_id.name or '',
            'booking_name': self.name or '',
            'existing_packages': existing,
            'available_products': products,
        }

    # States in which package services have already been reserved
    # (reservation happens at booking confirmation).
    _PACKAGE_RESERVED_STATES = ('confirmed', 'assigned', 'in_progress')

    def action_assign_packages_owl(self, package_ids):
        """Assign selected packages from OWL dialog.

        If the booking has already passed confirmation (when package services are
        reserved), reserve the newly-added packages and release any removed ones so
        usage stays correct even when packages are assigned after confirmation.
        For draft bookings, reservation still happens later at confirmation."""
        self.ensure_one()
        old_pkgs = self.package_ids
        self.write({'package_ids': [(6, 0, package_ids)]})
        if self.state in self._PACKAGE_RESERVED_STATES:
            new_pkgs = self.package_ids
            added = new_pkgs - old_pkgs
            removed = old_pkgs - new_pkgs
            if added:
                self._reserve_package_service(added)
            if removed:
                self._release_package_service(removed)
        return True

    def action_purchase_package_owl(self, product_template_id):
        """Open purchase wizard from OWL dialog."""
        self.ensure_one()
        return {
            'name': _('Purchase Package'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.prepaid.package.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_package_product_id': product_template_id,
                'default_source_fso_id': self.id,
                'default_currency_id': self.env.company.currency_id.id,
            },
        }

    def action_remove_packages_owl(self):
        """Remove all package assignments from OWL dialog.

        Release any services that were reserved (when the booking is past
        confirmation) before clearing the assignment."""
        self.ensure_one()
        if self.state in self._PACKAGE_RESERVED_STATES and self.package_ids:
            self._release_package_service(self.package_ids)
        self.write({'package_ids': [(5, 0, 0)]})
        return True
