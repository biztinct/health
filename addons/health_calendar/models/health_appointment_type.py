from odoo import models, fields, api, _


class ServiceType(models.Model):
    """Extend base service type with appointment booking functionality"""
    _inherit = 'health.service.type'
    
    # UI and Display
    icon = fields.Char('Icon', help='Font Awesome icon class (e.g., fa-stethoscope)')
    
    # Location type for appointments
    location_type = fields.Selection([
        ('clinic', 'Clinic Visit'),
        ('home', 'Home Visit'),
        ('online', 'Telemedicine')
    ], string='Primary Location Type', compute='_compute_location_type', store=True)
    
    # Appointment-specific booking configuration
    allow_online_booking = fields.Boolean('Allow Online Booking', default=True)
    advance_booking_days = fields.Integer('Advance Booking Days', default=30,
                                         help='How many days in advance can this be booked online')
    min_advance_hours = fields.Integer('Minimum Advance Hours', default=2,
                                      help='Minimum hours in advance required for booking')
    max_concurrent = fields.Integer('Max Concurrent Appointments', default=1,
                                   help='Maximum number of this type that can be scheduled simultaneously')
    
    # Additional scheduling fields
    buffer_time_before = fields.Integer('Buffer Time Before (Minutes)', default=0,
                                       help='Time needed before appointment (prep time)')
    buffer_time_after = fields.Integer('Buffer Time After (Minutes)', default=0,
                                      help='Time needed after appointment (cleanup time)')
    
    # Home visit enhancements (extends base travel settings)
    service_radius_km = fields.Float('Service Radius (KM)', default=0.0,
                                    help='Maximum distance for home visits')
    travel_fee = fields.Float('Travel Fee (VND)', default=0.0,
                             help='Additional fee for home visit travel')
    
    # Telemedicine platform (extends base telemedicine availability)
    platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('meet', 'Google Meet'),
        ('skype', 'Skype'),
        ('zalo', 'Zalo'),
        ('other', 'Other')
    ], string='Telemedicine Platform', help='Platform used for online consultations')
    
    # Booking form customization
    show_symptoms_field = fields.Boolean('Show Symptoms Field', default=True)
    show_urgency_field = fields.Boolean('Show Urgency Field', default=False)
    show_special_requirements = fields.Boolean('Show Special Requirements', default=True)
    required_fields = fields.Text('Required Fields', help='JSON list of required fields for booking')
    
    # Automation settings
    auto_confirm = fields.Boolean('Auto Confirm', default=False,
                                 help='Automatically confirm appointments of this type')
    send_reminder = fields.Boolean('Send Reminder', default=True)
    reminder_hours_before = fields.Integer('Reminder Hours Before', default=24)
    
    # Working schedule (appointment-specific)
    working_days = fields.Selection([
        ('weekdays', 'Weekdays Only'),
        ('weekends', 'Weekends Only'),
        ('all', 'All Days')
    ], string='Available Days', default='all')
    
    working_hours_start = fields.Float('Working Hours Start', default=8.0)
    working_hours_end = fields.Float('Working Hours End', default=17.0)
    
    # Appointment statistics
    appointment_count = fields.Integer('Total Appointments', compute='_compute_appointment_count')
    avg_duration_actual = fields.Float('Average Actual Duration', compute='_compute_avg_duration')
    
    _sql_constraints = [
        ('valid_working_hours', 'check(working_hours_end > working_hours_start)', 
         'End time must be after start time!'),
    ]
    
    @api.depends('available_clinic', 'available_home', 'available_telemedicine')
    def _compute_location_type(self):
        """Determine primary location type based on availability settings"""
        for record in self:
            if record.available_clinic and not record.available_home and not record.available_telemedicine:
                record.location_type = 'clinic'
            elif record.available_home and not record.available_clinic and not record.available_telemedicine:
                record.location_type = 'home'
            elif record.available_telemedicine and not record.available_clinic and not record.available_home:
                record.location_type = 'online'
            elif record.available_clinic:  # Default to clinic if multiple are available
                record.location_type = 'clinic'
            elif record.available_home:
                record.location_type = 'home'
            elif record.available_telemedicine:
                record.location_type = 'online'
            else:
                record.location_type = 'clinic'  # Fallback default
    
    @api.depends('appointment_count')  # Will be implemented when appointment model is linked
    def _compute_appointment_count(self):
        for record in self:
            # This will be implemented with proper domain
            record.appointment_count = 0
    
    def _compute_avg_duration(self):
        for record in self:
            # This will calculate actual average duration from completed appointments
            record.avg_duration_actual = record.duration_minutes
    
    def action_view_appointments(self):
        """View appointments of this type"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Appointments - {self.name}',
            'res_model': 'health.appointment',
            'view_mode': 'calendar,list,form',
            'domain': [('appointment_type_id', '=', self.id)],
            'context': {'default_appointment_type_id': self.id}
        }
    
    @api.model
    def get_available_slots(self, date, facility_id=None):
        """Get available time slots for online booking"""
        # This method will be used by the booking portal
        # Returns available time slots based on:
        # - Working hours
        # - Existing appointments
        # - Staff availability
        # - Facility capacity
        
        slots = []
        if not date:
            return slots
        
        # Basic slot generation (will be enhanced)
        start_hour = int(self.working_hours_start)
        end_hour = int(self.working_hours_end)
        
        for hour in range(start_hour, end_hour):
            for minute in [0, 30]:  # 30-minute intervals
                if hour == end_hour - 1 and minute == 30:
                    break  # Don't exceed end time
                
                time_float = hour + (minute / 60.0)
                slots.append({
                    'time': time_float,
                    'time_str': f'{hour:02d}:{minute:02d}',
                    'available': True,  # Will check actual availability
                })
        
        return slots
    
    def get_booking_form_config(self):
        """Get configuration for online booking form"""
        return {
            'name': self.name,
            'description': self.description,
            'duration_minutes': self.duration_minutes,
            'location_type': self.location_type,
            'color': self.color,
            'icon': self.icon,
            'base_price': self.base_price,
            'show_symptoms_field': self.show_symptoms_field,
            'show_urgency_field': self.show_urgency_field,
            'show_special_requirements': self.show_special_requirements,
            'min_advance_hours': self.min_advance_hours,
            'advance_booking_days': self.advance_booking_days,
            'working_hours_start': self.working_hours_start,
            'working_hours_end': self.working_hours_end,
        }