# -*- coding: utf-8 -*-
"""Transparent PHI encryption for patient narrative fields and identity numbers.

The original fields keep their names, labels and widgets — every form, the
PWA serializers and all ORM consumers keep working unchanged. Storage moves
to ``*_enc`` columns holding AES-256-GCM tokens; identity numbers get an
HMAC blind index so exact-match lookup still works (partial ``ilike``
searches resolve as exact matches on the full number).
"""
from odoo import api, fields, models

from . import phi_crypto

# exposed field -> (encrypted column, blind index column or None)
PARTNER_PHI_MAP = {
    'allergies': ('allergies_enc', None),
    'medical_history': ('medical_history_enc', None),
    'intake_diagnosis': ('intake_diagnosis_enc', None),
    'intake_notes': ('intake_notes_enc', None),
    'healthcare_notes': ('healthcare_notes_enc', None),
    'emergency_contact_name': ('emergency_contact_name_enc', None),
    'emergency_contact_phone': ('emergency_contact_phone_enc', None),
    'emergency_contact_relation': ('emergency_contact_relation_enc', None),
    'emergency_contact_relationship': ('emergency_contact_relationship_enc', None),
    'national_id': ('national_id_enc', 'national_id_bidx'),
    'cccd_number': ('cccd_number_enc', 'cccd_number_bidx'),
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    _phi_map = PARTNER_PHI_MAP

    # --- encrypted storage -------------------------------------------------
    allergies_enc = fields.Text('Known Allergies (encrypted)')
    medical_history_enc = fields.Text('Medical History (encrypted)')
    intake_diagnosis_enc = fields.Text('Intake Diagnosis (encrypted)')
    intake_notes_enc = fields.Text('Intake Notes (encrypted)')
    healthcare_notes_enc = fields.Text('Healthcare Notes (encrypted)')
    emergency_contact_name_enc = fields.Text('Emergency Contact Name (encrypted)')
    emergency_contact_phone_enc = fields.Text('Emergency Contact Phone (encrypted)')
    emergency_contact_relation_enc = fields.Text('Emergency Contact Relation (encrypted)')
    emergency_contact_relationship_enc = fields.Text('Emergency Contact Relationship (encrypted)')
    national_id_enc = fields.Text('National ID (encrypted)')
    national_id_bidx = fields.Char('National ID Index', index=True)
    cccd_number_enc = fields.Text('CCCD Number (encrypted)')
    cccd_number_bidx = fields.Char('CCCD Number Index', index=True)

    # --- exposed fields (same names/labels as before — views unchanged) ----
    allergies = fields.Text(
        'Known Allergies',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    medical_history = fields.Text(
        'Medical History Summary',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    intake_diagnosis = fields.Text(
        'Diagnosis', help='Medical diagnosis from intake',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    intake_notes = fields.Text(
        'Intake Notes', help='Additional notes from intake assessment',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    healthcare_notes = fields.Text(
        'Healthcare Notes', help='General healthcare-related notes',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    emergency_contact_name = fields.Char(
        'Emergency Contact Name',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    emergency_contact_phone = fields.Char(
        'Emergency Contact Phone',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    emergency_contact_relation = fields.Char(
        'Relation to Patient',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    emergency_contact_relationship = fields.Char(
        'Emergency Contact Relationship',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields')
    national_id = fields.Char(
        'National ID (CCCD/CMND)',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields',
        search='_search_national_id')
    cccd_number = fields.Char(
        'CCCD Number',
        help='Vietnamese Citizen Identification Card Number (from Excel CMF)',
        compute='_compute_phi_fields', inverse='_inverse_phi_fields',
        search='_search_cccd_number')

    # --- compute / inverse --------------------------------------------------
    @api.depends(*(enc for enc, _b in PARTNER_PHI_MAP.values()))
    def _compute_phi_fields(self):
        for rec in self:
            for exposed, (enc, _bidx) in self._phi_map.items():
                rec[exposed] = phi_crypto.decrypt(self.env, rec[enc]) or False

    def _inverse_phi_fields(self):
        for rec in self:
            for exposed, (enc, bidx) in self._phi_map.items():
                value = rec[exposed]
                rec[enc] = phi_crypto.encrypt(self.env, value) if value else False
                if bidx:
                    rec[bidx] = phi_crypto.blind_index(self.env, value)

    # --- exact-match search via blind index ---------------------------------
    def _phi_bidx_domain(self, bidx_field, enc_field, operator, value):
        """Translate a search on an encrypted identifier into a blind-index
        domain. ilike/like resolve as exact matches on the full number —
        partial matches are impossible on encrypted data by design."""
        if operator in ('=', '!=') and not value:
            # "field = False" must find records WITHOUT a value
            op = '=' if operator == '=' else '!='
            return [(enc_field, op, False)]
        if operator in ('in', 'not in'):
            # Odoo 19 normalizes "= False" into "in [False]" — falsy members
            # must translate to an emptiness check on the encrypted column.
            # value may be list/tuple/set or Odoo's OrderedSet — any
            # non-string iterable is a collection of candidates
            if isinstance(value, str) or not hasattr(value, '__iter__'):
                values = [value]
            else:
                values = list(value)
            hashes = [phi_crypto.blind_index(self.env, v) for v in values if v]
            has_false = any(not v for v in values)
            if operator == 'in':
                parts = []
                if hashes:
                    parts.append((bidx_field, 'in', hashes))
                if has_false:
                    parts.append((enc_field, '=', False))
                if not parts:
                    return [(0, '=', 1)]
                return ['|'] * (len(parts) - 1) + parts
            parts = [(bidx_field, 'not in', hashes)] if hashes else []
            if has_false:
                parts.append((enc_field, '!=', False))
            return parts or [(1, '=', 1)]
        negative = operator in ('!=', 'not ilike', 'not like')
        return [(bidx_field, '!=' if negative else '=',
                 phi_crypto.blind_index(self.env, value))]

    def _search_national_id(self, operator, value):
        return self._phi_bidx_domain('national_id_bidx', 'national_id_enc',
                                     operator, value)

    def _search_cccd_number(self, operator, value):
        return self._phi_bidx_domain('cccd_number_bidx', 'cccd_number_enc',
                                     operator, value)
