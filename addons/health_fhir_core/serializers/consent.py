# -*- coding: utf-8 -*-
"""Consent ← health.consent (health_consent).

PHI restraint: the free-text ``scope_note`` narrowing is NOT exported, and
signature/attachment binary is never emitted — only sourceAttachment
metadata (contentType + title)."""

from .base import FHIRSerializer, FHIRBadRequest, fhir_date
from . import fso_common

CONSENT_SCOPE_SYSTEM = 'http://terminology.hl7.org/CodeSystem/consentscope'
CONSENT_TYPE_SYSTEM = 'urn:health19:consent-types'

_STATUS = {'active': 'active', 'withdrawn': 'inactive', 'expired': 'inactive'}
_STATUS_SEARCH = {'active': ['active'], 'inactive': ['withdrawn', 'expired']}
_SCOPE_TREATMENT = ('service', 'emergency_treatment')


def _status_domain(value):
    states = _STATUS_SEARCH.get(value)
    if not states:
        raise FHIRBadRequest("Unknown status token: %r" % value)
    return [('state', 'in', states)]


class ConsentSerializer(FHIRSerializer):
    resource_type = 'Consent'
    odoo_model = 'health.consent'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'status': {'type': 'token', 'domain': _status_domain},
    }

    def base_domain(self, env):
        # Drafts are not evidence.
        return [('state', '!=', 'draft')]

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, consent):
        scope_code = ('treatment' if consent.consent_type in _SCOPE_TREATMENT
                      else 'patient-privacy')
        resource = {
            'resourceType': 'Consent',
            'id': str(consent.id),
            'meta': self.meta(consent),
            'status': _STATUS.get(consent.state, 'inactive'),
            'scope': {
                'coding': [{'system': CONSENT_SCOPE_SYSTEM,
                            'code': scope_code}],
            },
            'category': [{
                'coding': [{'system': CONSENT_TYPE_SYSTEM,
                            'code': consent.consent_type}],
            }],
            'patient': self.reference('Patient', consent.client_id.id,
                                      display=consent.client_id.name),
        }
        if consent.effective_date:
            resource['dateTime'] = fhir_date(consent.effective_date)
        performer_name = None
        if not consent.self_granted and consent.granted_by_partner_id:
            performer_name = consent.granted_by_partner_id.name
        elif consent.verbal_witness_id:
            performer_name = consent.verbal_witness_id.name
        if performer_name:
            resource['performer'] = [{'display': performer_name}]
        period = {}
        if consent.effective_date:
            period['start'] = fhir_date(consent.effective_date)
        if consent.expiry_date:
            period['end'] = fhir_date(consent.expiry_date)
        if period:
            resource['provision'] = {'period': period}
        # Metadata only — never the signature binary itself (PHI restraint).
        if consent.method == 'digital_signature' and consent.signature:
            resource['sourceAttachment'] = {
                'contentType': 'image/png',
                'title': 'digital signature',
            }
        return resource
