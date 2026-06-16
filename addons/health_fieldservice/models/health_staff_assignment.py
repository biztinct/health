from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import math
import logging

_logger = logging.getLogger(__name__)


def _selection_labels(record, field_name):
    return dict(record._fields[field_name]._description_selection(record.env))


def _selection_assignment_status(model):
    return [
        ('assigned', model.env._('Assigned')),
        ('confirmed', model.env._('Confirmed')),
        ('en_route', model.env._('En Route')),
        ('arrived', model.env._('Arrived')),
        ('in_progress', model.env._('In Progress')),
        ('completed', model.env._('Completed')),
        ('cancelled', model.env._('Cancelled')),
    ]


def _selection_assignment_state(model):
    return [
        ('template', model.env._('Template')),
        ('draft', model.env._('Draft')),
        ('assigned', model.env._('Assigned')),
        ('confirmed', model.env._('Staff Confirmed')),
        ('in_progress', model.env._('In Progress')),
        ('completed', model.env._('Completed')),
        ('cancelled', model.env._('Cancelled')),
        ('deferred', model.env._('Deferred')),
    ]


def _selection_assignment_priority(model):
    return [
        ('0', model.env._('Low')),
        ('1', model.env._('Normal')),
        ('2', model.env._('High')),
        ('3', model.env._('Urgent')),
        ('4', model.env._('Emergency')),
    ]


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
    patient_code = fields.Char(
        related='fso_id.patient_id.patient_code',
        string='Client Code',
        store=True,
        readonly=True
    )

    # --- Timeline card display helpers (avatar, labels, duration) ---
    patient_initials = fields.Char(
        'Client Initials', compute='_compute_card_avatar', store=True,
        help='First letters of the client name, shown on the timeline card avatar')
    avatar_hue = fields.Char(
        'Avatar Hue', compute='_compute_card_avatar', store=True,
        help='Palette index (0-8) used to color the timeline card avatar')
    state_label = fields.Char('State Label', compute='_compute_card_labels')
    type_label = fields.Char('Type Label', compute='_compute_card_labels')
    formatted_duration = fields.Char(
        'Formatted Duration', compute='_compute_formatted_duration',
        help='Human-friendly duration for the timeline card, e.g. "2h" or "1h 30m"')

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
        # Nurse-only picker (the nurse/lead-staff field). Doctor assignments are
        # created programmatically via the FSO doctor m2m, which bypasses this domain.
        domain=[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'),
                ('is_nurse_role', '=', True)],
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

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Area',
        related='fso_id.catchment_province_id',
        store=True,
        readonly=True,
        help='Catchment area used for filtering and access control'
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
    assignment_status = fields.Selection(
        _selection_assignment_status,
        string='Assignment Status', default='assigned', required=True, tracking=True)
    
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
    
    state = fields.Selection(
        _selection_assignment_state,
        string='Assignment State', default='assigned', tracking=True)

    priority = fields.Selection(
        _selection_assignment_priority,
        string='Priority', default='1', tracking=True)
    
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
        """Format datetime in BOOKING timezone (not user tz) for timeline display."""
        from pytz import timezone, utc
        for record in self:
            dt = record.planned_start_time or record.assignment_date
            if dt:
                bk_tz_name = (record.fso_id.booking_timezone if record.fso_id else False) or 'Asia/Ho_Chi_Minh'
                local_dt = dt.replace(tzinfo=utc).astimezone(timezone(bk_tz_name))
                record.formatted_datetime = local_dt.strftime('%d/%b-%I:%M %p')
            else:
                record.formatted_datetime = ''

    @api.depends('planned_start_time', 'assignment_date', 'fso_id.booking_timezone')
    def _compute_formatted_time(self):
        """Format time in BOOKING timezone (not user tz) for timeline display."""
        from pytz import timezone, utc
        for record in self:
            dt = record.planned_start_time or record.assignment_date
            if dt:
                bk_tz_name = (record.fso_id.booking_timezone if record.fso_id else False) or 'Asia/Ho_Chi_Minh'
                local_dt = dt.replace(tzinfo=utc).astimezone(timezone(bk_tz_name))
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

    @api.depends('patient_name')
    def _compute_card_avatar(self):
        """Initials + a stable palette index for the timeline card avatar."""
        palette_size = 9
        for record in self:
            name = (record.patient_name or '').strip()
            if name:
                parts = name.split()
                initials = parts[0][0] + (parts[1][0] if len(parts) > 1 else '')
                # Cheap deterministic hash so the same client always gets the same color
                h = 0
                for ch in name:
                    h = (h * 31 + ord(ch)) & 0xFFFFFFFF
                record.patient_initials = initials.upper()
                record.avatar_hue = str(h % palette_size)
            else:
                record.patient_initials = '?'
                record.avatar_hue = '0'

    @api.depends('state', 'assignment_type')
    def _compute_card_labels(self):
        """Translated selection labels for the timeline card."""
        state_map = dict(self._fields['state']._description_selection(self.env))
        type_map = dict(self._fields['assignment_type']._description_selection(self.env))
        for record in self:
            record.state_label = state_map.get(record.state, '')
            record.type_label = type_map.get(record.assignment_type, '')

    @api.depends('fso_duration_minutes')
    def _compute_formatted_duration(self):
        """Human-friendly duration, e.g. 120 -> '2h', 90 -> '1h 30m', 45 -> '45m'."""
        for record in self:
            minutes = record.fso_duration_minutes or 0
            if minutes < 60:
                record.formatted_duration = '%dm' % minutes
            else:
                hours, rem = divmod(minutes, 60)
                record.formatted_duration = ('%dh %dm' % (hours, rem)) if rem else ('%dh' % hours)

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

    def _sync_planned_end_time(self):
        """Force planned_end_time = planned_start_time + duration via direct SQL.

        planned_end_time is a stored, readonly=False computed field, so an explicit
        write (e.g. a timeline drag) overrides the computed value and sticks — the
        compute won't re-run unless a dependency changes. For non-FSO assignments
        there's no booking to re-enforce against, so a bad end time (seen historically
        as spans of several days, or even ending before the start) would persist and
        blow up the day-view card width. This keeps end pinned to start + duration.
        """
        for record in self:
            start = record.planned_start_time
            if not start:
                continue
            duration = record.fso_duration_minutes or 60
            correct_end = start + timedelta(minutes=duration)
            if record.planned_end_time != correct_end:
                self.env.cr.execute(
                    "UPDATE health_staff_assignment SET planned_end_time = %s WHERE id = %s",
                    (correct_end, record.id),
                )
                record.invalidate_recordset(['planned_end_time'])
                _logger.info(
                    '🔒 Synced %s planned_end_time to start + %d min', record.name, duration
                )

    @api.constrains('planned_start_time', 'planned_end_time')
    def _check_planned_times_ordered(self):
        """Backstop: an end at or before the start is always corrupt data.

        Normalization in create()/write() keeps end = start + duration, but this
        guards any other ORM write path from persisting an inverted/zero-length span.
        """
        for record in self:
            if (record.planned_start_time and record.planned_end_time
                    and record.planned_end_time <= record.planned_start_time):
                raise ValidationError(_(
                    'Planned end time (%(end)s) must be after the planned start time '
                    '(%(start)s) for assignment %(name)s.',
                    end=record.planned_end_time,
                    start=record.planned_start_time,
                    name=record.name or _('New Assignment'),
                ))

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

        records = super().create(vals_list)

        # POST-CREATE ENFORCEMENT: Force planned times to match FSO scheduled_datetime
        # Belt-and-suspenders: the pre-create override above sets correct vals, but
        # the timeline widget may issue a subsequent write() with click-position values.
        # This enforcement ensures the DB is definitively correct after creation.
        for record in records:
            if record.fso_id and record.fso_id.scheduled_datetime and record.state != 'template':
                correct_start = record.fso_id.scheduled_datetime
                duration = record.fso_id.scheduled_duration or 60
                correct_end = correct_start + timedelta(minutes=duration)
                if (record.planned_start_time != correct_start or
                        record.planned_end_time != correct_end or
                        record.assignment_date != correct_start):
                    self.env.cr.execute("""
                        UPDATE health_staff_assignment
                        SET planned_start_time = %s,
                            planned_end_time = %s,
                            assignment_date = %s
                        WHERE id = %s
                    """, (correct_start, correct_end, correct_start, record.id))
                    record.invalidate_recordset(
                        ['planned_start_time', 'planned_end_time', 'assignment_date']
                    )
                    _logger.info(
                        '🔒 POST-CREATE: Forced assignment %s times to FSO %s datetime %s',
                        record.name, record.fso_id.name, correct_start
                    )
            elif record.state != 'template':
                # Non-FSO assignment: keep end = start + duration even when the
                # timeline create passed a click-position end. See write() above.
                record._sync_planned_end_time()

        # Send push notification for assignments created in 'assigned' state
        for record in records:
            if record.state == 'assigned' and record.staff_id and record.fso_id:
                try:
                    record.fso_id._send_staff_assignment_notification(record.staff_id, record)
                except Exception as e:
                    _logger.warning('Failed to send push notification on assignment create: %s', e)

        return records
    
    def write(self, vals):
        """Override write to handle automatic state transitions and date changes"""
        # CRITICAL: Protect FSO-linked assignments from timeline widget overrides
        # When an assignment has an FSO, timeline should NOT override computed datetime fields
        has_fso_records = any(record.fso_id for record in self)

        if has_fso_records:
            # Force FSO datetime values for FSO-linked assignments instead of
            # allowing timeline widget to set click-position datetimes
            protected_fields = []

            for record in self.filtered(lambda r: r.fso_id and r.fso_id.scheduled_datetime):
                fso = record.fso_id
                duration_minutes = fso.scheduled_duration if fso.scheduled_duration else 60
                fso_end = fso.scheduled_datetime + timedelta(minutes=duration_minutes)

                if 'assignment_date' in vals and vals['assignment_date'] != fso.scheduled_datetime:
                    vals['assignment_date'] = fso.scheduled_datetime
                    if 'assignment_date' not in protected_fields:
                        protected_fields.append('assignment_date')

                if 'planned_start_time' in vals and vals['planned_start_time'] != fso.scheduled_datetime:
                    vals['planned_start_time'] = fso.scheduled_datetime
                    if 'planned_start_time' not in protected_fields:
                        protected_fields.append('planned_start_time')

                if 'planned_end_time' in vals and vals['planned_end_time'] != fso_end:
                    vals['planned_end_time'] = fso_end
                    if 'planned_end_time' not in protected_fields:
                        protected_fields.append('planned_end_time')
                break  # All FSO-linked records share the same FSO datetime

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

        result = super().write(vals)

        # POST-WRITE ENFORCEMENT: Force planned times to match FSO scheduled_datetime
        # The web_timeline widget calls write() AFTER create() to reposition items to the
        # click position, overriding our pre-write protection. This direct SQL update
        # guarantees FSO-linked assignments always have correct times.
        if any(f in vals for f in ('planned_start_time', 'planned_end_time', 'assignment_date')):
            for record in self:
                if record.fso_id and record.fso_id.scheduled_datetime:
                    correct_start = record.fso_id.scheduled_datetime
                    duration = record.fso_id.scheduled_duration or 60
                    correct_end = correct_start + timedelta(minutes=duration)
                    if (record.planned_start_time != correct_start or
                            record.planned_end_time != correct_end or
                            record.assignment_date != correct_start):
                        self.env.cr.execute("""
                            UPDATE health_staff_assignment
                            SET planned_start_time = %s,
                                planned_end_time = %s,
                                assignment_date = %s
                            WHERE id = %s
                        """, (correct_start, correct_end, correct_start, record.id))
                        record.invalidate_recordset(
                            ['planned_start_time', 'planned_end_time', 'assignment_date']
                        )
                        _logger.info(
                            '🔒 POST-WRITE: Forced assignment %s times to FSO %s datetime %s',
                            record.name, record.fso_id.name, correct_start
                        )
                else:
                    # Non-FSO assignments have no booking to enforce against, so a
                    # timeline drag — especially in week/month view where cards are
                    # visually spanned to the full day — can write a bogus
                    # planned_end_time (days off, or even before the start). Keep
                    # end = start + duration so the card width always reflects the
                    # real duration. See _sync_planned_end_time.
                    record._sync_planned_end_time()

        # When assignment state changes to 'confirmed' (nurse accepted via PWA),
        # advance the parent FSO from 'confirmed' (Booked) to 'assigned' state.
        # NOTE: We do NOT advance on 'assigned' (staff just added) - the nurse must confirm first.
        if 'state' in vals and vals['state'] == 'confirmed':
            for record in self:
                if record.fso_id and record.fso_id.state == 'confirmed' and record.staff_id:
                    try:
                        # Find the 'assigned' stage
                        assigned_stage = self.env['health.fieldservice.stage'].search([
                            ('state', '=', 'assigned'),
                            ('active', '=', True)
                        ], order='sequence', limit=1)
                        if assigned_stage:
                            record.fso_id.write({
                                'stage_id': assigned_stage.id,
                                'state': 'assigned',
                            })
                            _logger.info(
                                'Advanced FSO %s from Booked to Assigned (assignment %s state → %s)',
                                record.fso_id.name, record.id, vals['state']
                            )
                    except Exception as e:
                        _logger.warning('Failed to advance FSO state: %s', e)

        return result

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
    # Unified Staff Schedule (timeline overlay + drag validation)
    # ============================================================================

    @api.model
    @api.model
    def _schedule_tz_name(self):
        """Timezone the Unified Staff Schedule grid renders in: the operator's
        FACILITY timezone — never their physical/browser location. Falls back to
        the user's catchment province, then their Odoo tz, then Asia/Ho_Chi_Minh."""
        user = self.env.user
        emp = user.employee_id or self.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1)
        fac = emp.healthcare_facility_id if emp else False
        if fac and fac.timezone:
            return fac.timezone
        if user.catchment_province_id and user.catchment_province_id.timezone:
            return user.catchment_province_id.timezone
        return user.tz or 'Asia/Ho_Chi_Minh'

    @api.model
    def _facility_tz(self, facility_id=None):
        """Timezone of a given facility (the schedule follows the facility filter);
        falls back to the operator's facility tz when none is selected."""
        if facility_id:
            fac = self.env['health.facility'].browse(facility_id).exists()
            if fac and fac.timezone:
                return fac.timezone
        return self._schedule_tz_name()

    def _staff_tz(self, emp):
        """Facility timezone of a staff member (for availability checks)."""
        fac = emp.healthcare_facility_id if emp else False
        if fac and fac.timezone:
            return fac.timezone
        return self._schedule_tz_name()

    @api.model
    def get_schedule_meta(self):
        """Front-end bootstrap for the Staff Schedule: the grid timezone and the
        facility-filter options (defaulting to the operator's own facility)."""
        user = self.env.user
        emp = user.employee_id or self.env['hr.employee'].search(
            [('user_id', '=', user.id)], limit=1)
        default_fac = emp.healthcare_facility_id if emp else False
        facs = self.env['health.facility'].search([], order='name asc')
        default_tz = self._schedule_tz_name()
        return {
            'tz': default_tz,
            'facilities': [
                {'id': f.id, 'name': f.name, 'tz': f.timezone or default_tz}
                for f in facs
            ],
            'default_facility_id': default_fac.id if default_fac else False,
        }

    def _sched_parse_iso(self, value):
        """Parse a JS ISO datetime ('2026-06-13T01:30:00.000Z') to a naive-UTC
        datetime (the same basis as planned_start_time)."""
        if not value:
            return None
        if not isinstance(value, str):
            return value
        v = value.strip().replace('T', ' ').replace('Z', '')
        if '.' in v:
            v = v.split('.')[0]
        if '+' in v[10:]:
            v = v[:10] + v[10:].split('+')[0]
        try:
            return fields.Datetime.from_string(v)
        except Exception:
            return None

    @api.model
    def get_schedule_overlay(self, date_start, date_end, staff_ids=None, facility_id=None):
        """Overlay data for the Unified Staff Schedule timeline (engine A).

        Foreground assignment items are loaded by the timeline view itself; this
        returns everything *around* them, for the visible [date_start, date_end)
        window (ISO strings from the client):
          - 'rows'        : ALL active healthcare staff (ordered) with status +
                            capacity (used/cap/util%) — feeds the row labels &
                            ensures staff with no assignments still get a row.
          - 'backgrounds' : vis.js background segments per staff — off-hours and
                            leave — to shade the non-droppable time. Datetimes are
                            naive-UTC ISO (same basis as planned_start_time).
          - 'unassigned'  : bookings still needing staff, for the side rail.
        Reuses hr.employee._working_intervals_for / _has_leave_on / _get_duty_status.
        """
        import pytz
        from datetime import datetime as _dt, timedelta as _td, time as _time
        tz = pytz.timezone(self._facility_tz(facility_id))

        # Convention: datetimes exchanged with the front-end are LOCAL wall-clock
        # (the basis vis-timeline items end up on). DB queries convert to UTC.
        def to_utc(local_naive):
            return tz.localize(local_naive).astimezone(pytz.utc).replace(tzinfo=None)

        def to_local_str(naive_utc):
            return fields.Datetime.to_string(
                pytz.utc.localize(naive_utc).astimezone(tz).replace(tzinfo=None))

        def off_bg(emp_id, day, h_from, h_to, kind='off'):
            # Emit segment bounds as REAL UTC (the facility-local hour-of-day
            # converted to UTC), so the front-end positions them on the very same
            # basis as the foreground cards (which are stored UTC). vis then renders
            # both through the facility-tz `moment`, keeping shading and cards aligned.
            base = _dt.combine(day, _time(0, 0))
            return {
                'staff_id': emp_id,
                'start': fields.Datetime.to_string(to_utc(base + _td(hours=h_from))),
                'end': fields.Datetime.to_string(to_utc(base + _td(hours=h_to))),
                'kind': kind,
            }

        win_start = self._sched_parse_iso(date_start)   # naive LOCAL wall-clock
        win_end = self._sched_parse_iso(date_end)
        if not win_start or not win_end:
            return {'rows': [], 'backgrounds': [], 'unassigned': []}
        d0 = win_start.date()
        # exclusive end: a window ending exactly at local midnight must not pull
        # in the following day
        d1 = (win_end - _td(seconds=1)).date()
        if d1 < d0:
            d1 = d0
        win_start_utc = to_utc(win_start)
        win_end_utc = to_utc(win_end)

        Emp = self.env['hr.employee']
        if staff_ids:
            staff = Emp.browse(staff_ids).exists()
        else:
            staff_domain = [
                ('is_healthcare_staff', '=', True),
                ('employment_status', '=', 'active'),
            ]
            if facility_id:
                staff_domain.append(('healthcare_facility_id', '=', facility_id))
            staff = Emp.search(staff_domain, order='name asc')

        rows, backgrounds = [], []
        for emp in staff:
            day_asgs = self.search([
                ('staff_id', '=', emp.id),
                ('planned_start_time', '>=', win_start_utc),
                ('planned_start_time', '<', win_end_utc),
                ('state', 'not in', ['cancelled', 'template']),
            ])
            work_hours = 0.0
            day = d0
            while day <= d1:
                if emp._has_leave_on(day):
                    backgrounds.append(off_bg(emp.id, day, 0, 24, kind='leave'))
                else:
                    intervals = sorted(emp._working_intervals_for(day.weekday()))
                    if not intervals:
                        backgrounds.append(off_bg(emp.id, day, 0, 24))
                    else:
                        cursor = 0.0
                        for (f, t) in intervals:
                            work_hours += max(0.0, t - f)
                            if f > cursor:
                                backgrounds.append(off_bg(emp.id, day, cursor, f))
                            cursor = max(cursor, t)
                        if cursor < 24.0:
                            backgrounds.append(off_bg(emp.id, day, cursor, 24))
                day += _td(days=1)

            busy = 0.0
            for a in day_asgs:
                if a.planned_start_time and a.planned_end_time:
                    busy += (a.planned_end_time - a.planned_start_time).total_seconds() / 3600.0
            util = round(100 * busy / work_hours) if work_hours else 0
            duty = emp._get_duty_status(day=d0, day_assignments=day_asgs)
            rows.append({
                'id': emp.id,
                'name': emp.name or '',
                'initials': ''.join([p[0].upper() for p in (emp.name or 'U').split()[:2]]),
                'color': emp.color or 0,
                'facility': emp.healthcare_facility_id.name if emp.healthcare_facility_id else '',
                'role': emp.access_role_display or '',
                'status': duty['code'],
                'status_label': duty['label'],
                'used': len(day_asgs),
                'cap': emp.max_daily_assignments or 0,
                'util_pct': min(util, 999),
            })

        unassigned = []
        FSO = self.env['health.fieldservice.order']
        fso_domain = [
            ('scheduled_datetime', '>=', win_start_utc),
            ('scheduled_datetime', '<', win_end_utc),
            ('state', 'not in', ['cancelled', 'rejected', 'completed', 'closed']),
        ]
        if facility_id:
            fso_domain.append(('facility_id', '=', facility_id))
        fsos = FSO.search(fso_domain, order='scheduled_datetime asc', limit=80)
        svc_labels = _selection_labels(FSO.browse(), 'service_type') if fsos else {}
        for fso in fsos:
            has_staff = fso.assignment_ids.filtered(
                lambda a: a.state not in ('cancelled', 'template') and a.staff_id)
            if has_staff:
                continue
            unassigned.append({
                'fso_id': fso.id,
                'patient_name': fso.patient_id.name if fso.patient_id else '',
                'service_label': svc_labels.get(fso.service_type, fso.service_type or ''),
                'duration_min': fso.scheduled_duration or 60,
                'facility': fso.facility_id.name if fso.facility_id else '',
                'start_iso': to_local_str(fso.scheduled_datetime) if fso.scheduled_datetime else '',
                'start_utc': fields.Datetime.to_string(fso.scheduled_datetime) if fso.scheduled_datetime else '',
            })

        return {'rows': rows, 'backgrounds': backgrounds, 'unassigned': unassigned}

    def _check_emp_slot(self, emp, start_utc, end_utc, exclude_assignment_id=None):
        """Availability of ONE staff member for [start_utc, end_utc) (naive UTC),
        evaluated in that staff's facility timezone. Returns
        {ok, hard, reason, message[, overlap]} where hard=True means off-hours/leave
        (a snap-back) and overlap=True is a soft double-booking."""
        import pytz
        tz = pytz.timezone(self._staff_tz(emp))
        start_local = pytz.utc.localize(start_utc).astimezone(tz).replace(tzinfo=None)
        end_local = pytz.utc.localize(end_utc).astimezone(tz).replace(tzinfo=None)
        day = start_local.date()

        if emp._has_leave_on(day):
            return {'ok': False, 'hard': True, 'reason': 'on_leave',
                    'message': self.env._('%s is on leave that day.') % emp.name}

        intervals = sorted(emp._working_intervals_for(day.weekday()))
        # Merge contiguous/overlapping segments. A resource calendar often lists
        # several attendance lines that touch (e.g. 08:00-12:00 + 12:00-17:00); the
        # staff actually works straight through, so a booking that spans an internal
        # split must NOT be rejected. This mirrors the overlay shading, which merges
        # the same way (so validation and the visible working band always agree).
        merged = []
        for (f, t) in intervals:
            if merged and f <= merged[-1][1] + 1e-6:
                merged[-1] = (merged[-1][0], max(merged[-1][1], t))
            else:
                merged.append((f, t))
        s_h = start_local.hour + start_local.minute / 60.0
        e_h = end_local.hour + end_local.minute / 60.0
        if end_local.date() != day:
            e_h = 24.0
        inside = any(f <= s_h and e_h <= t for (f, t) in merged)
        if not merged or not inside:
            return {'ok': False, 'hard': True, 'reason': 'outside_hours',
                    'message': self.env._("Outside %s's working hours.") % emp.name}

        dom = [('staff_id', '=', emp.id),
               ('state', 'not in', ['cancelled', 'template']),
               ('planned_start_time', '<', end_utc),
               ('planned_end_time', '>', start_utc)]
        if exclude_assignment_id:
            dom.append(('id', '!=', exclude_assignment_id))
        clash = self.search(dom, limit=1)
        if clash:
            return {'ok': True, 'hard': False, 'reason': 'overlap', 'overlap': True,
                    'message': self.env._("Overlaps %(staff)s's booking %(bk)s.",
                                          staff=emp.name, bk=(clash.fso_id.name or ''))}
        return {'ok': True, 'hard': False, 'reason': 'ok'}

    @api.model
    def validate_drop(self, staff_id, start_iso, end_iso, assignment_id=None):
        """Validate a proposed timeline drop for a single staff member.
        Incoming times are REAL UTC (the basis of the timeline items); availability
        is checked in the STAFF's own facility timezone.
        Returns {ok, hard_block, reason, message, overlap}:
          - hard_block True  → outside working hours or on leave → caller snaps back.
          - overlap   True   → overlaps an existing assignment → caller confirms.
        """
        emp = self.env['hr.employee'].browse(staff_id).exists()
        if not emp:
            return {'ok': False, 'hard_block': True, 'reason': 'no_staff',
                    'message': self.env._('Unknown staff member.')}
        start_utc = self._sched_parse_iso(start_iso)
        end_utc = self._sched_parse_iso(end_iso) or (start_utc and start_utc + timedelta(hours=1))
        if not start_utc:
            return {'ok': False, 'hard_block': True, 'reason': 'bad_time',
                    'message': self.env._('Invalid time.')}
        r = self._check_emp_slot(emp, start_utc, end_utc, exclude_assignment_id=assignment_id)
        if r.get('hard'):
            return {'ok': False, 'hard_block': True, 'reason': r['reason'], 'message': r['message']}
        if r.get('overlap'):
            return {'ok': True, 'hard_block': False, 'reason': 'overlap', 'overlap': True,
                    'message': r['message'] + ' ' + self.env._('Assign anyway?')}
        return {'ok': True, 'hard_block': False, 'reason': 'ok'}

    def _effective_reschedule_times(self, fso, new_start_utc, new_end_utc, mode):
        """Day view uses the dropped times verbatim. Week/Month preserve the
        booking's facility-local time-of-day (and current duration) and move only
        the DATE — so a horizontal drag across day columns never changes the time."""
        if mode == 'day' or not fso or not fso.scheduled_datetime:
            return new_start_utc, new_end_utc
        import pytz
        from datetime import datetime as _dt
        tz = pytz.timezone(self._facility_tz(fso.facility_id.id if fso.facility_id else None))
        new_date = pytz.utc.localize(new_start_utc).astimezone(tz).date()
        cur_local = pytz.utc.localize(fso.scheduled_datetime).astimezone(tz)
        dur = fso.scheduled_duration or 60
        eff_local = tz.localize(_dt.combine(new_date, cur_local.time()))
        eff_start = eff_local.astimezone(pytz.utc).replace(tzinfo=None)
        return eff_start, eff_start + timedelta(minutes=dur)

    @api.model
    def migrate_booking_staff_roles(self, dry_run=False, limit=None):
        """Data migration — wired into migrations/19.0.2.3.7/post-migrate.py.

        For every staff member assigned in real bookings, ensure they hold the right
        ACCESS ROLE (Nurse / Doctor) — derived from the deprecated `healthcare_role`
        — creating an internal user (no invitation email) when the staff has none,
        then clearing `healthcare_role`. Idempotent.

        Classification by healthcare_role:
          - doctor / duty_doctor  -> Doctor access role
          - nurse / head_nurse    -> Nurse access role
          - anything else (admin, support, technician, none, ...) -> SKIPPED.

        Returns a summary dict; `created_user_ids` lets the run be reversed.
        Pass dry_run=True to report without writing, limit=N to process a subset.
        """
        Emp = self.env['hr.employee'].sudo()
        Users = self.env['res.users'].sudo()
        Role = self.env['access.role'].sudo()
        nurse_role = Role.search([('name', '=ilike', 'nurse')], limit=1)
        doctor_role = Role.search([('name', '=ilike', 'doctor')], limit=1)
        if not nurse_role or not doctor_role:
            return {'error': 'Nurse and/or Doctor access.role not found'}

        DOCTOR_HC = ('doctor', 'duty_doctor')
        NURSE_HC = ('nurse', 'head_nurse')

        staff = self.sudo().search([
            ('state', 'not in', ['template', 'cancelled']),
            ('staff_id', '!=', False),
        ]).mapped('staff_id')
        if limit:
            staff = staff[:limit]

        summary = {
            'assigned_staff': len(staff), 'nurses_done': 0, 'doctors_done': 0,
            'users_created': 0, 'cleaned': 0, 'skipped': 0, 'already_ok': 0,
            'kept_other_role': 0, 'dry_run': dry_run,
        }
        created_user_ids, would_create, other_role = [], [], []

        for emp in staff:
            hc = emp.healthcare_role
            if hc in DOCTOR_HC:
                target = doctor_role
            elif hc in NURSE_HC:
                target = nurse_role
            else:
                summary['skipped'] += 1
                continue

            user = emp.user_id
            # NEVER overwrite an existing access role. If the user already has ANY
            # role, leave it untouched (matches "only assign if they have no role").
            if user and user.access_role_id:
                if user.access_role_id.id == target.id:
                    summary['already_ok'] += 1
                    if not dry_run and emp.healthcare_role:
                        emp.healthcare_role = False  # correct role already; drop the dup tag
                        summary['cleaned'] += 1
                else:
                    summary['kept_other_role'] += 1
                    other_role.append('%s -> %s' % (emp.name, user.access_role_id.name))
                continue

            # No role yet: assign target (creating an internal user if needed).
            if dry_run:
                if not user:
                    summary['users_created'] += 1
                    would_create.append(emp.name)
                summary['cleaned'] += 1 if emp.healthcare_role else 0
                summary['nurses_done' if target == nurse_role else 'doctors_done'] += 1
                continue

            if not user:
                login = (emp.work_email or '').strip() or ('staff_%d' % emp.id)
                if Users.with_context(active_test=False).search_count([('login', '=', login)]):
                    login = 'staff_%d' % emp.id
                company = emp.company_id or self.env.company
                try:
                    user = Users.with_context(
                        no_reset_password=True, mail_create_nosubscribe=True,
                        mail_create_nolog=True, tracking_disable=True,
                    ).create({
                        'name': emp.name or login,
                        'login': login,
                        'company_id': company.id,
                        'company_ids': [(6, 0, [company.id])],
                        'access_role_id': target.id,
                    })
                except Exception as e:
                    _logger.warning(
                        'migrate_booking_staff_roles: user create failed for %s (%s): %s',
                        emp.name, emp.id, e)
                    continue
                created_user_ids.append(user.id)
                summary['users_created'] += 1
                emp.user_id = user.id
            else:
                user.write({'access_role_id': target.id})
            # keep the role.user_ids denormalisation consistent (onchange does this in the UI)
            if user.id not in target.user_ids.ids:
                target.write({'user_ids': [(4, user.id)]})

            if emp.healthcare_role:
                emp.healthcare_role = False
                summary['cleaned'] += 1
            summary['nurses_done' if target == nurse_role else 'doctors_done'] += 1

        summary['created_user_ids'] = created_user_ids
        if dry_run:
            summary['would_create_sample'] = would_create[:10]
        if other_role:
            summary['kept_other_role_detail'] = other_role
        return summary

    @api.model
    def validate_timeline_change(self, assignment_id, new_start_iso, new_end_iso,
                                 new_staff_id, mode='day'):
        """Validate a drag/resize of an existing assignment. Real-UTC inputs.
        Hard-blocks: dragged staff unavailable; any OTHER assigned staff unavailable
        at the new time; booking already in progress. Returns flags + names so the
        front-end can show the right confirm dialog before applying."""
        a = self.browse(assignment_id).exists()
        if not a:
            return {'ok': False, 'hard_block': True, 'reason': 'no_assignment',
                    'message': self.env._('Unknown assignment.')}
        fso = a.fso_id
        old_staff = a.staff_id
        new_staff = (self.env['hr.employee'].browse(new_staff_id).exists()
                     if new_staff_id else old_staff)
        if not new_staff:
            return {'ok': False, 'hard_block': True, 'reason': 'no_staff',
                    'message': self.env._('Drop on a staff member.')}
        ns = self._sched_parse_iso(new_start_iso)
        ne = self._sched_parse_iso(new_end_iso) or (ns and ns + timedelta(hours=1))
        if not ns:
            return {'ok': False, 'hard_block': True, 'reason': 'bad_time',
                    'message': self.env._('Invalid time.')}
        eff_start, eff_end = self._effective_reschedule_times(fso, ns, ne, mode)

        staff_changed = bool(new_staff_id) and new_staff.id != old_staff.id
        cur_dur = (fso.scheduled_duration or 60) if fso else 0
        new_dur = int(round((eff_end - eff_start).total_seconds() / 60.0))
        time_changed = bool(fso) and bool(fso.scheduled_datetime) and (
            eff_start != fso.scheduled_datetime or new_dur != cur_dur)

        if time_changed and fso:
            started = fso.assignment_ids.filtered(
                lambda x: x.state != 'template'
                and x.assignment_status in ('en_route', 'arrived', 'in_progress', 'completed'))
            if started:
                return {'ok': False, 'hard_block': True, 'reason': 'started',
                        'message': self.env._('This booking is already in progress and '
                                              'cannot be rescheduled here.')}

        if staff_changed:
            r = self._check_emp_slot(new_staff, eff_start, eff_end, exclude_assignment_id=a.id)
            if r.get('hard'):
                return {'ok': False, 'hard_block': True, 'reason': r['reason'],
                        'message': r['message']}

        co_staff_names, conflicts = [], []
        if time_changed and fso:
            for other in fso.assignment_ids.filtered(
                    lambda x: x.state not in ('cancelled', 'template') and x.staff_id):
                emp = new_staff if other.id == a.id else other.staff_id
                if other.id != a.id:
                    co_staff_names.append(other.staff_id.name)
                r = self._check_emp_slot(emp, eff_start, eff_end, exclude_assignment_id=other.id)
                if r.get('hard'):
                    conflicts.append('%s (%s)' % (emp.name, r['message']))
            if conflicts:
                return {'ok': False, 'hard_block': True, 'reason': 'staff_conflict',
                        'message': self.env._('Cannot reschedule — ') + '; '.join(conflicts)}

        import pytz
        tz = pytz.timezone(self._staff_tz(new_staff))
        el = pytz.utc.localize(eff_start).astimezone(tz)
        return {
            'ok': True, 'hard_block': False, 'reason': 'ok',
            'time_changed': time_changed, 'staff_changed': staff_changed,
            'co_staff_names': co_staff_names, 'multi': len(co_staff_names) > 0,
            'new_staff_name': new_staff.name, 'old_staff_name': old_staff.name or '',
            'patient_name': (fso.patient_id.name if fso and fso.patient_id else ''),
            'new_time_label': el.strftime('%H:%M'),
            'new_date_label': el.strftime('%a %d %b'),
        }

    @api.model
    def apply_timeline_change(self, assignment_id, new_start_iso, new_end_iso,
                              new_staff_id, mode='day'):
        """Persist a validated drag/resize. Staff change → reassign + notify new/old;
        time change → write the FSO datetime/duration (cascades to all assignments and
        fires reschedule notifications)."""
        a = self.browse(assignment_id).exists()
        if not a:
            return {'ok': False, 'message': self.env._('Unknown assignment.')}
        fso = a.fso_id
        old_staff = a.staff_id
        new_staff = (self.env['hr.employee'].browse(new_staff_id).exists()
                     if new_staff_id else old_staff)
        ns = self._sched_parse_iso(new_start_iso)
        ne = self._sched_parse_iso(new_end_iso) or (ns and ns + timedelta(hours=1))
        eff_start, eff_end = self._effective_reschedule_times(fso, ns, ne, mode)
        staff_changed = bool(new_staff_id) and new_staff and new_staff.id != old_staff.id
        dur = max(15, int(round((eff_end - eff_start).total_seconds() / 60.0)))
        time_changed = bool(fso) and fso.scheduled_datetime and (
            eff_start != fso.scheduled_datetime or dur != (fso.scheduled_duration or 60))

        if staff_changed:
            a.write({'staff_id': new_staff.id})
            try:
                if fso:
                    fso._send_staff_assignment_notification(new_staff, a)
                    if old_staff:
                        fso._send_staff_cancellation_notification(old_staff)
            except Exception as e:
                _logger.warning('Timeline reassign notification failed: %s', e)

        if time_changed and fso:
            fso.write({'scheduled_datetime': eff_start, 'scheduled_duration': dur})

        return {'ok': True, 'time_changed': time_changed, 'staff_changed': staff_changed}

    @api.model
    def assign_booking(self, fso_id, staff_id):
        """Assign a staff member to an unassigned booking (drag from the side rail).
        The booking keeps its own scheduled date/time — create() forces planned times
        from the FSO — so this only adds the staff link. Availability is validated by
        the caller via validate_drop. Returns {ok, message}."""
        fso = self.env['health.fieldservice.order'].browse(fso_id).exists()
        emp = self.env['hr.employee'].browse(staff_id).exists()
        if not fso or not emp:
            return {'ok': False, 'message': self.env._('Unknown booking or staff member.')}
        dup = self.search([
            ('fso_id', '=', fso_id),
            ('staff_id', '=', staff_id),
            ('state', 'not in', ['cancelled', 'template']),
        ], limit=1)
        if dup:
            return {'ok': False,
                    'message': self.env._('%s is already assigned to this booking.') % emp.name}
        self.create({'fso_id': fso_id, 'staff_id': staff_id})
        return {'ok': True}

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
    
    active = fields.Boolean('Active', default=True)

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
                'role': staff.access_role_display or 'Healthcare Staff',
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
                    'state_display': _selection_labels(assignment, 'state')[assignment.state],
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
            job_title = staff.access_role_display or 'Healthcare Staff'
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
