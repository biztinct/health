# -*- coding: utf-8 -*-
"""FSO extension (clinical spec §1.2.5).

Carries the compiled visit checklist and triggers task compilation
when a booking is confirmed/assigned, created in those states, or
rescheduled while in them (binding design decision: compilation is
wrapped in try/except inside _compile_tasks_for_orders and never
blocks the booking; re-runs are idempotent).
"""
from odoo import _, api, fields, models


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    careplan_task_ids = fields.One2many(
        'health.careplan.task', 'fso_id', string='Care Plan Tasks')
    careplan_task_count = fields.Integer(
        compute='_compute_careplan_task_counts', string='Care Tasks')
    careplan_task_done_count = fields.Integer(
        compute='_compute_careplan_task_counts', string='Care Tasks Done')
    has_open_careplan_tasks = fields.Boolean(
        compute='_compute_careplan_task_counts',
        help='Completion nudge: pending checklist items remain.')

    @api.depends('careplan_task_ids.state')
    def _compute_careplan_task_counts(self):
        for order in self:
            tasks = order.careplan_task_ids
            order.careplan_task_count = len(tasks)
            order.careplan_task_done_count = len(tasks.filtered(
                lambda task: task.state == 'done'))
            order.has_open_careplan_tasks = any(
                task.state == 'pending' for task in tasks)

    # ------------------------------------------------------------------
    # Compile hooks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        # Bookings born confirmed (e.g. auto-advance from a quote)
        # compile immediately; _compile_tasks_for_orders skips other
        # states and never raises.
        to_compile = orders.filtered(
            lambda order: order.state in ('confirmed', 'assigned'))
        if to_compile:
            self.env['health.careplan']._compile_tasks_for_orders(
                to_compile)
        return orders

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals or 'scheduled_datetime' in vals:
            to_compile = self.filtered(
                lambda order: order.state in ('confirmed', 'assigned'))
            if to_compile:
                self.env['health.careplan']._compile_tasks_for_orders(
                    to_compile)
        return result

    # ------------------------------------------------------------------
    # Smart button
    # ------------------------------------------------------------------
    def action_view_careplan_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Care Plan Tasks'),
            'res_model': 'health.careplan.task',
            'view_mode': 'list,form',
            'domain': [('fso_id', '=', self.id)],
            'context': {'default_fso_id': self.id},
        }
