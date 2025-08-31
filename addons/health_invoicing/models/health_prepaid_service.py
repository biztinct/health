# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthPrepaidService(models.Model):
    """
    DEPRECATED: Individual Service Consumption Tracking
    
    ⚠️ DEPRECATED MODEL - DO NOT USE FOR NEW DEVELOPMENT
    
    This model has been replaced by direct FSO package integration.
    Service consumption is now tracked directly when FSOs are completed.
    
    Legacy functionality maintained for backward compatibility:
    - Links to parent service package
    - Associates with FSO when service is delivered  
    - Tracks consumption date and quantity
    - Maintains service history for audit
    
    NEW APPROACH: Use health.fieldservice.order.package_id field instead
    """
    _name = 'health.prepaid.service'
    _description = 'Prepaid Service Consumption'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'service_date desc'
    _rec_name = 'display_name'
    
    # Core Consumption Information
    name = fields.Char(
        'Consumption Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New Consumption'),
        help='Unique reference for this service consumption'
    )
    
    display_name = fields.Char(
        'Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('name', 'package_id', 'quantity_consumed', 'service_date')
    def _compute_display_name(self):
        for consumption in self:
            if consumption.package_id and consumption.quantity_consumed:
                date_str = consumption.service_date.strftime('%d/%m/%Y') if consumption.service_date else 'No Date'
                consumption.display_name = f"{consumption.package_id.name} - {consumption.quantity_consumed} service(s) on {date_str}"
            else:
                consumption.display_name = consumption.name
    
    # Package and Service Links
    package_id = fields.Many2one(
        'health.service.package',
        string='Service Package',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Parent service package this consumption belongs to'
    )
    
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Field Service Order',
        help='FSO where this prepaid service was delivered'
    )
    
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        related='package_id.patient_id',
        store=True,
        readonly=True,
        help='Patient who consumed this service'
    )
    
    # Consumption Details
    quantity_consumed = fields.Integer(
        'Quantity Consumed',
        required=True,
        default=1,
        tracking=True,
        help='Number of services consumed from the package'
    )
    
    service_date = fields.Datetime(
        'Service Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help='Date and time when service was consumed'
    )
    
    # Service Value Calculation
    unit_value = fields.Monetary(
        'Unit Service Value',
        currency_field='currency_id',
        compute='_compute_unit_value',
        store=True,
        help='Calculated value per service unit consumed'
    )
    
    total_value = fields.Monetary(
        'Total Consumption Value',
        currency_field='currency_id',
        compute='_compute_total_value',
        store=True,
        help='Total value of this consumption (quantity × unit value)'
    )
    
    @api.depends('package_id.price_per_service', 'quantity_consumed')
    def _compute_unit_value(self):
        for consumption in self:
            consumption.unit_value = consumption.package_id.price_per_service if consumption.package_id else 0.0
    
    @api.depends('unit_value', 'quantity_consumed')
    def _compute_total_value(self):
        for consumption in self:
            consumption.total_value = consumption.unit_value * consumption.quantity_consumed
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='package_id.currency_id',
        store=True,
        readonly=True
    )
    
    # Consumption Status
    status = fields.Selection([
        ('consumed', 'Service Consumed'),
        ('invoiced', 'Invoiced'),
        ('refunded', 'Refunded'),
    ], string='Status', default='consumed', tracking=True,
       help='Current status of this service consumption')
    
    # Service Provider Information
    delivered_by_id = fields.Many2one(
        'hr.employee',
        string='Service Delivered By',
        domain="[('is_healthcare_staff', '=', True)]",
        help='Healthcare staff who delivered this service'
    )
    
    service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic Visit'),
        ('remote', 'Remote/Telemedicine'),
        ('other', 'Other Location'),
    ], string='Service Location',
       help='Where this service was delivered')
    
    # Additional Information
    service_notes = fields.Text(
        'Service Notes',
        help='Notes about the service delivery or consumption'
    )
    
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Invoice Line',
        help='Invoice line if this consumption was invoiced separately'
    )
    
    # Create sequence for consumption reference
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New Consumption')) == _('New Consumption'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.prepaid.service') or _('New Consumption')
        return super().create(vals_list)
    
    # Constraints and Validations
    @api.constrains('quantity_consumed')
    def _check_quantity(self):
        for consumption in self:
            if consumption.quantity_consumed <= 0:
                raise ValidationError(_('Consumed quantity must be positive.'))
    
    @api.constrains('package_id', 'quantity_consumed')
    def _check_package_availability(self):
        for consumption in self:
            if consumption.package_id:
                package = consumption.package_id
                # Calculate total consumed including this record
                other_consumptions = self.search([
                    ('package_id', '=', package.id),
                    ('id', '!=', consumption.id)
                ])
                total_consumed = sum(other_consumptions.mapped('quantity_consumed')) + consumption.quantity_consumed
                
                if total_consumed > package.total_services:
                    raise ValidationError(_(
                        'Cannot consume %d services. Package "%s" only has %d services total (%d already consumed).'
                    ) % (consumption.quantity_consumed, package.name, package.total_services, 
                         total_consumed - consumption.quantity_consumed))
    
    # Business Logic Methods
    def action_mark_invoiced(self):
        """Mark this consumption as invoiced"""
        self.ensure_one()
        
        if self.status == 'invoiced':
            raise UserError(_('This consumption is already marked as invoiced.'))
        
        self.status = 'invoiced'
        self.message_post(
            body=f"Service consumption marked as invoiced: {self.quantity_consumed} service(s) worth {self.total_value:,.0f} {self.currency_id.symbol}",
            subject="Consumption Invoiced"
        )
    
    def action_create_refund(self):
        """Create refund for this consumption"""
        self.ensure_one()
        
        if self.status == 'refunded':
            raise UserError(_('This consumption is already refunded.'))
        
        # Create refund transaction
        refund = self.env['health.payment.transaction'].create({
            'patient_id': self.patient_id.id,
            'fso_id': self.fso_id.id if self.fso_id else False,
            'package_id': self.package_id.id,
            'amount': -self.total_value,  # Negative amount for refund
            'payment_method': 'cash',  # Default to cash refund
            'transaction_type': 'refund',
            'status': 'collected',
            'collected_by_id': self.env.user.employee_id.id,
            'transaction_notes': f'Refund for prepaid service consumption {self.name}',
        })
        
        # Update consumption status
        self.status = 'refunded'
        
        # Return services to package
        self.package_id.consumed_services -= self.quantity_consumed
        if self.package_id.state == 'exhausted' and self.package_id.remaining_services > 0:
            self.package_id.state = 'active'
        
        return {
            'name': _('Refund Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.payment.transaction',
            'res_id': refund.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_fso(self):
        """View related Field Service Order"""
        self.ensure_one()
        
        if not self.fso_id:
            raise UserError(_('No Field Service Order associated with this consumption.'))
        
        return {
            'name': _('Field Service Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'res_id': self.fso_id.id,
            'view_mode': 'form',
            'target': 'current',
        }