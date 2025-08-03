from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, datetime
import re


class Patient(models.Model):
    """Patient/Client model for healthcare management"""
    _name = 'health.patient'
    _description = 'Healthcare Patient'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, patient_id'
    _rec_name = 'display_name'

    # Basic Information
    name = fields.Char('Full Name', required=True, tracking=True, index=True)
    patient_id = fields.Char(
        'Patient ID', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: self._generate_patient_id(),
        tracking=True,
        index=True
    )
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    # Personal Details
    first_name = fields.Char('First Name', tracking=True)
    last_name = fields.Char('Last Name', tracking=True)
    middle_name = fields.Char('Middle Name')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], string='Gender', tracking=True)
    
    birth_date = fields.Date('Date of Birth', tracking=True)
    age = fields.Integer('Age', compute='_compute_age', store=True)
    age_display = fields.Char('Age Display', compute='_compute_age_display')
    
    # Contact Information
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='cascade')
    image_1920 = fields.Image('Patient Photo', max_width=1920, max_height=1920)
    phone = fields.Char('Phone', tracking=True)
    mobile = fields.Char('Mobile', tracking=True)
    email = fields.Char('Email', tracking=True)
    
    # Address Information
    street = fields.Char('Street')
    street2 = fields.Char('Street 2')
    city = fields.Char('City')
    state_id = fields.Many2one('res.country.state', string='State/Province')
    zip = fields.Char('ZIP Code')
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.ref('base.vn'))
    
    # Healthcare Specific
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
    
    # Status & Tracking
    active = fields.Boolean('Active', default=True, tracking=True)
    patient_status = fields.Selection([
        ('new', 'New Patient'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deceased', 'Deceased')
    ], string='Status', default='new', tracking=True)
    
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
    
    # Computed Fields
    visit_count = fields.Integer('Total Visits', compute='_compute_visit_count')
    
    # Vietnamese Specific
    vietnamese_name = fields.Char('Vietnamese Name')
    national_id = fields.Char('National ID (CCCD/CMND)')
    
    @api.model
    def _generate_patient_id(self):
        """Generate unique patient ID"""
        sequence = self.env['ir.sequence'].next_by_code('health.patient') or '0001'
        return f'P{sequence}'
    
    @api.depends('name', 'patient_id')
    def _compute_display_name(self):
        for record in self:
            if record.patient_id and record.name:
                record.display_name = f'[{record.patient_id}] {record.name}'
            else:
                record.display_name = record.name or record.patient_id or 'New Patient'
    
    @api.depends('birth_date')
    def _compute_age(self):
        for record in self:
            if record.birth_date:
                today = date.today()
                record.age = today.year - record.birth_date.year - (
                    (today.month, today.day) < (record.birth_date.month, record.birth_date.day)
                )
            else:
                record.age = 0
    
    @api.depends('age')
    def _compute_age_display(self):
        for record in self:
            if record.age:
                record.age_display = f'{record.age} years old'
            else:
                record.age_display = 'Age unknown'
    
    def _compute_visit_count(self):
        # This will be implemented when appointment/visit models are created
        for record in self:
            record.visit_count = 0
    
    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', record.email):
                raise ValidationError(_('Please enter a valid email address.'))
    
    @api.constrains('phone', 'mobile')
    def _check_phone(self):
        for record in self:
            if record.phone and not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', record.phone):
                raise ValidationError(_('Please enter a valid phone number.'))
            if record.mobile and not re.match(r'^\+?[\d\s\-\(\)]{7,15}$', record.mobile):
                raise ValidationError(_('Please enter a valid mobile number.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create patient and sync with res.partner if needed"""
        patients = super().create(vals_list)
        for patient in patients:
            if not patient.partner_id:
                # Create corresponding res.partner
                partner_vals = {
                    'name': patient.name,
                    'phone': patient.phone,
                    'mobile': patient.mobile,
                    'email': patient.email,
                    'street': patient.street,
                    'street2': patient.street2,
                    'city': patient.city,
                    'state_id': patient.state_id.id,
                    'zip': patient.zip,
                    'country_id': patient.country_id.id,
                    'is_company': False,
                    'customer_rank': 1,
                    'category_id': [(4, self.env.ref('health_base.patient_category').id)]
                }
                partner = self.env['res.partner'].create(partner_vals)
                patient.partner_id = partner.id
        return patients
    
    def action_view_appointments(self):
        """Action to view patient appointments"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Patient Appointments',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,list,form',
            'target': 'current',
        }
    
    def action_create_appointment(self):
        """Quick create appointment action"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Appointment'),
            'res_model': 'calendar.event',  # Will be health.appointment later
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_ids': [(4, self.partner_id.id)],
                'default_name': f'Appointment - {self.name}'
            }
        }
    
    def action_activate_patient(self):
        """Activate patient - change status to active"""
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


class PatientCategory(models.Model):
    """Patient categories for classification"""
    _name = 'health.patient.category'
    _description = 'Patient Category'
    _order = 'sequence, name'

    name = fields.Char('Category Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    color = fields.Integer('Color Index', default=0)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    
    # Pricing and features
    price_multiplier = fields.Float('Price Multiplier', default=1.0, help='Multiplier for service pricing')
    special_requirements = fields.Text('Special Requirements')
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Category name must be unique!')
    ]