# -*- coding: utf-8 -*-
"""Append-only, PHI-encrypted family <-> care-team message.

One row per message on a :class:`health.family.thread`. The narrative body is
encrypted at rest with the clinical-note dual-field pattern (a stored
``body_enc`` column + a NON-STORED computed plaintext ``body``); never search
or order on ``body`` (conventions ledger §5.19) — the inbox orders/filters on
thread metadata only.

Messages are append-only (conventions ledger §5.17): once created, the content
fields cannot be rewritten and the row cannot be deleted below system-admin.
Only the read-tracking flags may change.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext

from odoo.addons.health_phi_encryption.models import phi_crypto

_logger = logging.getLogger(__name__)

BODY_MAX = 2000
# Content fields that must never change after create (append-only guard).
_LOCKED_FIELDS = frozenset({
    'body', 'body_enc', 'direction', 'thread_id', 'fso_id',
    'author_user_id', 'author_label',
})


class HealthFamilyMessage(models.Model):
    _name = 'health.family.message'
    _description = 'Family Message'
    _order = 'create_date asc, id asc'

    thread_id = fields.Many2one(
        'health.family.thread', string='Thread', required=True,
        index=True, ondelete='cascade')
    direction = fields.Selection([
        ('in', 'Family → Team'),
        ('out', 'Team → Family'),
    ], required=True, index=True)
    # -- encrypted storage (the dual-field clone) --------------------------
    body_enc = fields.Text('Body (encrypted)')
    body = fields.Text(
        'Message', compute='_compute_body', inverse='_inverse_body')
    # -- context / provenance ---------------------------------------------
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit Context',
        index=True, ondelete='set null',
        help='The visit this message was sent in the context of.')
    author_user_id = fields.Many2one(
        'res.users', string='Author (team)', ondelete='set null',
        help='Set for team → family replies.')
    author_label = fields.Char(
        string='Author', help='Denormalized display name of the sender '
                              '("Con gái (Daughter)" for a family message).')
    read_by_ops = fields.Boolean(string='Read by team', default=False)
    read_by_family = fields.Boolean(
        string='Read by family', default=False,
        help='Set when the token page renders this message to the family.')

    # ------------------------------------------------------------------
    # Crypto dual-field (conventions §1 / §5.19)
    # ------------------------------------------------------------------
    @api.depends('body_enc')
    def _compute_body(self):
        for rec in self:
            rec.body = phi_crypto.decrypt(self.env, rec.body_enc) or False

    def _inverse_body(self):
        # Reached only if someone assigns ``.body`` on an existing record; the
        # write guard then blocks the resulting body_enc change. On create the
        # body is set directly as ``body_enc`` (see create) so this does not
        # fire during the normal flow.
        for rec in self:
            rec.body_enc = (phi_crypto.encrypt(self.env, rec.body)
                            if rec.body else False)

    # ------------------------------------------------------------------
    # Sanitization (binding: plain text only, length-capped, escaped at render)
    # ------------------------------------------------------------------
    @api.model
    def _sanitize_body(self, raw):
        """Strip HTML to plain text and enforce the length cap. Raises when the
        body is over the cap so both entry points refuse it identically."""
        text = html2plaintext(raw or '').strip()
        if len(text) > BODY_MAX:
            raise ValidationError(_(
                'Message is too long (max %s characters).') % BODY_MAX)
        return text

    # ------------------------------------------------------------------
    # Append-only lifecycle
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Encrypt the sanitized body straight into the stored column so the
            # inverse never fires during create (keeps the append-only write
            # guard clean).
            if 'body' in vals:
                plain = self._sanitize_body(vals.pop('body'))
                vals['body_enc'] = (phi_crypto.encrypt(self.env, plain)
                                    if plain else False)
        return super().create(vals_list)

    def write(self, vals):
        locked = _LOCKED_FIELDS.intersection(vals)
        if locked:
            raise UserError(_(
                'Family messages are append-only; %s cannot be modified.')
                % ', '.join(sorted(locked)))
        return super().write(vals)

    def unlink(self):
        # Append-only: deletion is reserved for system administrators (and the
        # module-uninstall path, which runs as the superuser).
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Family messages are append-only and cannot be deleted.'))
        return super().unlink()
