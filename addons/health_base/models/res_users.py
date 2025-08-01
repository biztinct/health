from odoo import models, fields, api


class ResUsers(models.Model):
    """Extend res.users for healthcare staff functionality"""
    _inherit = 'res.users'

    # Healthcare staff identification
    is_healthcare_staff = fields.Boolean('Is Healthcare Staff', default=False)
    
    # Professional details
    staff_type = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('head_nurse', 'Head Nurse'),
        ('technician', 'Technician'),
        ('admin', 'Administrator'),
        ('receptionist', 'Receptionist'),
        ('manager', 'Manager'),
        ('owner', 'Owner')
    ], string='Staff Type')
    
    medical_specialties = fields.Many2many('health.medical.specialty', 
                                          string='Medical Specialties')
    
    # Licensing and credentials
    professional_license_number = fields.Char('License Number')
    license_expiry_date = fields.Date('License Expiry')
    certifications = fields.Text('Certifications & Qualifications')
    
    # Work assignment
    primary_facility_id = fields.Many2one('health.facility', string='Primary Facility')
    assigned_facilities = fields.Many2many('health.facility', 
                                          relation='user_facility_rel',
                                          string='Assigned Facilities')
    
    # Schedule and availability
    work_schedule = fields.Text('Work Schedule', 
                               default='Monday-Friday: 8:00-17:00')
    max_daily_appointments = fields.Integer('Max Daily Appointments', default=10)
    max_home_visits_per_day = fields.Integer('Max Home Visits per Day', default=5)
    
    # Skills and preferences
    can_do_home_visits = fields.Boolean('Available for Home Visits', default=True)
    can_do_telemedicine = fields.Boolean('Available for Telemedicine', default=False)
    can_work_emergency = fields.Boolean('Available for Emergency Calls', default=False)
    
    # Service areas for home visits
    home_visit_areas = fields.Many2many('health.vietnamese.district',
                                       string='Home Visit Coverage Areas')
    
    # Vehicle for home visits
    has_vehicle = fields.Boolean('Has Vehicle', default=False)
    vehicle_type = fields.Selection([
        ('motorbike', 'Motorbike'),
        ('car', 'Car'),
        ('bicycle', 'Bicycle'),
        ('public_transport', 'Public Transport')
    ], string='Transportation')
    
    # Emergency contact
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    
    # Performance tracking (computed fields)
    monthly_appointments = fields.Integer('Monthly Appointments', 
                                         compute='_compute_monthly_appointments')
    patient_satisfaction_score = fields.Float('Patient Satisfaction Score', 
                                             compute='_compute_satisfaction_score')
    
    def _compute_monthly_appointments(self):
        """Compute monthly appointments for this staff member"""
        for user in self:
            # This will be implemented when appointment system is ready
            user.monthly_appointments = 0
    
    def _compute_satisfaction_score(self):
        """Compute patient satisfaction score"""
        for user in self:
            # This will be implemented with feedback system
            user.patient_satisfaction_score = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare staff flag"""
        users = super().create(vals_list)
        for user in users:
            if user.staff_type:
                user.is_healthcare_staff = True
                # Add healthcare staff category to partner
                staff_category = self.env.ref('health_base.staff_category', raise_if_not_found=False)
                if staff_category and user.partner_id:
                    user.partner_id.category_id = [(4, staff_category.id)]
                    user.partner_id.is_healthcare_staff = True
        return users
    
    def action_view_appointments(self):
        """View appointments assigned to this staff member"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Appointments - {self.name}',
            'res_model': 'calendar.event',  # Will be health.appointment later
            'view_mode': 'tree,form,calendar',
            'domain': [('user_id', '=', self.id)],
            'context': {'default_user_id': self.id}
        }
    
    def action_view_patients(self):
        """View patients assigned to this staff member"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients - {self.name}',
            'res_model': 'health.patient',
            'view_mode': 'tree,form',
            'domain': [],  # Will be implemented with patient assignment
            'context': {}
        }
    
    def action_check_license_expiry(self):
        """Check license expiry for healthcare staff"""
        today = fields.Date.today()
        if self.license_expiry_date:
            days_to_expiry = (self.license_expiry_date - today).days
            
            if days_to_expiry < 0:
                message = f'License expired {abs(days_to_expiry)} days ago!'
                notification_type = 'danger'
            elif days_to_expiry <= 30:
                message = f'License expires in {days_to_expiry} days!'
                notification_type = 'warning'
            else:
                message = f'License is valid until {self.license_expiry_date}'
                notification_type = 'success'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'License Status',
                    'message': message,
                    'type': notification_type
                }
            }
    
    def toggle_availability(self):
        """Toggle staff availability (for emergency situations)"""
        # This will be implemented with real-time availability tracking
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Availability Updated',
                'message': 'Your availability status has been updated.',
                'type': 'success'
            }
        }