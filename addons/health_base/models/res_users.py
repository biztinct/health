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

    healthcare_role = fields.Selection([
        ('doctor', 'Doctor'),
        ('duty_doctor', 'Duty Doctor'),
        ('nurse', 'Nurse'),
        ('head_nurse', 'Head Nurse'),
        ('specialist', 'Specialist'),
        ('therapist', 'Therapist'),
        ('technician', 'Technician'),
        ('support', 'Support Staff'),
        ('operations_manager', 'Operations Manager'),
        ('admin', 'Admin'),
        ('owner', 'Owner'),
        ('accountant', 'Accountant'),
    ], string='Healthcare Role (Deprecated)')

    # Designated catchment province/area
    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        help='The catchment province/area where this user primarily works'
    )

    catchment_enforced = fields.Boolean(
        string='Catchment Scoping Applies',
        compute='_compute_catchment_enforced',
        help='True for staff whose record access is narrowed to their own '
             'catchment area. False for owners and for anyone who is not '
             'healthcare staff, so the global catchment rules leave them alone.'
    )

    @api.depends('group_ids', 'all_group_ids')
    def _compute_catchment_enforced(self):
        """Read by every global catchment rule (security/catchment_global_rules.xml
        here and in six other modules), so it has to be cheap and it has to be
        right for the non-staff cases — a portal patient or an integration user
        must pass straight through.

        It lives in health_base rather than health_catchment_scope because
        health_base's OWN rules read it, and health_catchment_scope depends on
        health_base: the other direction would be a dependency loop.

        Deliberately NOT stored. A stored flag goes stale the moment somebody's
        groups change, and a rule reading a stale flag either leaks or locks
        people out. has_group is already cached per user.
        """
        for user in self:
            user.catchment_enforced = (
                user.has_group('health_base.group_healthcare_base')
                and not user.has_group('health_base.group_healthcare_owner')
            )

    is_duty_doctor = fields.Boolean('Is Duty Doctor', default=False)
    is_head_nurse = fields.Boolean('Is Head Nurse', default=False)

    # Declared here, decided by the Access home above — see the long note on
    # `hr.employee`. `job_role_id` itself lives up there, because it points at
    # a role bundle and this module is the root of the tree; these two are the
    # answers read off it, and they stay here so that a module below can name
    # one in an `@api.depends` without the registry refusing to load.
    is_doctor_role = fields.Boolean(store=True, readonly=True)
    is_nurse_role = fields.Boolean(store=True, readonly=True)

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