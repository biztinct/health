from odoo import models, fields, api


class ResUsers(models.Model):
    """Extend res.users for basic healthcare integration"""
    _inherit = 'res.users'

    # Basic healthcare identification
    is_healthcare_staff = fields.Boolean(
        'Is Healthcare Staff',
        default=False,
        help='Mark if this user is healthcare staff'
    )
    
    # Quick access to employee healthcare role
    healthcare_role = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('specialist', 'Specialist'),
        ('therapist', 'Therapist'),
        ('technician', 'Technician'),
        ('support', 'Support Staff')
    ], string='Healthcare Role')

    # Designated catchment province/area
    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        help='The catchment province/area where this user primarily works'
    )

    def get_employee_record(self):
        """Get linked employee record if exists"""
        if hasattr(self, 'employee_id') and self.employee_id:
            return self.employee_id
        elif hasattr(self, 'employee_ids') and self.employee_ids:
            return self.employee_ids[0]
        else:
            # Create employee record if user is healthcare staff
            if self.is_healthcare_staff:
                return self.env['hr.employee'].create({
                    'name': self.name,
                    'user_id': self.id,
                    'is_healthcare_staff': True,
                    'healthcare_role': self.healthcare_role or 'support'
                })
        return False
    
    def action_view_my_assignments(self):
        """View my healthcare assignments (if I'm healthcare staff)"""
        employee = self.get_employee_record()
        if not employee or not employee.is_healthcare_staff:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Access Denied',
                    'message': 'You are not registered as healthcare staff.',
                    'type': 'warning'
                }
            }
        
        return employee.action_view_assignments()
    
    def action_view_my_schedule(self):
        """View my today's schedule (if I'm healthcare staff)"""
        employee = self.get_employee_record()
        if not employee or not employee.is_healthcare_staff:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Access Denied',
                    'message': 'You are not registered as healthcare staff.',
                    'type': 'warning'
                }
            }
        
        return employee.action_view_today_schedule()
    
    def action_toggle_availability(self):
        """Toggle my availability status (if I'm healthcare staff)"""
        employee = self.get_employee_record()
        if not employee or not employee.is_healthcare_staff:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Access Denied',
                    'message': 'You are not registered as healthcare staff.',
                    'type': 'warning'
                }
            }
        
        return employee.toggle_availability()