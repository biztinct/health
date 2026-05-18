# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DuplicateBookingWizard(models.TransientModel):
    _name = 'health.duplicate.booking.wizard'
    _description = 'Duplicate Booking Wizard'

    source_fso_id = fields.Many2one(
        'health.fieldservice.order', string='Source Booking',
        required=True, readonly=True,
    )
    booking_date = fields.Date(
        'Booking Date', required=True, default=fields.Date.today,
    )
    booking_time = fields.Float('Booking Time')
    booking_duration = fields.Float(
        'Duration (Hours)', default=1.0,
    )

    def action_duplicate_booking(self):
        self.ensure_one()
        src = self.source_fso_id

        from datetime import datetime
        import pytz

        tz_name = src.booking_timezone or src.facility_id.timezone if src.facility_id else 'Asia/Ho_Chi_Minh'
        tz = pytz.timezone(tz_name or 'Asia/Ho_Chi_Minh')
        hours = int(self.booking_time)
        minutes = int(round((self.booking_time - hours) * 60))
        local_dt = datetime.combine(self.booking_date, datetime.min.time()).replace(
            hour=hours, minute=minutes,
        )
        local_dt = tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

        vals = {
            'patient_id': src.patient_id.id,
            'service_type': src.service_type,
            'service_location': src.service_location,
            'facility_id': src.facility_id.id if src.facility_id else False,
            'booking_timezone': tz_name,
            'scheduled_datetime': utc_dt,
            'scheduled_duration': int(self.booking_duration * 60),
            'intake_notes': src.intake_notes,
            'commission_due_to': src.commission_due_to.id if src.commission_due_to else False,
            'commission_percentage': src.commission_percentage,
            'commission_duration': src.commission_duration,
            'crm_lead_id': src.crm_lead_id.id if src.crm_lead_id else False,
        }

        new_fso = self.env['health.fieldservice.order'].create(vals)

        staff_update = {}
        if src.assigned_staff_ids:
            staff_update['assigned_staff_ids'] = [(6, 0, src.assigned_staff_ids.ids)]
        if src.assigned_doctor_ids:
            staff_update['assigned_doctor_ids'] = [(6, 0, src.assigned_doctor_ids.ids)]
        if src.primary_nurse_id:
            staff_ids = set(src.assigned_staff_ids.ids) if src.assigned_staff_ids else set()
            staff_ids.add(src.primary_nurse_id.id)
            staff_update['assigned_staff_ids'] = [(6, 0, list(staff_ids))]
        if staff_update:
            new_fso.write(staff_update)

        if src.sale_order_id:
            new_fso.action_create_and_open_quote()

        view = self.env.ref('health_fieldservice.view_health_fso_form_ops', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': new_fso.display_name or _('Booking'),
            'res_model': 'health.fieldservice.order',
            'res_id': new_fso.id,
            'view_mode': 'form',
            'views': [[view.id if view else False, 'form']],
            'target': 'current',
        }
