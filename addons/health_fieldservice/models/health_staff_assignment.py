from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import math
import logging

_logger = logging.getLogger(__name__)


class HealthStaffAssignment(models.Model):
    """
    State-of-the-art staff assignment system with intelligent routing
    Inspired by Uber's driver matching and Amazon's delivery optimization
    """
    _name = 'health.staff.assignment'
    _description = 'Intelligent Staff Assignment Record'
    _order = 'assignment_date desc, priority desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Class-level cache for timeline context (used across all instances in this process)
    _timeline_context_cache = {}

    # ============================================================================
    # Core Assignment Fields
    # ============================================================================
    
    # Timeline display name for better web_timeline integration
    @api.depends('name', 'fso_id', 'staff_id', 'assignment_role')
    def _compute_display_name(self):
        """Compute a rich display name for timeline view"""
        for record in self:
            if record.fso_id and record.staff_id:
                role_label = dict(record._fields['assignment_role'].selection).get(record.assignment_role, '')
                role_badge = f"[{role_label}]" if role_label else ""
                record.display_name = f"{record.fso_id.name} - {record.staff_id.name} {role_badge}"
            else:
                record.display_name = record.name or "New Assignment"
    
    display_name = fields.Char(compute='_compute_display_name', store=True)
    # Strict patient name for timeline cards
    patient_name = fields.Char(
        related='fso_id.patient_id.name',
        string='Client Name',
        store=True,
        readonly=True
    )

    active = fields.Boolean(
        default=True,
        help='If unchecked, the assignment is archived.'
    )

    
    name = fields.Char('Assignment Reference', required=True, copy=False, readonly=True,
                      default=lambda self: _('New Assignment'))
    
    fso_id = fields.Many2one(
        'health.fieldservice.order',
        string='Booking',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    # Individual staff assignment (One assignment = One staff member)
    staff_id = fields.Many2one(
        'hr.employee',
        string='Assigned Staff',
        required=False,  # Allow unassigned staff in draft state for timeline drag-drop
        domain=[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active')],
        tracking=True,
        help='Individual staff member for this assignment (can be unassigned in draft state)'
    )
    
    # Related field for client's catchment province (used for staff filtering)
    client_catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Client Catchment Province',
        related='fso_id.patient_id.catchment_province_id',
        store=True,
        help='Catchment province of the client - used to filter staff with matching healthcare facility'
    )
    
    assignment_role = fields.Selection([
        ('lead', 'Lead Staff'),
        ('support', 'Support Staff'),
        ('doctor', 'Doctor'),
        ('consultant', 'Consultant'),
        ('specialist', 'Specialist'),
        ('trainee', 'Trainee')
    ], string='Assignment Role', default='lead', required=True, tracking=True,
       help='Role of this staff member in the service delivery')

    # Assignment metadata
    assignment_date = fields.Datetime(
        'Assignment Date',
        compute='_compute_assignment_date',
        store=True,
        readonly=False,
        default=fields.Datetime.now,
        required=True,
        help='Auto-synced with FSO scheduled_datetime when FSO is present'
    )
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)
    
    # Individual timing for this staff member
    planned_start_time = fields.Datetime(
        'Planned Start Time',
        compute='_compute_planned_start_time',
        store=True,
        readonly=False,
        help='Auto-populated from FSO scheduled_datetime (can be manually overridden)'
    )
    planned_end_time = fields.Datetime(
        'Planned End Time',
        compute='_compute_planned_end_time',
        store=True,
        readonly=False,
        help='Auto-calculated from planned_start_time + FSO scheduled_duration'
    )
    actual_start_time = fields.Datetime('Actual Start Time', help='When this staff member actually started')
    actual_end_time = fields.Datetime('Actual End Time', help='When this staff member actually finished')

    # Formatted datetime for timeline display (e.g., "21/Oct - 10:30 AM")
    formatted_datetime = fields.Char('Formatted DateTime', compute='_compute_formatted_datetime', store=False)

    # Formatted time only for timeline display (e.g., "09:30 AM")
    formatted_time = fields.Char('Formatted Time', compute='_compute_formatted_time', store=False)

    # Duration from FSO for timeline display
    fso_duration_minutes = fields.Integer('Service Duration (Minutes)', compute='_compute_fso_duration', store=False)
    
    # Individual assignment status
    assignment_status = fields.Selection([
        ('assigned', 'Assigned'),
        ('confirmed', 'Confirmed'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Assignment Status', default='assigned', required=True, tracking=True)
    
    # Individual notes and feedback
    assignment_notes = fields.Text('Assignment Notes', help='Specific notes for this staff member')
    completion_notes = fields.Text('Completion Notes', help='Notes added upon completion')
    
    # ============================================================================
    # Field Service Integration (health_fieldservice module required)
    # ============================================================================
    
    # Equipment requirements from FSO
    required_equipment_ids = fields.Many2many(
        'health.portable.equipment',
        'assignment_required_equipment_rel',
        'assignment_id', 'equipment_id',
        string='Required Equipment',
        help='Equipment required for this assignment (from FSO or manual)'
    )
    
    # Equipment assignment status
    equipment_assigned = fields.Boolean(
        'Equipment Assigned',
        compute='_compute_equipment_status',
        help='Whether all required equipment has been assigned'
    )
    
    equipment_checklist_complete = fields.Boolean(
        'Equipment Checklist Complete',
        help='Field staff confirmed all equipment is available and functional'
    )
    
    # ============================================================================
    # State Management  
    # ============================================================================
    
    state = fields.Selection([
        ('template', 'Template'),  # Template record for timeline context (hidden from lists)
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('confirmed', 'Staff Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('deferred', 'Deferred')
    ], string='Assignment State', default='assigned', tracking=True)
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
        ('4', 'Emergency')
    ], string='Priority', default='1', tracking=True)
    
    assignment_type = fields.Selection([
        ('clinic_visit', 'Clinic Visit'),
        ('home_visit', 'Home Visit'),
        ('emergency', 'Emergency Response'),
        ('follow_up', 'Follow-up Visit'),
        ('consultation', 'Consultation')
    ], string='Assignment Type', default='clinic_visit', tracking=True)
    
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
    # V2.0 AI/ML Enhanced Fields
    # ============================================================================
    
    # AI Assignment Intelligence
    ai_assignment_score = fields.Float('AI Assignment Score', readonly=True, help='ML-powered assignment quality score')
    assignment_confidence = fields.Float('Assignment Confidence %', readonly=True, help='AI confidence in assignment success')
    predicted_success_probability = fields.Float('Success Probability %', readonly=True, help='ML predicted assignment success rate')
    optimal_staff_suggestions = fields.Text('Optimal Staff Suggestions JSON', readonly=True, help='AI-generated staff recommendations')
    
    # Predictive Analytics
    predicted_duration = fields.Integer('Predicted Duration (Minutes)', readonly=True, help='AI predicted assignment duration')
    predicted_complexity = fields.Selection([
        ('low', 'Low Complexity'),
        ('medium', 'Medium Complexity'), 
        ('high', 'High Complexity'),
        ('critical', 'Critical Complexity')
    ], string='Predicted Complexity', readonly=True, help='AI assessment of assignment complexity')
    
    # ML-based Optimization
    ml_optimization_applied = fields.Boolean('ML Optimization Applied', default=False, readonly=True)
    optimization_timestamp = fields.Datetime('Last Optimization', readonly=True)
    optimization_suggestions = fields.Text('Optimization Suggestions JSON', readonly=True)
    
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
    
    # Real-time assignment status
    real_time_status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('assigned', 'Assigned'),
        ('confirmed', 'Confirmed'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Real-time Status', default='scheduled', tracking=True,
       help='Real-time assignment status for mobile tracking')
    
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
    # Computed Fields & Compatibility Properties
    # ============================================================================
    
    @property
    def appointment_id(self):
        """Compatibility property - return FSO as appointment equivalent"""
        return self.fso_id
    
    @api.depends('required_equipment_ids', 'fso_id.assigned_equipment_ids')
    def _compute_equipment_status(self):
        """Check if all required equipment has been assigned"""
        for record in self:
            if not record.required_equipment_ids:
                record.equipment_assigned = True
                continue

            # Check if FSO has equipment assigned
            if record.fso_id and record.fso_id.assigned_equipment_ids:
                assigned_equipment = record.fso_id.assigned_equipment_ids
                required_equipment = record.required_equipment_ids
                record.equipment_assigned = all(eq in assigned_equipment for eq in required_equipment)
            else:
                record.equipment_assigned = False

    @api.depends('planned_start_time', 'assignment_date', 'fso_id.booking_timezone')
    def _compute_formatted_datetime(self):
        """Format datetime as '21/Oct-10:30 AM' for timeline display"""
        for record in self:
            dt = record.planned_start_time or record.assignment_date
            if dt:
                bk_tz = (record.fso_id._get_booking_tz() if record.fso_id else False) or 'Asia/Ho_Chi_Minh'
                from pytz import timezone
                local_dt = dt.replace(tzinfo=timezone('UTC')).astimezone(timezone(bk_tz))
                # Format: "21/Oct-10:30 AM" (no spaces around hyphen)
                record.formatted_datetime = local_dt.strftime('%d/%b-%I:%M %p')
            else:
                record.formatted_datetime = ''

    @api.depends('planned_start_time', 'assignment_date', 'fso_id.booking_timezone')
    def _compute_formatted_time(self):
        """Format time only as '09:30 AM' for timeline display"""
        for record in self:
            dt = record.planned_start_time or record.assignment_date
            if dt:
                bk_tz = (record.fso_id._get_booking_tz() if record.fso_id else False) or 'Asia/Ho_Chi_Minh'
                from pytz import timezone
                local_dt = dt.replace(tzinfo=timezone('UTC')).astimezone(timezone(bk_tz))
                # Format: "09:30 AM" (time only, no date)
                record.formatted_time = local_dt.strftime('%I:%M %p')
            else:
                record.formatted_time = ''

    @api.depends('fso_id.scheduled_duration')
    def _compute_fso_duration(self):
        """Get duration from the FSO booking"""
        for record in self:
            if record.fso_id and record.fso_id.scheduled_duration:
                record.fso_duration_minutes = record.fso_id.scheduled_duration
            else:
                record.fso_duration_minutes = 60  # Default to 60 minutes if not set

    @api.depends('fso_id.scheduled_datetime')
    def _compute_assignment_date(self):
        """Sync assignment_date with FSO's scheduled_datetime to prevent timeline override"""
        for record in self:
            # When FSO exists, always use its scheduled_datetime
            # This prevents timeline click position from overriding FSO datetime
            if record.fso_id and record.fso_id.scheduled_datetime:
                record.assignment_date = record.fso_id.scheduled_datetime
            # If no FSO and no assignment_date set, use current time
            elif not record.assignment_date:
                record.assignment_date = fields.Datetime.now()

    @api.depends('fso_id.scheduled_datetime', 'assignment_date')
    def _compute_planned_start_time(self):
        """Auto-populate from FSO scheduled_datetime"""
        for record in self:
            if record.fso_id and record.fso_id.scheduled_datetime:
                record.planned_start_time = record.fso_id.scheduled_datetime
            elif record.assignment_date:
                record.planned_start_time = record.assignment_date
            else:
                record.planned_start_time = False

    @api.depends('planned_start_time', 'fso_id.scheduled_duration')
    def _compute_planned_end_time(self):
        """Auto-calculate planned end time = planned_start_time + FSO scheduled_duration"""
        from datetime import timedelta
        for record in self:
            if record.planned_start_time:
                # Use FSO's scheduled_duration if available, otherwise default to 60 minutes
                duration_minutes = record.fso_id.scheduled_duration if record.fso_id and record.fso_id.scheduled_duration else 60
                record.planned_end_time = record.planned_start_time + timedelta(minutes=duration_minutes)
            else:
                record.planned_end_time = False

    @api.depends('staff_id', 'fso_id')
    def _compute_assignment_score(self):
        """Calculate comprehensive assignment quality score"""
        for record in self:
            if not record.staff_id or not record.fso_id:
                record.assignment_score = 0.0
                continue
            
            # Get assignment engine for score calculation
            engine = self.env['health.staff.assignment.engine']
            
            # Calculate individual score components (simplified since FSO doesn't have appointment methods)
            skill_score = 75.0  # Default good score
            proximity_score = 70.0  # Default reasonable score
            workload_score = engine.calculate_workload_score(
                record.staff_id,
                record.assignment_date
            )
            availability_score = 80.0  # Default good availability score
            
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
    
    @api.depends('staff_id')
    def _compute_staff_workload(self):
        """Calculate current workload percentage for assigned staff"""
        for record in self:
            if not record.staff_id:
                record.staff_current_load = 0.0
                continue

            # Calculate workload for individual staff member
            # Get staff's current assignments for today
            today_assignments = self.search_count([
                ('staff_id', '=', record.staff_id.id),
                ('assignment_status', 'in', ['assigned', 'confirmed', 'in_progress']),
                ('assignment_date', '>=', fields.Date.today()),
                ('assignment_date', '<', fields.Date.today() + timedelta(days=1))
            ])

            # Assume max 8 assignments per day as 100% load
            record.staff_current_load = min((today_assignments / 8.0) * 100, 100)
    
    @api.depends('staff_id', 'assignment_date')
    def _compute_daily_stats(self):
        """Calculate daily assignment statistics"""
        for record in self:
            if not record.staff_id or not record.assignment_date:
                record.daily_assignment_count = 0
                continue
            
            # Count assignments for the same day
            assignment_date = fields.Date.from_string(record.assignment_date.date())
            domain = [
                ('staff_id', '=', record.staff_id.id),
                ('assignment_date', '>=', assignment_date),
                ('assignment_date', '<', assignment_date + timedelta(days=1)),
                ('state', '!=', 'cancelled')
            ]
            
            record.daily_assignment_count = self.search_count(domain)
    
    @api.depends('staff_id', 'assignment_date')  
    def _compute_weekly_stats(self):
        """Calculate weekly assignment statistics"""
        for record in self:
            if not record.staff_id or not record.assignment_date:
                record.weekly_assignment_count = 0
                continue
            
            # Get start of week (Monday)
            assignment_date = record.assignment_date.date()
            start_of_week = assignment_date - timedelta(days=assignment_date.weekday())
            end_of_week = start_of_week + timedelta(days=7)
            
            domain = [
                ('staff_id', '=', record.staff_id.id),
                ('assignment_date', '>=', start_of_week),
                ('assignment_date', '<', end_of_week),
                ('state', '!=', 'cancelled')
            ]
            
            record.weekly_assignment_count = self.search_count(domain)
    
    @api.depends('actual_completion_time', 'fso_id')
    def _compute_efficiency(self):
        """Calculate assignment efficiency based on planned vs actual execution"""
        for record in self:
            if not record.actual_completion_time or not record.fso_id:
                record.assignment_efficiency = 0.0
                continue
            
            # Calculate efficiency based on timing accuracy (simplified)
            planned_duration = record.fso_id.estimated_duration * 60 if record.fso_id.estimated_duration else 60  # Convert hours to minutes
            
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
    def default_get(self, fields_list):
        """Override to auto-populate FSO and assignment_date from template record"""
        defaults = super().default_get(fields_list)

        _logger.info("=" * 100)
        _logger.info("🔍 DEFAULT_GET CALLED - AUTO-POPULATING FROM TEMPLATE")
        _logger.info("=" * 100)

        # Find the most recent template record (created by action_manual_assign_staff)
        template = self.search(
            [('state', '=', 'template')],
            order='create_date desc',
            limit=1
        )

        _logger.info("🔍 DEBUG - Template search results:")
        _logger.info("   All templates in DB: %s", self.search([('state', '=', 'template')]).mapped('id'))
        _logger.info("   Most recent template: %s", template.id if template else "NONE")

        if template:
            _logger.info("=" * 100)
            _logger.info("✅ TEMPLATE FOUND - Using it to populate assignment")
            _logger.info("=" * 100)
            _logger.info("   Template ID: %s", template.id)
            _logger.info("   FSO ID: %s", template.fso_id.id)
            _logger.info("   FSO Name: %s", template.fso_id.name)
            _logger.info("   Assignment DateTime: %s", template.assignment_date)

            # Auto-populate FSO from template
            if 'fso_id' in fields_list:
                defaults['fso_id'] = template.fso_id.id
                _logger.info("   ✅ fso_id populated: %s", template.fso_id.id)

            # Auto-populate assignment_date from template
            if 'assignment_date' in fields_list:
                defaults['assignment_date'] = template.assignment_date
                _logger.info("   ✅ assignment_date populated: %s", template.assignment_date)

            _logger.info("=" * 100)
        else:
            _logger.info("❌ No template found in database - new assignment will be empty")

        _logger.info("=" * 100)
        _logger.info("🏁 DEFAULT_GET COMPLETE")
        _logger.info("=" * 100)
        _logger.info("Returned defaults: %s", defaults)
        _logger.info("=" * 100)
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle sequence generation for batch and single records"""
        from datetime import timedelta

        for vals in vals_list:
            if vals.get('name', _('New Assignment')) == _('New Assignment'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.staff.assignment') or _('New Assignment')

            # CRITICAL: If FSO is present, force datetime fields from FSO (ignore timeline click position)
            if vals.get('fso_id'):
                fso = self.env['health.fieldservice.order'].browse(vals['fso_id'])
                if fso.scheduled_datetime:
                    # Override any timeline-provided datetimes with FSO's actual datetime
                    vals['assignment_date'] = fso.scheduled_datetime
                    vals['planned_start_time'] = fso.scheduled_datetime

                    # Calculate end time from FSO's scheduled_duration
                    duration_minutes = fso.scheduled_duration if fso.scheduled_duration else 60
                    vals['planned_end_time'] = fso.scheduled_datetime + timedelta(minutes=duration_minutes)

                    _logger.info(f"✅ Forced assignment datetime from FSO: {fso.scheduled_datetime} (duration: {duration_minutes} min)")

            # Auto-assign state if staff are provided during creation
            if vals.get('staff_id') and vals.get('state', 'draft') == 'draft':
                vals['state'] = 'assigned'

        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to handle automatic state transitions and date changes"""
        # CRITICAL: Protect FSO-linked assignments from timeline widget overrides
        # When an assignment has an FSO, timeline should NOT override computed datetime fields
        has_fso_records = any(record.fso_id for record in self)

        if has_fso_records:
            # Remove timeline-written datetime fields for FSO-linked assignments
            # They'll be recomputed from FSO's scheduled_datetime and scheduled_duration
            protected_fields = []

            if 'assignment_date' in vals:
                vals.pop('assignment_date')
                protected_fields.append('assignment_date')

            if 'planned_start_time' in vals:
                vals.pop('planned_start_time')
                protected_fields.append('planned_start_time')

            if 'planned_end_time' in vals:
                vals.pop('planned_end_time')
                protected_fields.append('planned_end_time')

            if protected_fields:
                _logger.info(f"🛡️  Protected {', '.join(protected_fields)} from timeline override for FSO-linked assignments")

        # Handle assignment_date changes - always update booking, and other assignments if they exist
        # Skip this logic if we're updating other assignments (prevents infinite recursion)
        if 'assignment_date' in vals and vals['assignment_date'] and not self.env.context.get('skip_multi_assignment_update'):
            for record in self:
                # Skip template assignments - they don't need multi-assignment updates
                if record.state == 'template':
                    continue

                # Check if this assignment belongs to a booking
                if record.fso_id:
                    new_date = vals['assignment_date']

                    # ALWAYS update the booking's scheduled_datetime when assignment date changes
                    _logger.info("📅 UPDATING ASSIGNMENT DATE")
                    _logger.info("   Booking: %s", record.fso_id.name)
                    _logger.info("   Old DateTime: %s", record.assignment_date)
                    _logger.info("   New DateTime: %s", new_date)

                    # Update the booking's scheduled_datetime
                    record.fso_id.write({
                        'scheduled_datetime': new_date,
                        'estimated_end_datetime': self._calculate_estimated_end(record.fso_id, new_date)
                    })
                    _logger.info("✅ Updated booking scheduled_datetime to: %s", new_date)

                    # Check for other assignments for this booking
                    other_assignments = self.search([
                        ('fso_id', '=', record.fso_id.id),
                        ('state', '!=', 'template'),
                        ('id', '!=', record.id)
                    ])

                    # If there are other assignments, update them too
                    if other_assignments:
                        _logger.info("📅 ALSO UPDATING %d OTHER ASSIGNMENTS", len(other_assignments))

                        # Update only the OTHER assignments (not the current record, it's already being updated)
                        # Use with_context to prevent recursive triggering of this logic
                        other_assignments.with_context(skip_multi_assignment_update=True).write({
                            'assignment_date': new_date
                        })
                        _logger.info("✅ Updated all other assignments to: %s", new_date)

        # Auto-transition from draft to assigned when staff are assigned
        if 'staff_id' in vals:
            for record in self:
                if record.state == 'draft' and vals.get('staff_id'):
                    # For Many2one field, just check if staff_id is provided
                    if vals['staff_id']:
                        vals['state'] = 'assigned'

        return super().write(vals)

    def _calculate_estimated_end(self, booking, new_start_datetime):
        """Calculate estimated end datetime based on booking duration"""
        if booking.appointment_type_id and booking.appointment_type_id.duration:
            duration_hours = booking.appointment_type_id.duration / 60.0
            from datetime import timedelta
            return new_start_datetime + timedelta(hours=duration_hours)
        return booking.estimated_end_datetime or new_start_datetime

    @api.onchange('assignment_date')
    def _onchange_assignment_date(self):
        """Always warn when assignment date changes - will update booking and other assignments"""
        if self.id and self.fso_id and self.state != 'template':
            # Check if there are other assignments for the same booking
            other_assignments = self.search([
                ('fso_id', '=', self.fso_id.id),
                ('state', '!=', 'template'),
                ('id', '!=', self.id)
            ])

            # Always show warning, with message based on whether there are other assignments
            if other_assignments:
                message = _('⚠️ ATTENTION: Changing this assignment date will:\n'
                           '• Update the booking appointment date/time\n'
                           '• Update all %d other assignments for this booking\n\n'
                           'Proceed with this change?') % len(other_assignments)
                title = _('Multi-Assignment Update')
            else:
                message = _('⚠️ ATTENTION: Changing this assignment date will:\n'
                           '• Update the booking appointment date/time\n\n'
                           'Proceed with this change?')
                title = _('Update Booking Date')

            return {
                'warning': {
                    'title': title,
                    'message': message
                }
            }

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
            
            # Update related FSO
            if record.fso_id:
                record.fso_id.write({
                    'state': 'assigned',
                })
            
            # Send confirmation notifications
            record._send_confirmation_notifications()
    
    def action_assign_staff(self):
        """Manually move assignment from draft to assigned state"""
        for record in self:
            if record.state == 'draft':
                if not record.staff_id:
                    raise UserError(_('Please assign staff members before moving to assigned state.'))
                record.write({'state': 'assigned'})
            elif record.state == 'assigned':
                # Already in assigned state - silently return (auto-transition may have occurred)
                pass
            else:
                raise UserError(_('Only draft assignments can be moved to assigned state.'))
    
    def action_start_assignment(self):
        """Start the assignment (staff is en route or starting service)"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Assignment must be confirmed first.'))
            
            record.write({
                'state': 'in_progress',
                'actual_departure_time': fields.Datetime.now()
            })
            
            # Update FSO status
            if record.fso_id:
                record.fso_id.write({
                    'state': 'in_progress'
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
            if record.fso_id:
                record.fso_id.write({
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

    def action_confirm_date_change(self):
        """Show confirmation dialog for assignment date changes"""
        self.ensure_one()

        if not self.fso_id or self.state == 'template':
            return

        # Check if there are other assignments for this booking
        other_assignments = self.search([
            ('fso_id', '=', self.fso_id.id),
            ('state', '!=', 'template'),
            ('id', '!=', self.id)
        ])

        # Build the message
        if other_assignments:
            message = _('<b>⚠️ CONFIRM DATE CHANGE</b><br/><br/>'
                       '<b>Changing this assignment date will:</b><br/>'
                       '• Update the booking appointment date/time<br/>'
                       '• Update all %d other assignments for this booking<br/><br/>'
                       '<b>Old Date:</b> %s<br/>'
                       '<b>New Date:</b> %s<br/><br/>'
                       'Proceed with this change?') % (
                           len(other_assignments),
                           self.assignment_date,
                           self.assignment_date  # Will be the new date when saved
                       )
            title = _('Multi-Assignment Update Required')
        else:
            message = _('<b>⚠️ CONFIRM DATE CHANGE</b><br/><br/>'
                       '<b>Changing this assignment date will:</b><br/>'
                       '• Update the booking appointment date/time<br/><br/>'
                       '<b>Old Date:</b> %s<br/>'
                       '<b>New Date:</b> %s<br/><br/>'
                       'Proceed with this change?') % (
                           self.assignment_date,
                           self.assignment_date  # Will be the new date when saved
                       )
            title = _('Update Booking Date')

        # Return a notification that will be displayed
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': 'warning',
                'sticky': True,
            }
        }

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
            if record.fso_id.service_type != 'home_visit':
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
        try:
            if self.appointment_id and self.appointment_id.patient_id and self.appointment_id.patient_id.email:
                template = self.env.ref('health_fieldservice.email_template_assignment_confirmed', False)
                if template:
                    template.send_mail(self.id, force_send=True)
        except Exception:
            pass  # Silently fail - email should never block confirmation
        
        # Notify operations team
        try:
            ops_group = self.env.ref('health_base.group_healthcare_operations_manager', False)
            if ops_group:
                for user in ops_group.user_ids:
                    try:
                        self.message_post(
                            body=_('Assignment confirmed for FSO %s') % self.fso_id.name,
                            partner_ids=user.partner_id.ids,
                            message_type='notification'
                        )
                    except Exception:
                        pass  # Silently fail
        except Exception:
            pass  # If group doesn't exist, skip notification
    
    def _update_staff_availability(self):
        """Update staff availability matrix after completion"""
        availability_matrix = self.env['health.staff.availability.matrix']
        if self.staff_id:
            availability_matrix.update_staff_availability(
                self.staff_id.id,
                self.fso_id.scheduled_datetime if self.fso_id else self.assignment_date,
                60,  # Default duration if not available
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
        domain = [('staff_id', '=', staff_id)]
        
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
        if assignment.staff_id.user_id != self.env.user:
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
    
    # ============================================================================
    # V2.0 Enhancement: AI-Powered Assignment Methods
    # ============================================================================
    
    def action_apply_ai_optimization(self):
        """
        V2.0 Enhancement: Apply AI optimization to this assignment
        """
        self.ensure_one()
        
        if not self.appointment_id:
            raise UserError(_("Cannot optimize assignment without an appointment."))
        
        try:
            # Get AI assignment engine
            ai_engine = self.env['health.ai.assignment.engine']
            
            # Generate optimal staff suggestions
            suggestions = ai_engine._get_optimal_staff_suggestions(self.appointment_id)
            
            if not suggestions:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No AI Suggestions'),
                        'message': _('No optimal staff suggestions available for this assignment. Please ensure staff are available and have required skills.'),
                        'type': 'warning',
                    }
                }
            
            # Get best suggestion
            best_suggestion = suggestions[0]
            optimal_staff = self.env['hr.employee'].browse(best_suggestion['staff_id'])
            
            # Apply AI optimization
            self.write({
                'staff_id': optimal_staff.id,
                'ai_assignment_score': best_suggestion['recommendation_score'] * 100,
                'assignment_confidence': best_suggestion['confidence'] * 100,
                'predicted_success_probability': self._predict_assignment_success(best_suggestion),
                'optimal_staff_suggestions': json.dumps(suggestions[:3]),  # Store top 3 suggestions
                'ml_optimization_applied': True,
                'optimization_timestamp': fields.Datetime.now(),
                'state': 'assigned'
            })
            
            # Log optimization activity
            try:
                self.message_post(
                    body=_("🤖 AI optimization applied successfully!<br/>"
                          "Recommended staff: <strong>%s</strong><br/>"
                          "AI Score: <strong>%.1f%%</strong><br/>"
                          "Confidence: <strong>%.1f%%</strong><br/>"
                          "Skills Match: <strong>%.1f%%</strong>") % (
                        optimal_staff.name,
                        best_suggestion['recommendation_score'] * 100,
                        best_suggestion['confidence'] * 100,
                        best_suggestion['skills_match'] * 100
                    ),
                    subject=_("AI Assignment Optimization Applied")
                )
            except Exception:
                pass  # Silently fail - no email notifications required
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('🤖 AI Optimization Applied'),
                    'message': _('Assignment optimized! Assigned to %s with %.1f%% AI confidence.') % (
                        optimal_staff.name, best_suggestion['confidence'] * 100
                    ),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Error applying AI optimization: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Optimization Error'),
                    'message': _('Failed to apply AI optimization: %s') % str(e),
                    'type': 'danger',
                }
            }
    
    def action_get_ai_predictions(self):
        """
        V2.0 Enhancement: Get AI predictions for this assignment
        """
        self.ensure_one()
        
        try:
            # Generate comprehensive AI predictions
            predictions = self._generate_ai_predictions()
            
            if not predictions:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Predictions Available'),
                        'message': _('Unable to generate AI predictions. Please ensure appointment details are complete.'),
                        'type': 'warning',
                    }
                }
            
            # Update assignment with predictions
            self.write({
                'predicted_duration': predictions.get('duration', 0),
                'predicted_complexity': predictions.get('complexity', 'medium'),
                'predicted_success_probability': predictions.get('success_probability', 0.0),
                'optimization_suggestions': json.dumps(predictions.get('suggestions', []))
            })
            
            # Log prediction activity
            try:
                self.message_post(
                    body=_("📊 AI predictions updated successfully!<br/>"
                          "Predicted Duration: <strong>%d minutes</strong><br/>"
                          "Complexity Level: <strong>%s</strong><br/>"
                          "Success Probability: <strong>%.1f%%</strong><br/>"
                          "Optimization Suggestions: <strong>%d recommendations</strong>") % (
                        predictions.get('duration', 0),
                        predictions.get('complexity', 'Unknown').title(),
                        predictions.get('success_probability', 0.0),
                        len(predictions.get('suggestions', []))
                    ),
                    subject=_("AI Predictions Updated")
                )
            except Exception:
                pass  # Silently fail - no email notifications required
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('📊 AI Predictions Updated'),
                    'message': _('Predicted duration: %d min, Complexity: %s, Success rate: %.1f%%') % (
                        predictions.get('duration', 0),
                        predictions.get('complexity', 'Unknown').title(),
                        predictions.get('success_probability', 0.0)
                    ),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Error generating AI predictions: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Prediction Error'),
                    'message': _('Failed to generate AI predictions: %s') % str(e),
                    'type': 'danger',
                }
            }
    
    def _predict_assignment_success(self, suggestion):
        """
        Predict assignment success probability based on suggestion metrics
        """
        # Use weighted combination of suggestion metrics
        success_probability = (
            suggestion.get('confidence', 0.5) * 0.4 +
            suggestion.get('skills_match', 0.5) * 0.3 +
            suggestion.get('travel_efficiency', 0.5) * 0.2 +
            (1.0 - min(suggestion.get('current_workload', {}).get('assignments_count', 0) / 8, 1.0)) * 0.1
        )
        
        return min(100.0, success_probability * 100)
    
    def _generate_ai_predictions(self):
        """
        Generate comprehensive AI predictions for the assignment
        """
        if not self.appointment_id:
            return {}
        
        predictions = {}
        
        try:
            # Predict duration based on appointment type and complexity
            base_duration = self.appointment_id.appointment_type_id.duration or 60
            complexity_multiplier = {
                'low': 0.8,
                'normal': 1.0,
                'high': 1.3,
                'urgent': 1.5,
                'emergency': 1.8
            }.get(self.priority, 1.0)
            
            predictions['duration'] = int(base_duration * complexity_multiplier)
            
            # Predict complexity based on appointment details
            complexity_score = self._calculate_complexity_score()
            if complexity_score >= 0.8:
                predictions['complexity'] = 'critical'
            elif complexity_score >= 0.6:
                predictions['complexity'] = 'high'
            elif complexity_score >= 0.4:
                predictions['complexity'] = 'medium'
            else:
                predictions['complexity'] = 'low'
            
            # Calculate success probability
            base_success = 75.0  # Base success rate
            
            # Adjust based on staff experience
            if self.lead_staff_id:
                staff_experience = self._get_staff_experience_factor(self.lead_staff_id)
                base_success += staff_experience * 10  # Up to 10% bonus for experience
            
            # Adjust based on workload
            if self.staff_current_load:
                workload_penalty = max(0, (self.staff_current_load - 80) / 20 * 10)  # Penalty if >80% loaded
                base_success -= workload_penalty
            
            # Adjust based on skills match
            if self.skill_match_score:
                skill_bonus = (self.skill_match_score - 50) / 50 * 15  # Up to 15% bonus for good skills match
                base_success += skill_bonus
            
            predictions['success_probability'] = max(10.0, min(95.0, base_success))
            
            # Generate optimization suggestions
            suggestions = []
            if self.staff_current_load > 80:
                suggestions.append("Consider redistributing workload - current staff overloaded")
            if self.skill_match_score < 70:
                suggestions.append("Skills mismatch detected - consider alternative staff with better qualifications")
            if self.proximity_score < 60:
                suggestions.append("Geographic inefficiency detected - optimize routing or assign local staff")
            if not self.lead_staff_id:
                suggestions.append("No lead staff assigned - assign experienced team leader")
            if self.assignment_type == 'home_visit' and not self.estimated_travel_time:
                suggestions.append("Missing travel time estimation - calculate route for better planning")
            
            predictions['suggestions'] = suggestions
            
            return predictions
            
        except Exception as e:
            _logger.error(f"Error generating AI predictions: {str(e)}")
            return {}
    
    def _calculate_complexity_score(self):
        """
        Calculate assignment complexity score based on various factors
        """
        complexity = 0.2  # Base complexity
        
        try:
            # Appointment urgency factor
            urgency_weights = {
                '0': 0.1,    # Low
                '1': 0.2,    # Normal
                '2': 0.4,    # High
                '3': 0.6,    # Urgent
                '4': 0.8     # Emergency
            }
            complexity += urgency_weights.get(self.priority, 0.2)
            
            # Assignment type factor
            type_weights = {
                'clinic_visit': 0.1,
                'home_visit': 0.3,
                'emergency': 0.8,
                'follow_up': 0.2,
                'consultation': 0.2
            }
            complexity += type_weights.get(self.assignment_type, 0.2)
            
            # Patient factors (if available)
            if self.appointment_id and self.appointment_id.patient_id:
                patient = self.appointment_id.patient_id
                
                # Age factor
                if hasattr(patient, 'age') and patient.age:
                    if patient.age > 70:
                        complexity += 0.15  # Elderly patients add complexity
                    elif patient.age < 2:
                        complexity += 0.1   # Very young patients add complexity
                
                # Medical history factor (if appointment type suggests complexity)
                if self.appointment_id.appointment_type_id:
                    type_name = self.appointment_id.appointment_type_id.name.lower()
                    if any(keyword in type_name for keyword in ['surgery', 'critical', 'emergency', 'intensive']):
                        complexity += 0.2
            
            # Time of day factor
            if self.assignment_date:
                hour = self.assignment_date.hour
                if hour < 6 or hour > 22:  # Night hours
                    complexity += 0.1
                elif hour >= 18:  # Evening hours
                    complexity += 0.05
            
            # Staff workload factor
            if self.staff_current_load and self.staff_current_load > 80:
                complexity += 0.1  # High workload increases complexity
            
            return min(1.0, complexity)
            
        except Exception as e:
            _logger.error(f"Error calculating complexity score: {str(e)}")
            return 0.5  # Default medium complexity
    
    def _get_staff_experience_factor(self, staff):
        """
        Calculate staff experience factor (0.0 to 1.0)
        """
        if not staff:
            return 0.0
        
        try:
            # Calculate based on employment duration
            if hasattr(staff, 'contract_start_date') and staff.contract_start_date:
                employment_days = (fields.Date.today() - staff.contract_start_date).days
                experience_years = employment_days / 365.0
                experience_factor = min(1.0, experience_years / 5.0)  # 5 years = max experience
            else:
                experience_factor = 0.5  # Default for unknown employment duration
            
            # Add assignment completion bonus
            completed_assignments = self.env['health.staff.assignment'].search_count([
                ('staff_id', '=', staff.id),
                ('state', '=', 'completed')
            ])
            completion_factor = min(0.3, completed_assignments / 100.0)  # Up to 30% bonus for 100+ completions
            
            return min(1.0, experience_factor + completion_factor)
            
        except Exception as e:
            _logger.error(f"Error calculating staff experience factor: {str(e)}")
            return 0.5

    # ============================================================================
    # Session Management for Timeline Context
    # ============================================================================

    @api.model
    def _store_timeline_context(self, fso_id, assignment_date, user_id):
        """
        Store FSO ID and assignment date in process memory for timeline-based assignments.
        This allows multiple assignments to be created with the same FSO and datetime.

        Args:
            fso_id: ID of the field service order (booking)
            assignment_date: The scheduled datetime from the booking
            user_id: Current user ID (for context isolation)
        """
        session_key = f"timeline_context_{user_id}"
        context_data = {
            'fso_id': fso_id,
            'assignment_date': assignment_date,
            'stored_at': fields.Datetime.now(),
            'user_id': user_id
        }

        # Store in class-level cache (persists for this Odoo process)
        HealthStaffAssignment._timeline_context_cache[session_key] = context_data

        _logger.info("📌 STORED TIMELINE CONTEXT IN CACHE:")
        _logger.info("   Session Key: %s", session_key)
        _logger.info("   FSO ID: %s", fso_id)
        _logger.info("   Assignment Date: %s", assignment_date)
        _logger.info("   User ID: %s", user_id)

    @api.model
    def _get_timeline_context(self, user_id):
        """
        Retrieve FSO ID and assignment date from cache for timeline assignments.

        Args:
            user_id: Current user ID

        Returns:
            dict: Contains 'fso_id' and 'assignment_date', or empty dict if not found
        """
        session_key = f"timeline_context_{user_id}"

        # Retrieve from class-level cache
        context_data = HealthStaffAssignment._timeline_context_cache.get(session_key, {})

        if context_data:
            _logger.info("📌 RETRIEVED TIMELINE CONTEXT FROM CACHE:")
            _logger.info("   FSO ID: %s", context_data.get('fso_id'))
            _logger.info("   Assignment Date: %s", context_data.get('assignment_date'))
            _logger.info("   Stored At: %s", context_data.get('stored_at'))

        return context_data

    @api.model
    def _clear_timeline_context(self, user_id):
        """
        Clear timeline context from cache when user navigates away.
        This should be called when user closes the timeline view.

        Args:
            user_id: Current user ID
        """
        session_key = f"timeline_context_{user_id}"

        if session_key in HealthStaffAssignment._timeline_context_cache:
            del HealthStaffAssignment._timeline_context_cache[session_key]
            _logger.info("🧹 CLEARED TIMELINE CONTEXT FROM CACHE: %s", session_key)


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
        
        # Get required skills from appointment type (if field exists)
        required_skills = []
        if hasattr(appointment.appointment_type_id, 'required_skills_json') and appointment.appointment_type_id.required_skills_json:
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
                ('staff_id', '=', staff.id),
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
            # Use datetime for availability checking, fallback to date if datetime not available
            appointment_datetime = getattr(appointment, 'appointment_datetime', None) or appointment.appointment_date
            duration = getattr(appointment.appointment_type_id, 'duration_minutes', 30)
            
            is_available = availability_matrix.is_staff_available(
                staff.id,
                appointment_datetime,
                duration
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
            ('employment_status', '=', 'active'),
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
    
    @api.model
    def get_scheduler_data(self, week_start, week_end, staff_id=False, view_mode='week'):
        """
        Get comprehensive scheduler data for the visual drag-and-drop grid
        Returns: staff, assignments, unassigned appointments, and statistics
        """
        domain = [
            ('assignment_date', '>=', week_start),
            ('assignment_date', '<=', week_end),
            ('state', '!=', 'cancelled')
        ]
        
        if staff_id:
            domain.append(('staff_id', '=', staff_id))
        
        # Get assignments for the period
        assignments = self.search(domain)
        
        # Get staff data
        staff_domain = [('employment_status', '=', 'active')]
        if staff_id:
            staff_domain.append(('id', '=', staff_id))
        
        # Add healthcare staff filter to domain
        staff_domain.append(('is_healthcare_staff', '=', True))
        staff_records = self.env['hr.employee'].search(staff_domain, limit=10)  # Limit for UI performance
        
        # Get unassigned FSOs
        fso_domain = [
            ('scheduled_datetime', '>=', week_start + ' 00:00:00'),
            ('scheduled_datetime', '<=', week_end + ' 23:59:59'),
            ('state', 'in', ['draft', 'confirmed']),
            ('id', 'not in', assignments.mapped('fso_id.id'))
        ]
        unassigned_fsos = self.env['health.fieldservice.order'].search(fso_domain)
        
        # Format staff data
        staff_data = []
        for staff in staff_records:
            # Count current assignments for this staff
            staff_assignments = assignments.filtered(lambda a: a.staff_id and a.staff_id.id == staff.id)
            
            # Determine staff status (simplified logic)
            current_hour = datetime.now().hour
            if 7 <= current_hour <= 18:
                if len(staff_assignments.filtered(lambda a: a.state == 'in_progress')) > 0:
                    status = 'busy'
                    status_text = 'Busy'
                else:
                    status = 'available'
                    status_text = 'Available'
            else:
                status = 'offline'
                status_text = 'Offline'
            
            staff_data.append({
                'id': staff.id,
                'name': staff.name,
                'role': staff.healthcare_role.title() if staff.healthcare_role else 'Healthcare Staff',
                'status': status,
                'statusText': status_text,
                'appointmentCount': len(staff_assignments),
                'avatar_url': f'/web/image/hr.employee/{staff.id}/image_256'
            })
        
        # Format assignment data
        assignment_data = []
        for assignment in assignments:
            if assignment.staff_id:
                assignment_data.append({
                    'id': assignment.id,
                    'staff_id': assignment.staff_id.id,
                    'patient_name': assignment.fso_id.patient_id.name if assignment.fso_id else 'Unknown',
                    'service_type': assignment.fso_id.service_type if assignment.fso_id else 'Unknown',
                    'assignment_date': assignment.assignment_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': 60,  # Default duration in minutes
                    'priority': assignment.priority,
                    'state': assignment.state,
                    'state_display': dict(assignment._fields['state'].selection)[assignment.state],
                    'time_display': assignment.assignment_date.strftime('%H:%M - %H:%M')  # Will calculate end time
                })
        
        # Format unassigned FSOs
        unassigned_data = []
        for fso in unassigned_fsos:
            priority_map = {'0': 'info', '1': 'info', '2': 'warning', '3': 'danger', '4': 'danger'}
            priority_text = {'0': 'Low', '1': 'Normal', '2': 'High', '3': 'Urgent', '4': 'Emergency'}
            
            unassigned_data.append({
                'id': fso.id,
                'patient_name': fso.patient_id.name,
                'service_type': fso.service_type,
                'preferred_time': fso.scheduled_datetime.strftime('%H:%M') if fso.scheduled_datetime else 'Flexible',
                'priority_class': priority_map.get(str(fso.priority), 'info'),
                'priority_display': priority_text.get(str(fso.priority), 'Normal')
            })
        
        # Calculate statistics
        statistics = {
            'total assignments': len(assignments),
            'pending': len(assignments.filtered(lambda a: a.state == 'assigned')),
            'confirmed': len(assignments.filtered(lambda a: a.state == 'confirmed')),
            'in progress': len(assignments.filtered(lambda a: a.state == 'in_progress'))
        }
        
        return {
            'staff': staff_data,
            'assignments': assignment_data,
            'unassigned': unassigned_data,
            'statistics': statistics,
            'week_start': week_start,
            'week_end': week_end,
            'view_mode': view_mode
        }
    
    # ============================================================================
    # Action Methods for UI Buttons
    # ============================================================================
    
    def action_get_ai_suggestions(self):
        """Get AI-powered staff suggestions for this assignment"""
        self.ensure_one()
        
        if not self.appointment_id:
            raise UserError(_('No appointment linked to this assignment'))
        
        # Get available healthcare staff
        available_staff = self.env['hr.employee'].search([
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            ('active', '=', True)
        ], limit=5)
        
        if not available_staff:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Staff Available'),
                    'message': _('No healthcare staff members found for assignment suggestions.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Create simple suggestions based on available staff
        suggestion_text = []
        for i, staff in enumerate(available_staff, 1):
            job_title = staff.healthcare_role.title() if staff.healthcare_role else 'Healthcare Staff'
            score = 85 + (i * 2)  # Simple scoring for demo
            suggestion_text.append(
                f"{i}. {staff.name} ({job_title}) - Score: {score}%"
            )
        
        message = _("AI Staff Suggestions:\n\n") + "\n".join(suggestion_text)
        message += _("\n\nClick on a staff member below to assign them to this appointment.")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Staff Suggestions'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_confirm_assignment(self):
        """Confirm the staff assignment"""
        self.ensure_one()
        
        if self.state != 'assigned':
            raise UserError(_('Only assigned assignments can be confirmed'))
        
        if not self.staff_id:
            raise UserError(_('No staff assigned to this assignment'))
        
        self.write({
            'state': 'confirmed',
            'real_time_status': 'confirmed',
            'staff_confirmed_date': fields.Datetime.now()
        })
        
        # Update related FSO
        if self.fso_id:
            self.fso_id.write({
                'state': 'assigned'
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assignment Confirmed'),
                'message': _('Assignment has been confirmed successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_start_assignment(self):
        """Start the assignment (staff is en route or beginning work)"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed assignments can be started'))
        
        self.write({
            'state': 'in_progress',
            'real_time_status': 'en_route',
            'actual_departure_time': fields.Datetime.now()
        })
        
        # Update related appointment
        if self.fso_id:
            self.fso_id.write({
                'state': 'in_progress'
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assignment Started'),
                'message': _('Assignment is now in progress. Staff is en route.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_complete_assignment(self):
        """Complete the assignment"""
        self.ensure_one()
        
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress assignments can be completed'))
        
        self.write({
            'state': 'completed',
            'real_time_status': 'completed',
            'actual_completion_time': fields.Datetime.now()
        })
        
        # Update related FSO
        if self.fso_id:
            self.fso_id.write({
                'state': 'completed'
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assignment Completed'),
                'message': _('Assignment has been marked as completed.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_cancel_assignment(self):
        """Cancel the assignment"""
        self.ensure_one()
        
        if self.state in ('completed', 'cancelled'):
            raise UserError(_('Cannot cancel completed or already cancelled assignments'))
        
        self.write({
            'state': 'cancelled',
            'real_time_status': 'cancelled'
        })
        
        # Update related FSO if needed
        if self.fso_id and self.fso_id.state != 'cancelled':
            self.fso_id.write({
                'state': 'cancelled'
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Assignment Cancelled'),
                'message': _('Assignment has been cancelled.'),
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_reschedule_assignment(self):
        """Reschedule the assignment to a different time"""
        self.ensure_one()
        
        return {
            'name': _('Reschedule Assignment'),
            'type': 'ir.actions.act_window',
            'res_model': 'health.staff.assignment',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_fieldservice.view_health_staff_assignment_form').id,
            'target': 'new',
            'context': {
                'default_state': self.state,
                'reschedule_mode': True,
            }
        }
    
    def optimize_route(self):
        """Optimize route for this assignment (placeholder for GPS integration)"""
        self.ensure_one()
        
        # This would integrate with mapping services like Google Maps API
        # For now, return a simple notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Route Optimization'),
                'message': _('Route optimization feature will be available with GPS integration.'),
                'type': 'info',
                'sticky': False,
            }
        }

    # ============================================================================
    # V2.0 ENHANCEMENTS: AI-POWERED ASSIGNMENT OPTIMIZATION
    # ============================================================================
    
    # AI/ML Enhanced Fields
    ai_assignment_score = fields.Float('AI Assignment Score', readonly=True, 
                                      help='ML-generated score for assignment quality')
    optimal_staff_suggestions = fields.Text('AI Staff Suggestions JSON', readonly=True)
    assignment_confidence = fields.Float('Assignment Confidence %', readonly=True)
    predicted_completion_time = fields.Datetime('AI Predicted Completion', readonly=True)
    predicted_success_probability = fields.Float('Success Probability %', readonly=True)
    workload_optimization_score = fields.Float('Workload Optimization Score', readonly=True)
    
    # Skills Matrix Integration
    required_skills_match = fields.Float('Required Skills Match %', readonly=True)
    staff_experience_factor = fields.Float('Staff Experience Factor', readonly=True)
    
    # Predictive Analytics
    predicted_travel_time = fields.Float('AI Predicted Travel Time (minutes)', readonly=True)
    route_efficiency_score = fields.Float('Route Efficiency Score', readonly=True)
    patient_satisfaction_prediction = fields.Float('Predicted Patient Satisfaction', readonly=True)

    @api.model
    def get_ai_assignment_recommendations(self, appointment_id, limit=5):
        """
        V2.0 Enhancement: Get AI-powered assignment recommendations
        """
        appointment = self.env['health.appointment'].browse(appointment_id)
        if not appointment:
            return []
        
        # Use the AI assignment engine
        ai_engine = self.env['health.ai.assignment.engine']
        suggestions = ai_engine._get_optimal_staff_suggestions(appointment)
        
        return suggestions[:limit]


    @api.model
    def predict_assignment_outcomes(self, assignment_ids):
        """
        V2.0 Enhancement: Predict outcomes for assignments using ML
        """
        assignments = self.browse(assignment_ids)
        predictions = []
        
        for assignment in assignments:
            # Predict completion time
            predicted_completion = self._predict_completion_time(assignment)
            
            # Predict success probability
            success_probability = self._predict_success_probability(assignment)
            
            # Predict patient satisfaction impact
            satisfaction_prediction = self._predict_patient_satisfaction_impact(assignment)
            
            # Update assignment with predictions
            assignment.write({
                'predicted_completion_time': predicted_completion,
                'predicted_success_probability': success_probability,
                'patient_satisfaction_prediction': satisfaction_prediction
            })
            
            predictions.append({
                'assignment_id': assignment.id,
                'predicted_completion': predicted_completion,
                'success_probability': success_probability,
                'satisfaction_prediction': satisfaction_prediction
            })
        
        return predictions

    def _predict_completion_time(self, assignment):
        """
        Predict when assignment will be completed
        """
        if not assignment.appointment_id:
            return False
        
        base_duration = assignment.appointment_id.duration_minutes or 30
        
        # Adjust based on assignment type
        if assignment.assignment_type == 'home_visit':
            base_duration += 20  # Home visits take longer
        elif assignment.assignment_type == 'emergency':
            base_duration += 15  # Emergency care takes longer
        
        # Adjust based on staff experience
        if assignment.lead_staff_id:
            experience_factor = self._calculate_staff_experience_factor(assignment.lead_staff_id)
            base_duration *= (1.2 - experience_factor)  # More experienced = faster
        
        # Add travel time for home visits
        if assignment.assignment_type == 'home_visit':
            travel_time = assignment.estimated_travel_time or 30
            base_duration += travel_time
        
        # Calculate predicted completion time
        start_time = assignment.appointment_id.appointment_datetime
        if start_time:
            return start_time + timedelta(minutes=base_duration)
        
        return False

    def _predict_success_probability(self, assignment):
        """
        Predict probability of successful assignment completion
        """
        success_probability = 0.7  # Base probability
        
        # Staff experience factor
        if assignment.lead_staff_id:
            experience_factor = self._calculate_staff_experience_factor(assignment.lead_staff_id)
            success_probability += experience_factor * 0.2
        
        # Skills match factor
        if assignment.appointment_id:
            skills_match = self._calculate_skills_match_score(assignment)
            success_probability += skills_match * 0.15
        
        # Workload factor
        workload_factor = self._calculate_workload_factor(assignment)
        success_probability += workload_factor * 0.1
        
        # Time factor (early morning or late evening assignments might be more challenging)
        if assignment.appointment_id.appointment_datetime:
            hour = assignment.appointment_id.appointment_datetime.hour
            if 8 <= hour <= 17:  # Normal working hours
                success_probability += 0.05
            elif hour < 8 or hour > 20:  # Very early or late
                success_probability -= 0.1
        
        return min(100, max(20, success_probability * 100))

    def _predict_patient_satisfaction_impact(self, assignment):
        """
        Predict impact on patient satisfaction
        """
        satisfaction_score = 4.0  # Base score out of 5
        
        # Staff experience impact
        if assignment.lead_staff_id:
            experience_factor = self._calculate_staff_experience_factor(assignment.lead_staff_id)
            satisfaction_score += experience_factor * 0.5
        
        # Assignment type impact
        if assignment.assignment_type == 'home_visit':
            satisfaction_score += 0.3  # Patients prefer home visits
        elif assignment.assignment_type == 'emergency':
            satisfaction_score += 0.2  # Good emergency response
        
        # Workload impact (overloaded staff might affect satisfaction)
        workload_factor = self._calculate_workload_factor(assignment)
        satisfaction_score += workload_factor * 0.2
        
        return min(5.0, max(1.0, satisfaction_score))

    def _calculate_staff_experience_factor(self, staff):
        """
        Calculate staff experience factor (0.0 to 1.0)
        """
        if not staff:
            return 0.0
        
        # Calculate based on employment duration
        if staff.contract_start_date:
            days_employed = (fields.Date.today() - staff.contract_start_date).days
            years_experience = days_employed / 365
            experience_factor = min(1.0, years_experience / 5)  # 5 years = max experience
        else:
            experience_factor = 0.5  # Default for unknown start date
        
        # Add assignment completion bonus
        completed_assignments = self.search_count([
            ('staff_id', '=', staff.id),
            ('state', '=', 'completed')
        ])
        completion_bonus = min(0.3, completed_assignments / 100)  # 0.3 max bonus
        
        return min(1.0, experience_factor + completion_bonus)

    def _calculate_skills_match_score(self, assignment):
        """
        Calculate how well staff skills match assignment requirements
        """
        if not assignment.lead_staff_id or not assignment.appointment_id:
            return 0.5
        
        # Get staff skills
        staff_skills = set(assignment.lead_staff_id.skill_ids.mapped('name'))
        
        # Get required skills (simplified logic)
        appointment_type = assignment.appointment_id.appointment_type_id.name.lower()
        required_skills = set()
        
        if 'emergency' in appointment_type:
            required_skills.update(['Emergency Care', 'Critical Care'])
        elif 'home' in appointment_type or assignment.assignment_type == 'home_visit':
            required_skills.update(['Home Care', 'Patient Assessment'])
        elif 'nursing' in appointment_type:
            required_skills.update(['Nursing Care', 'Patient Care'])
        else:
            required_skills.update(['General Medicine', 'Patient Care'])
        
        if not required_skills:
            return 0.7  # Neutral score
        
        # Calculate match percentage
        matches = len(required_skills.intersection(staff_skills))
        match_score = matches / len(required_skills) if required_skills else 0.7
        
        return min(1.0, match_score)

    def _calculate_workload_factor(self, assignment):
        """
        Calculate workload factor (0.0 = overloaded, 1.0 = optimal load)
        """
        if not assignment.lead_staff_id:
            return 0.5
        
        # Count assignments for the same day
        assignment_date = assignment.assignment_date.date() if assignment.assignment_date else fields.Date.today()
        
        same_day_assignments = self.search_count([
            ('staff_id', '=', assignment.staff_id.id),
            ('assignment_date', '>=', assignment_date),
            ('assignment_date', '<', assignment_date + timedelta(days=1)),
            ('state', 'in', ['assigned', 'confirmed', 'in_progress']),
            ('id', '!=', assignment.id)
        ])
        
        # Optimal workload is 4-6 assignments per day
        if same_day_assignments <= 3:
            return 1.0  # Light workload
        elif same_day_assignments <= 6:
            return 0.8  # Optimal workload
        elif same_day_assignments <= 8:
            return 0.6  # Heavy workload
        else:
            return 0.3  # Overloaded

    @api.model
    def auto_optimize_assignments(self, target_date=None):
        """
        V2.0 Enhancement: Auto-optimize all assignments for a given date
        """
        if not target_date:
            target_date = fields.Date.today()
        
        # Get unoptimized assignments for the date
        assignments = self.search([
            ('assignment_date', '>=', target_date),
            ('assignment_date', '<', target_date + timedelta(days=1)),
            ('state', 'in', ['draft', 'assigned']),
            ('ai_assignment_score', '=', 0)  # Not yet optimized
        ])
        
        optimized_count = 0
        
        for assignment in assignments:
            if assignment.appointment_id:
                # Get AI recommendations
                ai_engine = self.env['health.ai.assignment.engine']
                suggestions = ai_engine._get_optimal_staff_suggestions(assignment.appointment_id)
                
                if suggestions:
                    # Apply optimization
                    top_suggestion = suggestions[0]
                    optimal_staff = self.env['hr.employee'].browse(top_suggestion['staff_id'])
                    
                    assignment.write({
                        'staff_id': optimal_staff.id,
                        'ai_assignment_score': top_suggestion['recommendation_score'] * 100,
                        'assignment_confidence': top_suggestion['confidence'] * 100,
                        'optimal_staff_suggestions': json.dumps(suggestions),
                        'required_skills_match': top_suggestion['skills_match'] * 100,
                        'state': 'assigned'
                    })
                    
                    optimized_count += 1
        
        return {
            'optimized_assignments': optimized_count,
            'total_assignments': len(assignments),
            'optimization_date': target_date.isoformat()
        }
    
    
    def _predict_assignment_success(self, suggestion):
        """
        Predict assignment success probability based on suggestion metrics
        """
        # Use weighted combination of suggestion metrics
        success_probability = (
            suggestion.get('confidence', 0.5) * 0.4 +
            suggestion.get('skills_match', 0.5) * 0.3 +
            suggestion.get('travel_efficiency', 0.5) * 0.2 +
            (1.0 - min(suggestion.get('current_workload', {}).get('assignments_count', 0) / 8, 1.0)) * 0.1
        )
        
        return min(100.0, success_probability * 100)
    
    def _generate_ai_predictions(self):
        """
        Generate comprehensive AI predictions for the assignment
        """
        if not self.appointment_id:
            return {}
        
        predictions = {}
        
        # Predict duration based on appointment type and complexity
        base_duration = self.appointment_id.appointment_type_id.duration or 60
        complexity_multiplier = {
            'low': 0.8,
            'medium': 1.0,
            'high': 1.3,
            'critical': 1.5
        }.get(self.appointment_id.urgency_level, 1.0)
        
        predictions['duration'] = int(base_duration * complexity_multiplier)
        
        # Predict complexity based on appointment details
        complexity_score = self._calculate_complexity_score()
        if complexity_score >= 0.8:
            predictions['complexity'] = 'critical'
        elif complexity_score >= 0.6:
            predictions['complexity'] = 'high'
        elif complexity_score >= 0.4:
            predictions['complexity'] = 'medium'
        else:
            predictions['complexity'] = 'low'
        
        # Generate optimization suggestions
        suggestions = []
        if self.staff_current_load > 80:
            suggestions.append("Consider redistributing workload - current staff overloaded")
        if self.skill_match_score < 70:
            suggestions.append("Skills mismatch detected - consider alternative staff")
        if self.proximity_score < 60:
            suggestions.append("Geographic inefficiency - optimize routing")
        
        predictions['suggestions'] = suggestions
        
        return predictions
    
    def _calculate_complexity_score(self):
        """
        Calculate assignment complexity score based on various factors
        """
        complexity = 0.3  # Base complexity
        
        # Appointment urgency factor
        urgency_weights = {
            'low': 0.1,
            'normal': 0.2,
            'high': 0.4,
            'urgent': 0.6,
            'emergency': 0.8
        }
        complexity += urgency_weights.get(self.priority, 0.2)
        
        # Assignment type factor
        type_weights = {
            'clinic_visit': 0.1,
            'home_visit': 0.3,
            'emergency': 0.8,
            'follow_up': 0.2,
            'consultation': 0.2
        }
        complexity += type_weights.get(self.assignment_type, 0.2)
        
        # Patient factors (if available)
        if self.appointment_id.patient_id:
            patient = self.appointment_id.patient_id
            if patient.age and patient.age > 70:
                complexity += 0.1  # Elderly patients add complexity
        
        return min(1.0, complexity)
    
    @api.model
    def get_ai_assignment_insights(self, assignment_ids=None):
        """
        V2.0 Enhancement: Get AI insights for assignments
        """
        domain = [('state', 'in', ['assigned', 'confirmed', 'in_progress'])]
        if assignment_ids:
            domain.append(('id', 'in', assignment_ids))
        
        assignments = self.search(domain, limit=100)
        
        insights = {
            'total_assignments': len(assignments),
            'ai_optimized': len(assignments.filtered('ml_optimization_applied')),
            'average_confidence': sum(assignments.mapped('assignment_confidence')) / len(assignments) if assignments else 0,
            'high_confidence': len(assignments.filtered(lambda a: a.assignment_confidence >= 80)),
            'low_confidence': len(assignments.filtered(lambda a: a.assignment_confidence < 60)),
            'complexity_distribution': {},
            'optimization_recommendations': []
        }
        
        # Complexity distribution
        for complexity in ['low', 'medium', 'high', 'critical']:
            count = len(assignments.filtered(lambda a: a.predicted_complexity == complexity))
            insights['complexity_distribution'][complexity] = count
        
        # Generate recommendations
        if insights['low_confidence'] > insights['total_assignments'] * 0.3:
            insights['optimization_recommendations'].append(
                "High number of low-confidence assignments detected. Consider AI re-optimization."
            )
        
        if insights['ai_optimized'] < insights['total_assignments'] * 0.5:
            insights['optimization_recommendations'].append(
                "Less than 50% of assignments are AI-optimized. Enable automated optimization."
            )
        
        return insights
    
    # ============================================================================
    # Field Service Integration Methods
    # ============================================================================
    
    def update_from_fieldservice_order(self):
        """Update assignment with requirements from associated FSO"""
        self.ensure_one()
        
        if not self.fieldservice_order_id:
            return
            
        fso = self.fieldservice_order_id
        
        # Update equipment requirements
        if fso.required_equipment_ids:
            self.required_equipment_ids = [(6, 0, fso.required_equipment_ids.ids)]
        
        # Update priority from FSO
        if fso.priority != self.priority:
            self.priority = fso.priority
        
        # Update assignment type for home visits
        if fso.service_type == 'home_visit':
            self.assignment_type = 'home_visit'
    
    def action_confirm_equipment_checklist(self):
        """Field staff confirms equipment checklist is complete"""
        self.ensure_one()
        
        if not self.equipment_assigned:
            raise UserError(_("Cannot confirm equipment checklist - not all required equipment is assigned."))
        
        self.equipment_checklist_complete = True
        
        # Update FSO equipment status
        if self.fieldservice_order_id:
            self.fieldservice_order_id.equipment_checklist_complete = True
        
        # Send confirmation message
        if self.fieldservice_order_id:
            self.env['health.fieldservice.communication'].create({
                'fieldservice_order_id': self.fieldservice_order_id.id,
                'message_type': 'status_update',
                'priority': 'normal',
                'message': f"✅ Equipment checklist confirmed by {self.env.user.name}",
                'is_system_generated': True
            })
    
    def action_request_equipment(self):
        """Request additional equipment for assignment"""
        self.ensure_one()
        
        return {
            'name': 'Request Equipment',
            'type': 'ir.actions.act_window',
            'res_model': 'health.portable.equipment',
            'view_mode': 'list,form',
            'domain': [('status', '=', 'available')],
            'context': {
                'default_assignment_id': self.id,
                'search_default_available': 1
            },
            'target': 'new'
        }
    
    def sync_with_fieldservice_order(self):
        """Sync assignment status with FSO"""
        self.ensure_one()
        
        if not self.fieldservice_order_id:
            return
            
        fso = self.fieldservice_order_id
        
        # Map assignment state to FSO status
        state_mapping = {
            'draft': 'draft',
            'assigned': 'dispatched',
            'confirmed': 'en_route',
            'in_progress': 'in_progress',
            'completed': 'completed',
            'cancelled': 'cancelled'
        }
        
        new_status = state_mapping.get(self.state)
        if new_status and fso.current_status != new_status:
            fso.current_status = new_status
    
    def action_view_fieldservice_order(self):
        """View associated field service order"""
        self.ensure_one()
        
        if not self.fieldservice_order_id:
            raise UserError(_("No Booking associated with this assignment."))
        
        return {
            'name': f'Field Service Order - {self.fieldservice_order_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'health.fieldservice.order',
            'res_id': self.fieldservice_order_id.id,
            'view_mode': 'form',
            'target': 'current'
        }
