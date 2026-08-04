# -*- coding: utf-8 -*-
from odoo import models, fields

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # Professional credentials
    license_number = fields.Char('Professional License Number', readonly=True)
    license_expiry = fields.Date('License Expiry Date', readonly=True)
    specializations = fields.Text('Medical Specializations', readonly=True)
    qualifications = fields.Text('Qualifications & Certifications', readonly=True)
    certifications = fields.Text('Additional Certifications', readonly=True)
    years_experience = fields.Integer('Years of Experience', readonly=True)
    
    # Employment Details
    staff_code = fields.Char('Staff Code', readonly=True)
    hire_date = fields.Date('Hire Date', readonly=True)
    employment_status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Employment Status', readonly=True)

    employment_type = fields.Selection([
        ('full_time', 'Full-Time Staff'),
        ('part_time', 'Part-Time Staff'),
        ('casual', 'Casual/Contract'),
    ], string='Employment Type', readonly=True)

    can_create_invoices = fields.Boolean('Can Create Invoices', readonly=True)
    
    # Facility Assignment
    healthcare_facility_id = fields.Many2one('health.facility', string='Healthcare Facility', readonly=True)
    staff_catchment_province_id = fields.Many2one('health.catchment.province', string='Staff Catchment Province', readonly=True)

    # Same non-standard field name as hr.employee, same reason. Keeps the
    # injected facet pointing at a field that exists here too.
    _catchment_field = 'staff_catchment_province_id'
    
    # Availability Settings
    available_for_clinic = fields.Boolean('Available for Clinic Visits', readonly=True)
    available_for_home_visits = fields.Boolean('Available for Home Visits', readonly=True)
    available_for_telemedicine = fields.Boolean('Available for Telemedicine', readonly=True)
    can_work_emergency = fields.Boolean('Available for Emergency Calls', readonly=True)
    
    # Transportation
    has_vehicle = fields.Boolean('Has Vehicle', readonly=True)
    vehicle_type = fields.Selection([
        ('motorbike', 'Motorbike'),
        ('car', 'Car'),
        ('bicycle', 'Bicycle'),
        ('public_transport', 'Public Transport')
    ], string='Transportation', readonly=True)
    
    # Working Schedule
    working_hours_monday = fields.Char('Monday Hours', readonly=True)
    working_hours_tuesday = fields.Char('Tuesday Hours', readonly=True)
    working_hours_wednesday = fields.Char('Wednesday Hours', readonly=True)
    working_hours_thursday = fields.Char('Thursday Hours', readonly=True)
    working_hours_friday = fields.Char('Friday Hours', readonly=True)
    working_hours_saturday = fields.Char('Saturday Hours', readonly=True)
    working_hours_sunday = fields.Char('Sunday Hours', readonly=True)
    
    # Appointment/Booking Settings
    max_appointments_per_day = fields.Integer('Max Appointments Per Day', readonly=True)
    max_home_visits_per_day = fields.Integer('Max Home Visits per Day', readonly=True)
    appointment_duration_default = fields.Integer('Default Appointment Duration (Minutes)', readonly=True)
    advance_booking_days = fields.Integer('Advance Booking Days', readonly=True)
    
    # Emergency Contact
    emergency_contact_name = fields.Char('Emergency Contact Name', readonly=True)
    emergency_contact_phone = fields.Char('Emergency Contact Phone', readonly=True)
    emergency_contact_relation = fields.Char('Emergency Contact Relation', readonly=True)
    emergency_contact_email = fields.Char('Emergency Contact Email', readonly=True)
    
    # Skills and Qualifications
    # Published here (SH-1 §4) so FHIR Practitioner.qualification can be built
    # by a minimally-grouped service token: hr.employee._check_private_fields
    # treats a field as public iff a field of that name exists on
    # hr.employee.public, so without this line reading healthcare_skill_ids
    # required an HR group and /fhir/r4/Practitioner answered 403.
    # Same comodel, relation table and columns as the hr.employee definition
    # (health_fieldservice/models/hr_employee.py) — sharing the relation is
    # allowed because hr.employee.public is _auto=False.
    healthcare_skill_ids = fields.Many2many(
        'health.staff.skill',
        'employee_healthcare_skill_rel',
        'employee_id', 'skill_id',
        string='Healthcare Skills', readonly=True
    )

    skill_level = fields.Selection([
        ('junior', 'Junior'),
        ('intermediate', 'Intermediate'),
        ('senior', 'Senior'),
        ('expert', 'Expert')
    ], string='Skill Level', readonly=True)
    
    # Assignment and Availability
    assignment_status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('busy', 'Busy'),
        ('off_duty', 'Off Duty'),
        ('on_leave', 'On Leave')
    ], string='Assignment Status', readonly=True)
    
    current_location = fields.Char('Current Location (GPS)', readonly=True)
    location_last_updated = fields.Datetime('Location Last Updated', readonly=True)
    
    max_travel_distance = fields.Float('Max Travel Distance (KM)', readonly=True)
    
    # Additional fields
    certification_expiry = fields.Date('Certification Expiry', readonly=True)
    max_daily_assignments = fields.Integer('Max Daily Assignments', readonly=True)
    preferred_shift = fields.Selection([
        ('morning', 'Morning Shift'),
        ('afternoon', 'Afternoon Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
        ('flexible', 'Flexible')
    ], string='Preferred Shift', readonly=True)
    travel_radius_km = fields.Float('Travel Radius (KM)', readonly=True)
    availability_status = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('break', 'On Break'),
        ('offline', 'Offline')
    ], string='Availability Status', readonly=True)
    
    # Workload and Performance Metrics
    daily_capacity = fields.Integer('Daily Capacity', readonly=True)
    booking_credit = fields.Integer('Booking Credits', readonly=True)
    total_assignments = fields.Integer('Total Assignments', readonly=True)
    completed_assignments = fields.Integer('Completed Assignments', readonly=True)
    assignment_success_rate = fields.Float('Assignment Success Rate %', readonly=True)
    
    # Scheduling Preferences
    preferred_working_hours_start = fields.Float('Preferred Start Time', readonly=True)
    preferred_working_hours_end = fields.Float('Preferred End Time', readonly=True)
    
    available_weekdays = fields.Selection([
        ('weekdays', 'Weekdays Only'),
        ('weekends', 'Weekends Only'),
        ('all', 'All Days')
    ], string='Available Days', readonly=True)
    
    home_visit_preference = fields.Selection([
        ('prefer', 'Prefer Home Visits'),
        ('neutral', 'No Preference'),
        ('avoid', 'Prefer Clinic Only')
    ], string='Home Visit Preference', readonly=True)
    
    # Communication
    mobile_for_assignments = fields.Char('Mobile for Assignments', readonly=True)
    notification_method = fields.Selection([
        ('email', 'Email Only'),
        ('sms', 'SMS Only'),
        ('both', 'Email and SMS'),
        ('app', 'Mobile App')
    ], string='Preferred Notification Method', readonly=True)
