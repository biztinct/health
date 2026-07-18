# -*- coding: utf-8 -*-
"""Condition ← health.condition (read + search on the R4 facade).

The patient problem list as FHIR R4 ``Condition``. Read-only (no write API —
the facade stays read-only, handover §0). Record rules + the data_sharing
consent gate apply exactly as for every other PHI resource — the registry
machinery does this; the serializer adds no sudo and bypasses nothing (§3).

``evidence.detail`` references ``DocumentReference/<note_id>`` (the same clinical
note serialized by health_fhir_core's DocumentReference — same compartment, no
new leak surface).
"""

from odoo.addons.health_fhir_core.serializers.base import (
    FHIRSerializer, fhir_date, date_param_domain,
)
from odoo.addons.health_fhir_core.serializers import fso_common

ICD10_SYSTEM = 'http://hl7.org/fhir/sid/icd-10'
CLINICAL_STATUS_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/condition-clinical')
VER_STATUS_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/condition-ver-status')


class ConditionSerializer(FHIRSerializer):
    resource_type = 'Condition'
    odoo_model = 'health.condition'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('patient_id')},
        'code': {'type': 'token',
                 'domain': lambda v: [('code_id.code', '=', v)]},
        'clinical-status': {'type': 'token',
                            'domain': lambda v: [('clinical_status', '=', v)]},
        'recorded-date': {'type': 'date',
                          'domain': date_param_domain('recorded_date')},
    }

    def base_domain(self, env):
        # Archived conditions are naturally excluded by search() (conventions
        # §5.27) — the CORRECT facade semantics: the working problem list.
        return []

    def patient_ids_of(self, records):
        return records.mapped('patient_id').ids

    def to_fhir(self, record):
        code = record.code_id
        display = code.display or code.display_vi or ''
        text = code.display_vi or code.display or ''
        resource = {
            'resourceType': 'Condition',
            'id': str(record.id),
            'meta': self.meta(record),
            'clinicalStatus': {
                'coding': [{
                    'system': CLINICAL_STATUS_SYSTEM,
                    'code': record.clinical_status,
                }],
            },
            'verificationStatus': {
                'coding': [{
                    'system': VER_STATUS_SYSTEM,
                    'code': record.verification_status,
                }],
            },
            'code': {
                'coding': [{
                    'system': ICD10_SYSTEM,
                    'code': code.code,
                    'display': display,
                }],
                'text': text,
            },
            'subject': self.reference('Patient', record.patient_id.id,
                                      display=record.patient_id.name),
        }
        if record.recorded_date:
            resource['recordedDate'] = fhir_date(record.recorded_date)
        if record.note_ids:
            resource['evidence'] = [{
                'detail': [self.reference('DocumentReference', note.id)
                           for note in record.note_ids],
            }]
        return resource
