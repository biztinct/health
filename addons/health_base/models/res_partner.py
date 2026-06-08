from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
from odoo.addons.health_base.models import geo_utils
from datetime import date
import re
import requests
import logging
import copy

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extend res.partner for healthcare functionality module"""
    _inherit = 'res.partner'

    # Healthcare Classification - FOUNDATIONAL FIELDS
    # CRITICAL: These fields are referenced by health_crm, health_fieldservice, health_invoicing
    # DO NOT REMOVE OR RENAME - other modules depend on these exact field names
    is_patient = fields.Boolean('Is Patient', default=False, tracking=True)
    is_healthcare_staff = fields.Boolean('Is Healthcare Staff', default=False)
    is_healthcare_facility = fields.Boolean('Is Healthcare Facility', default=False)
    is_emergency_contact = fields.Boolean('Is Emergency Contact', default=False)
    is_caregiver = fields.Boolean('Is Caregiver', default=False, help='This contact is a caregiver')
    is_payer = fields.Boolean('Is Payer', default=False, help='This contact is responsible for payments')
    is_referrer = fields.Boolean('Is Referrer', default=False, help='clients')

    # Patient Healthcare ID
    patient_code = fields.Char(
        'Patient ID',
        copy=False,
        readonly=True,
        tracking=True,
        index=True,
        help='client identifier (auto-generated)'
    )
    patient_code_display = fields.Char('Patient ID Display', compute='_compute_patient_code_display')

    # Personal Details (Patient-specific)
    title = fields.Char('Title')
    first_name = fields.Char('First Name', tracking=True)
    last_name = fields.Char('Last Name', tracking=True)
    middle_name = fields.Char('Middle Name')
    mobile = fields.Char('Mobile', tracking=True)
    birth_date = fields.Date('Date of Birth', tracking=True)
    age = fields.Integer('Age', compute='_compute_age', store=True)
    age_display = fields.Char('Age Display', compute='_compute_age_display')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], string='Gender', tracking=True)
    
    # Healthcare Specific Fields
    patient_category_id = fields.Many2one('health.patient.category', string='Client Category')
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-'),
        ('unknown', 'Unknown')
    ], string='Blood Group', default='unknown')
    
    allergies = fields.Text('Known Allergies')
    medical_history = fields.Text('Medical History Summary')

    # Intake Notes Fields
    intake_diagnosis = fields.Text('Diagnosis', help='Medical diagnosis from intake')
    intake_referring_doctor_id = fields.Many2one(
        'res.partner',
        string='Referring Doctor',
        help='Contact who referred this patient'
    )
    intake_goal_of_care = fields.Text('Goal of Care', help='Primary goal or objective of care')
    intake_required_equipment = fields.Text('Required Equipment', help='Equipment or supplies required for care')
    intake_notes = fields.Text('Intake Notes', help='Additional notes from intake assessment')

    # Emergency Contact Information
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    emergency_contact_relation = fields.Char('Relation to Patient')
    
    # Primary Healthcare Relationships (Patient Side - Many2one)
    primary_caregiver_id = fields.Many2one(
        'res.partner',
        string='Primary Caregiver',
        domain=[('is_caregiver', '=', True)],
        help='client'
    )
    primary_payer_id = fields.Many2one(
        'res.partner', 
        string='Primary Payer',
        domain=[('is_payer', '=', True)],
        help='client'
    )
    primary_referrer_id = fields.Many2one(
        'res.partner',
        string='Primary Referrer', 
        domain=[('is_referrer', '=', True)],
        help='client'
    )
    
    # Healthcare Relationships (Caregiver/Payer/Referrer Side - One2many)
    my_patients_as_caregiver = fields.One2many(
        'res.partner',
        'primary_caregiver_id',
        string='Clients I Care For',
        help='clients for whom I am the primary caregiver'
    )
    my_patients_as_payer = fields.One2many(
        'res.partner',
        'primary_payer_id',
        string='Clients I Pay For',
        help='clients for whom I am the primary payer'
    )
    my_patients_as_referrer = fields.One2many(
        'res.partner',
        'primary_referrer_id',
        string='Clients I Referred',
        help='clients I have referred to healthcare services'
    )

    
    # Insurance & Payment
    insurance_provider = fields.Char('Insurance Provider')
    insurance_number = fields.Char('Insurance Number')
    insurance_expiry = fields.Date('Insurance Expiry')
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('insurance', 'Insurance'),
        ('corporate', 'Corporate'),
        ('government', 'Government')
    ], string='Primary Payment Method', default='cash')
    
    # Commission tracking
    commission_due_to = fields.Selection([
        ('one_time', 'One Time'),
        ('30_days', '30 Days'),
    ], string='Commission Duration',
       help='Commission duration applied to this client from booking')
    
    # Patient Status & Tracking
    patient_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string='Client Status', default='active', tracking=True)
    deceased = fields.Boolean('Deceased', tracking=True)
    
    registration_date = fields.Datetime('Registration Date', default=fields.Datetime.now, readonly=True)
    last_visit_date = fields.Datetime('Last Visit', readonly=True)
    next_visit_date = fields.Datetime('Next Scheduled Visit')

    # MOH Compliance Fields
    profession = fields.Char('Profession', help='client occupation (Nghề nghiệp)')
    ethnicity = fields.Selection([
        ('kinh', 'Kinh (Vietnamese)'),
        ('tay', 'Tày'),
        ('thai', 'Thái'),
        ('muong', 'Mường'),
        ('khmer', 'Khmer'),
        ('hoa', 'Hoa (Chinese)'),
        ('nung', 'Nùng'),
        ('hmong', 'H\'Mông'),
        ('dao', 'Dao'),
        ('gia_rai', 'Gia Rai'),
        ('ede', 'Ê Đê'),
        ('ba_na', 'Ba Na'),
        ('sedang', 'Xơ Đăng'),
        ('co_ho', 'Cơ Ho'),
        ('cham', 'Chăm'),
        ('san_chay', 'Sán Chay'),
        ('other', 'Other')
    ], string='Ethnicity', help='client ethnic group (Dân tộc)')

    # Source Tracking
    source_type = fields.Selection([
        ('facebook', 'Facebook'),
        ('zalo', 'Zalo'),
        ('website', 'Website'),
        ('phone', 'Phone Call'),
        ('referral', 'Referral'),
        ('walk_in', 'Walk-in'),
        ('other', 'Other')
    ], string='Client Source', tracking=True)
    source_details = fields.Char('Source Details')
    referral_source = fields.Char('Referral Source')
    
    # Catchment Province Assignment
    catchment_province_id = fields.Many2one(
        'health.catchment.province',
        string='Catchment Province',
        help='The catchment province/area this client belongs to'
    )
    
    # Facility Assignment
    primary_facility_id = fields.Many2one('health.facility', string='Primary Facility')

    def _get_health_catchment_province(self):
        """Return the partner catchment, falling back to the primary facility."""
        self.ensure_one()
        return self.catchment_province_id or self.primary_facility_id.catchment_province_id
    
    # Medical specialties for healthcare staff
    medical_specialties = fields.Many2many('health.medical.specialty', 
                                          string='Medical Specialties')
    
    # Professional details for healthcare staff
    license_number = fields.Char('Professional License Number')
    license_expiry = fields.Date('License Expiry Date')
    
    # Vietnamese specific fields
    vietnamese_name = fields.Char('Vietnamese Name')
    national_id = fields.Char('National ID (CCCD/CMND)')

    # Vietnamese address structure fields
    province_code = fields.Char('Province Code', help='Mã tỉnh/thành phố')
    named_area = fields.Char('Named Area', help='Khu vực đặt tên')
    apartment_number = fields.Char('Apartment Number', help='Số căn hộ')
    building_name = fields.Char('Building Name', help='Tên tòa nhà')
    house_number = fields.Char('House Number', help='Số nhà')
    sub_alley_number = fields.Char('Sub-Alley Number', help='Số ngách')
    alley_number = fields.Char('Alley Number', help='Số ngõ')
    ward_commune = fields.Char('Ward/Commune', help='Phường/Xã')

    # Computed concatenated home address
    vietnamese_address = fields.Text(
        'Home Address',
        compute='_compute_vietnamese_address',
        store=True,
        help='Automatically formatted home address'
    )

    # Address Autocomplete & Geolocation fields
    address_search = fields.Char(
        'Address Search',
        help='Start typing to search addresses (minimum 3 characters)'
    )
    partner_latitude = fields.Float(
        'Latitude',
        digits=(10, 7),
        help='Geographical latitude'
    )
    partner_longitude = fields.Float(
        'Longitude',
        digits=(10, 7),
        help='Geographical longitude'
    )
    date_localization = fields.Date(
        'Geolocation Date',
        readonly=True,
        help='Date when coordinates were last updated'
    )
    geo_coordinates_display = fields.Char(
        'GPS Coordinates',
        compute='_compute_geo_coordinates',
        help='Latitude, Longitude coordinates'
    )

    # One-way DRIVING distance from the client's primary facility (computed via
    # geo_utils.driving_distance on geocode / facility change — not an @api.depends
    # compute because it makes a network call).
    clinic_drive_distance_km = fields.Float(
        'Driving Distance to Clinic (km)', digits=(8, 2), readonly=True,
        help='One-way driving distance from the primary facility to this client.')
    clinic_drive_minutes = fields.Float(
        'Driving Time to Clinic (min)', digits=(8, 1), readonly=True)
    clinic_distance_method = fields.Char('Distance Source', readonly=True,
        help='google / osrm / approx (straight-line fallback)')
    clinic_distance_display = fields.Char(
        'Driving Distance', compute='_compute_clinic_distance_display')

    # Computed Fields
    visit_count = fields.Integer('Total Visits', compute='_compute_visit_count')
    
    # Relationship count fields (for smart buttons)
    caregiver_patient_count = fields.Integer(
        'Patients as Caregiver',
        compute='_compute_relationship_counts',
        help='clients I care for'
    )
    payer_patient_count = fields.Integer(
        'Patients as Payer',
        compute='_compute_relationship_counts',
        help='clients I pay for'
    )
    referrer_patient_count = fields.Integer(
        'Patients as Referrer',
        compute='_compute_relationship_counts',
        help='clients I referred'
    )
    
    def _generate_patient_code(self, catchment_province=None):
        """
        Generate unique patient code in format: PP 00000YYYY
        Where:
        - PP = province code from catchment province
        - 00000 = sequential number (resets yearly, with leading zeros)
        - YYYY = current year
        """
        from datetime import datetime

        # Get catchment province (from parameter or assigned catchment province)
        if not catchment_province and self.catchment_province_id:
            catchment_province = self.catchment_province_id

        # Get province code from catchment province
        if catchment_province and catchment_province.code:
            province_code = catchment_province.code[:2] if len(catchment_province.code) >= 2 else catchment_province.code
        else:
            # If no catchment province or code, use default province code '99'
            province_code = '99'

        # Get current year
        current_year = datetime.now().year

        # Generate sequence code specific to province and year
        sequence_code = f'patient.{province_code}.{current_year}'

        # Check if sequence exists, if not create it
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', sequence_code)
        ], limit=1)

        if not sequence:
            # Create new sequence for this province/year combination
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f'Patient ID - Province {province_code} - {current_year}',
                'code': sequence_code,
                'implementation': 'standard',
                'prefix': '',
                'padding': 5,  # 5 digits with leading zeros
                'number_increment': 1,
                'number_next': 1,
            })

        # Get next sequence number
        seq_number = sequence.next_by_id()

        # Format: PP 00000YYYY (note the space)
        patient_code = f'{province_code} {seq_number}{current_year}'

        return patient_code
    
    @api.depends('province_code', 'named_area', 'apartment_number', 'building_name',
                 'house_number', 'sub_alley_number', 'alley_number', 'street', 'street2',
                 'ward_commune', 'city', 'state_id', 'zip', 'country_id')
    def _compute_vietnamese_address(self):
        """Compute formatted Vietnamese address"""
        for rec in self:
            address_parts = []

            # Building/Apartment info
            if rec.apartment_number:
                address_parts.append(f"Căn hộ {rec.apartment_number}")

            if rec.building_name:
                address_parts.append(rec.building_name)

            if rec.named_area:
                address_parts.append(rec.named_area)

            # Street address
            street_parts = []
            if rec.house_number:
                street_parts.append(rec.house_number)

            if rec.sub_alley_number:
                street_parts.append(f"Ngách {rec.sub_alley_number}")

            if rec.alley_number:
                street_parts.append(f"Ngõ {rec.alley_number}")

            if rec.street:
                street_parts.append(rec.street)

            if rec.street2:
                street_parts.append(rec.street2)

            if street_parts:
                address_parts.append(', '.join(street_parts))

            # Administrative divisions
            if rec.ward_commune:
                address_parts.append(f"Phường/Xã {rec.ward_commune}")

            if rec.city:
                address_parts.append(rec.city)

            if rec.state_id:
                address_parts.append(rec.state_id.name)

            if rec.zip:
                address_parts.append(rec.zip)

            if rec.country_id:
                address_parts.append(rec.country_id.name)

            rec.vietnamese_address = ', '.join(address_parts) if address_parts else ''

    @api.depends('birth_date')
    def _compute_age(self):
        """Compute age from birth date"""
        for partner in self:
            if partner.birth_date:
                today = date.today()
                partner.age = today.year - partner.birth_date.year - (
                    (today.month, today.day) < (partner.birth_date.month, partner.birth_date.day)
                )
            else:
                partner.age = 0
    
    @api.depends('age')
    @api.depends_context('lang')
    def _compute_age_display(self):
        """Compute age display string"""
        for partner in self:
            if partner.age:
                partner.age_display = partner.env._('%s years old', partner.age)
            else:
                partner.age_display = partner.env._('Age unknown')

    @api.depends('patient_code')
    def _compute_patient_code_display(self):
        """Compute patient code display with fallback"""
        for partner in self:
            if partner.patient_code:
                partner.patient_code_display = partner.patient_code
            else:
                partner.patient_code_display = 'Not Assigned'

    @api.depends('partner_latitude', 'partner_longitude')
    def _compute_geo_coordinates(self):
        """Compute display string for GPS coordinates"""
        for partner in self:
            if partner.partner_latitude and partner.partner_longitude:
                partner.geo_coordinates_display = f"{partner.partner_latitude:.6f}, {partner.partner_longitude:.6f}"
            else:
                partner.geo_coordinates_display = "Not geolocated"

    def write(self, vals):
        """Override write to auto-update date_localization and auto-geocode on address changes"""
        # Normalize Vietnamese phone fields for individual contacts (skip when
        # writing only to companies, e.g. the red-invoice seller).
        if any(vals.get(f) for f in self._VN_PHONE_FIELDS) and not all(p.is_company for p in self):
            for fname in self._VN_PHONE_FIELDS:
                if vals.get(fname):
                    vals[fname] = normalize_vn_phone(vals[fname])

        # Auto-set date_localization when coordinates are updated
        if ('partner_latitude' in vals or 'partner_longitude' in vals) and 'date_localization' not in vals:
            vals['date_localization'] = fields.Date.today()

        # Auto-geocode BEFORE write when Vietnamese address fields change
        address_fields = [
            'house_number', 'sub_alley_number', 'alley_number', 'street', 'street2',
            'ward_commune', 'city', 'state_id', 'country_id', 'named_area',
            'building_name', 'apartment_number', 'province_code'
        ]

        # Check if any address field was updated
        address_changed = any(field in vals for field in address_fields)

        # Pre-geocode BEFORE the main write so coordinates are included in the response
        if address_changed:
            # Process each partner individually with its own vals dict copy
            for partner in self:
                # Only auto-geocode if patient and has sufficient address info
                if partner.is_patient:
                    # Need to check with updated values
                    street = vals.get('street', partner.street)
                    city = vals.get('city', partner.city)
                    ward_commune = vals.get('ward_commune', partner.ward_commune)

                    if street or city or ward_commune:
                        try:
                            # Get coordinates synchronously BEFORE write
                            coords = partner._get_geocode_coordinates_sync(vals)
                            if coords:
                                # Add coordinates to vals so they're saved in one write
                                vals['partner_latitude'] = coords['latitude']
                                vals['partner_longitude'] = coords['longitude']
                                vals['date_localization'] = fields.Date.today()
                                _logger.info(f"Pre-geocoded for partner {partner.id}: lat={coords['latitude']}, lon={coords['longitude']}")
                        except Exception as e:
                            # Log error but don't block the save
                            _logger.warning(f"Pre-geocoding failed for partner {partner.id}: {e}")

        # Execute the write with coordinates already in vals
        result = super(ResPartner, self).write(vals)

        # Recompute one-way driving distance to the primary facility whenever the
        # client's coordinates or assigned facility change (skips the recursive
        # inner write, which only touches the clinic_drive_* fields).
        if not self.env.context.get('skip_distance_recompute') and \
                any(k in vals for k in ('partner_latitude', 'partner_longitude',
                                        'primary_facility_id')):
            for partner in self:
                if partner.is_patient:
                    partner._update_clinic_distance()
        return result

    @api.depends('clinic_drive_distance_km', 'clinic_drive_minutes')
    def _compute_clinic_distance_display(self):
        for p in self:
            if p.clinic_drive_distance_km:
                mins = (' · ~%d min' % round(p.clinic_drive_minutes)) if p.clinic_drive_minutes else ''
                p.clinic_distance_display = '%.1f km%s' % (p.clinic_drive_distance_km, mins)
            else:
                p.clinic_distance_display = ''

    def _update_clinic_distance(self):
        """Compute & store the one-way driving distance from primary_facility_id
        to this client. Safe to call after geocoding; no-op if coords missing."""
        for p in self:
            fac = p.primary_facility_id
            if not (p.partner_latitude and p.partner_longitude
                    and fac and fac.latitude and fac.longitude):
                continue
            res = geo_utils.driving_distance(
                self.env, fac.latitude, fac.longitude,
                p.partner_latitude, p.partner_longitude)
            if not res:
                continue
            p.with_context(skip_distance_recompute=True).write({
                'clinic_drive_distance_km': res['km'],
                'clinic_drive_minutes': res['minutes'],
                'clinic_distance_method': res['method'],
            })

    def _message_track(self, fields_iter, initial_values_dict):
        """
        Override _message_track to create tracking for ALL fields (for Audit Log) but filter
        what's displayed in chatter messages.

        Key insight: We must call parent with ALL fields to ensure tracking data is created,
        then filter the messages that get posted.
        """
        _logger.info(f"=== _message_track called ===")

        hidden_from_chatter_fields = {
            'is_patient', 'patient_code', 'first_name', 'last_name', 'birth_date', 'gender',
            'patient_status', 'source_type', 'partner_latitude', 'partner_longitude',
            'date_localization', 'street', 'street2', 'city', 'state_id', 'country_id', 'zip',
            'ward_commune', 'house_number', 'alley_number', 'sub_alley_number', 'named_area',
            'building_name', 'apartment_number', 'province_code', 'vietnamese_address',
            'geo_coordinates_display',
        }

        _logger.info(f"Original fields: {len(list(fields_iter))}")

        # Call parent with ALL fields so tracking data is created for Audit Log
        # The parent will create tracking data AND try to post messages
        # But we have message_post() override to filter those messages
        tracking = super()._message_track(fields_iter, initial_values_dict)

        return tracking

    def _filter_tracking_value_ids(self, tracking_value_ids):
        """
        Helper method to filter tracking_value_ids based on hidden fields.

        Shared by both message_post() and _message_log() to ensure consistent filtering.
        """
        hidden_from_chatter_fields = {
            'is_patient', 'patient_code', 'first_name', 'last_name', 'birth_date', 'gender',
            'patient_status', 'source_type', 'partner_latitude', 'partner_longitude',
            'date_localization', 'street', 'street2', 'city', 'state_id', 'country_id', 'zip',
            'ward_commune', 'house_number', 'alley_number', 'sub_alley_number', 'named_area',
            'building_name', 'apartment_number', 'province_code', 'vietnamese_address',
            'geo_coordinates_display',
        }

        filtered_tracking = []
        for tracking_value in tracking_value_ids:
            should_include = True
            if isinstance(tracking_value, (list, tuple)) and len(tracking_value) >= 3:
                tracking_dict = tracking_value[2]
                if isinstance(tracking_dict, dict):
                    field_id = tracking_dict.get('field_id')
                    if field_id:
                        try:
                            field_record = self.env['ir.model.fields'].browse(field_id)
                            field_name = field_record.name if field_record.exists() else None
                            if field_name and field_name in hidden_from_chatter_fields:
                                _logger.info(f"  Filtering out tracking for field: {field_name}")
                                should_include = False
                        except Exception as e:
                            _logger.warning(f"  Could not look up field_id {field_id}: {e}")

            if should_include:
                filtered_tracking.append(tracking_value)

        return filtered_tracking

    def message_post(self, **kwargs):
        """
        Override message_post to filter tracking_value_ids at the point of posting.

        This catches tracking messages from _message_track() before they're displayed.
        """
        if 'tracking_value_ids' in kwargs and kwargs['tracking_value_ids']:
            _logger.info(f"=== message_post called with tracking_value_ids ===")
            _logger.info(f"Original tracking_value_ids count: {len(kwargs['tracking_value_ids'])}")

            filtered_tracking = self._filter_tracking_value_ids(kwargs['tracking_value_ids'])
            _logger.info(f"Filtered tracking_value_ids: {len(filtered_tracking)} kept")

            if filtered_tracking:
                kwargs['tracking_value_ids'] = filtered_tracking
            else:
                # Remove tracking_value_ids if none remain
                kwargs.pop('tracking_value_ids', None)
                _logger.info(f"All tracking values filtered out, removing tracking_value_ids key")

        return super().message_post(**kwargs)

    def _message_log(self, **kwargs):
        """
        Override _message_log to hide tracking messages for sensitive fields from chatter.

        Strategy:
        1. Separate hidden and visible tracking values based on field names
        2. Post message with ONLY visible tracking values (for clean chatter)
        3. Create tracking records for hidden fields WITHOUT attaching to any message

        This ensures:
        - Chatter displays only non-sensitive field changes
        - Audit Log has complete tracking data (via mail.tracking.value records)
        - NO empty/blank messages appear in chatter
        """
        hidden_from_chatter_fields = {
            'is_patient', 'patient_code', 'first_name', 'last_name', 'birth_date', 'gender',
            'patient_status', 'source_type', 'partner_latitude', 'partner_longitude',
            'date_localization', 'street', 'street2', 'city', 'state_id', 'country_id', 'zip',
            'ward_commune', 'house_number', 'alley_number', 'sub_alley_number', 'named_area',
            'building_name', 'apartment_number', 'province_code', 'vietnamese_address',
            'geo_coordinates_display',
        }

        original_tracking_ids = kwargs.get('tracking_value_ids', [])
        base_kwargs = dict(kwargs)
        if original_tracking_ids:
            _logger.info(f"=== _message_log called with {len(original_tracking_ids)} tracking values ===")

            # Separate hidden and visible tracking values
            visible_tracking = []
            hidden_tracking = []

            for tracking_value in original_tracking_ids:
                is_hidden = False
                field_name = None

                # Try to extract field name from tracking value
                if isinstance(tracking_value, (list, tuple)) and len(tracking_value) >= 3:
                    tracking_dict = tracking_value[2]
                    if isinstance(tracking_dict, dict):
                        field_id = tracking_dict.get('field_id')

                        # Try to get field name from field_id
                        if field_id:
                            try:
                                field_record = self.env['ir.model.fields'].browse(field_id)
                                if field_record.exists():
                                    field_name = field_record.name
                                    _logger.info(f"  Field lookup success: ID {field_id} = {field_name}")
                            except Exception as e:
                                _logger.warning(f"  Field lookup failed for ID {field_id}: {e}")

                        # Check if field should be hidden
                        if field_name and field_name in hidden_from_chatter_fields:
                            is_hidden = True
                            _logger.info(f"  → Hidden: {field_name}")
                        elif not field_name:
                            _logger.warning(f"  ⚠ Could not determine field name for ID {field_id}")

                if is_hidden:
                    hidden_tracking.append(tracking_value)
                else:
                    visible_tracking.append(tracking_value)

            _logger.info(f"  Result: {len(visible_tracking)} visible, {len(hidden_tracking)} hidden")

            # Post message with only visible tracking values
            message = None
            if visible_tracking:
                visible_kwargs = dict(base_kwargs)
                visible_commands = [copy.deepcopy(cmd) for cmd in visible_tracking]
                for command in visible_commands:
                    if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                        command[2].pop('mail_message_id', None)
                visible_kwargs['tracking_value_ids'] = visible_commands
                message = super()._message_log(**visible_kwargs)
                _logger.info(f"Posted visible message {message.id}")

            if hidden_tracking:
                _logger.info(f"Creating hidden tracking message for {len(hidden_tracking)} fields")
                hidden_kwargs = dict(base_kwargs)
                hidden_commands = [copy.deepcopy(cmd) for cmd in hidden_tracking]
                for command in hidden_commands:
                    if isinstance(command, (list, tuple)) and len(command) >= 3 and command[0] == 0:
                        command[2].pop('mail_message_id', None)
                hidden_kwargs['tracking_value_ids'] = hidden_commands
                hidden_kwargs['message_type'] = 'user_notification'
                hidden_kwargs['partner_ids'] = False
                hidden_kwargs['attachment_ids'] = False
                hidden_kwargs['body'] = hidden_kwargs.get('body') or '<p></p>'

                hidden_message = super()._message_log(**hidden_kwargs)
                hidden_message.sudo().write({
                    'message_type': 'user_notification',
                    'subtype_id': False,
                    'is_internal': True,
                    'body': hidden_message.body or '<p></p>',
                })
                _logger.info(f"Stored hidden tracking message {hidden_message.id}")
                if not message:
                    message = hidden_message

            return message
        else:
            # No tracking values, just call parent
            return super()._message_log(**kwargs)

    def _compute_visit_count(self):
        """Compute total FSO bookings for patients"""
        for partner in self:
            if partner.is_patient:
                # Count FSO bookings for this patient
                try:
                    fso_count = self.env['health.fieldservice.order'].search_count([
                        ('patient_id', '=', partner.id)
                    ])
                    partner.visit_count = fso_count
                except:
                    # If FSO model not available, default to 0
                    partner.visit_count = 0
            else:
                partner.visit_count = 0
    
    @api.depends('my_patients_as_caregiver', 'my_patients_as_payer', 'my_patients_as_referrer')
    def _compute_relationship_counts(self):
        """Compute healthcare relationship counts for smart buttons"""
        for partner in self:
            # Representative Side: Count patients I care for/pay for/referred
            partner.caregiver_patient_count = len(partner.my_patients_as_caregiver)
            partner.payer_patient_count = len(partner.my_patients_as_payer)
            partner.referrer_patient_count = len(partner.my_patients_as_referrer)
    
    @api.constrains('email')
    def _check_email(self):
        """Validate email format"""
        for partner in self:
            if partner.email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', partner.email):
                raise ValidationError(_('Please enter a valid email address.'))
    
    # Phone/mobile fields that follow the Vietnamese 10-digit rule.
    # Applied to individual (non-company) contacts only, so the red-invoice
    # company phone and supplier companies are never affected.
    _VN_PHONE_FIELDS = ('phone', 'mobile', 'emergency_contact_phone')

    @api.constrains('phone', 'mobile', 'emergency_contact_phone')
    def _check_phone(self):
        """Enforce the Vietnamese phone format on individual contacts.

        Companies (e.g. the red-invoice seller) are skipped. ``write``/``create``
        already normalize these values; this is the safety net for any other
        write path (imports, direct ORM writes, etc.).
        """
        for partner in self:
            if partner.is_company:
                continue
            for fname in self._VN_PHONE_FIELDS:
                value = partner[fname]
                if value:
                    normalize_vn_phone(value)  # raises ValidationError if invalid

    @api.onchange('phone', 'mobile', 'emergency_contact_phone')
    def _onchange_normalize_vn_phone(self):
        """Live-format phone fields in the form (e.g. 938038028 -> 0938038028)
        and warn immediately when an entry is not a valid number."""
        if self.is_company:
            return
        invalid = []
        for fname in self._VN_PHONE_FIELDS:
            value = self[fname]
            if value:
                try:
                    self[fname] = normalize_vn_phone(value)
                except ValidationError:
                    invalid.append(value)
        if invalid:
            return {'warning': {
                'title': _("Invalid phone number"),
                'message': _(
                    "%s is not a valid phone number.\n\n"
                    "Enter a 9-digit number (a leading 0 is added automatically) "
                    "or a 10-digit number starting with a single 0."
                ) % ", ".join(invalid),
            }}

    @api.constrains('is_patient', 'catchment_province_id')
    def _check_patient_catchment_province(self):
        """Ensure patients have a catchment province assigned"""
        for partner in self:
            if partner.is_patient and not partner.catchment_province_id:
                raise ValidationError(_('Catchment Province is required for patients. Please select a catchment province to generate a valid Patient ID.'))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set healthcare flags and customer rank for patients"""
        # Normalize Vietnamese phone fields for individual contacts.
        for vals in vals_list:
            if not vals.get('is_company'):
                for fname in self._VN_PHONE_FIELDS:
                    if vals.get(fname):
                        vals[fname] = normalize_vn_phone(vals[fname])

        partners = super().create(vals_list)
        
        # Get healthcare category references
        patient_category = self.env.ref('health_base.patient_category', raise_if_not_found=False)
        staff_category = self.env.ref('health_base.staff_category', raise_if_not_found=False)
        facility_category = self.env.ref('health_base.facility_category', raise_if_not_found=False)
        
        for partner in partners:
            # Set healthcare flags based on categories
            if patient_category and patient_category in partner.category_id:
                partner.is_patient = True
            if staff_category and staff_category in partner.category_id:
                partner.is_healthcare_staff = True
            if facility_category and facility_category in partner.category_id:
                partner.is_healthcare_facility = True
            
            # Set customer rank for patients to enable CRM integration
            if partner.is_patient:
                if not partner.customer_rank:
                    partner.customer_rank = 1
                # Generate patient code if not already set
                if not partner.patient_code:
                    partner.patient_code = partner._generate_patient_code()
                
        return partners
    
    def action_view_appointments(self):
        """Action to view patient FSO bookings"""
        if not self.is_patient:
            return False

        list_view_id = self.env.ref(
            'health_fieldservice.view_health_fso_list_ops', raise_if_not_found=False
        )
        form_view_id = self.env.ref(
            'health_fieldservice.view_health_fso_form_ops', raise_if_not_found=False
        )
        return {
            'type': 'ir.actions.act_window',
            'name': f'Service Bookings - {self.name}',
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,calendar,form',
            'views': [
                [list_view_id and list_view_id.id or False, 'list'],
                [False, 'calendar'],
                [form_view_id and form_view_id.id or False, 'form'],
            ],
            # Open in the main area (not a dialog): multi-record views like the
            # calendar cannot be switched to inside a target='new' dialog, so the
            # calendar toggle would silently no-op. Full-page keeps it working,
            # with a breadcrumb back to the client.
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
    
    def action_create_appointment(self):
        """Quick create appointment action"""
        if not self.is_patient:
            return
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Appointment'),
            'res_model': 'health.appointment',  # Will be updated when appointment model is refactored
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_name': f'Appointment - {self.name}'
            }
        }
    
    def action_activate_patient(self):
        """Activate patient - change status to active"""
        if not self.is_patient:
            return
            
        self.patient_status = 'active'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Patient Activated',
                'message': f'{self.name} has been marked as active.',
                'type': 'success'
            }
        }
    
    def action_mark_inactive(self):
        """Mark patient as inactive"""
        if not self.is_patient:
            return
            
        self.patient_status = 'inactive'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Patient Deactivated',
                'message': f'{self.name} has been marked as inactive.',
                'type': 'warning'
            }
        }
    
    def action_view_lab_results(self):
        """Action to view patient lab results"""
        if not self.is_patient:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Lab Results - {self.name}',
            'res_model': 'health.lab.result',  # Will be implemented when lab module is added
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
            'help': """<p class="o_view_nocontent_smiling_face">
                No lab results found for this patient.
            </p>
            <p>
                Lab results will be displayed here when the laboratory module is installed.
            </p>"""
        }
    
    def action_view_prescriptions(self):
        """Action to view patient prescriptions"""
        if not self.is_patient:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Prescriptions - {self.name}',
            'res_model': 'health.prescription',  # Will be implemented when pharmacy module is added
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
            'help': """<p class="o_view_nocontent_smiling_face">
                No prescriptions found for this patient.
            </p>
            <p>
                Prescriptions will be displayed here when the pharmacy module is installed.
            </p>"""
        }
    
    def action_edit_vietnamese_address(self):
        """Open modal to edit Vietnamese address fields with auto-geocode on save."""
        self.ensure_one()
        view = self.env.ref('health_base.view_health_patient_address_form', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Address'),
            'res_model': 'res.partner',
            'view_mode': 'form',
            'views': [(view.id, 'form')] if view else [(False, 'form')],
            'res_id': self.id,
            'target': 'new',
            'context': dict(
                self.env.context,
                form_view_ref='health_base.view_health_patient_address_form',
                form_view_initial_mode='edit',
            ),
            # This flag tells Odoo to reload the parent form after the modal closes
            'flags': {'mode': 'edit'},
        }
    
    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Enhanced name search for patients including patient ID"""
        if domain is None:
            domain = []

        # If searching in patient context, include patient_id in search
        if self.env.context.get('search_patients'):
            domain = domain + ['|', ('name', operator, name), ('patient_code', operator, name)]
            name = ''

        return super().name_search(
            name=name,
            domain=domain,
            operator=operator,
            limit=limit,
        )
    
    def _get_name(self):
        """Override name display for patients to include patient code"""
        name = super()._get_name()
        if self.is_patient and self.patient_code:
            return f'[{self.patient_code}] {name}'
        return name
    
    def action_view_my_patients_as_caregiver(self):
        """View patients I care for"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients Cared For by {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('primary_caregiver_id', '=', self.id)],
            'context': {'search_default_is_patient': 1},
        }
    
    def action_view_my_patients_as_payer(self):
        """View patients I pay for"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients Paid For by {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('primary_payer_id', '=', self.id)],
            'context': {'search_default_is_patient': 1},
        }
    
    def action_view_my_patients_as_referrer(self):
        """View patients I referred"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients Referred by {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('primary_referrer_id', '=', self.id)],
            'context': {'search_default_is_patient': 1},
        }

    # ========================================================================
    # ADDRESS AUTOCOMPLETE & GEOLOCATION METHODS
    # ========================================================================

    def action_geocode_address_photon(self):
        """
        Geocode address using Photon API (Komoot - Free, OpenStreetMap-based)
        No API key required, worldwide coverage
        """
        for partner in self:
            # Build address string from components
            address_parts = []
            if partner.street:
                address_parts.append(partner.street)
            if partner.street2:
                address_parts.append(partner.street2)
            if partner.city:
                address_parts.append(partner.city)
            if partner.state_id:
                address_parts.append(partner.state_id.name)
            if partner.country_id:
                address_parts.append(partner.country_id.name)

            address = ', '.join(address_parts)

            if not address:
                raise UserError(_('Please fill in at least the street or city before geocoding.'))

            try:
                # Call Photon API (free, no authentication)
                url = 'https://photon.komoot.io/api/'
                params = {
                    'q': address,
                    'limit': 1
                }

                # Add location bias based on country center (Photon doesn't support country filtering)
                country_centers = {
                    'vn': {'lat': 16.0, 'lon': 106.0},  # Vietnam center
                    'id': {'lat': -2.5, 'lon': 118.0},  # Indonesia center
                    'sg': {'lat': 1.35, 'lon': 103.8},  # Singapore center
                    'jp': {'lat': 36.2, 'lon': 138.2},  # Japan center
                }

                if partner.country_id and partner.country_id.code:
                    country_code = partner.country_id.code.lower()
                    if country_code in country_centers:
                        center = country_centers[country_code]
                        params['lat'] = center['lat']
                        params['lon'] = center['lon']

                _logger.info(f"Geocoding address via Photon API: {address}")
                headers = {
                    'User-Agent': 'VAFHS-Healthcare-System/1.0 (Odoo; contact@vafhs.com)',
                    'Accept': 'application/json',
                }
                response = requests.get(url, params=params, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    if data.get('features') and len(data['features']) > 0:
                        # Extract coordinates (Photon returns [lon, lat] in GeoJSON format)
                        coords = data['features'][0]['geometry']['coordinates']
                        longitude = coords[0]
                        latitude = coords[1]

                        # Update partner with coordinates
                        partner.write({
                            'partner_longitude': longitude,
                            'partner_latitude': latitude,
                            'date_localization': fields.Date.today()
                        })

                        _logger.info(f"Geocoded successfully: lat={latitude}, lon={longitude}")

                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Geocoding Successful'),
                                'message': _('Address geocoded: %.6f, %.6f') % (latitude, longitude),
                                'type': 'success',
                                'sticky': False,
                            }
                        }
                    else:
                        raise UserError(_('No coordinates found for this address. Please check the address details.'))
                else:
                    raise UserError(_('Geocoding service error (HTTP %s). Please try again later.') % response.status_code)

            except requests.RequestException as e:
                _logger.error(f"Photon API request failed: {e}")
                raise UserError(_('Unable to connect to geocoding service. Please check your internet connection.'))
            except Exception as e:
                _logger.error(f"Geocoding error: {e}")
                raise UserError(_('Geocoding failed: %s') % str(e))

    def _get_geocode_coordinates_sync(self, vals=None):
        """
        Synchronously get geocode coordinates for Vietnamese address.
        Returns dict with latitude/longitude or None if geocoding fails.

        Args:
            vals: dict of values being written (to handle new values before they're saved)

        Returns:
            dict: {'latitude': float, 'longitude': float} or None
        """
        self.ensure_one()

        # Merge current values with new values from vals
        if vals is None:
            vals = {}

        # Build Vietnamese-style address query
        address_parts = []

        # Start with house/street level details
        street_parts = []
        house_number = vals.get('house_number', self.house_number)
        alley_number = vals.get('alley_number', self.alley_number)
        sub_alley_number = vals.get('sub_alley_number', self.sub_alley_number)
        street = vals.get('street', self.street)

        if house_number:
            street_parts.append(house_number)
        if alley_number:
            street_parts.append(f"Ngõ {alley_number}")
        if sub_alley_number:
            street_parts.append(f"Ngách {sub_alley_number}")
        if street:
            street_parts.append(street)

        if street_parts:
            address_parts.append(' '.join(street_parts))

        # Add ward/commune
        ward_commune = vals.get('ward_commune', self.ward_commune)
        if ward_commune:
            address_parts.append(ward_commune)

        # Add city/district
        city = vals.get('city', self.city)
        if city:
            address_parts.append(city)

        # Add state/province
        state_id = vals.get('state_id', self.state_id.id if self.state_id else None)
        if state_id:
            state = self.env['res.country.state'].browse(state_id)
            if state:
                address_parts.append(state.name)

        # Add country
        country_id = vals.get('country_id', self.country_id.id if self.country_id else None)
        if country_id:
            country = self.env['res.country'].browse(country_id)
            if country:
                address_parts.append(country.name)
        else:
            address_parts.append('Vietnam')  # Default

        address = ', '.join(address_parts)

        if not address or len(address) < 5:
            _logger.debug(f"Address too short for geocoding: {address}")
            return None

        try:
            # Call Photon API
            url = 'https://photon.komoot.io/api/'
            params = {
                'q': address,
                'limit': 1
            }

            # Add Vietnam center bias
            if not country_id or country_id == 241:  # Vietnam ID
                params['lat'] = 16.0
                params['lon'] = 106.0

            _logger.info(f"Geocoding address synchronously: {address}")
            headers = {
                'User-Agent': 'VAFHS-Healthcare-System/1.0 (Odoo; contact@vafhs.com)',
                'Accept': 'application/json',
            }
            response = requests.get(url, params=params, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()

                if data.get('features') and len(data['features']) > 0:
                    # Extract coordinates
                    coords = data['features'][0]['geometry']['coordinates']
                    longitude = coords[0]
                    latitude = coords[1]

                    _logger.info(f"Geocoded successfully: lat={latitude}, lon={longitude}")
                    return {
                        'latitude': latitude,
                        'longitude': longitude
                    }
                else:
                    _logger.debug(f"No geocoding results for: {address}")
                    return None
            else:
                _logger.warning(f"Geocoding API returned status {response.status_code}")
                return None

        except requests.RequestException as e:
            _logger.warning(f"Geocoding network error: {e}")
            return None
        except Exception as e:
            _logger.warning(f"Geocoding failed: {e}")
            return None

    def _auto_geocode_vietnamese_address(self):
        """
        Automatically geocode address using Vietnamese address fields.
        DEPRECATED: Use _get_geocode_coordinates_sync() instead.
        Kept for backward compatibility with manual geocode button.
        """
        self.ensure_one()

        # Build Vietnamese-style address query for better geocoding results
        address_parts = []

        # Start with house/street level details
        street_parts = []
        if self.house_number:
            street_parts.append(self.house_number)
        if self.alley_number:
            street_parts.append(f"Ngõ {self.alley_number}")
        if self.sub_alley_number:
            street_parts.append(f"Ngách {self.sub_alley_number}")
        if self.street:
            street_parts.append(self.street)

        if street_parts:
            address_parts.append(' '.join(street_parts))

        # Add ward/commune (important for Vietnam geocoding)
        if self.ward_commune:
            address_parts.append(self.ward_commune)

        # Add city/district
        if self.city:
            address_parts.append(self.city)

        # Add state/province
        if self.state_id:
            address_parts.append(self.state_id.name)

        # Always add country for better results
        if self.country_id:
            address_parts.append(self.country_id.name)
        else:
            address_parts.append('Vietnam')  # Default to Vietnam

        address = ', '.join(address_parts)

        if not address or len(address) < 5:
            _logger.debug(f"Address too short for geocoding: {address}")
            return False

        try:
            # Call Photon API
            url = 'https://photon.komoot.io/api/'
            params = {
                'q': address,
                'limit': 1
            }

            # Add Vietnam center bias for better results
            if not self.country_id or self.country_id.code.lower() == 'vn':
                params['lat'] = 16.0
                params['lon'] = 106.0

            _logger.info(f"Auto-geocoding address for partner {self.id}: {address}")
            headers = {
                'User-Agent': 'VAFHS-Healthcare-System/1.0 (Odoo; contact@vafhs.com)',
                'Accept': 'application/json',
            }
            response = requests.get(url, params=params, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()

                if data.get('features') and len(data['features']) > 0:
                    # Extract coordinates
                    coords = data['features'][0]['geometry']['coordinates']
                    longitude = coords[0]
                    latitude = coords[1]

                    # Update coordinates using normal write to trigger frontend notification
                    # Safe from recursion since address_fields won't be in this vals dict
                    self.write({
                        'partner_longitude': longitude,
                        'partner_latitude': latitude,
                        'date_localization': fields.Date.today()
                    })

                    _logger.info(f"Auto-geocoded successfully: lat={latitude}, lon={longitude}")
                    return True
                else:
                    _logger.debug(f"No geocoding results found for: {address}")
                    return False
            else:
                _logger.warning(f"Geocoding API returned status {response.status_code}")
                return False

        except requests.RequestException as e:
            _logger.warning(f"Auto-geocoding network error: {e}")
            return False
        except Exception as e:
            _logger.warning(f"Auto-geocoding failed: {e}")
            return False

    @api.model
    def photon_address_search(self, query, country_code=None, limit=10):
        """
        Search addresses using Photon API (for autocomplete widget)

        Args:
            query (str): Search query (address text)
            country_code (str): ISO country code for location bias (e.g., 'VN', 'ID', 'SG', 'JP')
            limit (int): Maximum number of results (default 10)

        Returns:
            list: List of address suggestions with coordinates
        """
        if not query or len(query) < 3:
            return []

        try:
            url = 'https://photon.komoot.io/api/'
            params = {
                'q': query,
                'limit': min(limit, 50)  # Photon max is 50
            }

            # Add location bias based on country (center coordinates)
            # Note: Photon API doesn't support 'countrycodes' parameter
            # Instead, we bias results toward the country's center coordinates
            country_centers = {
                'vn': {'lat': 16.0, 'lon': 106.0},  # Vietnam center
                'id': {'lat': -2.5, 'lon': 118.0},  # Indonesia center
                'sg': {'lat': 1.35, 'lon': 103.8},  # Singapore center
                'jp': {'lat': 36.2, 'lon': 138.2},  # Japan center
            }

            if country_code and country_code.lower() in country_centers:
                center = country_centers[country_code.lower()]
                params['lat'] = center['lat']
                params['lon'] = center['lon']

            _logger.info(f"Photon API request - URL: {url}, Params: {params}")
            headers = {
                'User-Agent': 'VAFHS-Healthcare-System/1.0 (Odoo; contact@vafhs.com)',
                'Accept': 'application/json',
            }
            response = requests.get(url, params=params, headers=headers, timeout=5)
            _logger.info(f"Photon API response - Status: {response.status_code}, URL: {response.url}")

            if response.status_code == 200:
                data = response.json()
                suggestions = []

                for feature in data.get('features', []):
                    props = feature.get('properties', {})
                    geom = feature.get('geometry', {})
                    coords = geom.get('coordinates', [None, None])

                    # Build display name from available properties
                    name_parts = []
                    if props.get('name'):
                        name_parts.append(props['name'])
                    if props.get('street'):
                        name_parts.append(props['street'])
                    if props.get('housenumber'):
                        name_parts.append(props['housenumber'])
                    if props.get('city'):
                        name_parts.append(props['city'])
                    if props.get('state'):
                        name_parts.append(props['state'])
                    if props.get('country'):
                        name_parts.append(props['country'])

                    display_name = ', '.join(name_parts) if name_parts else 'Unknown location'

                    suggestion = {
                        'display': display_name,
                        'street': props.get('street') or props.get('name') or '',
                        'housenumber': props.get('housenumber') or '',
                        'city': props.get('city') or '',
                        'state': props.get('state') or '',
                        'postcode': props.get('postcode') or '',
                        'country': props.get('country') or '',
                        'country_code': props.get('countrycode', '').upper(),
                        'lat': coords[1],  # GeoJSON format: [lon, lat]
                        'lon': coords[0],
                    }

                    suggestions.append(suggestion)

                return suggestions
            else:
                _logger.warning(f"Photon API returned status {response.status_code}, Response: {response.text[:200]}")
                return []

        except Exception as e:
            _logger.error(f"Photon address search failed: {e}", exc_info=True)
            return []
