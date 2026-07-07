# -*- coding: utf-8 -*-
"""FSO extension: assessments carried out during a visit."""
from odoo import _, api, fields, models


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    form_instance_ids = fields.One2many(
        'health.form.instance', 'order_id', string='Assessments')
    form_instance_count = fields.Integer(
        compute='_compute_form_instance_count', string='Assessment Count')

    def _compute_form_instance_count(self):
        counts = {}
        if self.ids:
            for group in self.env['health.form.instance']._read_group(
                    [('order_id', 'in', self.ids)],
                    ['order_id'], ['__count']):
                counts[group[0].id] = group[1]
        for order in self:
            order.form_instance_count = counts.get(order.id, 0)

    def action_new_form_instance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Assessment'),
            'res_model': 'health.form.instance',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_order_id': self.id,
                'default_client_id': self.patient_id.id,
            },
        }

    def action_view_form_instances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assessments'),
            'res_model': 'health.form.instance',
            'view_mode': 'list,form,graph',
            'domain': [('order_id', '=', self.id)],
            'context': {
                'default_order_id': self.id,
                'default_client_id': self.patient_id.id,
            },
        }
