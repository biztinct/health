# -*- coding: utf-8 -*-
"""Client extension — vitals smart button + thresholds
(clinical spec §2.2.5)."""
from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    observation_ids = fields.One2many(
        'health.observation', 'client_id', string='Observations')
    vitals_threshold_ids = fields.One2many(
        'health.vitals.threshold', 'client_id',
        string='Vitals Alert Thresholds')
    observation_count = fields.Integer(
        compute='_compute_observation_count', string='Vitals')

    def _compute_observation_count(self):
        counts = dict(self.env['health.observation']._read_group(
            [('client_id', 'in', self.ids)],
            groupby=['client_id'], aggregates=['__count']))
        for partner in self:
            partner.observation_count = counts.get(partner, 0)

    def action_view_observations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vitals'),
            'res_model': 'health.observation',
            'view_mode': 'list,graph,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }
