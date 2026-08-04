# -*- coding: utf-8 -*-
from odoo import fields, models


class HrLeave(models.Model):
    """Time Off, scoped to the area the staff member works in.

    The Time Off leaf is on the OPERATIONS sidebar and lists leave across the
    whole company. An ops manager in Hanoi has no business reading a Ho Chi
    Minh City nurse's medical leave, so the record inherits the employee's
    area — the same source the Healthcare Staff and Schedules leaves use.
    """
    _inherit = 'hr.leave'

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        related='employee_id.staff_catchment_province_id',
        store=True, index=True, readonly=True)
