# -*- coding: utf-8 -*-
"""Patient BHYT (social health insurance) extension.

Adds the coverage-scheme fields the claim spine snapshots at generation.
Reuses the existing canonical card field ``insurance_number`` (the BHYT card
no., FHIR ``urn:health19:bhyt``) and ``insurance_expiry`` — NO second card
field (handover §1, §2.1). All fields optional: no required-field migration
risk on existing partners.
"""
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bhyt_provider_id = fields.Many2one(
        'health.insurance.provider', string='BHYT Scheme',
        help='The BHYT (social health insurance) scheme record. Its default '
             'coverage % seeds the patient coverage rate when unset.')
    bhyt_coverage_rate = fields.Float(
        string='BHYT Coverage Rate (%)',
        help='Patient đồng-chi-trả (co-payment) coverage rate, 0–100 '
             '(e.g. 80 / 95 / 100). Defaults from the BHYT scheme.')
    bhyt_beneficiary_code = fields.Char(
        string='BHYT Beneficiary Code',
        help='Beneficiary-group code (mã đối tượng). Free text in Phase 1; '
             'the Decision-4210 category enum arrives with the Phase-2 schema.')
    bhyt_registered_facility = fields.Char(
        string='BHYT Registered Facility',
        help='Nơi đăng ký khám chữa bệnh ban đầu (initial registered facility).')
    bhyt_valid = fields.Boolean(
        string='BHYT Valid', compute='_compute_bhyt_valid',
        help='True when the patient has a BHYT card number and a non-expired '
             'card. Flags claim eligibility.')

    @api.depends('insurance_number', 'insurance_expiry')
    def _compute_bhyt_valid(self):
        today = fields.Date.context_today(self)
        for partner in self:
            partner.bhyt_valid = bool(
                partner.insurance_number and partner.insurance_expiry
                and partner.insurance_expiry >= today)

    @api.onchange('bhyt_provider_id')
    def _onchange_bhyt_provider_id(self):
        """Seed the coverage rate from the scheme default when unset."""
        for partner in self:
            if partner.bhyt_provider_id and not partner.bhyt_coverage_rate:
                partner.bhyt_coverage_rate = \
                    partner.bhyt_provider_id.coverage_percentage
