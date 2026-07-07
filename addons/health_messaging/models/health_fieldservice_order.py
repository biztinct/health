# -*- coding: utf-8 -*-
"""FSO messaging triggers + smart button.

Hook point is a write() override (not an action method): booking
confirmation/cancellation reach `confirmed`/`cancelled` through several
paths (direct state write, stage auto-sync, action methods), and only a
write override catches every one. A messaging failure must NEVER block the
booking workflow — the trigger is try/except-wrapped."""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    outbound_message_count = fields.Integer(
        compute='_compute_outbound_message_count')

    def _compute_outbound_message_count(self):
        counts = {}
        if self.ids:
            for group in self.env['health.outbound.message']._read_group(
                    [('fso_id', 'in', self.ids)], ['fso_id'], ['__count']):
                counts[group[0].id] = group[1]
        for order in self:
            order.outbound_message_count = counts.get(order.id, 0)

    def write(self, vals):
        track = 'state' in vals or 'stage_id' in vals
        before = {order.id: order.state for order in self} if track else {}
        result = super().write(vals)
        if track:
            for order in self:
                old, new = before.get(order.id), order.state
                if old == new:
                    continue
                try:
                    if new == 'confirmed':
                        self.env['health.outbound.message'].process_purpose(
                            order, 'booking_confirmation')
                    elif new == 'cancelled' and old in ('confirmed',
                                                        'assigned'):
                        self.env['health.outbound.message'].process_purpose(
                            order, 'cancellation_notice')
                except Exception:  # noqa: BLE001 — never block the booking
                    _logger.exception(
                        'Visit messaging trigger failed for FSO %s', order.id)
        return result

    def action_view_outbound_messages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Messages'),
            'res_model': 'health.outbound.message',
            'view_mode': 'list,form',
            'domain': [('fso_id', '=', self.id)],
            'context': {'default_fso_id': self.id,
                        'default_partner_id': self.patient_id.id},
        }
