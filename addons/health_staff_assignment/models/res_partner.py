from odoo import models, fields, api


class ResPartner(models.Model):
    """Extend res.partner with assignment-related patient data"""
    _inherit = 'res.partner'
    
    # Assignment preferences for patients
    preferred_staff_id = fields.Many2one(
        'hr.employee',
        string='Preferred Healthcare Staff',
        domain=[('is_healthcare_staff', '=', True)],
        help='Patient\'s preferred healthcare professional'
    )
    
    assignment_notes = fields.Text(
        'Assignment Notes',
        help='Special notes for staff assignment (accessibility, language preferences, etc.)'
    )
    
    # Assignment history
    total_assignments = fields.Integer(
        'Total Assignments',
        compute='_compute_assignment_stats'
    )
    
    last_assignment_date = fields.Datetime(
        'Last Assignment Date',
        compute='_compute_assignment_stats'
    )
    
    @api.depends('name')
    def _compute_assignment_stats(self):
        """Calculate assignment statistics for patients"""
        for partner in self:
            if hasattr(partner, 'is_patient') and partner.is_patient:
                # Count assignments through appointments
                appointments = self.env['health.appointment'].search([
                    ('patient_id', '=', partner.id)
                ])
                
                assignments = self.env['health.staff.assignment'].search([
                    ('appointment_id', 'in', appointments.ids)
                ])
                
                partner.total_assignments = len(assignments)
                partner.last_assignment_date = max(
                    assignments.mapped('assignment_date')
                ) if assignments else False
            else:
                partner.total_assignments = 0
                partner.last_assignment_date = False