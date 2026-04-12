# -*- coding: utf-8 -*-
"""Staff Notification Queue for PWA bell icon.

Stores cancel/reschedule notifications that appear in the bell icon panel.
Assignment confirmation notifications come from staff.assignment state='assigned'.
"""

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class PwaStaffNotification(models.Model):
    _name = 'health.pwa.staff.notification'
    _description = 'PWA Staff Notification'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='Staff User', required=True, index=True)
    fso_id = fields.Many2one('health.fieldservice.order', string='Booking', ondelete='cascade')
    notification_type = fields.Selection([
        ('cancelled', 'Booking Cancelled'),
        ('rescheduled', 'Booking Rescheduled'),
    ], string='Type', required=True)
    patient_name = fields.Char(string='Patient Name')
    fso_name = fields.Char(string='Booking Reference')
    message = fields.Text(string='Message')
    old_datetime = fields.Char(string='Old Date/Time')
    new_datetime = fields.Char(string='New Date/Time')
    is_read = fields.Boolean(string='Read', default=False, index=True)
    active = fields.Boolean(default=True)
