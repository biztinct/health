# -*- coding: utf-8 -*-
"""``bhyt.claim.event`` — append-only claim audit / reconciliation trail.

One immutable row per claim transition. Clone of
``health.consent.check.log`` — write()/unlink() raise UNCONDITIONALLY (uid 1
runs as su, so any su escape would void the append-only guarantee, conventions
§5.4). Phase 2 adds exported/submitted/acked events.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BhytClaimEvent(models.Model):
    _name = 'bhyt.claim.event'
    _description = 'BHYT Claim Event'
    _order = 'create_date desc, id desc'

    claim_id = fields.Many2one(
        'bhyt.claim', string='Claim', required=True,
        ondelete='cascade', index=True)
    event = fields.Selection([
        ('generated', 'Generated'),
        ('marked_ready', 'Marked ready'),
        ('reset', 'Reset to draft'),
        ('cancelled', 'Cancelled'),
    ], string='Event', required=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='By', default=lambda self: self.env.uid)
    amount_snapshot = fields.Monetary(
        string='Total (snapshot)', currency_field='currency_id')
    currency_id = fields.Many2one(
        related='claim_id.currency_id', string='Currency', readonly=True)
    note = fields.Char(string='Note')

    @api.model
    def _blocked(self):
        raise UserError(_(
            'BHYT claim events are append-only audit evidence and can never '
            'be modified or deleted.'))

    def write(self, vals):
        # No superuser escape (consent-log / EVV-event precedent, §5.4).
        self._blocked()

    def unlink(self):
        self._blocked()
