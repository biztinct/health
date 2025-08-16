from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
import re


class ResPartner(models.Model):
    """Extend res.partner for healthcare functionality module"""
    _inherit = 'res.partner'

    # Healthcare Classification
    is_patient = fields.Boolean('Is Patient', default=False, tracking=True)
    is_healthcare_staff = fields.Boolean('Is Healthcare Staff', default=False)
    is_healthcare_facility = fields.Boolean('Is Healthcare Facility', default=False)
    is_emergency_contact = fields.Boolean('Is Emergency Contact', default=False)
    
    # Patient Healthcare ID
    patient_code = fields.Char(
        'Patient ID', 
        copy=False, 
        readonly=True,
        tracking=True,
        index=True,
        help='Unique patient identifier (auto-generated)'
    )
    
    # Personal Details (Patient-specific)
    first_name = fields.Char('First Name', tracking=True)
    last_name = fields.Char('Last Name', tracking=True)
    middle_name = fields.Char('Middle Name')
    birth_date = fields.Date('Date of Birth', tracking=True)
    age = fields.Integer('Age', compute='_compute_age', store=True)
    age_display = fields.Char('Age Display', compute='_compute_age_display')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], string='Gender', tracking=True)
    
    # Healthcare Specific Fields
    patient_category_id = fields.Many2one('health.patient.category', string='Patient Category')
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-'),
        ('unknown', 'Unknown')
    ], string='Blood Group', default='unknown')
    
    allergies = fields.Text('Known Allergies')
    medical_history = fields.Text('Medical History Summary')
    
    # Emergency Contact Information
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    emergency_contact_relation = fields.Char('Relation to Patient')
    
    # Insurance & Payment
    insurance_provider = fields.Char('Insurance Provider')
    insurance_number = fields.Char('Insurance Number')
    insurance_expiry = fields.Date('Insurance Expiry')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('insurance', 'Insurance'),
        ('corporate', 'Corporate'),
        ('government', 'Government')
    ], string='Primary Payment Method', default='cash')
    
    # Patient Status & Tracking
    patient_status = fields.Selection([
        ('new', 'New Patient'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deceased', 'Deceased')
    ], string='Patient Status', default='new', tracking=True)
    
    registration_date = fields.Datetime('Registration Date', default=fields.Datetime.now, readonly=True)
    last_visit_date = fields.Datetime('Last Visit', readonly=True)
    next_visit_date = fields.Datetime('Next Scheduled Visit')
    
    # Source Tracking
    source_type = fields.Selection([
        ('facebook', 'Facebook'),
        ('zalo', 'Zalo'),
        ('website', 'Website'),
        ('phone', 'Phone Call'),
        ('referral', 'Referral'),
        ('walk_in', 'Walk-in'),
        ('other', 'Other')
    ], string='Patient Source', tracking=True)
    source_details = fields.Char('Source Details')
    referral_source = fields.Char('Referral Source')
    
    # Facility Assignment
    primary_facility_id = fields.Many2one('health.facility', string='Primary Facility')
    
    # Healthcare facility relationship
    facility_id = fields.Many2one('health.facility', string='Facility Record',
                                  help='Linked facility record if this contact is a healthcare facility')
    
    # Medical specialties for healthcare staff
    medical_specialties = fields.Many2many('health.medical.specialty', 
                                          string='Medical Specialties')
    
    # Professional details for healthcare staff
    license_number = fields.Char('Professional License Number')
    license_expiry = fields.Date('License Expiry Date')
    
    # Vietnamese specific fields
    vietnamese_name = fields.Char('Vietnamese Name')
    national_id = fields.Char('National ID (CCCD/CMND)')
    
    # Computed Fields
    visit_count = fields.Integer('Total Visits', compute='_compute_visit_count')
    
    def _generate_patient_code(self):
        """Generate unique patient code"""
        sequence = self.env['ir.sequence'].next_by_code('res.partner.patient') or '0001'
        return f'P{sequence}'
    
    @api.depends('birth_date')
    def _compute_age(self):
        """Compute age from birth date"""
        for partner in self:
            if partner.birth_date:
                today = date.today()
                partner.age = today.year - partner.birth_date.year - (
                    (today.month, today.day) < (partner.birth_date.month, partner.birth_date.day)
                )
            else:
                partner.age = 0
    
    @api.depends('age')
    def _compute_age_display(self):
        """Compute age display string"""
        for partner in self:
            if partner.age:
                partner.age_display = f'{partner.age} years old'
            else:
                partner.age_display = 'Age unknown'
    
    def _compute_visit_count(self):
        """Compute total visits for patients"""
        # This will be implemented when appointment models are updated
        for partner in self:
            if partner.is_patient:
                # TODO: Update when appointment model is refactored
                partner.visit_count = 0
            else:
                partner.visit_count = 0
    
    @api.constrains('email')
    def _check_email(self):
        """Validate email format"""
        for partner in self:
            if partner.email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', partner.email):
                raise ValidationError(_('Please enter a valid email address.'))
    
    @api.constrains('phone', 'mobile')
    def _check_phone(self):
        """Validate phone number format"""
        for partner in self:
            if partner.phone and not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', partner.phone):
                raise ValidationError(_('Please enter a valid phone number.'))
            if partner.mobile and not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', partner.mobile):
                raise ValidationError(_('Please enter a valid mobile number.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare flags and customer rank for patients"""
        partners = super().create(vals_list)
        
        # Get healthcare category references
        patient_category = self.env.ref('health_base.patient_category', raise_if_not_found=False)
        staff_category = self.env.ref('health_base.staff_category', raise_if_not_found=False)
        facility_category = self.env.ref('health_base.facility_category', raise_if_not_found=False)
        
        for partner in partners:
            # Set healthcare flags based on categories
            if patient_category and patient_category in partner.category_id:
                partner.is_patient = True
            if staff_category and staff_category in partner.category_id:
                partner.is_healthcare_staff = True
            if facility_category and facility_category in partner.category_id:
                partner.is_healthcare_facility = True
            
            # Set customer rank for patients to enable CRM integration
            if partner.is_patient:
                if not partner.customer_rank:
                    partner.customer_rank = 1
                # Generate patient code if not already set
                if not partner.patient_code:
                    partner.patient_code = partner._generate_patient_code()
                
        return partners
    
    def action_view_appointments(self):
        """Action to view patient appointments"""
        if not self.is_patient:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Appointments - {self.name}',
            'res_model': 'health.appointment',  # Will be updated when appointment model is refactored
            'view_mode': 'calendar,list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id}
        }
    
    def action_create_appointment(self):
        """Quick create appointment action"""
        if not self.is_patient:
            return
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Appointment'),
            'res_model': 'health.appointment',  # Will be updated when appointment model is refactored
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_name': f'Appointment - {self.name}'
            }
        }
    
    def action_activate_patient(self):
        """Activate patient - change status to active"""
        if not self.is_patient:
            return
            
        self.patient_status = 'active'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Patient Activated',
                'message': f'{self.name} has been marked as active.',
                'type': 'success'
            }
        }
    
    def action_mark_inactive(self):
        """Mark patient as inactive"""
        if not self.is_patient:
            return
            
        self.patient_status = 'inactive'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Patient Deactivated',
                'message': f'{self.name} has been marked as inactive.',
                'type': 'warning'
            }
        }
    
    def action_view_lab_results(self):
        """Action to view patient lab results"""
        if not self.is_patient:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lab Results - {self.name}',
            'res_model': 'health.lab.result',  # Will be implemented when lab module is added
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
            'help': """<p class="o_view_nocontent_smiling_face">
                No lab results found for this patient.
            </p>
            <p>
                Lab results will be displayed here when the laboratory module is installed.
            </p>"""
        }
    
    def action_view_prescriptions(self):
        """Action to view patient prescriptions"""
        if not self.is_patient:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Prescriptions - {self.name}',
            'res_model': 'health.prescription',  # Will be implemented when pharmacy module is added
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
            'help': """<p class="o_view_nocontent_smiling_face">
                No prescriptions found for this patient.
            </p>
            <p>
                Prescriptions will be displayed here when the pharmacy module is installed.
            </p>"""
        }
    
    def action_view_facility_record(self):
        """View the linked facility record"""
        if self.facility_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Facility Record',
                'res_model': 'health.facility',
                'res_id': self.facility_id.id,
                'view_mode': 'form',
                'target': 'current'
            }
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Enhanced name search for patients including patient ID"""
        if args is None:
            args = []
        
        # If searching in patient context, include patient_id in search
        if self.env.context.get('search_patients'):
            args = args + ['|', ('name', operator, name), ('patient_code', operator, name)]
            name = ''
        
        return super().name_search(name=name, args=args, operator=operator, limit=limit)
    
    def _get_name(self):
        """Override name display for patients to include patient code"""
        name = super()._get_name()
        if self.is_patient and self.patient_code:
            return f'[{self.patient_code}] {name}'
        return name