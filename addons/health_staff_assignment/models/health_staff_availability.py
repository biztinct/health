from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json


class HealthStaffAvailabilityMatrix(models.Model):
    """
    Real-time staff availability matrix for intelligent scheduling
    Tracks capacity, conflicts, and buffer time management
    """
    _name = 'health.staff.availability.matrix'
    _description = 'Staff Availability Matrix'
    _order = 'staff_id, availability_date, start_time'
    
    # ============================================================================
    # Core Availability Fields
    # ============================================================================
    
    staff_id = fields.Many2one(
        'hr.employee',
        string='Staff Member',
        required=True,
        domain=[('is_healthcare_staff', '=', True)],
        ondelete='cascade'
    )
    
    availability_date = fields.Date('Date', required=True, index=True)
    start_time = fields.Float('Start Time', required=True, help='Time in 24-hour format (e.g., 9.5 for 9:30 AM)')
    end_time = fields.Float('End Time', required=True, help='Time in 24-hour format')
    
    # Availability status
    status = fields.Selection([
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('blocked', 'Blocked'),
        ('tentative', 'Tentative'),
        ('break', 'Break/Lunch'),
        ('travel', 'Travel Time'),
        ('buffer', 'Buffer Time')
    ], string='Status', default='available', required=True, index=True)
    
    # ============================================================================
    # Capacity Management
    # ============================================================================
    
    capacity = fields.Integer('Capacity', default=1, help='How many appointments can be handled in this slot')
    booked_count = fields.Integer('Booked Count', default=0, help='Current number of bookings')
    remaining_capacity = fields.Integer('Remaining Capacity', compute='_compute_remaining_capacity', store=True)
    
    # ============================================================================
    # Assignment Details
    # ============================================================================
    
    appointment_id = fields.Many2one(
        'health.appointment',
        string='Related Appointment',
        ondelete='cascade',
        help='Appointment that booked this slot'
    )
    
    assignment_id = fields.Many2one(
        'health.staff.assignment',
        string='Staff Assignment',
        ondelete='cascade'
    )
    
    # ============================================================================
    # Buffer and Conflict Management
    # ============================================================================
    
    buffer_before = fields.Integer('Buffer Before (Minutes)', default=0, help='Required buffer time before')
    buffer_after = fields.Integer('Buffer After (Minutes)', default=0, help='Required buffer time after')
    
    conflict_detected = fields.Boolean('Conflict Detected', compute='_compute_conflicts', store=True)
    conflict_details = fields.Text('Conflict Details', compute='_compute_conflicts', store=True)
    
    # ============================================================================
    # Geographic and Travel Data
    # ============================================================================
    
    location_type = fields.Selection([
        ('clinic', 'Clinic'),
        ('home', 'Home Visit'),
        ('online', 'Telemedicine')
    ], string='Location Type', compute='_compute_location_type', store=True)
    
    travel_time_from_previous = fields.Float(
        'Travel Time from Previous (Hours)',
        help='Travel time from previous appointment location'
    )
    
    travel_time_to_next = fields.Float(
        'Travel Time to Next (Hours)',
        help='Travel time to next appointment location'
    )
    
    # ============================================================================
    # Scheduling Metadata
    # ============================================================================
    
    created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    created_date = fields.Datetime('Created Date', default=fields.Datetime.now)
    
    last_updated = fields.Datetime('Last Updated', default=fields.Datetime.now)
    updated_by = fields.Many2one('res.users', string='Last Updated By')
    
    # Auto-generated fields
    is_past = fields.Boolean('Is Past', compute='_compute_time_status')
    is_today = fields.Boolean('Is Today', compute='_compute_time_status')
    is_future = fields.Boolean('Is Future', compute='_compute_time_status')
    
    # ============================================================================
    # Computed Fields
    # ============================================================================
    
    @api.depends('capacity', 'booked_count')
    def _compute_remaining_capacity(self):
        """Calculate remaining capacity for the time slot"""
        for record in self:
            record.remaining_capacity = max(0, record.capacity - record.booked_count)
    
    @api.depends('start_time', 'end_time', 'availability_date', 'staff_id')
    def _compute_conflicts(self):
        """Detect scheduling conflicts with other appointments"""
        for record in self:
            conflicts = []
            
            if not record.staff_id or not record.availability_date:
                record.conflict_detected = False
                record.conflict_details = ''
                continue
            
            # Find overlapping slots for the same staff member
            overlapping_slots = self.search([
                ('staff_id', '=', record.staff_id.id),
                ('availability_date', '=', record.availability_date),
                ('id', '!=', record.id),
                ('status', 'in', ['booked', 'blocked', 'tentative']),
                '|',
                '&', ('start_time', '<=', record.start_time), ('end_time', '>', record.start_time),
                '&', ('start_time', '<', record.end_time), ('end_time', '>=', record.end_time)
            ])
            
            if overlapping_slots:
                for slot in overlapping_slots:
                    conflicts.append(f"Overlaps with {slot.status} slot from {slot.start_time:.2f} to {slot.end_time:.2f}")
            
            # Check buffer time conflicts
            if record.status == 'booked' and record.buffer_before > 0:
                buffer_start = record.start_time - (record.buffer_before / 60.0)
                buffer_conflicts = self.search([
                    ('staff_id', '=', record.staff_id.id),
                    ('availability_date', '=', record.availability_date),
                    ('id', '!=', record.id),
                    ('status', '=', 'booked'),
                    ('end_time', '>', buffer_start),
                    ('start_time', '<', record.start_time)
                ])
                
                if buffer_conflicts:
                    conflicts.append(f"Insufficient buffer time before appointment")
            
            record.conflict_detected = len(conflicts) > 0
            record.conflict_details = '\n'.join(conflicts) if conflicts else ''
    
    @api.depends('appointment_id')
    def _compute_location_type(self):
        """Determine location type from associated appointment"""
        for record in self:
            if record.appointment_id and record.appointment_id.appointment_type_id:
                record.location_type = record.appointment_id.appointment_type_id.location_type
            else:
                record.location_type = 'clinic'  # Default
    
    @api.depends('availability_date')
    def _compute_time_status(self):
        """Determine if the availability slot is past, present, or future"""
        today = fields.Date.today()
        
        for record in self:
            if not record.availability_date:
                record.is_past = False
                record.is_today = False
                record.is_future = False
                continue
            
            record.is_past = record.availability_date < today
            record.is_today = record.availability_date == today
            record.is_future = record.availability_date > today
    
    # ============================================================================
    # Constraints and Validations
    # ============================================================================
    
    @api.constrains('start_time', 'end_time')
    def _check_time_validity(self):
        """Ensure end time is after start time"""
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError(_('End time must be after start time.'))
            
            if record.start_time < 0 or record.end_time > 24:
                raise ValidationError(_('Time values must be between 0 and 24.'))
    
    @api.constrains('capacity', 'booked_count')
    def _check_capacity(self):
        """Ensure booked count doesn't exceed capacity"""
        for record in self:
            if record.booked_count > record.capacity:
                raise ValidationError(_('Booked count cannot exceed capacity.'))
    
    # ============================================================================
    # Business Logic Methods
    # ============================================================================
    
    @api.model
    def is_staff_available(self, staff_id, appointment_datetime, duration_minutes):
        """
        Check if staff member is available for appointment
        Returns True if available, False if not
        """
        if not staff_id or not appointment_datetime or not duration_minutes:
            return False
        
        # Convert datetime to date and time components
        if hasattr(appointment_datetime, 'date'):
            # It's a datetime object
            appointment_date = appointment_datetime.date()
            appointment_time = appointment_datetime.hour + (appointment_datetime.minute / 60.0)
        else:
            # It's already a date object
            appointment_date = appointment_datetime
            appointment_time = 9.0  # Default to 9 AM if no time specified
        
        end_time = appointment_time + (duration_minutes / 60.0)
        
        # Check for conflicting bookings
        conflicts = self.search([
            ('staff_id', '=', staff_id),
            ('availability_date', '=', appointment_date),
            ('status', 'in', ['booked', 'blocked']),
            '|',
            '&', ('start_time', '<=', appointment_time), ('end_time', '>', appointment_time),
            '&', ('start_time', '<', end_time), ('end_time', '>=', end_time)
        ])
        
        return len(conflicts) == 0
    
    @api.model
    def book_staff_slot(self, staff_id, appointment_datetime, duration_minutes, appointment_id=None, assignment_id=None):
        """
        Book a time slot for staff member
        Creates availability matrix entry with booked status
        """
        if hasattr(appointment_datetime, 'date'):
            # It's a datetime object
            appointment_date = appointment_datetime.date()
            appointment_time = appointment_datetime.hour + (appointment_datetime.minute / 60.0)
        else:
            # It's already a date object
            appointment_date = appointment_datetime
            appointment_time = 9.0  # Default to 9 AM if no time specified
        end_time = appointment_time + (duration_minutes / 60.0)
        
        # Check availability first
        if not self.is_staff_available(staff_id, appointment_datetime, duration_minutes):
            raise UserError(_('Staff member is not available at the requested time.'))
        
        # Create booked slot
        slot_vals = {
            'staff_id': staff_id,
            'availability_date': appointment_date,
            'start_time': appointment_time,
            'end_time': end_time,
            'status': 'booked',
            'capacity': 1,
            'booked_count': 1,
            'appointment_id': appointment_id,
            'assignment_id': assignment_id
        }
        
        # Add buffer times if specified
        if appointment_id:
            appointment = self.env['health.appointment'].browse(appointment_id)
            if appointment.exists():
                apt_type = appointment.appointment_type_id
                slot_vals.update({
                    'buffer_before': apt_type.buffer_time_before or 0,
                    'buffer_after': apt_type.buffer_time_after or 0
                })
        
        slot = self.create(slot_vals)
        
        # Create buffer time slots if needed
        self._create_buffer_slots(slot)
        
        return slot
    
    def _create_buffer_slots(self, main_slot):
        """Create buffer time slots before and after main appointment"""
        buffer_slots = []
        
        # Buffer before
        if main_slot.buffer_before > 0:
            buffer_start = main_slot.start_time - (main_slot.buffer_before / 60.0)
            if buffer_start >= 0:  # Don't go before midnight
                buffer_vals = {
                    'staff_id': main_slot.staff_id.id,
                    'availability_date': main_slot.availability_date,
                    'start_time': buffer_start,
                    'end_time': main_slot.start_time,
                    'status': 'buffer',
                    'appointment_id': main_slot.appointment_id.id if main_slot.appointment_id else None,
                    'assignment_id': main_slot.assignment_id.id if main_slot.assignment_id else None
                }
                buffer_slots.append(self.create(buffer_vals))
        
        # Buffer after
        if main_slot.buffer_after > 0:
            buffer_end = main_slot.end_time + (main_slot.buffer_after / 60.0)
            if buffer_end <= 24:  # Don't go past midnight
                buffer_vals = {
                    'staff_id': main_slot.staff_id.id,
                    'availability_date': main_slot.availability_date,
                    'start_time': main_slot.end_time,
                    'end_time': buffer_end,
                    'status': 'buffer',
                    'appointment_id': main_slot.appointment_id.id if main_slot.appointment_id else None,
                    'assignment_id': main_slot.assignment_id.id if main_slot.assignment_id else None
                }
                buffer_slots.append(self.create(buffer_vals))
        
        return buffer_slots
    
    @api.model
    def update_staff_availability(self, staff_id, appointment_datetime, duration_minutes, status):
        """
        Update staff availability status for a specific time slot
        Used when appointments are cancelled, rescheduled, or completed
        """
        if hasattr(appointment_datetime, 'date'):
            # It's a datetime object
            appointment_date = appointment_datetime.date()
            appointment_time = appointment_datetime.hour + (appointment_datetime.minute / 60.0)
        else:
            # It's already a date object
            appointment_date = appointment_datetime
            appointment_time = 9.0  # Default to 9 AM if no time specified
        end_time = appointment_time + (duration_minutes / 60.0)
        
        # Find existing slots
        existing_slots = self.search([
            ('staff_id', '=', staff_id),
            ('availability_date', '=', appointment_date),
            ('start_time', '>=', appointment_time),
            ('end_time', '<=', end_time)
        ])
        
        if status == 'available':
            # Free up the time - delete booked/buffer slots
            existing_slots.filtered(lambda s: s.status in ['booked', 'buffer']).unlink()
        else:
            # Update existing slots or create new ones
            if existing_slots:
                existing_slots.write({'status': status})
            else:
                # Create new slot with specified status
                self.create({
                    'staff_id': staff_id,
                    'availability_date': appointment_date,
                    'start_time': appointment_time,
                    'end_time': end_time,
                    'status': status
                })
    
    def calculate_buffer_score(self, staff_id, appointment_datetime, duration_minutes):
        """
        Calculate buffer score based on surrounding availability
        Returns score 0-100 (higher is better)
        """
        if hasattr(appointment_datetime, 'date'):
            # It's a datetime object
            appointment_date = appointment_datetime.date()
            appointment_time = appointment_datetime.hour + (appointment_datetime.minute / 60.0)
        else:
            # It's already a date object
            appointment_date = appointment_datetime
            appointment_time = 9.0  # Default to 9 AM if no time specified
        
        # Check availability in 2-hour window around appointment
        window_start = max(0, appointment_time - 2)
        window_end = min(24, appointment_time + (duration_minutes / 60.0) + 2)
        
        # Count available slots in the window
        available_slots = self.search_count([
            ('staff_id', '=', staff_id),
            ('availability_date', '=', appointment_date),
            ('start_time', '>=', window_start),
            ('end_time', '<=', window_end),
            ('status', '=', 'available')
        ])
        
        # Count total possible slots (15-minute intervals)
        total_possible_slots = int((window_end - window_start) * 4)  # 4 slots per hour
        
        if total_possible_slots == 0:
            return 50.0  # Neutral score
        
        # Calculate buffer score
        availability_ratio = available_slots / total_possible_slots
        buffer_score = availability_ratio * 100
        
        return min(buffer_score, 100.0)
    
    # ============================================================================
    # Reporting and Analytics Methods
    # ============================================================================
    
    @api.model
    def get_staff_utilization_report(self, staff_id, date_from, date_to):
        """Get utilization report for staff member"""
        domain = [
            ('staff_id', '=', staff_id),
            ('availability_date', '>=', date_from),
            ('availability_date', '<=', date_to)
        ]
        
        all_slots = self.search(domain)
        booked_slots = all_slots.filtered(lambda s: s.status == 'booked')
        
        total_hours = sum(slot.end_time - slot.start_time for slot in all_slots)
        booked_hours = sum(slot.end_time - slot.start_time for slot in booked_slots)
        
        utilization_rate = (booked_hours / total_hours * 100) if total_hours > 0 else 0
        
        return {
            'staff_id': staff_id,
            'period': f"{date_from} to {date_to}",
            'total_hours': total_hours,
            'booked_hours': booked_hours,
            'utilization_rate': round(utilization_rate, 2),
            'total_appointments': len(booked_slots),
            'conflict_count': len(all_slots.filtered('conflict_detected'))
        }
    
    @api.model
    def get_availability_summary(self, date_from, date_to):
        """Get overall availability summary for date range"""
        domain = [
            ('availability_date', '>=', date_from),
            ('availability_date', '<=', date_to)
        ]
        
        all_slots = self.search(domain)
        
        summary = {
            'total_slots': len(all_slots),
            'available_slots': len(all_slots.filtered(lambda s: s.status == 'available')),
            'booked_slots': len(all_slots.filtered(lambda s: s.status == 'booked')),
            'blocked_slots': len(all_slots.filtered(lambda s: s.status == 'blocked')),
            'conflicts_detected': len(all_slots.filtered('conflict_detected')),
            'staff_count': len(all_slots.mapped('staff_id')),
        }
        
        summary['availability_rate'] = (
            summary['available_slots'] / summary['total_slots'] * 100
            if summary['total_slots'] > 0 else 0
        )
        
        return summary
    
    # ============================================================================
    # Cleanup and Maintenance
    # ============================================================================
    
    @api.model
    def cleanup_past_availability(self, days_to_keep=30):
        """Clean up old availability records to maintain performance"""
        cutoff_date = fields.Date.today() - timedelta(days=days_to_keep)
        
        old_records = self.search([
            ('availability_date', '<', cutoff_date),
            ('status', 'in', ['available', 'buffer'])  # Keep booked records for history
        ])
        
        deleted_count = len(old_records)
        old_records.unlink()
        
        return {
            'deleted_records': deleted_count,
            'cutoff_date': cutoff_date
        }
    
    @api.model
    def generate_default_availability(self, staff_id, date_from, date_to, 
                                    working_hours_start=8.0, working_hours_end=17.0):
        """
        Generate default availability slots for a staff member
        Creates 30-minute intervals during working hours
        """
        current_date = date_from
        created_slots = []
        
        while current_date <= date_to:
            # Skip weekends (optional - can be configured)
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                
                # Generate 30-minute slots
                current_time = working_hours_start
                while current_time < working_hours_end:
                    slot_end = min(current_time + 0.5, working_hours_end)  # 30-minute slots
                    
                    # Check if slot already exists
                    existing = self.search([
                        ('staff_id', '=', staff_id),
                        ('availability_date', '=', current_date),
                        ('start_time', '=', current_time),
                        ('end_time', '=', slot_end)
                    ])
                    
                    if not existing:
                        slot_vals = {
                            'staff_id': staff_id,
                            'availability_date': current_date,
                            'start_time': current_time,
                            'end_time': slot_end,
                            'status': 'available',
                            'capacity': 1
                        }
                        created_slots.append(self.create(slot_vals))
                    
                    current_time = slot_end
            
            current_date += timedelta(days=1)
        
        return created_slots