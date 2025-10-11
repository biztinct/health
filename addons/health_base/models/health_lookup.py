from odoo import models, fields, api, _


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


class ServiceType(models.Model):
    """Healthcare service types"""
    _name = 'health.service.type'
    _description = 'Healthcare Service Type'
    _order = 'sequence, name'

    name = fields.Char('Service Name', required=True, translate=True)
    code = fields.Char('Service Code', required=True, size=10)
    description = fields.Text('Description', translate=True)
    category = fields.Selection([
        ('consultation', 'Consultation'),
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('telemedicine', 'Telemedicine'),
        ('nursing_care', 'Nursing Care'),
        ('physiotherapy', 'Physiotherapy'),
        ('laboratory', 'Laboratory'),
        ('imaging', 'Imaging'),
        ('emergency', 'Emergency'),
        ('other', 'Other')
    ], string='Category', required=True, default='consultation')
    
    # Pricing
    base_price = fields.Float('Base Price (VND)', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    duration_minutes = fields.Integer('Duration (Minutes)', default=30)
    
    # Location settings
    available_home = fields.Boolean('Available for Home Visits', default=True)
    available_clinic = fields.Boolean('Available in Clinic', default=True)
    available_telemedicine = fields.Boolean('Available via Telemedicine', default=False)
    
    # Travel and logistics
    requires_travel = fields.Boolean('Requires Travel', default=False)
    travel_time_minutes = fields.Integer('Travel Time (Minutes)', default=0)
    equipment_required = fields.Text('Equipment Required')
    
    # Staff requirements
    requires_doctor = fields.Boolean('Requires Doctor', default=False)
    requires_nurse = fields.Boolean('Requires Nurse', default=True)
    staff_count = fields.Integer('Staff Count Required', default=1)
    
    # System fields
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence', default=10)
    color = fields.Integer('Color Index', default=0)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Service code must be unique!'),
        ('positive_price', 'check(base_price >= 0)', 'Base price must be positive!'),
        ('positive_duration', 'check(duration_minutes > 0)', 'Duration must be positive!')
    ]


class MedicalSpecialty(models.Model):
    """Medical specialties for healthcare professionals"""
    _name = 'health.medical.specialty'
    _description = 'Medical Specialty'
    _order = 'name'

    name = fields.Char('Specialty Name', required=True, translate=True)
    code = fields.Char('Specialty Code', size=10)
    description = fields.Text('Description', translate=True)
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Specialty name must be unique!')
    ]


class Symptom(models.Model):
    """Common symptoms for initial patient assessment"""
    _name = 'health.symptom'
    _description = 'Health Symptom'
    _order = 'category, name'

    name = fields.Char('Symptom Name', required=True, translate=True)
    code = fields.Char('Symptom Code', size=10)
    category = fields.Selection([
        ('general', 'General'),
        ('pain', 'Pain & Discomfort'),
        ('respiratory', 'Respiratory'),
        ('cardiovascular', 'Cardiovascular'),
        ('digestive', 'Digestive'),
        ('neurological', 'Neurological'),
        ('skin', 'Skin & Dermatological'),
        ('musculoskeletal', 'Musculoskeletal'),
        ('mental_health', 'Mental Health'),
        ('other', 'Other')
    ], string='Category', default='general')
    
    severity_levels = fields.Text('Severity Levels', default='Mild, Moderate, Severe')
    urgency_level = fields.Selection([
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('emergency', 'Emergency')
    ], string='Default Urgency', default='medium')
    
    description = fields.Text('Description', translate=True)
    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color Index', default=0)


class ReferralSource(models.Model):
    """Referral sources for patient tracking"""
    _name = 'health.referral.source'
    _description = 'Referral Source'
    _order = 'source_type, name'

    name = fields.Char('Source Name', required=True)
    source_type = fields.Selection([
        ('facebook', 'Facebook'),
        ('zalo', 'Zalo'),
        ('website', 'Website'),
        ('google', 'Google'),
        ('doctor', 'Doctor Referral'),
        ('hospital', 'Hospital Referral'),
        ('friend', 'Friend/Family'),
        ('advertisement', 'Advertisement'),
        ('other', 'Other')
    ], string='Source Type', required=True)
    
    description = fields.Text('Description')
    contact_person = fields.Char('Contact Person')
    contact_phone = fields.Char('Contact Phone')
    contact_email = fields.Char('Contact Email')
    
    # Tracking
    is_paid_source = fields.Boolean('Paid Marketing Source', default=False)
    cost_per_lead = fields.Float('Cost per Lead (VND)', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    conversion_rate = fields.Float('Conversion Rate (%)', default=0.0)
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'unique(name, source_type)', 
         'Source name must be unique within the same source type!')
    ]


class InsuranceProvider(models.Model):
    """Insurance providers for patient coverage"""
    _name = 'health.insurance.provider'
    _description = 'Insurance Provider'
    _order = 'name'

    name = fields.Char('Provider Name', required=True)
    code = fields.Char('Provider Code', size=10)
    contact_phone = fields.Char('Contact Phone')
    contact_email = fields.Char('Contact Email')
    website = fields.Char('Website')
    
    # Coverage details
    coverage_percentage = fields.Float('Default Coverage %', default=0.0)
    deductible_amount = fields.Float('Deductible Amount (VND)', default=0.0)
    max_coverage_annual = fields.Float('Max Annual Coverage (VND)', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    
    # Service coverage
    covers_home_visits = fields.Boolean('Covers Home Visits', default=True)
    covers_clinic_visits = fields.Boolean('Covers Clinic Visits', default=True)
    covers_telemedicine = fields.Boolean('Covers Telemedicine', default=False)
    covers_emergency = fields.Boolean('Covers Emergency', default=True)
    
    notes = fields.Text('Notes')
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Provider name must be unique!'),
        ('coverage_valid', 'check(coverage_percentage >= 0 and coverage_percentage <= 100)', 
         'Coverage percentage must be between 0 and 100!')
    ]


class UrgencyLevel(models.Model):
    """Urgency levels for appointments and cases"""
    _name = 'health.urgency.level'
    _description = 'Urgency Level'
    _order = 'priority_score desc'

    name = fields.Char('Urgency Level', required=True, translate=True)
    code = fields.Char('Code', size=10, required=True)
    description = fields.Text('Description', translate=True)
    
    priority_score = fields.Integer('Priority Score', default=1, 
                                  help='Higher score = higher priority')
    response_time_hours = fields.Float('Target Response Time (Hours)', default=24.0)
    color = fields.Integer('Color Index', default=0)
    
    # Automation flags
    auto_assign = fields.Boolean('Auto Assign Staff', default=False)
    send_alerts = fields.Boolean('Send Priority Alerts', default=False)
    requires_approval = fields.Boolean('Requires Manager Approval', default=False)
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Urgency code must be unique!'),
        ('positive_score', 'check(priority_score > 0)', 'Priority score must be positive!')
    ]


class VietnameseDistricts(models.Model):
    """Vietnamese districts for location tracking"""
    _name = 'health.vietnamese.district'
    _description = 'Vietnamese District'
    _order = 'province_name, name'

    name = fields.Char('District Name', required=True)
    province_name = fields.Char('Province Name', required=True)
    region = fields.Selection([
        ('north', 'Northern Vietnam'),
        ('central', 'Central Vietnam'),
        ('south', 'Southern Vietnam')
    ], string='Region', default='south')
    
    # Service delivery
    supports_home_visits = fields.Boolean('Supports Home Visits', default=True)
    travel_zone = fields.Selection([
        ('zone_1', 'Zone 1 (Inner City)'),
        ('zone_2', 'Zone 2 (Suburban)'),
        ('zone_3', 'Zone 3 (Outer Areas)')
    ], string='Travel Zone', default='zone_2')
    
    base_travel_fee = fields.Float('Base Travel Fee (VND)', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    average_travel_time = fields.Integer('Average Travel Time (Minutes)', default=30)
    
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('district_province_unique', 'unique(name, province_name)',
         'District name must be unique within province!')
    ]


class BookingCancellationReason(models.Model):
    """Booking cancellation reasons for structured cancellation tracking"""
    _name = 'health.booking.cancellation.reason'
    _description = 'Booking Cancellation Reason'
    _order = 'sequence, name'

    name = fields.Char('Reason', required=True, translate=True)
    reason_type = fields.Selection([
        ('patient', 'Patient-initiated'),
        ('provider', 'Provider-initiated'),
        ('system', 'System/Technical'),
        ('emergency', 'Emergency/Force Majeure'),
    ], string='Reason Type', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description', translate=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Cancellation reason must be unique!')
    ]