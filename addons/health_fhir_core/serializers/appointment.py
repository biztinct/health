# -*- coding: utf-8 -*-
"""Appointment ← health.fieldservice.order (planned slot; all states)."""

from .base import FHIRSerializer, fhir_instant
from . import fso_common


class AppointmentSerializer(FHIRSerializer):
    resource_type = 'Appointment'
    odoo_model = fso_common.FSO_MODEL

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_reference_domain},
        'date': {'type': 'date', 'domain': fso_common.scheduled_date_domain()},
        'status': {'type': 'token',
                   'domain': fso_common.status_token_domain(
                       fso_common.APPOINTMENT_STATUS_MAP)},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('patient_id').ids

    def to_fhir(self, order):
        resource = {
            'resourceType': 'Appointment',
            'id': str(order.id),
            'meta': self.meta(order),
            'identifier': [
                {'system': 'urn:health19:fso', 'value': order.name or str(order.id)},
            ],
            'status': fso_common.APPOINTMENT_STATUS_MAP.get(order.state, 'proposed'),
            'participant': self._participants(order),
        }
        start = order.scheduled_datetime
        end = order.estimated_end_datetime
        if start and not end and order.scheduled_duration:
            from datetime import timedelta
            end = start + timedelta(minutes=order.scheduled_duration)
        # FHIR invariant: start and end come together or not at all
        if start:
            resource['start'] = fhir_instant(start)
            resource['end'] = fhir_instant(end or start)
        service_text = fso_common.service_code_text(order)
        if service_text:
            resource['serviceType'] = [{'text': service_text}]
        if order.symptoms:
            resource['description'] = order.symptoms
        return resource

    def _participants(self, order):
        participants = [{
            'actor': self.reference('Patient', order.patient_id.id,
                                    display=order.patient_id.name),
            'required': 'required',
            'status': 'accepted',
        }]
        for employee, role_label in fso_common.practitioner_participants(order):
            participant = {
                'actor': self.reference('Practitioner', employee.id,
                                        display=employee.name),
                'status': 'accepted',
            }
            if role_label:
                participant['type'] = [{'text': role_label}]
            participants.append(participant)
        return participants
