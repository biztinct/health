from odoo import models, fields, api, _
from datetime import datetime, timedelta


class HrEmployee(models.Model):
    """Extend HR Employee with healthcare staff assignment capabilities"""
    _inherit = 'hr.employee'
    
    # ============================================================================
    # Healthcare Staff Classification
    # ============================================================================
    
    is_healthcare_staff = fields.Boolean(
        'Healthcare Staff',
        help='Check if this employee provides healthcare services'
    )
    
    healthcare_role = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('specialist', 'Specialist'),
        ('therapist', 'Therapist'),
        ('technician', 'Technician'),
        ('support', 'Support Staff')
    ], string='Healthcare Role')
    
    # Professional credentials
    license_number = fields.Char('Professional License Number')
    license_expiry = fields.Date('License Expiry Date')
    specializations = fields.Text('Medical Specializations')
    
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
    
    # Performance metrics
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
    
    @api.depends('user_id')
    def _compute_current_assignments(self):
        """Calculate current active assignments"""
        for employee in self:
            if employee.is_healthcare_staff:
                assignments = self.env['health.staff.assignment'].search_count([
                    ('assigned_staff_ids', 'in', [employee.id]),
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
                    ('assigned_staff_ids', 'in', [employee.id]),
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
                ('assigned_staff_ids', 'in', [employee.id]),
                ('state', '=', 'completed')
            ])
            
            total_assignments = self.env['health.staff.assignment'].search_count([
                ('assigned_staff_ids', 'in', [employee.id]),
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
            'domain': [('assigned_staff_ids', 'in', [self.id])],
            'context': {
                'default_assigned_staff_ids': [(6, 0, [self.id])],
                'search_default_my_assignments': 1
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
                ('assigned_staff_ids', 'in', [self.id]),
                ('assignment_date', '>=', today),
                ('assignment_date', '<', today + timedelta(days=1))
            ],
            'context': {
                'default_assigned_staff_ids': [(6, 0, [self.id])],
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
            ('assigned_staff_ids', 'in', [self.id]),
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
            ('assigned_staff_ids', 'in', [staff_id]),
            ('assignment_date', '>=', today),
            ('assignment_date', '<', today + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress'])
        ], order='assignment_date asc')
        
        assignment_data = []
        for assignment in assignments:
            apt = assignment.appointment_id
            assignment_data.append({
                'assignment_id': assignment.id,
                'appointment_id': apt.id,
                'patient_name': apt.patient_id.name,
                'service_type': apt.appointment_type_id.name,
                'appointment_time': apt.appointment_date,
                'status': assignment.state,
                'address': apt.visit_address or (apt.facility_id.name if apt.facility_id else ''),
                'priority': assignment.priority,
                'estimated_duration': apt.appointment_type_id.duration_minutes
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


# Note: HealthStaffSkill and HealthServiceArea models are now defined in healthcare_skill.py
# to avoid duplicate model definitions and field naming conflicts.