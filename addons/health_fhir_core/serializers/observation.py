# -*- coding: utf-8 -*-
"""Observation ← health.observation (health_vitals).

Panels (blood pressure) carry no value of their own — they serialize their
``child_ids`` as ``component[]``. Non-panel rows carry a valueQuantity or
valueString. Child rows still serialize standalone too (reachable by search).
"""

from .base import (
    FHIRSerializer, FHIRBadRequest, fhir_instant, date_param_domain,
    LOINC_SYSTEM, UCUM_SYSTEM,
)
from . import fso_common

OBSERVATION_CATEGORY_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/observation-category')

# health.observation.state → FHIR Observation.status
_STATE_TO_STATUS = {
    'preliminary': 'preliminary',
    'final': 'final',
    'amended': 'amended',
    'entered_in_error': 'entered-in-error',
}
_STATUS_TO_STATE = {v: k for k, v in _STATE_TO_STATUS.items()}


def _status_domain(value):
    state = _STATUS_TO_STATE.get(value)
    if not state:
        raise FHIRBadRequest("Unknown status token: %r" % value)
    return [('state', '=', state)]


def _code_concept(record):
    """CodeableConcept for one observation row from its vitals type."""
    vtype = record.vitals_type_id
    coding = {'system': LOINC_SYSTEM}
    if record.loinc_code:
        coding['code'] = record.loinc_code
    if vtype.name:
        coding['display'] = vtype.name
    return {'coding': [coding], 'text': vtype.name or ''}


def _quantity(record):
    """valueQuantity dict for a numeric observation row."""
    quantity = {'value': record.value_quantity}
    if record.unit_display:
        quantity['unit'] = record.unit_display
    if record.ucum_unit:
        quantity['system'] = UCUM_SYSTEM
        quantity['code'] = record.ucum_unit
    return quantity


class ObservationSerializer(FHIRSerializer):
    resource_type = 'Observation'
    odoo_model = 'health.observation'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'date': {'type': 'date',
                 'domain': date_param_domain('effective_datetime')},
        'status': {'type': 'token', 'domain': _status_domain},
        'code': {'type': 'token',
                 'domain': lambda v: [('vitals_type_id.loinc_code', '=', v)]},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, record):
        resource = {
            'resourceType': 'Observation',
            'id': str(record.id),
            'meta': self.meta(record),
            'status': _STATE_TO_STATUS.get(record.state, 'final'),
            'code': _code_concept(record),
            'subject': self.reference('Patient', record.client_id.id,
                                      display=record.client_id.name),
        }
        if record.vitals_type_id.is_fhir_vital_sign:
            resource['category'] = [{
                'coding': [{
                    'system': OBSERVATION_CATEGORY_SYSTEM,
                    'code': 'vital-signs',
                    'display': 'Vital Signs',
                }],
            }]
        encounter = fso_common.encounter_ref_if_qualifies(self, record.order_id)
        if encounter:
            resource['encounter'] = encounter
        if record.effective_datetime:
            resource['effectiveDateTime'] = fhir_instant(
                record.effective_datetime)
        if record.performer_id:
            resource['performer'] = [{'display': record.performer_id.name}]
        if record.method:
            resource['method'] = {'text': record.method}
        if record.device:
            resource['device'] = {'display': record.device}
        # Value vs. panel components.
        if record.vitals_type_id.value_type == 'panel':
            components = []
            for child in record.child_ids:
                components.append({
                    'code': _code_concept(child),
                    'valueQuantity': _quantity(child),
                })
            if components:
                resource['component'] = components
        elif record.vitals_type_id.value_type == 'string':
            if record.value_text:
                resource['valueString'] = record.value_text
        else:
            resource['valueQuantity'] = _quantity(record)
        return resource
