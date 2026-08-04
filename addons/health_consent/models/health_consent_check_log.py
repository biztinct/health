# -*- coding: utf-8 -*-
"""Append-only consent check log — compliance evidence.

Every `check_consent()` / `check_consents()` call writes one row
(create-only; write/unlink blocked). Rows are created with sudo() by
the service API so a check from any caller context always leaves
evidence, in both log-only and enforce modes (DESIGN §7.1).

Durability (GC-3 R1, gotcha ledger §5.99): the subject FK is
`ondelete='set null'`, NOT cascade. A cascade deletes the evidence at
the SQL layer, where the Python append-only guard below never runs —
which is exactly what happened to the GC-2 probe's deny rows. The row
must outlive its subject, so the subject's label is ALSO frozen into
`client_ref` at create time."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HealthConsentCheckLog(models.Model):
    _name = 'health.consent.check.log'
    _description = 'Consent Check Log'
    _order = 'create_date desc, id desc'

    # Not `required`: a SET NULL from a deleted partner has to be able to
    # land, and a row whose subject is gone is still evidence (client_ref
    # names it). Every writer passes client_id; nothing creates rows without.
    client_id = fields.Many2one(
        'res.partner', string='Client',
        ondelete='set null', index=True)
    client_ref = fields.Char(
        string='Client (at check time)', readonly=True,
        help='Subject label frozen when the check was made — "Name [code]" '
             '— so a surviving row still names its subject after the '
             'partner record is deleted. Empty on rows created before this '
             'field existed (GC-3): no backfill was run for the handful of '
             'live rows, and a fabricated label would be worse evidence '
             'than an honest blank.')
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
    # Same shape as health.consent's own (health_consent.py:143) — the client
    # first, its facility as fallback. A row whose client has since been
    # deleted keeps client_ref as evidence but loses its area, and then only an
    # owner can see it. That is the correct reading: an orphan row belongs to
    # no area.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True)

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)
    user_id = fields.Many2one(
        'res.users', string='Checked By',
        default=lambda self: self.env.uid)
    source = fields.Char(
        help='Caller tag (context key consent_check_source), '
             'e.g. "pwa", "zalo", "fhir".')

    @api.model
    def _client_label(self, partner):
        """`Nguyễn Văn A [P00123]` — the subject as it was at check time.

        sudo: the label is compliance evidence and must be captured whatever
        the caller's read rights on res.partner happen to be (the row itself
        is already written with sudo by `_log_check`)."""
        if not partner:
            return False
        partner = partner.sudo()
        name = partner.name or ''
        code = partner.patient_code or ''
        if code:
            return '%s [%s]' % (name, code)
        return name or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('client_ref'):
                continue
            vals['client_ref'] = self._client_label(
                self.env['res.partner'].browse(vals.get('client_id') or []))
        return super().create(vals_list)

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
