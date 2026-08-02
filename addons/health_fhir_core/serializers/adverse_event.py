# -*- coding: utf-8 -*-
"""AdverseEvent ← health.incident (health_incident),
Flag ← health.fall.risk (health_base).

PHI restraint: the incident narrative fields (description,
investigation_notes, root_cause, contributing_factors, immediate_actions)
are NOT exported — the facade carries the event's coded facts, not the story.
"""

from .base import (
    FHIRSerializer, fhir_instant, date_param_domain, token_domain,
)
from . import fso_common

INCIDENT_TYPE_SYSTEM = 'urn:health19:incident-types'
FLAG_TYPE_SYSTEM = 'urn:health19:flag-types'
ADVERSE_SEVERITY_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/adverse-event-severity')
FLAG_CATEGORY_SYSTEM = 'http://terminology.hl7.org/CodeSystem/flag-category'


def _severity_code(severity):
    if severity in ('1', '2'):
        return 'mild'
    if severity == '3':
        return 'moderate'
    return 'severe'  # 4, 5


class AdverseEventSerializer(FHIRSerializer):
    resource_type = 'AdverseEvent'
    odoo_model = 'health.incident'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'date': {'type': 'date',
                 'domain': date_param_domain('incident_datetime')},
        # local 1–5 severity scale (no base-spec ValueSet — the capability
        # deliberately omits a canonical for it), token syntax tolerated.
        'severity': {'type': 'token', 'domain': token_domain('severity')},
    }

    def base_domain(self, env):
        # R4 AdverseEvent.subject is mandatory (1..1) — staff-only incidents
        # (no client) are NOT exposed on the facade.
        return [('client_id', '!=', False)]

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, incident):
        type_label = dict(
            incident._fields['incident_type']._description_selection(
                incident.env)).get(incident.incident_type, '')
        resource = {
            'resourceType': 'AdverseEvent',
            'id': str(incident.id),
            'meta': self.meta(incident),
            'actuality': ('potential' if incident.incident_type == 'near_miss'
                          else 'actual'),
            'event': {
                'coding': [{
                    'system': INCIDENT_TYPE_SYSTEM,
                    'code': incident.incident_type,
                }],
                'text': type_label,
            },
            'subject': self.reference('Patient', incident.client_id.id,
                                      display=incident.client_id.name),
        }
        if incident.incident_datetime:
            resource['date'] = fhir_instant(incident.incident_datetime)
            resource['detected'] = fhir_instant(incident.incident_datetime)
        if incident.reported_datetime:
            resource['recordedDate'] = fhir_instant(
                incident.reported_datetime)
        if incident.severity:
            resource['severity'] = {
                'coding': [{
                    'system': ADVERSE_SEVERITY_SYSTEM,
                    'code': _severity_code(incident.severity),
                }],
            }
        if incident.reporter_id:
            resource['recorder'] = {'display': incident.reporter_id.name}
        encounter = fso_common.encounter_ref_if_qualifies(
            self, incident.order_id)
        if encounter:
            resource['encounter'] = encounter
        return resource


class FlagSerializer(FHIRSerializer):
    resource_type = 'Flag'
    odoo_model = 'health.fall.risk'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('patient_id')},
    }

    def base_domain(self, env):
        # Only HIGH-band Morse assessments become standing fall-risk flags.
        return [('risk_level', '=', 'high')]

    def patient_ids_of(self, records):
        return records.mapped('patient_id').ids

    def to_fhir(self, assessment):
        # active when this is the patient's most recent fall-risk assessment
        # (any band); a newer assessment supersedes it → inactive.
        newer = assessment.search_count([
            ('patient_id', '=', assessment.patient_id.id),
            ('assessment_date', '>', assessment.assessment_date),
        ])
        resource = {
            'resourceType': 'Flag',
            'id': str(assessment.id),
            'meta': self.meta(assessment),
            'status': 'inactive' if newer else 'active',
            'category': [{
                'coding': [{
                    'system': FLAG_CATEGORY_SYSTEM,
                    'code': 'clinical',
                    'display': 'Clinical',
                }],
            }],
            'code': {
                'coding': [{
                    'system': FLAG_TYPE_SYSTEM,
                    'code': 'falls-risk',
                }],
                'text': 'High falls risk (Morse %s)' % assessment.morse_score,
            },
            'subject': self.reference('Patient', assessment.patient_id.id,
                                      display=assessment.patient_id.name),
        }
        if assessment.assessment_date:
            resource['period'] = {
                'start': fhir_instant(assessment.assessment_date)}
        return resource
