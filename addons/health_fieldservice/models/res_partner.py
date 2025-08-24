from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
                # Count assignments through unified FSO system
                fso_records = self.env['health.fieldservice.order'].search([
                    ('patient_id', '=', partner.id)
                ])
                
                assignments = self.env['health.staff.assignment'].search([
                    ('fso_id', 'in', fso_records.ids)
                ])
                
                partner.total_assignments = len(assignments)
                partner.last_assignment_date = max(
                    assignments.mapped('assignment_date')
                ) if assignments else False
            else:
                partner.total_assignments = 0
                partner.last_assignment_date = False
    
    def action_create_fso(self):
        """Create a new Field Service Order for this patient"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Field Service Orders created.'))
        
        # Create new FSO with patient pre-filled
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Create Field Service Order'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_patient_id': self.id,
                'default_customer_id': self.id,
                'default_state': 'draft',
            }
        }
        return action
    
    def action_view_fso_orders(self):
        """View all Field Service Orders for this patient"""
        if not self.is_patient:
            raise UserError(_('Only patients can have Field Service Orders.'))
        
        fso_orders = self.env['health.fieldservice.order'].search([
            ('patient_id', '=', self.id)
        ])
        
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Field Service Orders'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
                'default_customer_id': self.id,
            }
        }
        
        if len(fso_orders) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = fso_orders.id
        
        return action