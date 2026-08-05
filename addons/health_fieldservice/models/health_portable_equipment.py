from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HealthPortableEquipment(models.Model):
    """
    Portable Medical Equipment - Track equipment for field service operations
    """
    _name = 'health.portable.equipment'
    _description = 'Portable Medical Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'health.lifecycle.mixin']
    _order = 'name'
    
    name = fields.Char('Equipment Name', required=True, tracking=True)
    description = fields.Text('Description')
    
    # Equipment classification
    equipment_type = fields.Selection([
        ('diagnostic', 'Diagnostic Equipment'),
        ('therapeutic', 'Therapeutic Equipment'),
        ('monitoring', 'Monitoring Equipment'),
        ('safety', 'Safety Equipment'),
        ('supplies', 'Medical Supplies'),
        ('documentation', 'Documentation Equipment')
    ], string='Equipment Type', required=True, tracking=True)
    
    category = fields.Char('Category', help="Specific category within type (e.g., 'Blood Pressure Monitor')")
    
    # Equipment identification
    serial_number = fields.Char('Serial Number', tracking=True)
    model_number = fields.Char('Model Number')
    manufacturer = fields.Char('Manufacturer')
    
    # Equipment status
    status = fields.Selection([
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('calibration', 'Calibration Required'),
        ('repair', 'Under Repair'),
        ('unavailable', 'Unavailable'),
        ('retired', 'Retired')
    ], string='Status', default='available', tracking=True, required=True)
    
    # Assignment tracking
    current_fso_id = fields.Many2one('health.fieldservice.order', 
                                    string='Current Assignment',
                                    help="Currently assigned to this field service order")
    
    assigned_team_id = fields.Many2one('health.fieldservice.team',
                                      string='Assigned Team',
                                      help="Team that currently has this equipment")
    
    assigned_staff_id = fields.Many2one('hr.employee',
                                       string='Assigned Staff',
                                       domain=[('is_healthcare_staff', '=', True)],
                                       help="Staff member currently assigned this equipment")

    # Equipment physically lives in an area and keeps it while idle, so this is
    # an editable field of its own rather than something computed from the
    # current assignment — a computed one would blank out the moment a device
    # came back off a visit, and fail-closed would then hide it from everybody.
    # Defaulted from the assigned staff member as a convenience only.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area', index=True,
        tracking=True,
        help="The area this equipment is based in. Staff only see equipment "
             "from their own area.")

    @api.onchange('assigned_staff_id')
    def _onchange_assigned_staff_catchment(self):
        """Fill the area from the staff member, never overwrite a set one."""
        for rec in self:
            if rec.assigned_staff_id and not rec.catchment_province_id:
                rec.catchment_province_id = \
                    rec.assigned_staff_id.staff_catchment_province_id
    
    # Equipment specifications
    weight_kg = fields.Float('Weight (kg)')
    dimensions = fields.Char('Dimensions')
    power_source = fields.Selection([
        ('battery', 'Battery Powered'),
        ('mains', 'Mains Power'),
        ('both', 'Battery + Mains'),
        ('manual', 'Manual Operation'),
        ('none', 'No Power Required')
    ], string='Power Source')
    
    battery_life_hours = fields.Float('Battery Life (hours)')
    
    # Maintenance and compliance
    last_maintenance_date = fields.Date('Last Maintenance', tracking=True)
    next_maintenance_date = fields.Date('Next Maintenance Due', tracking=True)
    calibration_due_date = fields.Date('Calibration Due', tracking=True)
    
    maintenance_interval_days = fields.Integer('Maintenance Interval (days)', default=90)
    calibration_interval_days = fields.Integer('Calibration Interval (days)', default=365)
    
    # Compliance and certification
    certification_number = fields.Char('Certification Number')
    certification_expiry = fields.Date('Certification Expiry')
    regulatory_approval = fields.Char('Regulatory Approval (e.g., FDA, CE)')
    
    # Usage tracking
    total_usage_hours = fields.Float('Total Usage Hours', readonly=True)
    usage_count = fields.Integer('Usage Count', readonly=True,
                                help="Number of times this equipment has been used")
    
    # Service history
    service_history_ids = fields.One2many('health.equipment.service.history',
                                         'equipment_id',
                                         string='Service History')
    
    # Financial information
    purchase_date = fields.Date('Purchase Date')
    purchase_cost = fields.Monetary('Purchase Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Required for specific service types
    required_for_service_ids = fields.Many2many('health.service.type',
                                               string='Required for Services',
                                               help="Service types that require this equipment")
    
    # Active status
    active = fields.Boolean('Active', default=True)
    
    # Computed fields
    is_maintenance_due = fields.Boolean('Maintenance Due', compute='_compute_maintenance_status', store=True)
    is_calibration_due = fields.Boolean('Calibration Due', compute='_compute_maintenance_status', store=True)
    days_until_maintenance = fields.Integer('Days Until Maintenance', compute='_compute_maintenance_status', store=True)
    
    @api.depends('next_maintenance_date', 'calibration_due_date')
    def _compute_maintenance_status(self):
        """Compute maintenance and calibration status"""
        today = fields.Date.today()
        
        for equipment in self:
            # Maintenance status
            if equipment.next_maintenance_date:
                equipment.days_until_maintenance = (equipment.next_maintenance_date - today).days
                equipment.is_maintenance_due = equipment.next_maintenance_date <= today
            else:
                equipment.days_until_maintenance = 0
                equipment.is_maintenance_due = False
            
            # Calibration status
            if equipment.calibration_due_date:
                equipment.is_calibration_due = equipment.calibration_due_date <= today
            else:
                equipment.is_calibration_due = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Set initial maintenance dates if not provided"""
        for vals in vals_list:
            if not vals.get('next_maintenance_date') and vals.get('maintenance_interval_days'):
                vals['next_maintenance_date'] = fields.Date.add(
                    fields.Date.today(), 
                    days=vals['maintenance_interval_days']
                )
            
            if not vals.get('calibration_due_date') and vals.get('calibration_interval_days'):
                vals['calibration_due_date'] = fields.Date.add(
                    fields.Date.today(),
                    days=vals['calibration_interval_days']
                )
        
        return super().create(vals_list)
    
    def action_assign_to_fso(self):
        """Assign equipment to a field service order"""
        self.ensure_one()
        
        if self.status != 'available':
            raise ValidationError(_("Equipment must be available to assign to field service order."))
        
        return {
            'name': 'Assign Equipment to Field Service Order',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'domain': [('current_status', 'not in', ['completed', 'cancelled'])],
            'context': {'default_assigned_equipment_ids': [(4, self.id)]}
        }
    
    def action_mark_in_use(self, fso_id=None):
        """Mark equipment as in use"""
        self.ensure_one()
        
        if self.status != 'available':
            raise ValidationError(_("Only available equipment can be marked as in use."))
        
        self.status = 'in_use'
        if fso_id:
            self.current_fso_id = fso_id
        
        # Record usage
        self.usage_count += 1
    
    def action_mark_available(self):
        """Mark equipment as available"""
        self.ensure_one()
        
        self.status = 'available'
        self.current_fso_id = False
        self.assigned_staff_id = False
    
    def action_schedule_maintenance(self):
        """Schedule maintenance for equipment"""
        self.ensure_one()
        
        return {
            'name': f'Schedule Maintenance - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.equipment.service.history',
            'view_mode': 'form',
            'context': {
                'default_equipment_id': self.id,
                'default_service_type': 'maintenance',
                'default_scheduled_date': fields.Date.today()
            },
            'target': 'new'
        }
    
    def action_view_service_history(self):
        """View equipment service history"""
        self.ensure_one()
        
        return {
            'name': f'Service History - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.equipment.service.history',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id}
        }


class HealthEquipmentServiceHistory(models.Model):
    """
    Equipment Service History - Track maintenance, calibration, and repairs
    """
    _name = 'health.equipment.service.history'
    _description = 'Equipment Service History'
    _order = 'service_date desc'
    
    active = fields.Boolean('Active', default=True)

    equipment_id = fields.Many2one('health.portable.equipment', required=True, ondelete='cascade')
    
    service_type = fields.Selection([
        ('maintenance', 'Routine Maintenance'),
        ('calibration', 'Calibration'),
        ('repair', 'Repair'),
        ('inspection', 'Inspection'),
        ('upgrade', 'Upgrade/Modification')
    ], required=True)
    
    service_date = fields.Date('Service Date', required=True)
    scheduled_date = fields.Date('Scheduled Date')
    completed_date = fields.Date('Completed Date')
    
    service_provider = fields.Char('Service Provider')
    technician_name = fields.Char('Technician Name')
    
    description = fields.Text('Service Description')
    findings = fields.Text('Findings/Issues')
    actions_taken = fields.Text('Actions Taken')
    
    cost = fields.Monetary('Service Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    next_service_due = fields.Date('Next Service Due')
    
    # Attachments for certificates, reports
    attachment_ids = fields.Many2many('ir.attachment', string='Service Documents')
    
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='scheduled', required=True)
