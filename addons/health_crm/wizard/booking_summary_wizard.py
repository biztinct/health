# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class BookingSummaryWizard(models.TransientModel):
    _name = 'health.booking.summary.wizard'
    _description = 'Booking Summary'

    booking_ids = fields.Many2many(
        'health.fieldservice.order',
        'booking_summary_wiz_fso_rel',
        'wizard_id', 'fso_id',
        string='Created Bookings',
    )
    booking_count = fields.Integer(compute='_compute_summary')
    summary_text = fields.Text(compute='_compute_summary')
    source_wizard = fields.Selection([
        ('booking', 'Single Booking'),
        ('recurring', 'Recurring Booking'),
    ])

    @api.depends('booking_ids')
    def _compute_summary(self):
        for wiz in self:
            bookings = wiz.booking_ids
            wiz.booking_count = len(bookings)
            if bookings:
                facility = bookings[0].facility_id.name if bookings[0].facility_id else ''
                service_type = bookings[0].service_type or ''
                if len(bookings) == 1:
                    wiz.summary_text = _('%s at %s') % (service_type.replace('_', ' ').title(), facility)
                else:
                    dates = bookings.mapped('scheduled_datetime')
                    valid_dates = [d for d in dates if d]
                    if valid_dates:
                        first = min(valid_dates).strftime('%d/%m/%Y')
                        last = max(valid_dates).strftime('%d/%m/%Y')
                        wiz.summary_text = _('%s at %s\nFrom %s to %s') % (
                            service_type.replace('_', ' ').title(), facility, first, last)
                    else:
                        wiz.summary_text = _('%s at %s') % (service_type.replace('_', ' ').title(), facility)
            else:
                wiz.summary_text = ''

    def _open_summary(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings Created'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_add_services(self):
        services_wiz = self.env['health.booking.services.wizard'].create({
            'booking_ids': [(6, 0, self.booking_ids.ids)],
        })
        return services_wiz._open_wizard()

    def action_view_bookings(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Bookings'),
            'res_model': 'health.fieldservice.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.booking_ids.ids)],
            'target': 'current',
        }

    def action_done(self):
        return {'type': 'ir.actions.act_window_close'}
