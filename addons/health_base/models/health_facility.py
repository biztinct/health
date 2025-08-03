from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Facility(models.Model):
    """Healthcare facilities/clinics"""
    _name = 'health.facility'
    _description = 'Healthcare Facility'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Facility Name', required=True, tracking=True)
    code = fields.Char('Facility Code', required=True, size=10, tracking=True)
    
    # Facility type
    facility_type = fields.Selection([
        ('main_clinic', 'Main Clinic'),
        ('branch_clinic', 'Branch Clinic'),
        ('home_care_center', 'Home Care Center'),
        ('telemedicine_center', 'Telemedicine Center'),
        ('mobile_unit', 'Mobile Unit'),
        ('partner_clinic', 'Partner Clinic')
    ], string='Facility Type', required=True, default='branch_clinic', tracking=True)
    
    # Contact Information
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='cascade')
    phone = fields.Char('Phone', tracking=True)
    email = fields.Char('Email', tracking=True)
    website = fields.Char('Website')
    
    # Address
    street = fields.Char('Street', required=True)
    street2 = fields.Char('Street 2')
    city = fields.Char('City', required=True)
    state_id = fields.Many2one('res.country.state', string='State/Province')
    zip = fields.Char('ZIP Code')
    country_id = fields.Many2one('res.country', string='Country', 
                                default=lambda self: self.env.ref('base.vn'))
    
    # Operating Hours
    operating_hours = fields.Text('Operating Hours', 
                                 default='Monday-Friday: 8:00-17:00\nSaturday: 8:00-12:00')
    timezone = fields.Selection('_get_timezone_list', string='Timezone', 
                               default='Asia/Ho_Chi_Minh')
    
    # Services and Capabilities
    services_offered = fields.Many2many('health.service.type', 
                                       string='Services Offered')
    specialties = fields.Many2many('health.medical.specialty', 
                                  string='Medical Specialties')
    
    # Staff and Resources
    max_daily_patients = fields.Integer('Max Daily Patients', default=50)
    has_emergency_services = fields.Boolean('Emergency Services', default=False)
    has_laboratory = fields.Boolean('Laboratory Services', default=False)
    has_imaging = fields.Boolean('Imaging Services', default=False)
    has_pharmacy = fields.Boolean('Pharmacy', default=False)
    
    # Equipment and Facilities
    total_beds = fields.Integer('Total Beds', default=0)
    available_beds = fields.Integer('Available Beds', compute='_compute_available_beds')
    consultation_rooms = fields.Integer('Consultation Rooms', default=1)
    parking_spaces = fields.Integer('Parking Spaces', default=0)
    wheelchair_accessible = fields.Boolean('Wheelchair Accessible', default=True)
    
    # Financial
    default_currency_id = fields.Many2one('res.currency', string='Default Currency',
                                         default=lambda self: self.env.ref('base.VND'))
    accepts_insurance = fields.Boolean('Accepts Insurance', default=True)
    accepted_insurance_providers = fields.Many2many('health.insurance.provider',
                                                   string='Accepted Insurance Providers')
    
    # Home Visit Coverage
    covers_home_visits = fields.Boolean('Provides Home Visits', default=True)
    home_visit_radius_km = fields.Float('Home Visit Radius (KM)', default=20.0)
    home_visit_districts = fields.Many2many('health.vietnamese.district',
                                           string='Home Visit Coverage Areas')
    base_home_visit_fee = fields.Float('Base Home Visit Fee (VND)', default=100000.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Status and Compliance
    active = fields.Boolean('Active', default=True, tracking=True)
    facility_status = fields.Selection([
        ('planning', 'Planning'),
        ('construction', 'Under Construction'),
        ('operational', 'Operational'),
        ('maintenance', 'Under Maintenance'),
        ('closed_temporary', 'Temporarily Closed'),
        ('closed_permanent', 'Permanently Closed')
    ], string='Status', default='operational', tracking=True)
    
    # Licensing and Compliance
    business_license_number = fields.Char('Business License Number')
    health_license_number = fields.Char('Health License Number')
    license_expiry_date = fields.Date('License Expiry Date')
    last_inspection_date = fields.Date('Last Inspection Date')
    next_inspection_date = fields.Date('Next Inspection Date')
    
    # Manager and Staff
    facility_manager_id = fields.Many2one('res.users', string='Facility Manager')
    head_nurse_id = fields.Many2one('res.users', string='Head Nurse')
    total_staff_count = fields.Integer('Total Staff Count', default=0)
    
    # Statistics (computed fields)
    patient_count = fields.Integer('Total Patients', compute='_compute_patient_count')
    monthly_revenue = fields.Float('Monthly Revenue', compute='_compute_monthly_revenue')
    
    @api.model
    def _get_timezone_list(self):
        """Get timezone list for Vietnam and region"""
        return [
            ('Asia/Ho_Chi_Minh', 'Ho Chi Minh City (GMT+7)'),
            ('Asia/Hanoi', 'Hanoi (GMT+7)'),
            ('Asia/Bangkok', 'Bangkok (GMT+7)'),
            ('UTC', 'UTC (GMT+0)')
        ]
    
    def _compute_available_beds(self):
        """Compute available beds (placeholder for future bed management)"""
        for facility in self:
            # This will be implemented with bed management system
            facility.available_beds = facility.total_beds
    
    def _compute_patient_count(self):
        """Compute total patients served by this facility"""
        for facility in self:
            # This will be implemented when patient-facility relationships are established
            facility.patient_count = 0
    
    def _compute_monthly_revenue(self):
        """Compute monthly revenue for this facility"""
        for facility in self:
            # This will be implemented with invoicing integration
            facility.monthly_revenue = 0.0
    
    @api.constrains('home_visit_radius_km')
    def _check_home_visit_radius(self):
        for facility in self:
            if facility.home_visit_radius_km < 0:
                raise ValidationError(_('Home visit radius cannot be negative.'))
            if facility.home_visit_radius_km > 100:
                raise ValidationError(_('Home visit radius seems too large (>100km).'))
    
    @api.constrains('license_expiry_date')
    def _check_license_expiry(self):
        today = fields.Date.today()
        for facility in self:
            if facility.license_expiry_date and facility.license_expiry_date < today:
                raise ValidationError(_('License expiry date cannot be in the past.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create facility and corresponding partner"""
        facilities = super().create(vals_list)
        for facility in facilities:
            if not facility.partner_id:
                partner_vals = {
                    'name': facility.name,
                    'phone': facility.phone,
                    'email': facility.email,
                    'website': facility.website,
                    'street': facility.street,
                    'street2': facility.street2,
                    'city': facility.city,
                    'state_id': facility.state_id.id,
                    'zip': facility.zip,
                    'country_id': facility.country_id.id,
                    'is_company': True,
                    'supplier_rank': 0,
                    'customer_rank': 0,
                    'category_id': [(4, self.env.ref('health_base.facility_category').id)]
                }
                partner = self.env['res.partner'].create(partner_vals)
                facility.partner_id = partner.id
        return facilities
    
    def action_view_patients(self):
        """View patients associated with this facility"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facility Patients'),
            'res_model': 'health.patient',
            'view_mode': 'list,form',
            'domain': [('primary_facility_id', '=', self.id)],
            'context': {'default_primary_facility_id': self.id}
        }
    
    def action_view_appointments(self):
        """View appointments for this facility"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facility Appointments',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,list,form',
            'target': 'current',
        }
    
    def action_check_license_expiry(self):
        """Check and alert for license expiry"""
        today = fields.Date.today()
        expiring_soon = self.search([
            ('license_expiry_date', '<=', fields.Date.add(today, days=30)),
            ('license_expiry_date', '>=', today),
            ('active', '=', True)
        ])
        
        if expiring_soon:
            message = _('The following facilities have licenses expiring within 30 days:\n')
            for facility in expiring_soon:
                message += f'- {facility.name}: {facility.license_expiry_date}\n'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('License Expiry Alert'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('License Status'),
                    'message': _('All facility licenses are current.'),
                    'type': 'success'
                }
            }
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Facility code must be unique!'),
        ('positive_beds', 'check(total_beds >= 0)', 'Total beds cannot be negative!'),
        ('positive_rooms', 'check(consultation_rooms > 0)', 'Must have at least one consultation room!'),
        ('positive_radius', 'check(home_visit_radius_km >= 0)', 'Home visit radius cannot be negative!')
    ]