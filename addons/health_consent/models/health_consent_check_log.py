# -*- coding: utf-8 -*-
"""Append-only consent check log — compliance evidence.

Every `check_consent()` / `check_consents()` call writes one row
(create-only; write/unlink blocked). Rows are created with sudo() by
the service API so a check from any caller context always leaves
evidence, in both log-only and enforce modes (DESIGN §7.1)."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HealthConsentCheckLog(models.Model):
    _name = 'health.consent.check.log'
    _description = 'Consent Check Log'
    _order = 'create_date desc, id desc'

    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        ondelete='cascade', index=True)
    consent_type = fields.Char(
        required=True, index=True,
        help='Checked consent type (Char, not Selection: stays valid '
             'when new types such as data_sharing_family are added).')
    scope = fields.Char(
        help='Scope requested by the caller, when any.')
    at_date = fields.Date(
        help='Date the consent window was evaluated against.')
    result = fields.Boolean(
        help='True = an active consent covered the check.')
    consent_id = fields.Many2one(
        'health.consent', string='Matched Consent', ondelete='set null')
    user_id = fields.Many2one(
        'res.users', string='Checked By',
        default=lambda self: self.env.uid)
    source = fields.Char(
        help='Caller tag (context key consent_check_source), '
             'e.g. "pwa", "zalo", "fhir".')

    @api.model
    def _blocked(self):
        raise UserError(_(
            'Consent check logs are append-only compliance evidence '
            'and can never be modified or deleted.'))

    def write(self, vals):
        self._blocked()

    def unlink(self):
        # No superuser escape (EVV event precedent): uid 1 always runs
        # as su, so any su bypass voids the append-only guarantee.
        # Data-retention scripts must go through SQL deliberately.
        self._blocked()
