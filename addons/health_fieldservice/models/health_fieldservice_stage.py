from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HealthFieldServiceStage(models.Model):
    """
    Field Service Order Stages - Standalone model for FSO workflow stages
    """
    _name = 'health.fieldservice.stage'
    _description = 'Healthcare Booking Stages'
    _order = 'sequence, name'
    
    name = fields.Char('Stage Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    sequence = fields.Integer('Sequence', default=10)
    
    # KEY: State mapping for backend logic
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('completed_pending_invoice', 'Completed - Pending Invoice'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Related State', required=False, default='draft',
       help='Backend state that this stage represents for logic and validation')
    
    # Kanban view configuration
    color = fields.Integer('Color Index', default=0,
                          help='Color index (0-12) for kanban view. 0=No Color, 1=Red, 2=Orange, 3=Yellow, 4=Light Blue, 5=Dark Purple, 6=Salmon Pink, 7=Medium Blue, 8=Dark Blue, 9=Fuchsia, 10=Green, 11=Purple, 12=Dark Red')
    fold = fields.Boolean('Folded in Kanban', default=False)
    
    # Stage requirements and validations
    require_quote = fields.Boolean('Require Quote', default=False,
                                   help='Quote must exist to move to this stage')
    require_quote_items = fields.Boolean('Require Quote Items', default=False,
                                        help='Quote must have items to move to this stage')
    require_staff_assignment = fields.Boolean('Require Staff Assignment', default=False,
                                             help='Staff must be assigned to move to this stage')
    require_patient_contact = fields.Boolean('Require Patient Contact', default=False,
                                            help='client contact must be confirmed to move to this stage')
    
    # Stage behavior
    is_closed = fields.Boolean('Is Closed Stage', default=False, 
                              help="Indicates this is a final stage (completed/cancelled)")
    is_default = fields.Boolean('Default Stage', default=False,
                               help="This stage is used as default for new FSOs")
    allow_edit = fields.Boolean('Allow Editing', default=True,
                               help="Whether FSOs in this stage can be edited")
    
    # Active flag
    active = fields.Boolean('Active', default=True)
    
    # Related fields
    fso_count = fields.Integer('FSO Count', compute='_compute_fso_count')
    
    @api.depends()
    def _compute_fso_count(self):
        """Count FSOs in this stage"""
        for stage in self:
            stage.fso_count = self.env['health.fieldservice.order'].search_count([
                ('stage_id', '=', stage.id)
            ])
    
    @api.model
    def _get_default_stage(self):
        """Get the default stage for new FSOs"""
        return self.search([('is_default', '=', True)], limit=1) or self.search([], limit=1)
    
    def validate_stage_requirements(self, fso):
        """Validate if FSO meets requirements to move to this stage"""
        self.ensure_one()
        errors = []
        
        if self.require_quote and not fso.sale_order_id:
            errors.append(_('Quote is required for stage "%s"') % self.name)
        
        if self.require_quote_items and (not fso.sale_order_id or not fso.sale_order_id.order_line):
            errors.append(_('Quote with items is required for stage "%s"') % self.name)
        
        if self.require_staff_assignment and not fso.assigned_staff_ids:
            errors.append(_('Staff assignment is required for stage "%s"') % self.name)
        
        if self.require_patient_contact and not fso.patient_contact_confirmed:
            errors.append(_('Patient contact confirmation is required for stage "%s"') % self.name)
        
        return errors
    
    @api.constrains('state', 'is_default')
    def _check_default_stage(self):
        """Ensure only one default stage per state"""
        for stage in self:
            if stage.is_default:
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('state', '=', stage.state),
                    ('id', '!=', stage.id)
                ])
                if other_defaults:
                    raise ValidationError(_('Only one stage can be default for state "%s"') % stage.state)
    
    def action_view_fsos(self):
        """Action to view FSOs in this stage"""
        self.ensure_one()
        return {
            'name': f'Bookings - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form,kanban',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id}
        }