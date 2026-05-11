# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import pytz


class RecurringBookingWizard(models.TransientModel):
    _name = 'health.recurring.booking.wizard'
    _description = 'Recurring Booking Wizard'

    current_step = fields.Selection([
        ('1_services', 'Services'),
        ('2_recurrence', 'Recurrence & Location'),
    ], default='1_services')

    client_id = fields.Many2one(
        'res.partner', string='Client', readonly=True,
        domain="[('is_patient', '=', True)]",
    )

    # ── Step 1: Service Requirements ──

    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('consultation', 'Consultation'),
        ('telemedicine', 'Telemedicine'),
        ('follow_up', 'Follow-up'),
        ('preventive', 'Preventive Care'),
        ('rehabilitation', 'Rehabilitation'),
    ], string='Service Type', default='home_visit')

    service_category = fields.Selection([
        ('medical', 'Medical Care'),
        ('nursing', 'Nursing Care'),
        ('therapy', 'Therapy'),
        ('companion', 'Companion Care'),
        ('other', 'Other'),
    ], string='Service Category', default='nursing')

    service_subcategory = fields.Char('Sub-Category')

    service_location = fields.Selection([
        ('home', 'Patient Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('nursing_home', 'Nursing Home'),
        ('other', 'Other Location'),
    ], string='Service Location', default='home')

    service_notes = fields.Text('Service Notes')

    commission_due_to = fields.Many2one('res.partner', string='Commission Due To')
    commission_percentage = fields.Float('Commission %', digits=(5, 2))
    commission_duration = fields.Selection([
        ('one_time', 'One Time'),
        ('30_days', '30 Days'),
    ], string='Commission Duration', default='one_time')

    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
    )

    # ── Step 2: Recurrence Pattern ──

    day_mon = fields.Boolean('Mon')
    day_tue = fields.Boolean('Tue')
    day_wed = fields.Boolean('Wed')
    day_thu = fields.Boolean('Thu')
    day_fri = fields.Boolean('Fri')
    day_sat = fields.Boolean('Sat')
    day_sun = fields.Boolean('Sun')

    booking_time = fields.Float('Time')
    booking_duration = fields.Float('Duration (Hours)', default=1.0)

    date_start = fields.Date('Start Date', default=fields.Date.today)
    date_end = fields.Date('End Date')

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Province',
    )
    facility_id = fields.Many2one(
        'health.facility', string='Healthcare Facility',
        domain="[('active', '=', True), ('catchment_province_id', '=', catchment_province_id)]",
    )
    booking_notes = fields.Text('Additional Notes')


    booking_count = fields.Integer(
        'Bookings to Create', compute='_compute_booking_count',
    )
    booking_summary = fields.Char(
        'Summary', compute='_compute_booking_count',
    )

    @api.onchange('service_type')
    def _onchange_service_type(self):
        if self.service_type == 'telemedicine':
            self.service_location = 'online'
        elif self.service_type in ('home_visit', 'follow_up'):
            self.service_location = 'home'
        elif self.service_type == 'clinic_visit':
            self.service_location = 'clinic'

    @api.onchange('client_id')
    def _onchange_client_for_province(self):
        if self.client_id and self.client_id.catchment_province_id:
            self.catchment_province_id = self.client_id.catchment_province_id

    @api.onchange('catchment_province_id')
    def _onchange_catchment_province_id(self):
        if self.facility_id and self.facility_id.catchment_province_id != self.catchment_province_id:
            self.facility_id = False

    def _get_selected_weekdays(self):
        days = []
        if self.day_mon: days.append(0)
        if self.day_tue: days.append(1)
        if self.day_wed: days.append(2)
        if self.day_thu: days.append(3)
        if self.day_fri: days.append(4)
        if self.day_sat: days.append(5)
        if self.day_sun: days.append(6)
        return days

    def _get_booking_dates(self):
        if not self.date_start or not self.date_end:
            return []
        weekdays = self._get_selected_weekdays()
        if not weekdays:
            return []
        dates = []
        current = self.date_start
        while current <= self.date_end:
            if current.weekday() in weekdays:
                dates.append(current)
            current += timedelta(days=1)
        return dates

    @api.depends('day_mon', 'day_tue', 'day_wed', 'day_thu', 'day_fri',
                 'day_sat', 'day_sun', 'date_start', 'date_end')
    def _compute_booking_count(self):
        day_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        for wiz in self:
            dates = wiz._get_booking_dates()
            wiz.booking_count = len(dates)
            weekdays = wiz._get_selected_weekdays()
            if dates and weekdays:
                day_str = ', '.join(day_names[d] for d in weekdays)
                wiz.booking_summary = _('%d bookings on %s') % (len(dates), day_str)
            else:
                wiz.booking_summary = _('Select days and date range')


    # ── Navigation ──

    def action_next_step(self):
        self.ensure_one()
        self._validate_step(self.current_step)
        if self.current_step == '1_services':
            self.current_step = '2_recurrence'
        return self._reload()

    def action_prev_step(self):
        self.ensure_one()
        if self.current_step == '2_recurrence':
            self.current_step = '1_services'
        return self._reload()

    def _reload(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recurring Booking'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Create Bookings ──

    def _validate_step(self, step):
        missing = []
        if step == '1_services':
            if not self.service_type:
                missing.append('Service Type')
        elif step == '2_recurrence':
            if not self.date_start:
                missing.append('Start Date')
            if not self.date_end:
                missing.append('End Date')
            if not self.facility_id:
                missing.append('Healthcare Facility')
            if not self._get_selected_weekdays():
                missing.append('At least one day of the week (Mon–Sun)')
        if missing:
            raise ValidationError(
                _('Please fill in the following required fields:\n• %s') % '\n• '.join(missing)
            )

    def action_create_recurring_bookings(self):
        self.ensure_one()
        if not self.client_id:
            raise ValidationError(_('Client is required. Please reopen the wizard from a client record.'))
        self._validate_step('2_recurrence')

        if self.date_end < self.date_start:
            raise ValidationError(_('End Date must be after Start Date.'))

        dates = self._get_booking_dates()
        if not dates:
            raise ValidationError(_('No booking dates found in the selected range.'))

        tz_name = (self.facility_id.timezone if self.facility_id
                   else self.catchment_province_id.timezone if self.catchment_province_id
                   else 'Asia/Ho_Chi_Minh')
        tz = pytz.timezone(tz_name or 'Asia/Ho_Chi_Minh')

        hours = int(self.booking_time)
        minutes = int(round((self.booking_time - hours) * 60))

        FSO = self.env['health.fieldservice.order']
        created = FSO

        for d in dates:
            local_dt = datetime.combine(d, datetime.min.time()).replace(
                hour=hours, minute=minutes,
            )
            local_dt = tz.localize(local_dt)
            utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

            vals = {
                'patient_id': self.client_id.id,
                'service_type': self.service_type,
                'service_location': self.service_location,
                'facility_id': self.facility_id.id,
                'booking_timezone': tz_name,
                'scheduled_datetime': utc_dt,
                'scheduled_duration': int(self.booking_duration * 60),
                'intake_notes': self.booking_notes,
                'commission_due_to': self.commission_due_to.id if self.commission_due_to else False,
                'commission_percentage': self.commission_percentage,
                'commission_duration': self.commission_duration,
            }
            created |= FSO.create(vals)

        # Open summary wizard
        summary_wiz = self.env['health.booking.summary.wizard'].create({
            'booking_ids': [(6, 0, created.ids)],
            'source_wizard': 'recurring',
        })
        return summary_wiz._open_summary()
