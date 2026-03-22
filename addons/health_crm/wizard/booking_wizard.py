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
    client_address = fields.Text('Address')  # Kept for backward compatibility
    client_dob = fields.Date('Date of Birth')
    client_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    
    # Address sub-fields for popup editor
    address_house_number = fields.Char('House Number')
    address_street = fields.Char('Street')
    address_alley = fields.Char('Alley/Lane')
    address_sub_alley = fields.Char('Sub-Alley')
    address_ward = fields.Char('Ward/Commune')
    address_district = fields.Char('District')
    address_city = fields.Char('City/Province')
    address_building = fields.Char('Building Name')
    address_apartment = fields.Char('Apartment/Unit')
    address_edit_mode = fields.Boolean('Address Edit Mode', default=False)
    
    # Consolidated address display
    consolidated_address = fields.Char(
        'Full Address',
        compute='_compute_consolidated_address',
        store=False,
        help='Full address in consolidated format'
    )
    
    @api.depends('address_house_number', 'address_street', 'address_alley', 
                 'address_sub_alley', 'address_ward', 'address_district', 
                 'address_city', 'address_building', 'address_apartment', 'client_address')
    def _compute_consolidated_address(self):
        for wizard in self:
            parts = []
            if wizard.address_apartment:
                parts.append(f"Apt {wizard.address_apartment}")
            if wizard.address_building:
                parts.append(wizard.address_building)
            if wizard.address_house_number:
                parts.append(f"No. {wizard.address_house_number}")
            if wizard.address_sub_alley:
                parts.append(f"Sub-alley {wizard.address_sub_alley}")
            if wizard.address_alley:
                parts.append(f"Alley {wizard.address_alley}")
            if wizard.address_street:
                parts.append(wizard.address_street)
            if wizard.address_ward:
                parts.append(wizard.address_ward)
            if wizard.address_district:
                parts.append(wizard.address_district)
            if wizard.address_city:
                parts.append(wizard.address_city)
            
            if parts:
                wizard.consolidated_address = ', '.join(parts)
            elif wizard.client_address:
                wizard.consolidated_address = wizard.client_address
            else:
                wizard.consolidated_address = ''
    
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
    
    service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('nursing_home', 'Nursing Home'),
        ('office', 'Office'),
        ('online', 'Online/Telemedicine'),
        ('other', 'Other Location'),
    ], string='Service Location', default='home',
       help='Where the service will be provided')
    
    @api.onchange('service_type')
    def _onchange_service_type(self):
        """Set service_location based on service_type (matching FSO logic)"""
        if self.service_type == 'telemedicine':
            self.service_location = 'online'
        elif self.service_type in ['home_visit', 'follow_up']:
            self.service_location = 'home'
        elif self.service_type == 'clinic_visit':
            self.service_location = 'clinic'
    
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
        ('30_days', '30 Days'),
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

    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        help='Catchment province for the booking (defaults from client record)'
    )

    facility_id = fields.Many2one(
        'health.facility',
        string='Healthcare Facility',
        domain="[('active', '=', True), ('catchment_province_id', '=', catchment_province_id)]",
        help='Facility for this booking. Timezone is derived from this facility.'
    )

    @api.onchange('client_id')
    def _onchange_client_for_province(self):
        """Set catchment province from client's record"""
        if self.client_id and self.client_id.catchment_province_id:
            self.catchment_province_id = self.client_id.catchment_province_id

    @api.onchange('catchment_province_id')
    def _onchange_catchment_province_id(self):
        """Reset facility when catchment province changes"""
        if self.facility_id and self.facility_id.catchment_province_id != self.catchment_province_id:
            self.facility_id = False

    booking_time = fields.Float(
        'Booking Time',
        help='Time of the booking (24h format)'
    )
    
    booking_duration = fields.Float(
        'Duration (Hours)',
        default=1.0,
        help='Expected duration of service'
    )
    
    # Note: service_location is now defined in Step 2 (Service Requirements section)
    # as a Selection field matching FSO's service_location
    
    booking_notes = fields.Text(
        'Booking Notes',
        help='Additional notes for the booking'
    )
    
    # =========================================================================
    # STEP 4: ASSIGN BOOKING
    # =========================================================================
    
    assigned_staff_ids = fields.Many2many(
        'hr.employee',
        'booking_wizard_assigned_staff_rel',
        'wizard_id', 'employee_id',
        string='Assigned Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('healthcare_role', '!=', 'doctor'), ('primary_facility_id', '=', facility_id)]",
        help='Staff members to assign to this booking (filtered by selected facility)'
    )
    
    lead_staff_id = fields.Many2one(
        'hr.employee',
        string='Lead Staff',
        domain="[('is_healthcare_staff', '=', True), ('employment_status', '=', 'active'), ('healthcare_role', '!=', 'doctor'), ('primary_facility_id', '=', facility_id)]",
        help='Primary staff member responsible for this service'
    )
    
    assigned_doctor_ids = fields.Many2many(
        'hr.employee',
        'booking_wizard_assigned_doctor_rel',
        'wizard_id', 'doctor_id',
        string='Assigned Doctors',
        domain="[('is_healthcare_staff', '=', True), ('healthcare_role', '=', 'doctor'), ('employment_status', '=', 'active'), ('primary_facility_id', '=', facility_id)]",
        help='Doctors to assign to this booking (filtered by selected facility)'
    )
    
    # Legacy field - kept for backward compatibility
    assigned_nurse_id = fields.Many2one(
        'hr.employee',
        string='Assigned Nurse/Staff',
        domain="[('job_id.name', 'ilike', 'nurse')]",
        help='Deprecated - use assigned_staff_ids instead'
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
            if not self.facility_id:
                raise ValidationError(_('Please select a Healthcare Facility before proceeding.'))
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
    
    def action_edit_address(self):
        """Open address edit popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Address'),
            'res_model': 'health.booking.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('health_crm.view_booking_address_edit_form').id,
            'target': 'new',
        }
    
    def action_save_address(self):
        """Save address and return to main wizard"""
        self.ensure_one()
        # Update client_address with consolidated address
        self.client_address = self.consolidated_address
        return self._reload_wizard()
    
    # =========================================================================
    # FINALIZE BOOKING
    # =========================================================================
    
    def action_create_booking(self):
        """Create the booking from wizard data"""
        self.ensure_one()
        
        if not self.facility_id:
            raise ValidationError(_('Please select a Healthcare Facility before creating the booking.'))
        
        # Create or get client
        client = None
        
        if self.client_id:
            # Existing client selected
            client = self.client_id
            # Update existing client with any changes from the wizard
            update_vals = {}
            if self.client_phone and self.client_phone != (client.phone or ''):
                update_vals['phone'] = self.client_phone
            if self.client_email and self.client_email != (client.email or ''):
                update_vals['email'] = self.client_email
            if self.client_dob and self.client_dob != client.birth_date:
                update_vals['birth_date'] = self.client_dob
            if self.client_gender and self.client_gender != (client.gender or ''):
                update_vals['gender'] = self.client_gender
            if self.client_address and self.client_address != (client.street or ''):
                update_vals['street'] = self.client_address
            if update_vals:
                client.write(update_vals)
        elif self.is_new_client and self.lead_id:
            # New client from lead - use lead's _get_or_create_patient to properly 
            # transfer unique_contact_code as patient_code
            client = self.lead_id._get_or_create_patient(self.client_name)
            
            # Update client with additional info from wizard
            update_vals = {}
            if self.client_phone and not client.phone:
                update_vals['phone'] = self.client_phone
            if self.client_email and not client.email:
                update_vals['email'] = self.client_email
            if self.client_address and not client.street:
                update_vals['street'] = self.client_address
            if self.client_dob:
                update_vals['birth_date'] = self.client_dob
            if self.client_gender:
                update_vals['gender'] = self.client_gender
            if update_vals:
                client.write(update_vals)
                
        elif self.is_new_client and self.client_name:
            # New client without lead - create directly with a default catchment province
            # Get default catchment province from user's facility or first available
            catchment_province = False
            user_facility = self.env.user.facility_id if hasattr(self.env.user, 'facility_id') else False
            if user_facility and user_facility.catchment_province_id:
                catchment_province = user_facility.catchment_province_id
            else:
                # Get first available catchment province
                catchment_province = self.env['health.catchment.province'].search([('active', '=', True)], limit=1)
            
            client = self.env['res.partner'].create({
                'name': self.client_name,
                'phone': self.client_phone,
                'email': self.client_email,
                'street': self.client_address,
                'is_patient': True,
                'birth_date': self.client_dob,
                'gender': self.client_gender,
                'catchment_province_id': catchment_province.id if catchment_province else False,
            })
        else:
            raise ValidationError(_('No client selected or entered.'))
        
        # Update client with commission duration if 30_days is selected
        if self.commission_duration == '30_days' and client:
            client.write({'commission_due_to': self.commission_duration})
        
        # Create the booking (FSO)
        booking_vals = {
            'patient_id': client.id,
            'service_type': self.service_type or 'consultation',
            'scheduled_datetime': self._get_scheduled_datetime(),
            'scheduled_duration': self.booking_duration,
            'service_location': self.service_location,
            'intake_notes': self.booking_notes,
            'facility_id': self.facility_id.id if self.facility_id else False,
            'booking_timezone': self.facility_id.timezone if self.facility_id else (
                self.catchment_province_id.timezone if self.catchment_province_id else 'Asia/Ho_Chi_Minh'
            ),
            # Commission fields
            'commission_due_to': self.commission_due_to.id if self.commission_due_to else False,
            'commission_percentage': self.commission_percentage,
            'commission_duration': self.commission_duration,
            'service_fee_vnd': self.service_fee_vnd,
        }
        
        # Assign staff if provided (legacy support)
        if self.assigned_nurse_id:
            booking_vals['primary_nurse_id'] = self.assigned_nurse_id.id
        
        # Create booking
        FSO = self.env['health.fieldservice.order']
        booking = FSO.create(booking_vals)
        
        # Assign staff from wizard fields (this triggers FSO inverse methods
        # which create health.staff.assignment records automatically)
        staff_update = {}
        if self.assigned_staff_ids:
            staff_update['assigned_staff_ids'] = [(6, 0, self.assigned_staff_ids.ids)]
        if self.lead_staff_id:
            # Ensure lead staff is in assigned_staff_ids too
            staff_ids = set(self.assigned_staff_ids.ids) if self.assigned_staff_ids else set()
            staff_ids.add(self.lead_staff_id.id)
            staff_update['assigned_staff_ids'] = [(6, 0, list(staff_ids))]
        if self.assigned_doctor_ids:
            staff_update['assigned_doctor_ids'] = [(6, 0, self.assigned_doctor_ids.ids)]
        if staff_update:
            booking.write(staff_update)
        
        # Link client to lead and update status
        if self.lead_id and client:
            lead_update_vals = {
                'patient_id': client.id,
                'partner_id': client.id,  # Also set partner_id for View Client Dashboard button
                'contact_status': 'booking',
                'booking_status': 'pending',
                'health_contact_outcome': 'service_booked',
                'contact_outcome': 'service_booked',
            }
            self.lead_id.write(lead_update_vals)
            
            # If caller is a representative (not the client), ensure the relation is created
            if self.lead_id.contact_relationship_type and self.lead_id.contact_relationship_type != 'client':
                representative = self.lead_id._create_or_get_representative()
                if representative:
                    self.lead_id._create_health_relationship(client, representative)
            
            # Post to chatter
            self.lead_id.message_post(
                body=_('Booking created: %s for client: %s (ID: %s)') % (
                    booking.name, 
                    client.name,
                    client.patient_code or 'N/A'
                ),
                message_type='notification',
            )
        
        # Notify OM about new booking
        self._notify_om_new_booking(booking)
        
        # Return to booking form with proper name for breadcrumb
        booking_display_name = booking.display_name or booking.name or _('Booking')
        return {
            'type': 'ir.actions.act_window',
            'name': booking_display_name,
            'res_model': 'health.fieldservice.order',
            'res_id': booking.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
    
    def _get_scheduled_datetime(self):
        """Convert date and time to UTC datetime.

        The time picker shows service times in the facility's timezone.
        We interpret the entered time using the facility's timezone and convert
        to UTC for storage.
        """
        from datetime import datetime
        import pytz
        if self.booking_date:
            hours = int(self.booking_time)
            minutes = int((self.booking_time - hours) * 60)
            naive_local = datetime.combine(
                self.booking_date,
                datetime.min.time()
            ).replace(hour=hours, minute=minutes)
            # Use facility timezone, fallback to catchment province, then default
            tz_name = 'Asia/Ho_Chi_Minh'
            if self.facility_id and self.facility_id.timezone:
                tz_name = self.facility_id.timezone
            elif self.catchment_province_id and self.catchment_province_id.timezone:
                tz_name = self.catchment_province_id.timezone
            facility_tz = pytz.timezone(tz_name)
            local_dt = facility_tz.localize(naive_local)
            return local_dt.astimezone(pytz.utc).replace(tzinfo=None)
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
            
            # Check if there's an existing partner (client)
            if lead.partner_id:
                client = lead.partner_id
                defaults['client_id'] = client.id
                defaults['is_new_client'] = False
                # Populate fields ONLY from the client record - never fall back
                # to lead.phone/lead.email_from because those belong to the
                # CONTACT (caller), not the CLIENT (patient)
                defaults['client_name'] = client.name
                defaults['client_phone'] = client.phone or client.mobile or ''
                defaults['client_email'] = client.email or ''
                defaults['client_address'] = client.street or ''
                if hasattr(client, 'birth_date'):
                    defaults['client_dob'] = client.birth_date
                if hasattr(client, 'gender'):
                    defaults['client_gender'] = client.gender
            else:
                defaults['is_new_client'] = True
                # Check relationship type to avoid phone contamination
                if lead.contact_relationship_type == 'client':
                    # Caller IS the client - lead data is client data
                    defaults['client_name'] = lead.name
                    defaults['client_phone'] = lead.phone
                    defaults['client_email'] = lead.email_from
                    defaults['client_address'] = lead.street_address
                else:
                    # Caller is NOT the client (caregiver, payer, etc.)
                    # Do NOT use lead.phone - it belongs to the caller
                    defaults['client_name'] = lead.client_name or lead.name
                    defaults['client_phone'] = ''
                    defaults['client_email'] = ''
                    defaults['client_address'] = ''
                    # Try to find client by client_name
                    if lead.client_name:
                        client_partner = self.env['res.partner'].search([
                            ('is_patient', '=', True),
                            ('name', 'ilike', lead.client_name),
                        ], limit=1)
                        if client_partner:
                            defaults['client_id'] = client_partner.id
                            defaults['is_new_client'] = False
                            defaults['client_phone'] = client_partner.phone or client_partner.mobile or ''
                            defaults['client_email'] = client_partner.email or ''
                            defaults['client_address'] = client_partner.street or ''
        
        return defaults
