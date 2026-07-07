# -*- coding: utf-8 -*-
"""Client extension: medication orders smart button (spec §3.2.6)."""
from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    medication_order_ids = fields.One2many(
        'health.medication.order', 'client_id',
        string='Medication Orders')
    medication_order_count = fields.Integer(
        compute='_compute_medication_order_count')

    def _compute_medication_order_count(self):
        counts = {}
        if self.ids:
            for group in self.env['health.medication.order']._read_group(
                    [('client_id', 'in', self.ids)],
                    ['client_id'], ['__count']):
                counts[group[0].id] = group[1]
        for partner in self:
            partner.medication_order_count = counts.get(partner.id, 0)

    def action_view_medication_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Medication Orders'),
            'res_model': 'health.medication.order',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }
