from odoo import models, fields, api, _
from datetime import datetime, timedelta


class HrEmployee(models.Model):
    """Extend HR Employee with healthcare staff assignment capabilities"""
    _inherit = 'hr.employee'

    # ============================================================================
    # Healthcare Staff Classification
    # ============================================================================
    # Note: is_healthcare_staff and healthcare_role are defined in health_base

    # Professional credentials (consolidated from all staff models)
    license_number = fields.Char('Professional License Number', tracking=True)
    license_expiry = fields.Date('License Expiry Date', tracking=True)
    specializations = fields.Text('Medical Specializations')
    qualifications = fields.Text('Qualifications & Certifications')
    certifications = fields.Text('Additional Certifications')
    years_experience = fields.Integer('Years of Experience', default=0)
    
    # Medical Specialties
    medical_specialties = fields.Many2many(
        'health.medical.specialty', 
        'employee_medical_specialty_rel',
        'employee_id', 'specialty_id',
        string='Medical Specialties'
    )
    
    # Employment Details (from health.staff)
    staff_code = fields.Char('Staff Code', copy=False, readonly=True)
    hire_date = fields.Date('Hire Date', tracking=True)
    employment_status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Employment Status', default='active', tracking=True)

    # Part-Time Workflow Support
    employment_type = fields.Selection([
        ('full_time', 'Full-Time Staff'),
        ('part_time', 'Part-Time Staff'),
        ('casual', 'Casual/Contract'),
    ], string='Employment Type', default='full_time', required=True, tracking=True,
       help='Full-time staff can create invoices; part-time/casual staff require Operations invoicing')

    can_create_invoices = fields.Boolean(
        'Can Create Invoices',
        compute='_compute_can_create_invoices',
        store=True,
        help='Computed based on employment type - full-time staff can create invoices'
    )
    
    # Facility Assignment (consolidated)
    facility_ids = fields.Many2many(
        'health.facility', 
        'employee_facility_rel',
        'employee_id', 'facility_id',
        string='Assigned Facilities',
        help='Healthcare facilities where this employee works'
    )
    primary_facility_id = fields.Many2one('health.facility', string='Primary Facility')
    
    # Service Capabilities
    service_type_ids = fields.Many2many(
        'health.service.type',
        'employee_service_type_rel', 
        'employee_id', 'service_type_id',
        string='Qualified Service Types',
        help='Types of services this staff can provide'
    )
    
    # Availability Settings (consolidated)
    available_for_clinic = fields.Boolean('Available for Clinic Visits', default=True)
    available_for_home_visits = fields.Boolean('Available for Home Visits', default=True)
    available_for_telemedicine = fields.Boolean('Available for Telemedicine', default=False)
    can_work_emergency = fields.Boolean('Available for Emergency Calls', default=False)
    
    # Transportation for home visits
    has_vehicle = fields.Boolean('Has Vehicle', default=False)
    vehicle_type = fields.Selection([
        ('motorbike', 'Motorbike'),
        ('car', 'Car'),
        ('bicycle', 'Bicycle'),
        ('public_transport', 'Public Transport')
    ], string='Transportation')
    
    # Coverage Areas for home visits
    home_visit_areas = fields.Many2many(
        'health.vietnamese.district',
        'employee_district_rel',
        'employee_id', 'district_id',
        string='Home Visit Coverage Areas'
    )
    
    # Working Schedule (consolidated)
    working_hours_monday = fields.Char('Monday Hours', default='09:00-17:00')
    working_hours_tuesday = fields.Char('Tuesday Hours', default='09:00-17:00')
    working_hours_wednesday = fields.Char('Wednesday Hours', default='09:00-17:00')
    working_hours_thursday = fields.Char('Thursday Hours', default='09:00-17:00')
    working_hours_friday = fields.Char('Friday Hours', default='09:00-17:00')
    working_hours_saturday = fields.Char('Saturday Hours', default='09:00-13:00')
    working_hours_sunday = fields.Char('Sunday Hours', default='')
    
    # Appointment/Booking Settings (consolidated)
    max_appointments_per_day = fields.Integer('Max Appointments Per Day', default=20)
    max_home_visits_per_day = fields.Integer('Max Home Visits per Day', default=5)
    appointment_duration_default = fields.Integer('Default Appointment Duration (Minutes)', default=30)
    advance_booking_days = fields.Integer(
        'Advance Booking Days', 
        default=30,
        help='clients can book with this staff'
    )
    
    # Emergency Contact
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    emergency_contact_relation = fields.Char('Emergency Contact Relation')
    emergency_contact_email = fields.Char('Emergency Contact Email')
    
    # ============================================================================
    # Skills and Qualifications
    # ============================================================================
    
    healthcare_skill_ids = fields.Many2many(
        'health.staff.skill',
        'employee_healthcare_skill_rel',
        'employee_id', 'skill_id',
        string='Healthcare Skills'
    )
    
    skill_level = fields.Selection([
        ('junior', 'Junior'),
        ('intermediate', 'Intermediate'),
        ('senior', 'Senior'),
        ('expert', 'Expert')
    ], string='Skill Level', default='intermediate')
    
    # Languages spoken (important for Vietnamese healthcare)
    language_ids = fields.Many2many(
        'res.lang',
        'employee_language_rel',
        'employee_id', 'lang_id',
        string='Languages Spoken'
    )
    
    # ============================================================================
    # Assignment and Availability
    # ============================================================================
    
    # Current assignment status
    assignment_status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('busy', 'Busy'),
        ('off_duty', 'Off Duty'),
        ('on_leave', 'On Leave')
    ], string='Assignment Status', default='available', tracking=True)
    
    # Current location (for home visit optimization)
    current_location = fields.Char('Current Location (GPS)', help='Real-time GPS coordinates')
    location_last_updated = fields.Datetime('Location Last Updated')
    
    # Service areas for home visits
    service_area_ids = fields.Many2many(
        'health.service.area',
        'employee_service_area_rel',
        'employee_id', 'area_id',
        string='Service Areas'
    )
    
    max_travel_distance = fields.Float('Max Travel Distance (KM)', default=20.0)
    
    # Additional fields for healthcare staff views
    certification_expiry = fields.Date('Certification Expiry')
    max_daily_assignments = fields.Integer('Max Daily Assignments', default=8)
    preferred_shift = fields.Selection([
        ('morning', 'Morning Shift'),
        ('afternoon', 'Afternoon Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
        ('flexible', 'Flexible')
    ], string='Preferred Shift', default='morning')
    travel_radius_km = fields.Float('Travel Radius (KM)', default=15.0)
    availability_status = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('break', 'On Break'),
        ('offline', 'Offline')
    ], string='Availability Status', default='available')
    
    # ============================================================================
    # Workload and Performance Metrics
    # ============================================================================
    
    # Current workload
    current_assignments_count = fields.Integer(
        'Current Assignments',
        compute='_compute_current_assignments'
    )
    
    daily_capacity = fields.Integer('Daily Capacity', default=8, help='Maximum assignments per day')
    current_load_percentage = fields.Float(
        'Current Load %',
        compute='_compute_workload_metrics'
    )
    
    # Performance metrics (consolidated)
    assignment_completion_rate = fields.Float(
        'Completion Rate %',
        compute='_compute_performance_metrics'
    )
    
    average_patient_rating = fields.Float(
        'Average Patient Rating',
        compute='_compute_performance_metrics'
    )
    
    total_appointments_completed = fields.Integer(
        'Total Appointments',
        compute='_compute_performance_metrics'
    )

    # Booking Credits (PWA Mobile Booking System)
    booking_credit = fields.Integer(
        'Booking Credits',
        default=0,
        help='Number of bookings created by this staff member via mobile PWA',
        tracking=True
    )

    # Additional computed fields
    total_assignments = fields.Integer(
        'Total Assignments',
        compute='_compute_assignment_totals',
        store=True
    )
    
    completed_assignments = fields.Integer(
        'Completed Assignments', 
        compute='_compute_assignment_totals',
        store=True
    )
    
    assignment_success_rate = fields.Float(
        'Assignment Success Rate %',
        compute='_compute_assignment_totals',
        store=True
    )
    
    monthly_appointments = fields.Integer(
        'Monthly Appointments', 
        compute='_compute_monthly_appointments'
    )
    
    patient_satisfaction_score = fields.Float(
        'Patient Satisfaction Score', 
        compute='_compute_satisfaction_score'
    )
    
    # Availability Status
    is_available_today = fields.Boolean('Available Today', compute='_compute_availability_today')
    
    # Display Settings
    color = fields.Integer('Color Index', default=lambda self: self._default_color(), help='Color for calendar display and badge colors')

    def _default_color(self):
        """Generate a random color index (0-11 for Odoo's predefined colors)"""
        import random
        return random.randint(0, 11)
    
    # ============================================================================
    # Scheduling Preferences
    # ============================================================================
    
    preferred_working_hours_start = fields.Float('Preferred Start Time', default=8.0)
    preferred_working_hours_end = fields.Float('Preferred End Time', default=17.0)
    
    available_weekdays = fields.Selection([
        ('weekdays', 'Weekdays Only'),
        ('weekends', 'Weekends Only'),
        ('all', 'All Days')
    ], string='Available Days', default='weekdays')
    
    home_visit_preference = fields.Selection([
        ('prefer', 'Prefer Home Visits'),
        ('neutral', 'No Preference'),
        ('avoid', 'Prefer Clinic Only')
    ], string='Home Visit Preference', default='neutral')
    
    # ============================================================================
    # Communication and Notifications
    # ============================================================================
    
    mobile_for_assignments = fields.Char('Mobile for Assignments', help='Phone number for assignment notifications')
    notification_method = fields.Selection([
        ('email', 'Email Only'),
        ('sms', 'SMS Only'),
        ('both', 'Email and SMS'),
        ('app', 'Mobile App')
    ], string='Preferred Notification Method', default='both')
    
    # ============================================================================
    # Computed Fields
    # ============================================================================
    
    def _generate_staff_code(self):
        """Generate unique staff code"""
        sequence = self.env['ir.sequence'].next_by_code('hr.employee.healthcare') or '0001'
        return f'S{sequence}'
    
    @api.depends('employment_type')
    def _compute_can_create_invoices(self):
        """Compute invoice creation permission based on employment type"""
        for employee in self:
            employee.can_create_invoices = employee.employment_type == 'full_time'

    @api.depends('user_id')
    def _compute_current_assignments(self):
        """Calculate current active assignments"""
        for employee in self:
            if employee.is_healthcare_staff:
                assignments = self.env['health.staff.assignment'].search_count([
                    ('staff_id', '=', employee.id),
                    ('state', 'in', ['assigned', 'confirmed', 'in_progress'])
                ])
                employee.current_assignments_count = assignments
            else:
                employee.current_assignments_count = 0
    
    @api.depends('current_assignments_count', 'daily_capacity')
    def _compute_workload_metrics(self):
        """Calculate workload percentage and metrics"""
        for employee in self:
            if employee.is_healthcare_staff and employee.daily_capacity > 0:
                # Calculate today's assignments
                today_assignments = self.env['health.staff.assignment'].search_count([
                    ('staff_id', '=', employee.id),
                    ('assignment_date', '>=', fields.Date.today()),
                    ('assignment_date', '<', fields.Date.today() + timedelta(days=1)),
                    ('state', 'in', ['assigned', 'confirmed', 'in_progress'])
                ])
                
                employee.current_load_percentage = min(
                    (today_assignments / employee.daily_capacity) * 100, 100
                )
            else:
                employee.current_load_percentage = 0.0
    
    @api.depends('user_id')
    def _compute_performance_metrics(self):
        """Calculate performance metrics"""
        for employee in self:
            if not employee.is_healthcare_staff:
                employee.assignment_completion_rate = 0.0
                employee.average_patient_rating = 0.0
                employee.total_appointments_completed = 0
                continue
            
            # Get completed assignments
            completed_assignments = self.env['health.staff.assignment'].search([
                ('staff_id', '=', employee.id),
                ('state', '=', 'completed')
            ])
            
            total_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', employee.id),
                ('state', 'in', ['completed', 'cancelled'])
            ])
            
            # Completion rate
            if total_assignments > 0:
                employee.assignment_completion_rate = (
                    len(completed_assignments) / total_assignments
                ) * 100
            else:
                employee.assignment_completion_rate = 0.0
            
            # Total completed appointments
            employee.total_appointments_completed = len(completed_assignments)
            
            # Average patient rating (would come from patient feedback)
            # For now, set a default good rating
            employee.average_patient_rating = 4.2  # This would be calculated from actual feedback
    
    @api.depends('is_healthcare_staff')
    def _compute_assignment_totals(self):
        """Compute total assignments and success rate"""
        for employee in self:
            if not employee.is_healthcare_staff:
                employee.total_assignments = 0
                employee.completed_assignments = 0
                employee.assignment_success_rate = 0.0
                continue
            
            # Get all assignments
            all_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', employee.id)
            ])
            
            completed_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', employee.id),
                ('state', '=', 'completed')
            ])
            
            employee.total_assignments = all_assignments
            employee.completed_assignments = completed_assignments
            
            # Calculate success rate
            if all_assignments > 0:
                employee.assignment_success_rate = (completed_assignments / all_assignments) * 100
            else:
                employee.assignment_success_rate = 0.0
    
    def _compute_monthly_appointments(self):
        """Compute monthly appointments for healthcare staff"""
        for employee in self:
            if employee.is_healthcare_staff:
                # TODO: Implement when appointment system is updated
                employee.monthly_appointments = 0
            else:
                employee.monthly_appointments = 0
    
    def _compute_satisfaction_score(self):
        """Compute patient satisfaction score"""
        for employee in self:
            if employee.is_healthcare_staff:
                # TODO: Implement with feedback system
                employee.patient_satisfaction_score = 4.0
            else:
                employee.patient_satisfaction_score = 0.0
    
    def _compute_availability_today(self):
        """Check if staff is available today"""
        for employee in self:
            if employee.is_healthcare_staff:
                # TODO: Implement real availability checking
                employee.is_available_today = employee.assignment_status == 'available'
            else:
                employee.is_available_today = False
    
    # ============================================================================
    # Business Logic Methods
    # ============================================================================
    
    def action_view_assignments(self):
        """View all assignments for this staff member"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Assignments - {self.name}',
            'res_model': 'health.staff.assignment',
            'view_mode': 'calendar,kanban,list,form',
            'domain': [('staff_id', '=', self.id)],
            'context': {
                'default_staff_id': self.id,
                'search_default_my_assignments': 1
            }
        }
    
    def action_view_availability(self):
        """View availability schedule for this staff member"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Availability - {self.name}',
            'res_model': 'health.staff.availability.matrix',
            'view_mode': 'calendar,list,form',
            'domain': [('staff_id', '=', self.id)],
            'context': {
                'default_staff_id': self.id
            }
        }
    
    def action_view_today_schedule(self):
        """View today's schedule for staff member"""
        today = fields.Date.today()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Today's Schedule - {self.name}",
            'res_model': 'health.staff.assignment',
            'view_mode': 'calendar,list',
            'domain': [
                ('staff_id', '=', self.id),
                ('assignment_date', '>=', today),
                ('assignment_date', '<', today + timedelta(days=1))
            ],
            'context': {
                'default_staff_id': self.id,
                'calendar_default_date': today.strftime('%Y-%m-%d')
            }
        }
    
    def update_assignment_status(self, new_status):
        """Update staff assignment status"""
        if not self.is_healthcare_staff:
            return False
        
        self.write({
            'assignment_status': new_status,
            'location_last_updated': fields.Datetime.now()
        })
        
        # Notify assignment system of status change
        self.env['health.staff.assignment.engine']._handle_staff_status_change(
            self.id, new_status
        )
        
        return True
    
    def update_current_location(self, latitude, longitude):
        """Update staff member's current GPS location"""
        if not self.is_healthcare_staff:
            return False
        
        location_string = f"{latitude},{longitude}"
        self.write({
            'current_location': location_string,
            'location_last_updated': fields.Datetime.now()
        })
        
        # Update any active assignments with new location
        active_assignments = self.env['health.staff.assignment'].search([
            ('staff_id', '=', self.id),
            ('state', 'in', ['confirmed', 'in_progress'])
        ])
        
        for assignment in active_assignments:
            assignment.update_location_mobile(assignment.id, latitude, longitude)
        
        return True
    
    def get_availability_for_date(self, date):
        """Get availability status for specific date"""
        if not self.is_healthcare_staff:
            return []
        
        availability_matrix = self.env['health.staff.availability.matrix']
        return availability_matrix.search([
            ('staff_id', '=', self.id),
            ('availability_date', '=', date)
        ])
    
    def is_available_for_appointment(self, appointment_datetime, duration_minutes):
        """Check if staff is available for specific appointment"""
        if not self.is_healthcare_staff:
            return False
        
        availability_matrix = self.env['health.staff.availability.matrix']
        return availability_matrix.is_staff_available(
            self.id, appointment_datetime, duration_minutes
        )
    
    def get_optimal_assignments_score(self, appointment):
        """Get AI-calculated assignment score for this staff member"""
        if not self.is_healthcare_staff:
            return 0.0
        
        assignment_engine = self.env['health.staff.assignment.engine']
        return assignment_engine.calculate_assignment_score(self, appointment)
    
    # ============================================================================
    # API Methods for Mobile App
    # ============================================================================
    
    @api.model
    def get_mobile_dashboard_data(self, staff_id):
        """Get dashboard data for mobile staff app"""
        staff = self.browse(staff_id)
        if not staff.exists() or not staff.is_healthcare_staff:
            return {'error': 'Invalid staff member'}
        
        today = fields.Date.today()
        
        # Get today's assignments
        assignments = self.env['health.staff.assignment'].search([
            ('staff_id', '=', staff_id),
            ('assignment_date', '>=', today),
            ('assignment_date', '<', today + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress'])
        ], order='assignment_date asc')
        
        assignment_data = []
        for assignment in assignments:
            fso = assignment.fso_id
            assignment_data.append({
                'assignment_id': assignment.id,
                'fso_id': fso.id,
                'patient_name': fso.patient_id.name,
                'service_type': fso.service_type_id.name,
                'scheduled_time': fso.scheduled_datetime,
                'status': assignment.state,
                'address': fso.visit_address or (fso.facility_id.name if fso.facility_id else ''),
                'priority': assignment.priority,
                'estimated_duration': fso.estimated_duration_minutes
            })
        
        return {
            'staff_info': {
                'id': staff.id,
                'name': staff.name,
                'role': staff.healthcare_role,
                'current_status': staff.assignment_status,
                'current_load': staff.current_load_percentage
            },
            'today_assignments': assignment_data,
            'performance_metrics': {
                'completion_rate': staff.assignment_completion_rate,
                'patient_rating': staff.average_patient_rating,
                'total_completed': staff.total_appointments_completed
            }
        }
    
    @api.model
    def update_status_mobile(self, staff_id, new_status, location_data=None):
        """Update staff status from mobile app"""
        staff = self.browse(staff_id)
        if not staff.exists() or not staff.is_healthcare_staff:
            return {'error': 'Invalid staff member'}
        
        # Update status
        staff.update_assignment_status(new_status)
        
        # Update location if provided
        if location_data and 'latitude' in location_data and 'longitude' in location_data:
            staff.update_current_location(
                location_data['latitude'],
                location_data['longitude']
            )
        
        return {'success': True, 'status': staff.assignment_status}
    
    def action_view_patients(self):
        """View patients assigned to this staff member"""
        if not self.is_healthcare_staff:
            return
            
        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients - {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('is_patient', '=', True)],  # TODO: Add staff assignment filter
            'context': {'search_patients': True}
        }
    
    def action_check_license_expiry(self):
        """Check license expiry for healthcare staff"""
        if not self.is_healthcare_staff:
            return
            
        today = fields.Date.today()
        if self.license_expiry:
            days_to_expiry = (self.license_expiry - today).days
            
            if days_to_expiry < 0:
                message = f'License expired {abs(days_to_expiry)} days ago!'
                notification_type = 'danger'
            elif days_to_expiry <= 30:
                message = f'License expires in {days_to_expiry} days!'
                notification_type = 'warning'
            else:
                message = f'License is valid until {self.license_expiry}'
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
        """Toggle staff availability status"""
        if not self.is_healthcare_staff:
            return
            
        if self.assignment_status == 'available':
            new_status = 'off_duty'
            message = 'You are now marked as Off Duty'
        else:
            new_status = 'available'
            message = 'You are now marked as Available'
            
        self.assignment_status = new_status
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Availability Updated',
                'message': message,
                'type': 'success'
            }
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare staff categories"""
        employees = super().create(vals_list)
        
        for employee in employees:
            if employee.is_healthcare_staff:
                # Generate staff code if not already set
                if not employee.staff_code:
                    employee.staff_code = employee._generate_staff_code()
                    
                # Set customer rank for CRM integration
                if employee.user_id and employee.user_id.partner_id:
                    employee.user_id.partner_id.is_healthcare_staff = True
                    
                    # Add healthcare staff category
                    staff_category = self.env.ref('health_base.staff_category', raise_if_not_found=False)
                    if staff_category:
                        employee.user_id.partner_id.category_id = [(4, staff_category.id)]
                        
        return employees