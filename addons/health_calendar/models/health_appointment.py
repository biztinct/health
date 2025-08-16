from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import pytz


class Appointment(models.Model):
    """Advanced Healthcare Appointment Management"""
    _name = 'health.appointment'
    _description = 'Healthcare Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'appointment_date desc, appointment_time desc'
    _rec_name = 'display_name'

    # Basic Information
    name = fields.Char('Appointment Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New Appointment'))
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    # Patient Information
    patient_id = fields.Many2one('res.partner', string='Patient', required=True, tracking=True,
                                domain=[('is_patient', '=', True)],
                                help='Select a patient (contact marked as patient)')
    patient_code = fields.Char('Patient Code', related='patient_id.patient_code', readonly=True)
    patient_phone = fields.Char('Patient Phone', related='patient_id.mobile', readonly=True)
    patient_email = fields.Char('Patient Email', related='patient_id.email', readonly=True)
    
    # Appointment Details
    appointment_type_id = fields.Many2one('health.service.type', string='Appointment Type', 
                                         required=True, tracking=True)
    appointment_date = fields.Date('Appointment Date', required=True, tracking=True)
    appointment_time = fields.Float('Appointment Time', required=True, tracking=True,
                                   help='Time in 24-hour format (e.g., 14.5 for 2:30 PM)')
    appointment_datetime = fields.Datetime('Appointment DateTime', compute='_compute_appointment_datetime', 
                                          store=True, tracking=True)
    duration_minutes = fields.Integer('Duration (Minutes)', related='appointment_type_id.duration_minutes', 
                                     store=True, readonly=True)
    end_datetime = fields.Datetime('End DateTime', compute='_compute_end_datetime', store=True)
    
    # Location & Service
    location_type = fields.Selection(string='Location Type', related='appointment_type_id.location_type', store=True, readonly=True)
    
    facility_id = fields.Many2one('health.facility', string='Healthcare Facility', 
                                 domain="[('active', '=', True)]")
    service_ids = fields.Many2many('health.service.type', string='Services')
    
    # Home Visit Specific
    visit_address = fields.Text('Visit Address', help='Address for home visits')
    travel_time_minutes = fields.Integer('Travel Time (Minutes)', default=0)
    travel_distance_km = fields.Float('Travel Distance (KM)', default=0.0)
    travel_fee = fields.Float('Travel Fee (VND)', default=0.0)
    
    # Staff Assignment
    assigned_staff_ids = fields.Many2many('res.users', string='Assigned Staff',
                                         domain=[('is_healthcare_staff', '=', True)])
    assigned_staff_id = fields.Many2one('res.users', string='Assigned Staff',
                                        domain=[('is_healthcare_staff', '=', True)])
    primary_doctor_id = fields.Many2one('res.users', string='Primary Doctor',
                                       domain=[('staff_type', '=', 'doctor')])
    primary_nurse_id = fields.Many2one('res.users', string='Primary Nurse',
                                      domain=[('staff_type', 'in', ['nurse', 'head_nurse'])])
    
    # Online/Telemedicine
    online_meeting_url = fields.Char('Online Meeting URL', help='Video consultation link')
    
    # Status & Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled')
    ], string='Status', default='draft', tracking=True, required=True)
    
    booking_source = fields.Selection([
        ('portal', 'Patient Portal'),
        ('website', 'Website Booking'),
        ('phone', 'Phone Call'),
        ('walk_in', 'Walk-in'),
        ('staff', 'Staff Created'),
        ('facebook', 'Facebook'),
        ('zalo', 'Zalo')
    ], string='Booking Source', default='staff', tracking=True)
    
    # Booking Information
    booking_date = fields.Datetime('Booking Date', default=fields.Datetime.now, readonly=True)
    booking_user_id = fields.Many2one('res.users', string='Booked By', default=lambda self: self.env.user)
    confirmation_date = fields.Datetime('Confirmation Date', readonly=True)
    confirmed_by_id = fields.Many2one('res.users', string='Confirmed By', readonly=True)
    
    # Patient Requirements & Notes
    symptoms = fields.Text('Symptoms/Reason for Visit')
    patient_notes = fields.Text('Patient Notes')
    special_requirements = fields.Text('Special Requirements')
    urgency_level = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Urgency Level', default='routine', tracking=True)
    
    # Clinical Information
    chief_complaint = fields.Text('Chief Complaint')
    clinical_notes = fields.Text('Clinical Notes')
    diagnosis = fields.Text('Diagnosis')
    treatment_plan = fields.Text('Treatment Plan')
    prescription = fields.Text('Prescription')
    
    # Follow-up
    requires_followup = fields.Boolean('Requires Follow-up', default=False)
    follow_up_required = fields.Boolean('Follow-up Required', default=False)
    followup_date = fields.Date('Follow-up Date')
    followup_notes = fields.Text('Follow-up Notes')
    
    # Communication & Feedback
    reminder_sent = fields.Boolean('Reminder Sent', default=False)
    rating = fields.Selection([
        ('1', '1 - Poor'),
        ('2', '2 - Fair'),
        ('3', '3 - Good'),
        ('4', '4 - Very Good'),
        ('5', '5 - Excellent')
    ], string='Rating')
    feedback = fields.Text('Patient Feedback')
    
    # Financial
    estimated_cost = fields.Float('Estimated Cost (VND)', default=0.0)
    actual_cost = fields.Float('Actual Cost (VND)', default=0.0)
    base_price = fields.Monetary('Base Price', currency_field='currency_id')
    additional_fees = fields.Monetary('Additional Fees', currency_field='currency_id')
    total_amount = fields.Monetary('Total Amount', currency_field='currency_id', compute='_compute_total_amount', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                  default=lambda self: self.env.company.currency_id)
    payment_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded')
    ], string='Payment Status', default='pending', tracking=True)
    insurance_covered = fields.Boolean('Insurance Covered', default=False)
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    
    # Integration
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event')
    external_booking_id = fields.Char('External Booking ID', help='ID from external booking systems')
    
    # Computed Fields
    color = fields.Integer('Color', related='appointment_type_id.color', store=True)
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_is_overdue')
    can_reschedule = fields.Boolean('Can Reschedule', compute='_compute_can_reschedule')
    can_cancel = fields.Boolean('Can Cancel', compute='_compute_can_cancel')
    
    # System Fields
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    @api.depends('name', 'patient_id.name', 'appointment_date', 'appointment_time')
    def _compute_display_name(self):
        for record in self:
            if record.patient_id and record.appointment_date:
                time_str = self._float_to_time_string(record.appointment_time)
                record.display_name = f"{record.patient_id.name} - {record.appointment_date} {time_str}"
            else:
                record.display_name = record.name or _('New Appointment')
    
    @api.depends('appointment_date', 'appointment_time')
    def _compute_appointment_datetime(self):
        for record in self:
            if record.appointment_date and record.appointment_time:
                # Convert float time to datetime
                hours = int(record.appointment_time)
                minutes = int((record.appointment_time - hours) * 60)
                datetime_local = datetime.combine(record.appointment_date, 
                                                datetime.min.time().replace(hour=hours, minute=minutes))
                
                # Convert to UTC for storage
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                datetime_tz = user_tz.localize(datetime_local)
                record.appointment_datetime = datetime_tz.astimezone(pytz.UTC).replace(tzinfo=None)
            else:
                record.appointment_datetime = False
    
    @api.depends('appointment_datetime', 'duration_minutes')
    def _compute_end_datetime(self):
        for record in self:
            if record.appointment_datetime and record.duration_minutes:
                record.end_datetime = record.appointment_datetime + timedelta(minutes=record.duration_minutes)
            else:
                record.end_datetime = False
    
    @api.depends('appointment_datetime', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_overdue = (record.appointment_datetime and 
                               record.appointment_datetime < now and 
                               record.state in ['confirmed', 'in_progress'])
    
    @api.depends('state', 'appointment_datetime')
    def _compute_can_reschedule(self):
        for record in self:
            record.can_reschedule = record.state in ['draft', 'requested', 'confirmed']
    
    @api.depends('state', 'appointment_datetime')
    def _compute_can_cancel(self):
        for record in self:
            record.can_cancel = record.state in ['draft', 'requested', 'confirmed']
    
    @api.depends('base_price', 'additional_fees', 'travel_fee')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = (record.base_price or 0.0) + (record.additional_fees or 0.0) + (record.travel_fee or 0.0)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New Appointment')) == _('New Appointment'):
                vals['name'] = self.env['ir.sequence'].next_by_code('health.appointment') or _('New Appointment')
        
        appointments = super().create(vals_list)
        
        # Create calendar events for confirmed appointments
        for appointment in appointments:
            if appointment.state in ['confirmed', 'in_progress']:
                appointment._create_calendar_event()
        
        return appointments
    
    def write(self, vals):
        result = super().write(vals)
        
        # Update calendar events if datetime changes
        if any(field in vals for field in ['appointment_datetime', 'duration_minutes', 'state']):
            for record in self:
                if record.calendar_event_id:
                    record._update_calendar_event()
        
        return result
    
    def _create_calendar_event(self):
        """Create calendar event for appointment"""
        if not self.appointment_datetime:
            return
        
        event_vals = {
            'name': f'Appointment: {self.patient_id.name}',
            'start': self.appointment_datetime,
            'stop': self.end_datetime,
            'description': f'''
Appointment Details:
- Patient: {self.patient_id.name}
- Type: {self.appointment_type_id.name}
- Location: {dict(self._fields['location_type'].selection)[self.location_type]}
- Phone: {self.patient_phone or 'N/A'}
- Symptoms: {self.symptoms or 'None specified'}
            '''.strip(),
            'user_id': self.primary_doctor_id.id or self.env.user.id,
            'partner_ids': [(4, self.patient_id.id)] if self.patient_id else [],
            'alarm_ids': [(6, 0, [])],  # No default alarms, can be customized
        }
        
        calendar_event = self.env['calendar.event'].create(event_vals)
        self.calendar_event_id = calendar_event.id
    
    def _update_calendar_event(self):
        """Update existing calendar event"""
        if not self.calendar_event_id:
            return
        
        self.calendar_event_id.write({
            'start': self.appointment_datetime,
            'stop': self.end_datetime,
            'name': f'Appointment: {self.patient_id.name}',
        })
    
    def _float_to_time_string(self, float_time):
        """Convert float time to string format"""
        if not float_time:
            return ''
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f'{hours:02d}:{minutes:02d}'
    
    def action_confirm(self):
        """Confirm appointment"""
        if self.state != 'requested':
            raise UserError(_('Only requested appointments can be confirmed.'))
        
        self.write({
            'state': 'confirmed',
            'confirmation_date': fields.Datetime.now(),
            'confirmed_by_id': self.env.user.id,
        })
        
        # Create calendar event
        self._create_calendar_event()
        
        # Send confirmation email/SMS
        self._send_confirmation_notification()
        
        return True
    
    def action_start(self):
        """Start appointment (mark as in progress)"""
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed appointments can be started.'))
        
        self.state = 'in_progress'
        return True
    
    def action_complete(self):
        """Complete appointment"""
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress appointments can be completed.'))
        
        self.state = 'completed'
        
        # Update patient's last visit date
        if self.patient_id:
            self.patient_id.last_visit_date = fields.Datetime.now()
            if self.patient_id.patient_status == 'new':
                self.patient_id.patient_status = 'active'
        
        return True
    
    def action_cancel(self):
        """Cancel appointment"""
        if not self.can_cancel:
            raise UserError(_('This appointment cannot be cancelled.'))
        
        self.state = 'cancelled'
        
        # Remove calendar event
        if self.calendar_event_id:
            self.calendar_event_id.unlink()
            self.calendar_event_id = False
        
        # Send cancellation notification
        self._send_cancellation_notification()
        
        return True
    
    def action_mark_no_show(self):
        """Mark appointment as no show"""
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed appointments can be marked as no show.'))
        
        self.state = 'no_show'
        return True
    
    def action_reschedule(self):
        """Open reschedule wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reschedule Appointment'),
            'res_model': 'health.appointment.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_appointment_id': self.id}
        }
    
    def action_view_calendar_event(self):
        """View associated calendar event"""
        if not self.calendar_event_id:
            raise UserError(_('No calendar event associated with this appointment.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Calendar Event'),
            'res_model': 'calendar.event',
            'res_id': self.calendar_event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _send_confirmation_notification(self):
        """Send appointment confirmation via email/SMS"""
        # Email notification
        template = self.env.ref('health_calendar.email_template_appointment_confirmation', False)
        if template and self.patient_email:
            template.send_mail(self.id, force_send=True)
        
        # SMS notification (if SMS module is available)
        if self.patient_phone and hasattr(self.env, 'sms'):
            message = _('Your appointment at VAFHS is confirmed for %s at %s. Location: %s') % (
                self.appointment_date.strftime('%Y-%m-%d'),
                self._float_to_time_string(self.appointment_time),
                dict(self._fields['location_type'].selection)[self.location_type]
            )
            # self.env['sms.api'].send_sms(self.patient_phone, message)
    
    def _send_cancellation_notification(self):
        """Send appointment cancellation notification"""
        template = self.env.ref('health_calendar.email_template_appointment_cancellation', False)
        if template and self.patient_email:
            template.send_mail(self.id, force_send=True)
    
    @api.constrains('appointment_date', 'appointment_time')
    def _check_appointment_datetime(self):
        for record in self:
            if record.appointment_date and record.appointment_time:
                # Check if appointment is in the past
                appointment_dt = datetime.combine(record.appointment_date, 
                                                datetime.min.time().replace(
                                                    hour=int(record.appointment_time),
                                                    minute=int((record.appointment_time % 1) * 60)
                                                ))
                if appointment_dt < datetime.now():
                    raise ValidationError(_('Cannot create appointments in the past.'))
    
    @api.constrains('appointment_time')
    def _check_appointment_time(self):
        for record in self:
            if record.appointment_time < 0 or record.appointment_time >= 24:
                raise ValidationError(_('Appointment time must be between 0:00 and 23:59.'))
    
    def _get_portal_return_url(self):
        return '/my/appointments/%s' % self.id
    
    # ============================================================================
    # V2.0 ENHANCEMENTS: PREDICTIVE SCHEDULING & AI INTEGRATION
    # ============================================================================
    
    # AI/ML Fields
    predicted_duration = fields.Integer('AI Predicted Duration (Minutes)', readonly=True)
    optimal_time_score = fields.Float('Optimal Time Score', readonly=True, 
                                     help='AI score for appointment timing optimization')
    rescheduling_suggestions = fields.Text('AI Rescheduling Suggestions', readonly=True)
    no_show_probability = fields.Float('No-Show Probability %', readonly=True)
    patient_satisfaction_prediction = fields.Float('Predicted Satisfaction Score', readonly=True)
    
    # Smart Scheduling
    auto_assigned = fields.Boolean('Auto-Assigned by AI', default=False, readonly=True)
    assignment_confidence = fields.Float('Assignment Confidence %', readonly=True)
    alternative_slots = fields.Text('Alternative Time Slots JSON', readonly=True)
    
    # Clinical Integration
    clinical_protocol_id = fields.Many2one('health.clinical.protocol', 
                                          string='Recommended Protocol', readonly=True)
    care_recommendations = fields.Text('AI Care Recommendations', readonly=True)
    
    @api.model
    def get_smart_booking_suggestions(self, patient_id, appointment_type_id, preferred_date=None):
        """
        V2.0 Enhancement: Get AI-powered booking suggestions
        """
        predictive_engine = self.env['health.predictive.scheduling']
        
        # Get smart suggestions from predictive engine
        suggestions = predictive_engine.get_smart_appointment_suggestions(
            patient_id, appointment_type_id
        )
        
        # Add patient-specific optimizations
        patient = self.env['res.partner'].browse(patient_id)
        optimized_suggestions = []
        
        for suggestion in suggestions:
            # Enhance with patient history
            suggestion['patient_history_match'] = self._calculate_patient_history_match(
                patient, suggestion['time']
            )
            
            # Add travel optimization for home visits
            appointment_type = self.env['health.service.type'].browse(appointment_type_id)
            if appointment_type.available_home:
                suggestion['travel_optimization'] = self._calculate_travel_optimization(
                    patient, suggestion['date'], suggestion['time']
                )
            
            optimized_suggestions.append(suggestion)
        
        return optimized_suggestions
    
    def _calculate_patient_history_match(self, patient, suggested_time):
        """
        Calculate how well suggested time matches patient's history
        """
        # Get patient's historical appointments
        historical_appointments = self.search([
            ('patient_id', '=', patient.id),
            ('state', '=', 'completed')
        ], limit=10)
        
        if not historical_appointments:
            return 0.5  # Neutral score for new patients
        
        # Calculate average preferred time
        avg_time = sum(apt.appointment_time for apt in historical_appointments) / len(historical_appointments)
        
        # Score based on proximity to historical preference
        time_diff = abs(suggested_time - avg_time)
        match_score = max(0, 1 - (time_diff / 8))  # 8-hour maximum difference
        
        return match_score
    
    def _calculate_travel_optimization(self, patient, date, time):
        """
        Calculate travel optimization score for home visits
        """
        # Get other appointments on the same date
        same_day_appointments = self.search([
            ('appointment_date', '=', date),
            ('location_type', '=', 'home'),
            ('state', 'in', ['confirmed', 'in_progress'])
        ])
        
        if not same_day_appointments:
            return {'score': 0.7, 'reason': 'No travel conflicts'}
        
        # Calculate geographic clustering potential
        # This would integrate with actual mapping service
        travel_score = 0.8  # Simplified score
        
        return {
            'score': travel_score,
            'reason': 'Optimized for travel efficiency',
            'nearby_appointments': len(same_day_appointments)
        }
    
    @api.model
    def predict_appointment_outcomes(self, appointment_ids):
        """
        V2.0 Enhancement: Predict appointment outcomes using ML
        """
        appointments = self.browse(appointment_ids)
        predictions = []
        
        predictive_engine = self.env['health.predictive.scheduling']
        
        for appointment in appointments:
            # Predict no-show probability
            no_show_prob = self._predict_no_show_probability(appointment)
            
            # Predict duration
            predicted_duration = self._predict_appointment_duration(appointment)
            
            # Predict satisfaction
            satisfaction_pred = self._predict_patient_satisfaction(appointment)
            
            # Update appointment with predictions
            appointment.write({
                'no_show_probability': no_show_prob,
                'predicted_duration': predicted_duration,
                'patient_satisfaction_prediction': satisfaction_pred
            })
            
            predictions.append({
                'appointment_id': appointment.id,
                'no_show_probability': no_show_prob,
                'predicted_duration': predicted_duration,
                'satisfaction_prediction': satisfaction_pred
            })
        
        return predictions
    
    def _predict_no_show_probability(self, appointment):
        """
        Predict probability of patient no-show
        """
        # Factors affecting no-show probability
        base_probability = 0.15  # 15% base no-show rate
        
        # Patient history factor
        patient_appointments = self.search([
            ('patient_id', '=', appointment.patient_id.id),
            ('state', 'in', ['completed', 'no_show'])
        ])
        
        if patient_appointments:
            no_shows = patient_appointments.filtered(lambda a: a.state == 'no_show')
            history_factor = len(no_shows) / len(patient_appointments)
            base_probability += history_factor * 0.3
        
        # Time factors
        if appointment.appointment_time < 9:  # Early morning
            base_probability += 0.05
        elif appointment.appointment_time > 17:  # Late afternoon
            base_probability += 0.1
        
        # Weather factor (simplified)
        if appointment.appointment_date.month in [6, 7, 8]:  # Rainy season
            base_probability += 0.05
        
        # Urgency factor
        if appointment.urgency_level == 'routine':
            base_probability += 0.05
        elif appointment.urgency_level == 'emergency':
            base_probability -= 0.1
        
        return min(0.8, max(0.05, base_probability * 100))
    
    def _predict_appointment_duration(self, appointment):
        """
        Predict actual appointment duration
        """
        base_duration = appointment.duration_minutes or 30
        
        # Patient factors
        if appointment.patient_id.age and appointment.patient_id.age > 65:
            base_duration += 10  # Elderly patients typically need more time
        
        # Appointment type factors
        if appointment.urgency_level == 'emergency':
            base_duration += 15
        elif appointment.urgency_level == 'routine':
            base_duration -= 5
        
        # Location factors
        if appointment.location_type == 'home':
            base_duration += 20  # Home visits typically take longer
        
        # Historical adjustment
        patient_appointments = self.search([
            ('patient_id', '=', appointment.patient_id.id),
            ('state', '=', 'completed'),
            ('duration_minutes', '>', 0)
        ], limit=5)
        
        if patient_appointments:
            avg_duration = sum(apt.duration_minutes for apt in patient_appointments) / len(patient_appointments)
            # Weighted average with historical data
            base_duration = (base_duration * 0.7) + (avg_duration * 0.3)
        
        return int(base_duration)
    
    def _predict_patient_satisfaction(self, appointment):
        """
        Predict patient satisfaction score
        """
        base_score = 4.0  # Base satisfaction score out of 5
        
        # Time factors
        if 9 <= appointment.appointment_time <= 16:  # Preferred hours
            base_score += 0.2
        
        # Location factors
        if appointment.location_type == 'home':
            base_score += 0.3  # Higher satisfaction for home visits
        
        # Staff assignment factors
        if appointment.assigned_staff_id:
            # Check staff rating if available
            base_score += 0.1
        
        # Wait time prediction
        same_day_appointments = self.search([
            ('appointment_date', '=', appointment.appointment_date),
            ('appointment_time', '<', appointment.appointment_time),
            ('state', 'in', ['confirmed', 'in_progress'])
        ])
        
        if len(same_day_appointments) > 5:  # Busy day
            base_score -= 0.2
        
        return min(5.0, max(1.0, base_score))
    
    @api.model
    def auto_optimize_schedule(self, target_date=None):
        """
        V2.0 Enhancement: Automatically optimize appointment schedule
        """
        if not target_date:
            target_date = fields.Date.today()
        
        # Get all appointments for the date
        appointments = self.search([
            ('appointment_date', '=', target_date),
            ('state', 'in', ['confirmed', 'requested'])
        ])
        
        if not appointments:
            return {'status': 'no_appointments', 'message': 'No appointments to optimize'}
        
        # Get optimization suggestions
        predictive_engine = self.env['health.predictive.scheduling']
        optimization_data = predictive_engine.optimize_staff_schedule(target_date)
        
        optimizations_applied = 0
        recommendations = []
        
        for appointment in appointments:
            # Calculate optimal time score
            optimal_score = self._calculate_optimal_time_score(appointment)
            appointment.optimal_time_score = optimal_score
            
            # Generate rescheduling suggestions if score is low
            if optimal_score < 0.6:
                suggestions = self._generate_rescheduling_suggestions(appointment)
                appointment.rescheduling_suggestions = suggestions
                recommendations.append({
                    'appointment_id': appointment.id,
                    'current_score': optimal_score,
                    'suggestions': suggestions
                })
        
        return {
            'status': 'optimization_complete',
            'appointments_analyzed': len(appointments),
            'recommendations': recommendations,
            'optimization_data': optimization_data
        }
    
    def _calculate_optimal_time_score(self, appointment):
        """
        Calculate how optimal the appointment time is
        """
        score = 0.5  # Base score
        
        # Time of day optimization
        if 9 <= appointment.appointment_time <= 11:
            score += 0.2  # Morning preferred
        elif 14 <= appointment.appointment_time <= 16:
            score += 0.15  # Early afternoon good
        elif appointment.appointment_time < 8 or appointment.appointment_time > 17:
            score -= 0.2  # Outside normal hours
        
        # Day of week optimization
        if appointment.appointment_date.weekday() < 5:  # Weekday
            score += 0.1
        else:  # Weekend
            score -= 0.1
        
        # Staff availability consideration
        if appointment.assigned_staff_id:
            score += 0.15
        
        # Travel optimization for home visits
        if appointment.location_type == 'home':
            travel_score = self._calculate_travel_efficiency(appointment)
            score += travel_score * 0.2
        
        return min(1.0, max(0.0, score))
    
    def _calculate_travel_efficiency(self, appointment):
        """
        Calculate travel efficiency for home visits
        """
        # Get other home visits on the same day
        same_day_visits = self.search([
            ('appointment_date', '=', appointment.appointment_date),
            ('location_type', '=', 'home'),
            ('id', '!=', appointment.id),
            ('state', 'in', ['confirmed', 'in_progress'])
        ])
        
        if not same_day_visits:
            return 0.5  # Neutral score for single visit
        
        # Simple clustering efficiency (would use real geographic data)
        # For now, return high efficiency if there are nearby appointments
        return min(1.0, len(same_day_visits) * 0.3)
    
    def _generate_rescheduling_suggestions(self, appointment):
        """
        Generate AI-powered rescheduling suggestions
        """
        suggestions = []
        
        # Get optimal time slots for next 7 days
        predictive_engine = self.env['health.predictive.scheduling']
        optimal_slots = predictive_engine.get_smart_appointment_suggestions(
            appointment.patient_id.id, 
            appointment.appointment_type_id.id
        )
        
        # Filter and format suggestions
        for slot in optimal_slots[:3]:  # Top 3 suggestions
            if slot['confidence'] > 0.7:  # Only high-confidence suggestions
                suggestions.append({
                    'date': slot['date'],
                    'time': slot['time'],
                    'confidence': slot['confidence'],
                    'reason': slot['reason'],
                    'improvement': f"+{(slot['confidence'] - appointment.optimal_time_score) * 100:.0f}% optimization"
                })
        
        return json.dumps(suggestions) if suggestions else json.dumps([])
    
    def action_apply_ai_optimization(self):
        """
        Action to apply AI optimization suggestions
        """
        if not self.rescheduling_suggestions:
            raise UserError(_('No AI optimization suggestions available for this appointment.'))
        
        suggestions = json.loads(self.rescheduling_suggestions)
        
        if not suggestions:
            raise UserError(_('No valid optimization suggestions found.'))
        
        # Return wizard to select optimization
        return {
            'type': 'ir.actions.act_window',
            'name': _('AI Optimization Suggestions'),
            'res_model': 'health.appointment.optimization.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_appointment_id': self.id,
                'suggestions': suggestions
            }
        }