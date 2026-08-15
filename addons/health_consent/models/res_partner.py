# -*- coding: utf-8 -*-
"""Client extension — consent smart button, summary and the
can_send_marketing() soft enforcement helper (clinical spec §6.2.2 /
§6.8)."""
from odoo import _, api, fields, models

# Fixed FHIR-stable consent types (spec §6.10 — no lookup seeds).
CONSENT_TYPES = ('service', 'data_sharing', 'photography',
                 'emergency_treatment', 'marketing')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    consent_ids = fields.One2many(
        'health.consent', 'client_id', string='Consents')
    consent_count = fields.Integer(
        compute='_compute_consent_count', string='Consents')
    consent_summary = fields.Char(
        compute='_compute_consent_summary',
        help='Plain-text per-type active-consent glance, '
             'e.g. "service ✓, data_sharing ✗, photography ✓".')

    def _compute_consent_count(self):
        counts = dict(self.env['health.consent']._read_group(
            [('client_id', 'in', self.ids)],
            groupby=['client_id'], aggregates=['__count']))
        for partner in self:
            partner.consent_count = counts.get(partner, 0)

    def _compute_consent_summary(self):
        today = fields.Date.context_today(self)
        Consent = self.env['health.consent'].sudo()
        actives = Consent.search([
            ('client_id', 'in', self.ids),
            ('state', '=', 'active'),
            ('effective_date', '<=', today),
            '|', ('expiry_date', '=', False),
            ('expiry_date', '>=', today),
        ]) if self.ids else Consent
        by_partner = {}
        for consent in actives:
            by_partner.setdefault(
                consent.client_id.id, set()).add(consent.consent_type_code)
        for partner in self:
            granted = by_partner.get(partner.id, set())
            partner.consent_summary = ', '.join(
                '%s %s' % (consent_type,
                           '✓' if consent_type in granted
                           else '✗')
                for consent_type in CONSENT_TYPES)

    def action_view_consents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consents'),
            'res_model': 'health.consent',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def can_send_marketing(self):
        """Soft enforcement helper (spec §6.8.2) for health_zalo/ZNS
        flows to adopt: True iff the client holds an active marketing
        consent today. Log-only friendly — never raises."""
        self.ensure_one()
        return self.env['health.consent'].check_consent(
            self, 'marketing')
