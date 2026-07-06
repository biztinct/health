# -*- coding: utf-8 -*-
"""Encounter ← health.fieldservice.order (actual visit; class=HH home health).

Only FSOs whose state implies a real/underway visit surface as Encounters
(assigned/in_progress/completed/completed_pending_invoice/closed); scheduling
states are covered by Appointment.
"""

from .base import FHIRSerializer, fhir_instant
from . import fso_common

ACTCODE_SYSTEM = 'http://terminology.hl7.org/CodeSystem/v3-ActCode'
EVV_EXTENSION_URL = 'urn:health19:evv-verified'


class EncounterSerializer(FHIRSerializer):
    resource_type = 'Encounter'
    odoo_model = fso_common.FSO_MODEL

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_reference_domain},
        'date': {'type': 'date', 'domain': fso_common.scheduled_date_domain()},
        'status': {'type': 'token',
                   'domain': fso_common.status_token_domain(
                       fso_common.ENCOUNTER_STATUS_MAP,
                       restrict_states=fso_common.ENCOUNTER_STATES)},
    }

    def base_domain(self, env):
        return [('state', 'in', list(fso_common.ENCOUNTER_STATES))]

    def patient_ids_of(self, records):
        return records.mapped('patient_id').ids

    def to_fhir(self, order):
        resource = {
            'resourceType': 'Encounter',
            'id': str(order.id),
            'meta': self.meta(order),
            'identifier': [
                {'system': 'urn:health19:fso', 'value': order.name or str(order.id)},
            ],
            'status': fso_common.ENCOUNTER_STATUS_MAP.get(order.state, 'planned'),
            'class': {
                'system': ACTCODE_SYSTEM,
                'code': 'HH',
                'display': 'home health',
            },
            'subject': self.reference('Patient', order.patient_id.id,
                                      display=order.patient_id.name),
            'appointment': [self.reference('Appointment', order.id)],
        }
        period = {}
        start = order.actual_start_datetime or order.scheduled_datetime
        end = order.actual_end_datetime or order.estimated_end_datetime
        if start:
            period['start'] = fhir_instant(start)
        if end:
            period['end'] = fhir_instant(end)
        if period:
            resource['period'] = period
        participants = []
        for employee, role_label in fso_common.practitioner_participants(order):
            participant = {
                'individual': self.reference('Practitioner', employee.id,
                                             display=employee.name),
            }
            if role_label:
                participant['type'] = [{'text': role_label}]
            participants.append(participant)
        if participants:
            resource['participant'] = participants
        if order.facility_id:
            resource['serviceProvider'] = self.reference(
                'Organization', order.facility_id.id,
                display=order.facility_id.name)
        # health_evv is optional — consume its field defensively
        if 'evv_verified' in order._fields:
            resource['extension'] = [{
                'url': EVV_EXTENSION_URL,
                'valueBoolean': bool(order.evv_verified),
            }]
        return resource
