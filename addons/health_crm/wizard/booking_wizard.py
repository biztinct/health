# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HealthBookingWizard(models.TransientModel):
    """
    Multi-Step Booking Wizard
    
    This wizard provides a stepped workflow for creating bookings:
    Step 1: Client Details
    Step 2: Service Requirements (with commission fields)
    Step 3: Booking Details (date/time)
    Step 4: Assign Booking (optional)
    """
    _name = 'health.booking.wizard'
    _description = 'Booking Creation Wizard'

    # =========================================================================
    # STEP TRACKING
    # =========================================================================
    
    current_step = fields.Selection([
        ('1_client', 'Client Details'),
        ('2_services', 'Service Requirements'),
        ('3_booking', 'Booking Details'),
        ('4_assign', 'Assign Booking'),
    ], string='Current Step', default='1_client', required=True)
    
    # Source lead/contact
    lead_id = fields.Many2one(
        'crm.lead',
        string='Source Contact',
        help='The contact that initiated this booking'
    )
    
    # =========================================================================
    # STEP 1: CLIENT DETAILS
    # =========================================================================
    
    # Select existing client or create new
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain="[('is_patient', '=', True)]",
        help='Select existing client or create new'
    )
    
    is_new_client = fields.Boolean(
        'New Client',
        default=False,
        help='Check if this is a new client'
    )
    
    # New client fields
    client_name = fields.Char('Client Name')
    client_phone = fields.Char('Phone')
    client_email = fields.Char('Email')
    client_address = fields.Text('Address')
    client_dob = fields.Date('Date of Birth')
    client_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    
    # Client info display (for existing clients)
    client_display_name = fields.Char(
        'Client',
        compute='_compute_client_display',
        store=False
    )
    
    @api.depends('client_id', 'client_name')
    def _compute_client_display(self):
        for wizard in self:
            if wizard.client_id:
                wizard.client_display_name = wizard.client_id.name
            else:
                wizard.client_display_name = wizard.client_name or ''
    
    # =========================================================================
    # STEP 2: SERVICE REQUIREMENTS
    # =========================================================================
    
    # Use selection field matching FSO service types
    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('telemedicine', 'Telemedicine'),
        ('emergency', 'Emergency'),
        ('follow_up', 'Follow-up'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
        ('vaccination', 'Vaccination'),
        ('diagnostic', 'Diagnostic'),
    ], string='Service Type', default='home_visit',
       help='Type of service requested')
    
    service_category = fields.Selection([
        ('medical', 'Medical Care'),
        ('nursing', 'Nursing Care'),
        ('therapy', 'Therapy'),
        ('companion', 'Companion Care'),
        ('other', 'Other'),
    ], string='Service Category', default='nursing',
       help='Category of service')
    
    service_subcategory = fields.Char(
        'Sub-Category',
        help='Specific sub-category if applicable'
    )
    
    service_notes = fields.Text(
        'Service Notes',
        help='Additional notes about service requirements'
    )
    
    # Commission fields (from design requirement)
    commission_due_to = fields.Many2one(
        'res.partner',
        string='Commission Due To',
        help='Person or company receiving commission'
    )
    
    commission_percentage = fields.Float(
        'Commission %',
        digits=(5, 2),
        help='Commission percentage'
    )
    
    commission_duration = fields.Selection([
        ('one_time', 'One Time'),
        ('3_months', '3 Months'),
        ('6_months', '6 Months'),
        ('12_months', '12 Months'),
        ('ongoing', 'Ongoing'),
    ], string='Commission Duration', default='one_time',
       help='How long commission applies')
    
    # Service Fee for casual providers
    service_fee_vnd = fields.Monetary(
        'Service Fee (VND)',
        currency_field='currency_id',
        help='Fee negotiated with casual provider'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # =========================================================================
    # STEP 3: BOOKING DETAILS
    # =========================================================================
    
    booking_date = fields.Date(
        'Booking Date',
        default=fields.Date.today,
        help='Date of the booking'
    )
    
    booking_time = fields.Float(
        'Booking Time',
        help='Time of the booking (24h format)'
    )
    
    booking_duration = fields.Float(
        'Duration (Hours)',
        default=1.0,
        help='Expected duration of service'
    )
    
    booking_location = fields.Text(
        'Location',
        help='Where the service will be provided'
    )
    
    booking_notes = fields.Text(
        'Booking Notes',
        help='Additional notes for the booking'
    )
    
    # =========================================================================
    # STEP 4: ASSIGN BOOKING
    # =========================================================================
    
    assigned_nurse_id = fields.Many2one(
        'hr.employee',
        string='Assigned Nurse/Staff',
        domain="[('job_id.name', 'ilike', 'nurse')]",
        help='Staff member to assign to this booking'
    )
    
    assignment_notes = fields.Text(
        'Assignment Notes',
        help='Instructions for the assigned staff'
    )
    
    # =========================================================================
    # NAVIGATION METHODS
    # =========================================================================
    
    def action_next_step(self):
        """Move to next step"""
        self.ensure_one()
        
        steps = ['1_client', '2_services', '3_booking', '4_assign']
        current_idx = steps.index(self.current_step)
        
        # Validate current step before moving
        if self.current_step == '1_client':
            if not self.client_id and not self.client_name:
                raise ValidationError(_('Please select or enter a client.'))
        elif self.current_step == '2_services':
            if not self.service_type:
                raise ValidationError(_('Please select a service type.'))
        elif self.current_step == '3_booking':
            if not self.booking_date:
                raise ValidationError(_('Please select a booking date.'))
        
        if current_idx < len(steps) - 1:
            self.current_step = steps[current_idx + 1]
        
        return self._reload_wizard()
    
    def action_prev_step(self):
        """Move to previous step"""
        self.ensure_one()
        
        steps = ['1_client', '2_services', '3_booking', '4_assign']
        current_idx = steps.index(self.current_step)
        
        if current_idx > 0:
            self.current_step = steps[current_idx - 1]
        
        return self._reload_wizard()
    
    def action_back_to_contact(self):
        """Return to the source contact form"""
        self.ensure_one()
        
        if self.lead_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contact Details'),
                'res_model': 'crm.lead',
                'res_id': self.lead_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _reload_wizard(self):
        """Reload the wizard to show current step"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Booking'),
            'res_model': 'health.booking.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    # =========================================================================
    # FINALIZE BOOKING
    # =========================================================================
    
    def action_create_booking(self):
        """Create the booking from wizard data"""
        self.ensure_one()
        
        # Create or get client
        if self.is_new_client and self.client_name:
            client = self.env['res.partner'].create({
                'name': self.client_name,
                'phone': self.client_phone,
                'email': self.client_email,
                'street': self.client_address,
                'is_patient': True,
            })
        elif self.client_id:
            client = self.client_id
        else:
            raise ValidationError(_('No client selected or entered.'))
        
        # Create the booking (FSO)
        booking_vals = {
            'patient_id': client.id,
            'service_type': self.service_type or 'consultation',
            'scheduled_start_datetime': self._get_scheduled_datetime(),
            'duration': self.booking_duration,
            'location': self.booking_location,
            'description': self.booking_notes,
            # Commission fields
            'commission_due_to': self.commission_due_to.id if self.commission_due_to else False,
            'commission_percentage': self.commission_percentage,
            'commission_duration': self.commission_duration,
            'service_fee_vnd': self.service_fee_vnd,
        }
        
        # Assign staff if provided
        if self.assigned_nurse_id:
            booking_vals['assigned_nurse_id'] = self.assigned_nurse_id.id
        
        # Create booking
        FSO = self.env['health.fieldservice.order']
        booking = FSO.create(booking_vals)
        
        # Update source lead
        if self.lead_id:
            self.lead_id.write({
                'contact_status': 'booking',
                'booking_status': 'pending',
            })
            # Post to chatter
            self.lead_id.message_post(
                body=_('Booking created: %s') % booking.name,
                message_type='notification',
            )
        
        # Notify OM about new booking
        self._notify_om_new_booking(booking)
        
        # Return to booking form
        return {
            'type': 'ir.actions.act_window',
            'name': _('Booking'),
            'res_model': 'health.fieldservice.order',
            'res_id': booking.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _get_scheduled_datetime(self):
        """Convert date and time to datetime"""
        from datetime import datetime, timedelta
        if self.booking_date:
            hours = int(self.booking_time)
            minutes = int((self.booking_time - hours) * 60)
            return datetime.combine(
                self.booking_date,
                datetime.min.time()
            ).replace(hour=hours, minute=minutes)
        return False
    
    def _notify_om_new_booking(self, booking):
        """Notify Operations Manager about new booking"""
        # Find OM users
        om_group = self.env.ref('health_base.group_health_operations_manager', raise_if_not_found=False)
        if not om_group:
            return
        
        om_users = self.env['res.users'].search([
            ('groups_id', 'in', [om_group.id]),
            ('active', '=', True),
        ])
        
        # Create activity for each OM
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if activity_type and om_users:
            for om in om_users:
                booking.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('New Booking Created'),
                    note=_('New booking from contact: %s') % (self.lead_id.name if self.lead_id else 'Direct'),
                    user_id=om.id,
                    date_deadline=fields.Date.today(),
                )
    
    def action_finish(self):
        """Finish without creating booking (from assign step)"""
        self.ensure_one()
        return self.action_create_booking()
    
    # =========================================================================
    # DEFAULT VALUES
    # =========================================================================
    
    @api.model
    def default_get(self, fields_list):
        """Pre-fill from context lead"""
        defaults = super().default_get(fields_list)
        
        lead_id = self.env.context.get('default_lead_id') or self.env.context.get('active_id')
        if lead_id and self.env.context.get('active_model') == 'crm.lead':
            lead = self.env['crm.lead'].browse(lead_id)
            defaults['lead_id'] = lead.id
            defaults['client_name'] = lead.name
            defaults['client_phone'] = lead.phone
            defaults['client_email'] = lead.email_from
            defaults['client_address'] = lead.street_address
            
            # Check if there's an existing partner
            if lead.partner_id:
                defaults['client_id'] = lead.partner_id.id
                defaults['is_new_client'] = False
            else:
                defaults['is_new_client'] = True
        
        return defaults
