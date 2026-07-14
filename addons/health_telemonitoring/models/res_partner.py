# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    news2_spo2_scale2 = fields.Boolean(
        string='NEWS2 SpO₂ Scale 2 (hypercapnic)',
        default=False, tracking=True,
        help='Use NEWS2 SpO₂ Scale 2 for this patient — for hypercapnic '
             'respiratory failure (e.g. COPD) with a target saturation '
             'range of 88–92%. Leave off for the default Scale 1.')

    # Phase 2 — home-device registry link (inverse of device.client_id).
    monitor_device_ids = fields.One2many(
        'health.monitor.device', 'client_id', string='Monitoring Devices')
    monitor_device_count = fields.Integer(
        string='Monitoring Devices', compute='_compute_monitor_device_count')

    def _compute_monitor_device_count(self):
        data = self.env['health.monitor.device']._read_group(
            [('client_id', 'in', self.ids)],
            groupby=['client_id'], aggregates=['__count'])
        counts = {client.id: count for client, count in data}
        for rec in self:
            rec.monitor_device_count = counts.get(rec.id, 0)
