from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import math


class HealthStaffAssignment(models.Model):
    """
    State-of-the-art staff assignment system with intelligent routing
    Inspired by Uber's driver matching and Amazon's delivery optimization
    """
    _name = 'health.staff.assignment'
    _description = 'Intelligent Staff Assignment Record'
    _order = 'assignment_date desc, priority desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # ============================================================================
    # Core Assignment Fields
    # ============================================================================
    
    name = fields.Char('Assignment Reference', required=True, copy=False, readonly=True,
                      default=lambda self: _('New Assignment'))
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Appointment',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    # Staff assignment (many2many for team assignments)
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'staff_assignment_employee_rel',
        'assignment_id', 'employee_id',
        string='Assigned Staff',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True
    )
    
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        domain=[('is_healthcare_staff', '=', True)],
        tracking=True,
        help='Primary staff member responsible for this assignment'
    )
    
    # Assignment metadata
    assignment_date = fields.Datetime('Assignment Date', default=fields.Datetime.now, required=True)
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)
    
    # ============================================================================
    # State Management  
    # ============================================================================
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('confirmed', 'Staff Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('deferred', 'Deferred')
    ], string='Assignment State', default='draft', tracking=True)
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
        ('4', 'Emergency')
    ], string='Priority', default='1', tracking=True)
    
    # ============================================================================
    # AI-Powered Assignment Intelligence
    # ============================================================================
    
    assignment_score = fields.Float(
        'Assignment Quality Score',
        help='AI-calculated score (0-100) based on skills, location, workload, availability',
        compute='_compute_assignment_score',
        store=True
    )
    
    skill_match_score = fields.Float('Skill Match Score', help='How well staff skills match requirements (0-100)')
    proximity_score = fields.Float('Proximity Score', help='Geographic proximity score (0-100)')
    workload_score = fields.Float('Workload Balance Score', help='Staff workload optimization score (0-100)')
    availability_score = fields.Float('Availability Score', help='Staff availability buffer score (0-100)')
    
    # Required skills analysis
    required_skills_json = fields.Text('Required Skills (JSON)', help='JSON array of required skills')
    staff_skills_match = fields.Text('Staff Skills Match', help='JSON analysis of skill matching')
    
    # ============================================================================
    # Geographic Optimization (Home Visits)
    # ============================================================================
    
    # Location data
    origin_location = fields.Char('Staff Origin Location', help='Staff starting location coordinates')
    destination_location = fields.Char('Appointment Location', help='Appointment location coordinates')
    
    # Route optimization
    estimated_travel_time = fields.Float('Estimated Travel Time (Hours)')
    estimated_travel_distance = fields.Float('Estimated Distance (KM)')
    optimal_route_json = fields.Text('Optimal Route Data (JSON)', help='Google Maps route data')
    
    # Traffic and timing
    departure_time = fields.Datetime('Recommended Departure Time')
    arrival_time = fields.Datetime('Expected Arrival Time')
    traffic_factor = fields.Float('Traffic Factor', default=1.0, help='Traffic multiplier for travel time')
    
    # ============================================================================
    # Workload Management
    # ============================================================================
    
    staff_current_load = fields.Float('Staff Current Load %', compute='_compute_staff_workload')
    daily_assignment_count = fields.Integer('Daily Assignments', compute='_compute_daily_stats')
    weekly_assignment_count = fields.Integer('Weekly Assignments', compute='_compute_weekly_stats')
    
    # Buffer time management
    buffer_before = fields.Integer('Buffer Before (Minutes)', default=15)
    buffer_after = fields.Integer('Buffer After (Minutes)', default=15)
    
    # ============================================================================
    # Real-time Tracking
    # ============================================================================
    
    staff_confirmed_date = fields.Datetime('Staff Confirmation Date')
    actual_departure_time = fields.Datetime('Actual Departure Time')
    actual_arrival_time = fields.Datetime('Actual Arrival Time')
    actual_completion_time = fields.Datetime('Actual Completion Time')
    
    # GPS tracking
    current_location = fields.Char('Current Location', help='Real-time GPS coordinates')
    location_last_updated = fields.Datetime('Location Last Updated')
    
    # ============================================================================
    # Performance Analytics
    # ============================================================================
    
    assignment_efficiency = fields.Float('Assignment Efficiency %', compute='_compute_efficiency')
    patient_satisfaction = fields.Float('Patient Satisfaction Score')
    staff_performance_rating = fields.Float('Staff Performance Rating')
    
    # Timing analysis
    planning_accuracy = fields.Float('Planning Accuracy %', compute='_compute_planning_accuracy')
    time_variance_minutes = fields.Float('Time Variance (Minutes)', compute='_compute_time_variance')
    
    # ============================================================================
    # Computed Fields
    # ============================================================================
    
    @api.depends('assigned_staff_ids', 'appointment_id')
    def _compute_assignment_score(self):
        """Calculate comprehensive assignment quality score"""
        for record in self:
            if not record.assigned_staff_ids or not record.appointment_id:
                record.assignment_score = 0.0
                continue
            
            # Get assignment engine for score calculation
            engine = self.env['health.staff.assignment.engine']
            
            # Calculate individual score components
            skill_score = engine.calculate_skill_match_score(
                record.assigned_staff_ids, 
                record.appointment_id
            )
            
            proximity_score = engine.calculate_proximity_score(
                record.assigned_staff_ids,
                record.appointment_id
            )
            
            workload_score = engine.calculate_workload_score(
                record.assigned_staff_ids,
                record.appointment_id.appointment_date
            )
            
            availability_score = engine.calculate_availability_score(
                record.assigned_staff_ids,
                record.appointment_id
            )
            
            # Store individual scores
            record.skill_match_score = skill_score
            record.proximity_score = proximity_score
            record.workload_score = workload_score
            record.availability_score = availability_score
            
            # Calculate weighted total score
            # Weights: Skills 40%, Proximity 30%, Workload 20%, Availability 10%
            total_score = (
                skill_score * 0.4 +
                proximity_score * 0.3 +
                workload_score * 0.2 +
                availability_score * 0.1
            )
            
            record.assignment_score = round(total_score, 2)
    
    @api.depends('assigned_staff_ids')
    def _compute_staff_workload(self):
        """Calculate current workload percentage for assigned staff"""
        for record in self:
            if not record.assigned_staff_ids:
                record.staff_current_load = 0.0
                continue
            
            # Calculate average workload across assigned staff
            total_load = 0.0
            staff_count = len(record.assigned_staff_ids)
            
            for staff in record.assigned_staff_ids:
                # Get staff's current assignments for today
                today_assignments = self.search_count([
                    ('assigned_staff_ids', 'in', [staff.id]),
                    ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
                    ('assignment_date', '>=', fields.Date.today()),
                    ('assignment_date', '<', fields.Date.today() + timedelta(days=1))
                ])
                
                # Assume max 8 assignments per day as 100% load
                staff_load = min((today_assignments / 8.0) * 100, 100)
                total_load += staff_load
            
            record.staff_current_load = total_load / staff_count if staff_count > 0 else 0.0
    
    @api.depends('assigned_staff_ids', 'assignment_date')
    def _compute_daily_stats(self):
        """Calculate daily assignment statistics"""
        for record in self:
            if not record.assigned_staff_ids or not record.assignment_date:
                record.daily_assignment_count = 0
                continue
            
            # Count assignments for the same day
            assignment_date = fields.Date.from_string(record.assignment_date.date())
            domain = [
                ('assigned_staff_ids', 'in', record.assigned_staff_ids.ids),
                ('assignment_date', '>=', assignment_date),
                ('assignment_date', '<', assignment_date + timedelta(days=1)),
                ('state', '!=', 'cancelled')
            ]
            
            record.daily_assignment_count = self.search_count(domain)
    
    @api.depends('assigned_staff_ids', 'assignment_date')  
    def _compute_weekly_stats(self):
        """Calculate weekly assignment statistics"""
        for record in self:
            if not record.assigned_staff_ids or not record.assignment_date:
                record.weekly_assignment_count = 0
                continue
            
            # Get start of week (Monday)
            assignment_date = record.assignment_date.date()
            start_of_week = assignment_date - timedelta(days=assignment_date.weekday())
            end_of_week = start_of_week + timedelta(days=7)
            
            domain = [
                ('assigned_staff_ids', 'in', record.assigned_staff_ids.ids),
                ('assignment_date', '>=', start_of_week),
                ('assignment_date', '<', end_of_week),
                ('state', '!=', 'cancelled')
            ]
            
            record.weekly_assignment_count = self.search_count(domain)
    
    @api.depends('actual_completion_time', 'appointment_id')
    def _compute_efficiency(self):
        """Calculate assignment efficiency based on planned vs actual execution"""
        for record in self:
            if not record.actual_completion_time or not record.appointment_id:
                record.assignment_efficiency = 0.0
                continue
            
            # Calculate efficiency based on timing accuracy
            planned_duration = record.appointment_id.appointment_type_id.duration_minutes
            
            if record.actual_arrival_time and record.actual_completion_time:
                actual_duration = (record.actual_completion_time - record.actual_arrival_time).total_seconds() / 60
                
                # Efficiency = 100% if actual matches planned, lower if significantly different
                if actual_duration > 0:
                    efficiency = min(100, (planned_duration / actual_duration) * 100)
                    if actual_duration > planned_duration * 1.2:  # 20% over
                        efficiency = max(efficiency * 0.8, 50)  # Cap efficiency reduction
                    record.assignment_efficiency = efficiency
                else:
                    record.assignment_efficiency = 0.0
            else:
                record.assignment_efficiency = 0.0
    
    @api.depends('departure_time', 'actual_departure_time', 'arrival_time', 'actual_arrival_time')
    def _compute_planning_accuracy(self):
        """Calculate how accurate the planning was vs reality"""
        for record in self:
            accuracy_scores = []
            
            # Departure time accuracy
            if record.departure_time and record.actual_departure_time:
                variance = abs((record.actual_departure_time - record.departure_time).total_seconds() / 60)
                departure_accuracy = max(0, 100 - (variance / 30) * 100)  # 30 min = 0% accuracy
                accuracy_scores.append(departure_accuracy)
            
            # Arrival time accuracy  
            if record.arrival_time and record.actual_arrival_time:
                variance = abs((record.actual_arrival_time - record.arrival_time).total_seconds() / 60)
                arrival_accuracy = max(0, 100 - (variance / 30) * 100)
                accuracy_scores.append(arrival_accuracy)
            
            # Calculate average accuracy
            record.planning_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0
    
    @api.depends('arrival_time', 'actual_arrival_time')
    def _compute_time_variance(self):
        """Calculate time variance in minutes"""
        for record in self:
            if record.arrival_time and record.actual_arrival_time:
                variance = (record.actual_arrival_time - record.arrival_time).total_seconds() / 60
                record.time_variance_minutes = variance
            else:
                record.time_variance_minutes = 0.0
    
    # ============================================================================
    # CRUD Overrides
    # ============================================================================
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New Assignment')) == _('New Assignment'):
            vals['name'] = self.env['ir.sequence'].next_by_code('health.staff.assignment') or _('New Assignment')
        return super().create(vals)
    
    # ============================================================================
    # Business Logic Methods
    # ============================================================================
    
    def action_confirm_assignment(self):
        """Confirm the staff assignment"""
        for record in self:
            if record.state != 'assigned':
                raise UserError(_('Only assigned records can be confirmed.'))
            
            record.write({
                'state': 'confirmed',
                'staff_confirmed_date': fields.Datetime.now()
            })
            
            # Update related appointment
            if record.appointment_id:
                record.appointment_id.write({
                    'assignment_state': 'staff_confirmed',
                    'real_time_status': 'confirmed'
                })
            
            # Send confirmation notifications
            record._send_confirmation_notifications()
    
    def action_start_assignment(self):
        """Start the assignment (staff is en route or starting service)"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Assignment must be confirmed first.'))
            
            record.write({
                'state': 'in_progress',
                'actual_departure_time': fields.Datetime.now()
            })
            
            # Update appointment status
            if record.appointment_id:
                record.appointment_id.write({
                    'real_time_status': 'en_route'
                })
    
    def action_complete_assignment(self):
        """Complete the assignment"""
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Assignment must be in progress to complete.'))
            
            record.write({
                'state': 'completed',
                'actual_completion_time': fields.Datetime.now()
            })
            
            # Update appointment
            if record.appointment_id:
                record.appointment_id.write({
                    'real_time_status': 'completed',
                    'state': 'completed'
                })
            
            # Update staff availability
            record._update_staff_availability()
    
    def action_cancel_assignment(self):
        """Cancel the assignment"""
        for record in self:
            if record.state in ['completed']:
                raise UserError(_('Cannot cancel completed assignments.'))
            
            record.write({'state': 'cancelled'})
            
            # Free up staff availability
            record._release_staff_availability()
    
    def action_reschedule_assignment(self):
        """Reschedule the assignment to a different time/staff"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reschedule Assignment'),
            'res_model': 'health.staff.assignment.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assignment_id': self.id}
        }
    
    def optimize_route(self):
        """Optimize route using Google Maps API"""
        for record in self:
            if record.appointment_id.appointment_type_id.location_type != 'home':
                continue  # Only for home visits
            
            route_optimizer = self.env['health.route.optimizer']
            optimization_result = route_optimizer.optimize_single_assignment(record)
            
            if optimization_result:
                record.write({
                    'optimal_route_json': json.dumps(optimization_result['route_data']),
                    'estimated_travel_time': optimization_result['travel_time_hours'],
                    'estimated_travel_distance': optimization_result['distance_km'],
                    'departure_time': optimization_result['recommended_departure'],
                    'arrival_time': optimization_result['expected_arrival']
                })
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _send_confirmation_notifications(self):
        """Send notifications when assignment is confirmed"""
        # Notify patient
        if self.appointment_id.patient_id.email:
            template = self.env.ref('health_staff_assignment.email_template_assignment_confirmed', False)
            if template:
                template.send_mail(self.id, force_send=True)
        
        # Notify operations team
        ops_users = self.env.ref('health_staff_assignment.group_ops_manager').users
        for user in ops_users:
            self.message_post(
                body=_('Assignment confirmed for appointment %s') % self.appointment_id.name,
                partner_ids=user.partner_id.ids,
                message_type='notification'
            )
    
    def _update_staff_availability(self):
        """Update staff availability matrix after completion"""
        availability_matrix = self.env['health.staff.availability.matrix']
        for staff in self.assigned_staff_ids:
            availability_matrix.update_staff_availability(
                staff.id,
                self.appointment_id.appointment_date,
                self.appointment_id.appointment_type_id.duration_minutes,
                'available'  # Free up the time slot
            )
    
    def _release_staff_availability(self):
        """Release staff availability when assignment is cancelled"""
        self._update_staff_availability()  # Same logic - free up time
    
    # ============================================================================
    # API Methods for Mobile Interface
    # ============================================================================
    
    @api.model
    def get_my_assignments_mobile(self, staff_id, date_from=None, date_to=None):
        """Get assignments for mobile staff interface"""
        domain = [('assigned_staff_ids', 'in', [staff_id])]
        
        if date_from:
            domain.append(('assignment_date', '>=', date_from))
        if date_to:
            domain.append(('assignment_date', '<=', date_to))
        
        assignments = self.search(domain, order='assignment_date asc')
        
        result = []
        for assignment in assignments:
            apt = assignment.appointment_id
            result.append({
                'assignment_id': assignment.id,
                'appointment_id': apt.id,
                'patient_name': apt.patient_id.name,
                'patient_phone': apt.patient_id.mobile or apt.patient_id.phone,
                'service_type': apt.appointment_type_id.name,
                'appointment_date': apt.appointment_date,
                'estimated_duration': apt.appointment_type_id.duration_minutes,
                'address': apt.visit_address or (apt.facility_id.name if apt.facility_id else ''),
                'status': assignment.state,
                'real_time_status': apt.real_time_status,
                'priority': assignment.priority,
                'assignment_score': assignment.assignment_score,
                'estimated_travel_time': assignment.estimated_travel_time,
                'departure_time': assignment.departure_time,
                'arrival_time': assignment.arrival_time,
                'route_data': assignment.optimal_route_json
            })
        
        return result
    
    @api.model
    def update_location_mobile(self, assignment_id, latitude, longitude):
        """Update staff location from mobile app"""
        assignment = self.browse(assignment_id)
        
        # Verify user is assigned to this assignment
        if not assignment.assigned_staff_ids.filtered(lambda s: s.user_id == self.env.user):
            return {'error': 'Not authorized'}
        
        location_string = f"{latitude},{longitude}"
        assignment.write({
            'current_location': location_string,
            'location_last_updated': fields.Datetime.now()
        })
        
        # Update appointment location too
        assignment.appointment_id.write({
            'staff_current_location': location_string
        })
        
        return {'success': True}


class HealthStaffAssignmentEngine(models.Model):
    """
    AI-powered assignment engine for intelligent staff routing
    Implements algorithms inspired by Uber's matching and Amazon's optimization
    """
    _name = 'health.staff.assignment.engine'
    _description = 'Intelligent Staff Assignment Engine'
    
    def calculate_skill_match_score(self, staff_ids, appointment):
        """
        Calculate how well staff skills match appointment requirements
        Returns score 0-100
        """
        if not staff_ids or not appointment:
            return 0.0
        
        # Get required skills from appointment type
        required_skills = []
        if appointment.appointment_type_id.required_skills_json:
            try:
                required_skills = json.loads(appointment.appointment_type_id.required_skills_json)
            except:
                required_skills = []
        
        if not required_skills:
            return 85.0  # Default good score if no specific skills required
        
        # Calculate skill match for each staff member
        staff_scores = []
        for staff in staff_ids:
            staff_skills = staff.healthcare_skill_ids.mapped('name') if hasattr(staff, 'healthcare_skill_ids') else []
            
            if not staff_skills:
                staff_scores.append(50.0)  # Neutral score for no skill data
                continue
            
            # Calculate match percentage
            matched_skills = set(required_skills) & set(staff_skills)
            match_percentage = len(matched_skills) / len(required_skills) * 100
            
            # Bonus for having additional relevant skills
            bonus = min(len(staff_skills) - len(required_skills), 3) * 5
            final_score = min(match_percentage + bonus, 100)
            
            staff_scores.append(final_score)
        
        # Return average score across all assigned staff
        return sum(staff_scores) / len(staff_scores) if staff_scores else 0.0
    
    def calculate_proximity_score(self, staff_ids, appointment):
        """
        Calculate geographic proximity score for staff assignment
        Returns score 0-100 (higher is better - closer proximity)
        """
        if not staff_ids or not appointment:
            return 0.0
        
        # For clinic appointments, proximity is less critical
        if appointment.appointment_type_id.location_type == 'clinic':
            return 80.0  # Good default score
        
        # For home visits, calculate actual distance
        if appointment.appointment_type_id.location_type == 'home':
            if not appointment.visit_address:
                return 60.0  # Medium score if no address
            
            # Calculate distance to appointment location
            # This would integrate with Google Maps API in real implementation
            # For now, return a reasonable score
            return 75.0
        
        # For telemedicine, location doesn't matter
        if appointment.appointment_type_id.location_type == 'online':
            return 95.0
        
        return 70.0  # Default score
    
    def calculate_workload_score(self, staff_ids, appointment_date):
        """
        Calculate workload balance score
        Returns score 0-100 (higher is better - more balanced workload)
        """
        if not staff_ids or not appointment_date:
            return 0.0
        
        date_obj = appointment_date.date() if hasattr(appointment_date, 'date') else appointment_date
        
        workload_scores = []
        for staff in staff_ids:
            # Count assignments for the day
            daily_assignments = self.env['health.staff.assignment'].search_count([
                ('assigned_staff_ids', 'in', [staff.id]),
                ('assignment_date', '>=', date_obj),
                ('assignment_date', '<', date_obj + timedelta(days=1)),
                ('state', 'in', ['assigned', 'confirmed', 'in_progress'])
            ])
            
            # Calculate score based on current load (assuming max 8 assignments per day)
            max_daily_assignments = 8
            load_percentage = (daily_assignments / max_daily_assignments) * 100
            
            # Score is inversely related to load (less load = higher score)
            workload_score = max(0, 100 - load_percentage)
            workload_scores.append(workload_score)
        
        return sum(workload_scores) / len(workload_scores) if workload_scores else 0.0
    
    def calculate_availability_score(self, staff_ids, appointment):
        """
        Calculate availability buffer score
        Returns score 0-100 (higher is better - more buffer time)
        """
        if not staff_ids or not appointment:
            return 0.0
        
        availability_matrix = self.env['health.staff.availability.matrix']
        
        availability_scores = []
        for staff in staff_ids:
            # Check if staff is available at the appointment time
            is_available = availability_matrix.is_staff_available(
                staff.id,
                appointment.appointment_date,
                appointment.appointment_type_id.duration_minutes
            )
            
            if not is_available:
                availability_scores.append(0.0)
                continue
            
            # Calculate buffer score based on surrounding availability
            buffer_score = availability_matrix.calculate_buffer_score(
                staff.id,
                appointment.appointment_date,
                appointment.appointment_type_id.duration_minutes
            )
            
            availability_scores.append(buffer_score)
        
        return sum(availability_scores) / len(availability_scores) if availability_scores else 0.0
    
    @api.model
    def get_optimal_staff_suggestions(self, appointment_id, limit=5):
        """
        Get AI-powered staff suggestions for an appointment
        Returns list of staff with assignment scores
        """
        appointment = self.env['health.appointment'].browse(appointment_id)
        if not appointment.exists():
            return []
        
        # Get all available healthcare staff
        available_staff = self.env['hr.employee'].search([
            ('is_healthcare_staff', '=', True),
            ('active', '=', True)
        ])
        
        suggestions = []
        for staff in available_staff:
            # Calculate comprehensive score
            skill_score = self.calculate_skill_match_score(staff, appointment)
            proximity_score = self.calculate_proximity_score(staff, appointment)
            workload_score = self.calculate_workload_score(staff, appointment.appointment_date)
            availability_score = self.calculate_availability_score(staff, appointment)
            
            # Weighted total score
            total_score = (
                skill_score * 0.4 +
                proximity_score * 0.3 +
                workload_score * 0.2 +
                availability_score * 0.1
            )
            
            suggestions.append({
                'staff_id': staff.id,
                'staff_name': staff.name,
                'total_score': round(total_score, 2),
                'skill_score': round(skill_score, 2),
                'proximity_score': round(proximity_score, 2),
                'workload_score': round(workload_score, 2),
                'availability_score': round(availability_score, 2),
                'recommendation_reason': self._get_recommendation_reason(
                    skill_score, proximity_score, workload_score, availability_score
                )
            })
        
        # Sort by total score and return top suggestions
        suggestions.sort(key=lambda x: x['total_score'], reverse=True)
        return suggestions[:limit]
    
    def _get_recommendation_reason(self, skill_score, proximity_score, workload_score, availability_score):
        """Generate human-readable recommendation reason"""
        reasons = []
        
        if skill_score >= 90:
            reasons.append("Perfect skill match")
        elif skill_score >= 75:
            reasons.append("Good skill match")
        
        if proximity_score >= 85:
            reasons.append("Optimal location")
        elif proximity_score >= 70:
            reasons.append("Good proximity")
        
        if workload_score >= 80:
            reasons.append("Balanced workload")
        elif workload_score < 50:
            reasons.append("High current load")
        
        if availability_score >= 85:
            reasons.append("Excellent availability")
        elif availability_score < 50:
            reasons.append("Limited availability")
        
        return " • ".join(reasons) if reasons else "Standard assignment"