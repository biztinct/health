from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HealthStaffSkill(models.Model):
    """Healthcare skills and competencies for staff assignment"""
    _name = 'health.staff.skill'
    _description = 'Healthcare Skill'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char('Skill Name', required=True)
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description')
    skill_category_id = fields.Many2one(
        'health.lookup.value',
        string='Category',
        domain="[('category_code', '=', 'staff_skill_category'), ('active', '=', True)]",
        ondelete='restrict',
        default=lambda self: self.env['health.lookup.value']._default_for('staff_skill_category', 'medical'))
    
    required_certification = fields.Boolean('Requires Certification', default=False)
    certification_body = fields.Char('Certification Body')
    
    # Skill importance for assignment scoring
    weight = fields.Float('Assignment Weight', default=1.0, 
                         help='Weight factor for assignment scoring (0.1 - 2.0)')
    
    is_active = fields.Boolean('Active', related='active', store=True, readonly=False)
    
    # Related employees with this skill
    employee_ids = fields.Many2many('hr.employee', 'employee_skill_rel', 
                                   'skill_id', 'employee_id', 
                                   string='Employees with this Skill')
    
    @api.constrains('weight')
    def _check_weight(self):
        for record in self:
            if record.weight < 0.1 or record.weight > 2.0:
                raise ValidationError(_('Weight must be between 0.1 and 2.0'))


class HealthServiceArea(models.Model):
    """Geographic service areas for staff assignment optimization"""
    _name = 'health.service.area'
    _description = 'Service Area'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char('Area Name', required=True)
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description')
    area_code = fields.Char('Area Code', required=True)
    
    # Geographic boundaries (simplified)
    center_latitude = fields.Float('Center Latitude')
    center_longitude = fields.Float('Center Longitude')
    radius_km = fields.Float('Radius (KM)', default=5.0)
    
    # Assignment optimization
    travel_time_minutes = fields.Integer('Average Travel Time (Minutes)', default=15)
    is_active = fields.Boolean('Active', related='active', store=True, readonly=False)
    
    # Coverage priority (1=highest, 5=lowest)
    priority = fields.Selection([
        ('1', 'Highest Priority'),
        ('2', 'High Priority'),
        ('3', 'Normal Priority'),
        ('4', 'Low Priority'),
        ('5', 'Lowest Priority')
    ], string='Coverage Priority', default='3')
    
    # Statistics
    assignment_count = fields.Integer('Total Assignments', 
                                     compute='_compute_assignment_stats')
    average_response_time = fields.Float('Avg Response Time (Minutes)',
                                        compute='_compute_assignment_stats')
    
    @api.depends()
    def _compute_assignment_stats(self):
        """Compute assignment statistics for this service area"""
        for record in self:
            # This would integrate with assignment records
            record.assignment_count = 0
            record.average_response_time = 0.0
