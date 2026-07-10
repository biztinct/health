# -*- coding: utf-8 -*-
"""Extend the PWA bell notification type with a family-message value.

NOTE (report-back c): the shipped PWA bell (health_pwa app.js) switches on
``notification_type`` with NO default branch, so an unknown type renders an
empty card in today's app shell. We add the correct data-model value here (so
the queue rows are semantically honest and a future PWA-versioned phase can add
the render case) and rely on the VAPID push as the working in-app signal today.
We do NOT touch any PWA asset (conventions §3/§4).
"""
from odoo import fields, models


class PwaStaffNotification(models.Model):
    _inherit = 'health.pwa.staff.notification'

    notification_type = fields.Selection(
        selection_add=[('family_message', 'Family Message')],
        ondelete={'family_message': 'cascade'})
