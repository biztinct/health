# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HealthQuickBookingWizard(models.TransientModel):
    """Quick 2-step booking wizard launched from Client form.

    All client details (catchment province, facility, address) are
    inherited from the client record automatically.
    """
    _name = 'health.quick.booking.wizard'
    _description = 'Quick Booking Wizard'

    current_step = fields.Selection([
        ('1_services', 'Service Requirements'),
        ('2_booking', 'Booking Details'),
    ], string='Current Step', default='1_services', required=True)

    client_id = fields.Many2one(
        'res.partner', string='Client',
        domain="[('is_patient', '=', True)]",
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # === Service Requirements ===

    service_category = fields.Selection([
        ('medical', 'Medical Care'),
        ('nursing', 'Nursing Care'),
        ('therapy', 'Therapy'),
        ('companion', 'Companion Care'),
        ('other', 'Other'),
    ], string='Category', default='nursing')

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
    ], string='Service Type', default='home_visit', required=True)

    service_subcategory = fields.Char('Sub-Category')

    service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('nursing_home', 'Nursing Home'),
        ('office', 'Office'),
        ('online', 'Online/Telemedicine'),
        ('other', 'Other Location'),
    ], string='Service Location', default='home')

    service_notes = fields.Text('Service Notes')

    # === Booking Details ===

    booking_date = fields.Date('Booking Date', default=fields.Date.today)
    booking_time = fields.Float('Booking Time')
    booking_duration = fields.Float('Duration (Hours)', default=1.0)
    booking_notes = fields.Text('Booking Notes')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Province',
    )
    facility_id = fields.Many2one(
        'health.facility', string='Healthcare Facility',
        domain="[('active', '=', True), ('catchment_province_id', '=', catchment_province_id)]",
    )

    @api.onchange('service_type')
    def _onchange_service_type(self):
        if self.service_type == 'telemedicine':
            self.service_location = 'online'
        elif self.service_type in ('home_visit', 'follow_up'):
            self.service_location = 'home'
        elif self.service_type == 'clinic_visit':
            self.service_location = 'clinic'

    @api.onchange('catchment_province_id')
    def _onchange_catchment_province_id(self):
        if self.facility_id and self.facility_id.catchment_province_id != self.catchment_province_id:
            self.facility_id = False

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        client_id = self.env.context.get('default_client_id')
        if client_id:
            client = self.env['res.partner'].browse(client_id)
            if client.exists():
                if 'catchment_province_id' in fields_list and client.catchment_province_id:
                    defaults['catchment_province_id'] = client.catchment_province_id.id
                if 'facility_id' in fields_list and client.primary_facility_id:
                    defaults['facility_id'] = client.primary_facility_id.id
        return defaults

    # === Navigation ===

    def action_next_step(self):
        self.ensure_one()
        if self.current_step == '1_services':
            if not self.service_type:
                raise ValidationError(_('Please select a service type.'))
            self.current_step = '2_booking'
        return self._reload()

    def action_prev_step(self):
        self.ensure_one()
        if self.current_step == '2_booking':
            self.current_step = '1_services'
        return self._reload()

    def _reload(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Booking'),
            'res_model': 'health.quick.booking.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # === Create Booking ===

    def action_create_booking(self):
        self.ensure_one()
        if not self.client_id:
            raise ValidationError(_('Please select a Client.'))
        client = self.client_id

        if not self.facility_id:
            raise ValidationError(_('Please select a Healthcare Facility.'))

        booking_vals = {
            'patient_id': client.id,
            'service_type': self.service_type or 'consultation',
            'scheduled_datetime': self._get_scheduled_datetime(),
            'scheduled_duration': int(self.booking_duration * 60),
            'service_location': self.service_location,
            'intake_notes': self.booking_notes,
            'facility_id': self.facility_id.id,
            'booking_timezone': self.facility_id.timezone if self.facility_id else (
                self.catchment_province_id.timezone if self.catchment_province_id else 'Asia/Ho_Chi_Minh'
            ),
        }

        booking = self.env['health.fieldservice.order'].create(booking_vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'ops_booking_detail',
            'name': booking.display_name or booking.name or _('Booking'),
            'target': 'current',
            'context': {'active_id': booking.id},
        }

    def _get_scheduled_datetime(self):
        from datetime import datetime
        import pytz
        if self.booking_date:
            hours = int(self.booking_time)
            minutes = int((self.booking_time - hours) * 60)
            naive_local = datetime.combine(
                self.booking_date,
                datetime.min.time()
            ).replace(hour=hours, minute=minutes)
            tz_name = 'Asia/Ho_Chi_Minh'
            if self.facility_id and self.facility_id.timezone:
                tz_name = self.facility_id.timezone
            elif self.catchment_province_id and self.catchment_province_id.timezone:
                tz_name = self.catchment_province_id.timezone
            facility_tz = pytz.timezone(tz_name)
            local_dt = facility_tz.localize(naive_local)
            return local_dt.astimezone(pytz.utc).replace(tzinfo=None)
        return False
