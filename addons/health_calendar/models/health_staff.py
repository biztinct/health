from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime


class HealthStaff(models.Model):
    """Healthcare Staff Management for VAFHS"""
    _name = 'health.staff'
    _description = 'Healthcare Staff'
    _order = 'staff_type, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Basic Information
    name = fields.Char('Full Name', required=True, tracking=True)
    staff_code = fields.Char('Staff Code', required=True, copy=False, tracking=True,
                            default=lambda self: _('New'))
    user_id = fields.Many2one('res.users', string='User Account', 
                             help='Link to user account for login access')
    partner_id = fields.Many2one('res.partner', string='Contact', 
                                help='Contact information')
    
    # Professional Information
    staff_type = fields.Selection([
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
        ('specialist', 'Specialist'),
        ('therapist', 'Therapist'),
        ('technician', 'Medical Technician'),
        ('administrator', 'Healthcare Administrator'),
        ('other', 'Other')
    ], string='Staff Type', required=True, default='doctor', tracking=True)
    
    # Medical Credentials
    license_number = fields.Char('Medical License Number', tracking=True)
    license_expiry = fields.Date('License Expiry Date', tracking=True)
    qualifications = fields.Text('Qualifications & Certifications')
    specialization_ids = fields.Many2many('health.specialization', 
                                         string='Specializations')
    years_experience = fields.Integer('Years of Experience', default=0)
    
    # Contact Information
    email = fields.Char('Email', related='partner_id.email', store=True)
    mobile = fields.Char('Mobile', related='partner_id.mobile', store=True)
    phone = fields.Char('Phone', related='partner_id.phone', store=True)
    
    # Employment Details
    employee_id = fields.Char('Employee ID')
    hire_date = fields.Date('Hire Date', default=fields.Date.today, tracking=True)
    employment_status = fields.Selection([
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Employment Status', default='active', tracking=True)
    
    # Facility Assignment
    facility_ids = fields.Many2many('health.facility', string='Assigned Facilities',
                                   help='Healthcare facilities where this staff works')
    primary_facility_id = fields.Many2one('health.facility', string='Primary Facility')
    
    # Service Capabilities
    service_type_ids = fields.Many2many('health.service.type', 
                                       string='Qualified Service Types',
                                       help='Types of services this staff can provide')
    
    # Availability Settings
    available_for_clinic = fields.Boolean('Available for Clinic Visits', default=True)
    available_for_home_visits = fields.Boolean('Available for Home Visits', default=False)
    available_for_telemedicine = fields.Boolean('Available for Telemedicine', default=False)
    
    # Working Schedule
    working_hours_monday = fields.Char('Monday Hours', default='09:00-17:00')
    working_hours_tuesday = fields.Char('Tuesday Hours', default='09:00-17:00')
    working_hours_wednesday = fields.Char('Wednesday Hours', default='09:00-17:00')
    working_hours_thursday = fields.Char('Thursday Hours', default='09:00-17:00')
    working_hours_friday = fields.Char('Friday Hours', default='09:00-17:00')
    working_hours_saturday = fields.Char('Saturday Hours', default='09:00-13:00')
    working_hours_sunday = fields.Char('Sunday Hours', default='')
    
    # Booking Settings
    max_appointments_per_day = fields.Integer('Max Appointments Per Day', default=20)
    appointment_duration_default = fields.Integer('Default Appointment Duration (Minutes)', default=30)
    advance_booking_days = fields.Integer('Advance Booking Days', default=30,
                                         help='How many days in advance patients can book with this staff')
    
    # Statistics
    total_appointments = fields.Integer('Total Appointments', compute='_compute_appointment_stats')
    completed_appointments = fields.Integer('Completed Appointments', compute='_compute_appointment_stats')
    patient_rating = fields.Float('Average Patient Rating', compute='_compute_patient_rating')
    
    # Status and Flags
    active = fields.Boolean('Active', default=True, tracking=True)
    is_available_today = fields.Boolean('Available Today', compute='_compute_availability_today')
    
    # Display
    color = fields.Integer('Color Index', default=1, help='Color for calendar display')
    image_1920 = fields.Image('Photo', max_width=1920, max_height=1920)
    image_512 = fields.Image('Photo (512px)', related='image_1920', max_width=512, max_height=512, store=True)
    image_256 = fields.Image('Photo (256px)', related='image_1920', max_width=256, max_height=256, store=True)
    
    _sql_constraints = [
        ('staff_code_uniq', 'unique(staff_code)', 'Staff code must be unique!'),
        ('license_number_uniq', 'unique(license_number)', 'Medical license number must be unique!'),
    ]
    
    @api.model
    def create(self, vals):
        """Generate staff code on creation"""
        if vals.get('staff_code', _('New')) == _('New'):
            vals['staff_code'] = self.env['ir.sequence'].next_by_code('health.staff') or _('New')
        return super().create(vals)
    
    @api.depends('total_appointments', 'completed_appointments')
    def _compute_appointment_stats(self):
        """Calculate appointment statistics"""
        for staff in self:
            # This would be implemented when appointment model is linked
            staff.total_appointments = 0
            staff.completed_appointments = 0
    
    def _compute_patient_rating(self):
        """Calculate average patient rating"""
        for staff in self:
            # This would calculate from patient feedback/reviews
            staff.patient_rating = 0.0
    
    @api.depends('working_hours_monday', 'working_hours_tuesday', 'working_hours_wednesday',
                 'working_hours_thursday', 'working_hours_friday', 'working_hours_saturday', 
                 'working_hours_sunday', 'employment_status')
    def _compute_availability_today(self):
        """Check if staff is available today"""
        today = fields.Date.today().weekday()  # 0=Monday, 6=Sunday
        
        for staff in self:
            if staff.employment_status != 'active':
                staff.is_available_today = False
                continue
                
            # Get today's working hours
            working_hours_fields = [
                'working_hours_monday', 'working_hours_tuesday', 'working_hours_wednesday',
                'working_hours_thursday', 'working_hours_friday', 'working_hours_saturday',
                'working_hours_sunday'
            ]
            
            today_hours = getattr(staff, working_hours_fields[today])
            staff.is_available_today = bool(today_hours and today_hours.strip())
    
    @api.constrains('license_expiry')
    def _check_license_expiry(self):
        """Validate license expiry date"""
        for staff in self:
            if staff.license_expiry and staff.license_expiry < fields.Date.today():
                raise ValidationError(_('Medical license has expired for %s') % staff.name)
    
    @api.constrains('hire_date')
    def _check_hire_date(self):
        """Validate hire date"""
        for staff in self:
            if staff.hire_date and staff.hire_date > fields.Date.today():
                raise ValidationError(_('Hire date cannot be in the future'))
    
    def action_create_user_account(self):
        """Create user account for staff member"""
        if self.user_id:
            raise ValidationError(_('User account already exists for %s') % self.name)
        
        # Create partner if doesn't exist
        if not self.partner_id:
            self.partner_id = self.env['res.partner'].create({
                'name': self.name,
                'email': self.email,
                'mobile': self.mobile,
                'phone': self.phone,
                'is_company': False,
                'customer_rank': 0,
                'supplier_rank': 0,
            })
        
        # Create user account
        user_vals = {
            'name': self.name,
            'login': self.email or f'{self.staff_code}@vafhs.com',
            'partner_id': self.partner_id.id,
            'groups_id': [(6, 0, [self.env.ref('health_calendar.group_health_user').id])],
        }
        
        self.user_id = self.env['res.users'].create(user_vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('User Account Created'),
                'message': _('User account created successfully for %s') % self.name,
                'type': 'success'
            }
        }
    
    def action_view_appointments(self):
        """View appointments assigned to this staff member"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Staff Appointments - %s') % self.name,
            'res_model': 'health.appointment',
            'view_mode': 'calendar,list,form',
            'domain': [('assigned_staff_id', '=', self.id)],
            'context': {'default_assigned_staff_id': self.id},
        }
    
    def action_set_availability(self):
        """Open staff availability configuration"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Set Availability - %s') % self.name,
            'res_model': 'health.staff.availability',
            'view_mode': 'calendar,list,form',
            'domain': [('staff_id', '=', self.id)],
            'context': {'default_staff_id': self.id},
        }
    
    @api.model
    def get_workload_dashboard_data(self, time_range='week', include_assignments=True, include_availability=True):
        """Get workload dashboard data for all staff members"""
        
        # Calculate date range
        today = fields.Date.today()
        if time_range == 'today':
            date_from = date_to = today
        elif time_range == 'week':
            date_from = today - timedelta(days=today.weekday())
            date_to = date_from + timedelta(days=6)
        elif time_range == 'month':
            date_from = today.replace(day=1)
            next_month = date_from + timedelta(days=32)
            date_to = next_month.replace(day=1) - timedelta(days=1)
        elif time_range == 'quarter':
            quarter = (today.month - 1) // 3
            date_from = today.replace(month=quarter * 3 + 1, day=1)
            date_to = (date_from + timedelta(days=93)).replace(day=1) - timedelta(days=1)
        else:
            date_from = date_to = today
        
        # Get active staff members
        staff_members = self.search([
            ('employment_status', '=', 'active')
        ])
        
        staff_data = []
        all_assignments = []
        
        for staff in staff_members:
            # Get staff assignments in the time range
            assignments = []
            if include_assignments:
                assignments = self.env['health.staff.assignment'].search([
                    '|',
                    ('assigned_staff_ids', 'in', [staff.id]),
                    ('lead_staff_id', '=', staff.id),
                    ('assignment_date', '>=', date_from),
                    ('assignment_date', '<=', date_to)
                ])
                
                # Add to all assignments list
                for assignment in assignments:
                    all_assignments.append({
                        'id': assignment.id,
                        'name': assignment.name,
                        'state': assignment.state,
                        'priority': assignment.priority,
                        'assignment_type': assignment.assignment_type,
                        'assignment_date': assignment.assignment_date.isoformat() if assignment.assignment_date else None,
                        'assigned_staff_ids': assignment.assigned_staff_ids.ids,
                        'lead_staff_id': assignment.lead_staff_id.id if assignment.lead_staff_id else None,
                        'appointment_id': assignment.appointment_id.id if assignment.appointment_id else None,
                        'appointment_name': assignment.appointment_id.name if assignment.appointment_id else None,
                        'estimated_duration': getattr(assignment.appointment_id, 'duration_minutes', 60) if assignment.appointment_id else 60,
                    })
            
            # Calculate workload statistics
            total_assignments = len(assignments)
            active_assignments = len(assignments.filtered(lambda a: a.state in ['assigned', 'confirmed', 'in_progress']))
            pending_assignments = len(assignments.filtered(lambda a: a.state in ['draft', 'assigned']))
            completed_today = len(assignments.filtered(lambda a: a.state == 'completed' and a.assignment_date and a.assignment_date.date() == today))
            
            # Calculate workload percentage (simplified)
            # In a full implementation, this would consider working hours, capacity, etc.
            max_daily_capacity = staff.max_appointments_per_day or 8
            if time_range == 'today':
                workload_percentage = (active_assignments / max_daily_capacity) * 100 if max_daily_capacity > 0 else 0
            else:
                # For longer periods, calculate average daily workload
                days_in_range = (date_to - date_from).days + 1
                avg_daily_assignments = total_assignments / days_in_range if days_in_range > 0 else 0
                workload_percentage = (avg_daily_assignments / max_daily_capacity) * 100 if max_daily_capacity > 0 else 0
            
            workload_percentage = min(workload_percentage, 150)  # Cap at 150%
            
            staff_data.append({
                'id': staff.id,
                'name': staff.name,
                'staff_code': staff.staff_code,
                'staff_type': staff.staff_type,
                'employment_status': staff.employment_status,
                'workload_percentage': workload_percentage,
                'active_assignments': active_assignments,
                'pending_assignments': pending_assignments,
                'completed_today': completed_today,
                'total_assignments': total_assignments,
                'max_daily_capacity': max_daily_capacity,
                'email': staff.email,
                'mobile': staff.mobile,
            })
        
        return {
            'staff_members': staff_data,
            'assignments': all_assignments,
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat(),
                'range_type': time_range
            },
            'summary': {
                'total_staff': len(staff_data),
                'available_staff': len([s for s in staff_data if s['workload_percentage'] <= 80]),
                'busy_staff': len([s for s in staff_data if 80 < s['workload_percentage'] <= 95]),
                'overloaded_staff': len([s for s in staff_data if s['workload_percentage'] > 95]),
                'total_assignments': len(all_assignments),
            }
        }
    
    @api.model
    def get_timeline_data(self, date=None, view_mode='week', include_assignments=True):
        """Get timeline data for assignment timeline view"""
        
        if not date:
            date = fields.Date.today()
        else:
            date = fields.Date.from_string(date)
        
        # Calculate date range based on view mode
        if view_mode == 'day':
            date_from = date_to = date
        elif view_mode == 'week':
            # Get start of week (Monday)
            days_since_monday = date.weekday()
            date_from = date - timedelta(days=days_since_monday)
            date_to = date_from + timedelta(days=6)
        elif view_mode == 'month':
            date_from = date.replace(day=1)
            # Get last day of month
            if date.month == 12:
                date_to = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                date_to = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
        else:
            date_from = date_to = date
        
        # Get active staff members
        staff_members = self.search([
            ('employment_status', '=', 'active')
        ])
        
        staff_data = []
        all_assignments = []
        
        for staff in staff_members:
            # Get staff assignments in the date range
            assignments = []
            if include_assignments:
                assignments = self.env['health.staff.assignment'].search([
                    '|',
                    ('assigned_staff_ids', 'in', [staff.id]),
                    ('lead_staff_id', '=', staff.id),
                    ('assignment_date', '>=', date_from),
                    ('assignment_date', '<=', date_to)
                ])
                
                # Add to all assignments list
                for assignment in assignments:
                    # Calculate assignment start/end times
                    assignment_datetime = assignment.assignment_date
                    if hasattr(assignment_datetime, 'date'):
                        assignment_date = assignment_datetime.date()
                    else:
                        assignment_date = assignment_datetime
                    
                    # For timeline, we need proper start and end datetimes
                    if assignment.appointment_id:
                        # Use appointment datetime if available
                        if hasattr(assignment.appointment_id, 'appointment_datetime') and assignment.appointment_id.appointment_datetime:
                            start_datetime = assignment.appointment_id.appointment_datetime
                            duration_minutes = getattr(assignment.appointment_id, 'duration_minutes', 60)
                        else:
                            # Fallback to assignment date with default time (9 AM)
                            start_datetime = datetime.combine(assignment_date, datetime.min.time().replace(hour=9))
                            duration_minutes = 60
                    else:
                        # No appointment - use assignment date with default time
                        start_datetime = datetime.combine(assignment_date, datetime.min.time().replace(hour=9))
                        duration_minutes = 60
                    
                    end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                    
                    all_assignments.append({
                        'id': assignment.id,
                        'name': assignment.name,
                        'state': assignment.state,
                        'priority': assignment.priority,
                        'assignment_type': assignment.assignment_type,
                        'assignment_date': assignment_date.isoformat(),
                        'start_datetime': start_datetime.isoformat() if hasattr(start_datetime, 'isoformat') else str(start_datetime),
                        'end_datetime': end_datetime.isoformat() if hasattr(end_datetime, 'isoformat') else str(end_datetime),
                        'assigned_staff_ids': assignment.assigned_staff_ids.ids,
                        'lead_staff_id': assignment.lead_staff_id.id if assignment.lead_staff_id else None,
                        'appointment_id': assignment.appointment_id.id if assignment.appointment_id else None,
                        'appointment_name': assignment.appointment_id.name if assignment.appointment_id else None,
                        'estimated_duration': duration_minutes,
                    })
            
            # Calculate current workload
            total_assignments = len(assignments)
            active_assignments = len(assignments.filtered(lambda a: a.state in ['assigned', 'confirmed', 'in_progress']))
            
            # Simplified workload calculation
            max_daily_capacity = staff.max_appointments_per_day or 8
            days_in_range = (date_to - date_from).days + 1
            avg_daily_assignments = total_assignments / days_in_range if days_in_range > 0 else 0
            workload_percentage = (avg_daily_assignments / max_daily_capacity) * 100 if max_daily_capacity > 0 else 0
            workload_percentage = min(workload_percentage, 150)  # Cap at 150%
            
            staff_data.append({
                'id': staff.id,
                'name': staff.name,
                'staff_code': staff.staff_code,
                'staff_type': staff.staff_type,
                'employment_status': staff.employment_status,
                'workload_percentage': workload_percentage,
                'active_assignments': active_assignments,
                'total_assignments': total_assignments,
                'max_daily_capacity': max_daily_capacity,
                'email': staff.email,
                'mobile': staff.mobile,
            })
        
        return {
            'staff_members': staff_data,
            'assignments': all_assignments,
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat(),
                'view_mode': view_mode,
                'current_date': date.isoformat()
            },
            'timeline_config': {
                'hour_width': 60,
                'row_height': 80,
                'min_duration': 15,
                'snap_to_grid': 15
            }
        }


class HealthSpecialization(models.Model):
    """Medical Specializations"""
    _name = 'health.specialization'
    _description = 'Medical Specialization'
    _order = 'name'
    
    name = fields.Char('Specialization Name', required=True)
    code = fields.Char('Code', required=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
    
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Specialization code must be unique!'),
    ]


class HealthStaffAvailability(models.Model):
    """Staff Availability Schedule"""
    _name = 'health.staff.availability'
    _description = 'Staff Availability'
    _order = 'date_start desc'
    
    name = fields.Char('Name', compute='_compute_name', store=True)
    staff_id = fields.Many2one('health.staff', string='Staff Member', required=True, ondelete='cascade')
    date_start = fields.Datetime('Start Date & Time', required=True)
    date_end = fields.Datetime('End Date & Time', required=True)
    
    availability_type = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('off', 'Day Off'),
        ('vacation', 'Vacation'),
        ('sick_leave', 'Sick Leave'),
        ('training', 'Training'),
        ('meeting', 'Meeting')
    ], string='Type', required=True, default='available')
    
    facility_id = fields.Many2one('health.facility', string='Facility',
                                 help='Specific facility for this availability period')
    notes = fields.Text('Notes')
    recurring = fields.Boolean('Recurring', default=False)
    recurring_rule = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], string='Recurring Rule')
    recurring_until = fields.Date('Recur Until', help='End date for recurring availability')
    recurring_count = fields.Integer('Number of Occurrences', default=1, help='How many times to repeat')
    
    color = fields.Integer('Color', compute='_compute_color')
    
    @api.depends('staff_id', 'availability_type', 'date_start', 'date_end')
    def _compute_name(self):
        """Compute display name for availability records"""
        for record in self:
            if record.staff_id and record.date_start and record.date_end:
                staff_name = record.staff_id.name or 'Unknown Staff'
                availability_type = dict(record._fields['availability_type'].selection).get(record.availability_type, record.availability_type)
                
                # Format dates
                start_date = record.date_start.strftime('%Y-%m-%d %H:%M') if record.date_start else ''
                end_date = record.date_end.strftime('%Y-%m-%d %H:%M') if record.date_end else ''
                
                record.name = f"{staff_name} - {availability_type} ({start_date} to {end_date})"
            else:
                record.name = 'Staff Availability'
    
    @api.depends('availability_type')
    def _compute_color(self):
        """Set calendar color based on availability type"""
        color_map = {
            'available': 10,  # Green
            'busy': 7,        # Red
            'off': 4,         # Blue
            'vacation': 6,    # Yellow
            'sick_leave': 1,  # Purple
            'training': 9,    # Orange
            'meeting': 8      # Gray
        }
        for record in self:
            record.color = color_map.get(record.availability_type, 1)
    
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Validate date range"""
        for record in self:
            if record.date_end <= record.date_start:
                raise ValidationError(_('End date must be after start date'))
    
    @api.constrains('recurring', 'recurring_until', 'recurring_count')
    def _check_recurring_params(self):
        """Validate recurring parameters"""
        for record in self:
            if record.recurring:
                if not record.recurring_rule:
                    raise ValidationError(_('Recurring rule is required when recurring is enabled'))
                if not record.recurring_until and not record.recurring_count:
                    raise ValidationError(_('Either "Recur Until" date or "Number of Occurrences" must be specified for recurring availability'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create availability records with recurring support"""
        records = super().create(vals_list)
        
        # Handle recurring for each created record
        for record in records:
            if record.recurring and record.recurring_rule:
                self._create_recurring_records(record, record._get_vals_dict())
        
        return records
    
    def _get_vals_dict(self):
        """Get record values as dictionary for recurring creation"""
        return {
            'staff_id': self.staff_id.id,
            'availability_type': self.availability_type,
            'facility_id': self.facility_id.id if self.facility_id else False,
            'notes': self.notes or '',
            'recurring': self.recurring,
            'recurring_rule': self.recurring_rule,
            'recurring_until': self.recurring_until,
            'recurring_count': self.recurring_count,
        }
    
    def write(self, vals):
        """Update availability records"""
        result = super().write(vals)
        
        # If recurring settings changed, recreate recurring records
        if any(key in vals for key in ['recurring', 'recurring_rule', 'recurring_until', 'recurring_count']):
            for record in self:
                if record.recurring and record.recurring_rule:
                    # Remove existing recurring records (those created by this record)
                    self._remove_recurring_records(record)
                    # Create new recurring records
                    self._create_recurring_records(record, vals)
        
        return result
    
    def _create_recurring_records(self, base_record, vals):
        """Create recurring availability records"""
        if not base_record.recurring or not base_record.recurring_rule:
            return
        
        recurring_rule = base_record.recurring_rule
        recurring_until = base_record.recurring_until
        recurring_count = base_record.recurring_count or 10  # Default to 10 if not specified
        
        # Calculate duration
        duration = base_record.date_end - base_record.date_start
        
        created_count = 0
        current_start = base_record.date_start
        
        while created_count < recurring_count:
            # Calculate next occurrence
            if recurring_rule == 'daily':
                current_start = current_start + timedelta(days=1)
            elif recurring_rule == 'weekly':
                current_start = current_start + timedelta(weeks=1)
            elif recurring_rule == 'monthly':
                # Add one month (approximate)
                if current_start.month == 12:
                    current_start = current_start.replace(year=current_start.year + 1, month=1)
                else:
                    current_start = current_start.replace(month=current_start.month + 1)
            
            # Check if we've exceeded the until date BEFORE creating the record
            if recurring_until and current_start.date() > recurring_until:
                break
            
            # If recurring_until is set, ignore recurring_count limit
            if recurring_until:
                recurring_count = 1000  # Set high limit to rely on date check
            
            # Create the recurring record
            recurring_vals = {
                'staff_id': base_record.staff_id.id,
                'date_start': current_start,
                'date_end': current_start + duration,
                'availability_type': base_record.availability_type,
                'facility_id': base_record.facility_id.id if base_record.facility_id else False,
                'notes': base_record.notes or '',
                'recurring': False,  # Don't make recurring records themselves recurring
                'color': base_record.color,
            }
            
            # Create without triggering recursion
            super(HealthStaffAvailability, self).create([recurring_vals])
            created_count += 1
    
    def _remove_recurring_records(self, base_record):
        """Remove recurring records created by this base record"""
        # This is a simplified version - in a full implementation,
        # you'd track which records were created by which base record
        # For now, we won't remove existing records to avoid data loss
        pass