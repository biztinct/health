# -*- coding: utf-8 -*-
"""FSO extension — Vitals smart button (clinical spec §2.5)."""
from odoo import _, api, fields, models


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    observation_ids = fields.One2many(
        'health.observation', 'order_id', string='Observations')
    observation_count = fields.Integer(
        compute='_compute_observation_count', string='Vitals')

    @api.depends('observation_ids')
    def _compute_observation_count(self):
        for order in self:
            order.observation_count = len(order.observation_ids)

    def action_view_observations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vitals'),
            'res_model': 'health.observation',
            'view_mode': 'list,graph,form',
            'domain': [('order_id', '=', self.id)],
            'context': {
                'default_order_id': self.id,
                'default_client_id': self.patient_id.id,
            },
        }
