# -*- coding: utf-8 -*-
"""ServiceRequest ← health.fieldservice.order (+ sale order lines as orderDetail)."""

from .base import FHIRSerializer, fhir_instant
from . import fso_common


class ServiceRequestSerializer(FHIRSerializer):
    resource_type = 'ServiceRequest'
    odoo_model = fso_common.FSO_MODEL

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_reference_domain},
        'status': {'type': 'token',
                   'domain': fso_common.status_token_domain(
                       fso_common.SERVICE_REQUEST_STATUS_MAP)},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('patient_id').ids

    def to_fhir(self, order):
        resource = {
            'resourceType': 'ServiceRequest',
            'id': str(order.id),
            'meta': self.meta(order),
            'identifier': [
                {'system': 'urn:health19:fso', 'value': order.name or str(order.id)},
            ],
            'status': fso_common.SERVICE_REQUEST_STATUS_MAP.get(order.state, 'active'),
            'intent': 'order',
            'subject': self.reference('Patient', order.patient_id.id,
                                      display=order.patient_id.name),
        }
        service_text = fso_common.service_code_text(order)
        if service_text:
            resource['code'] = {'text': service_text}
        # quote_line_ids is a related on sale_order_id.order_line (FSO L1150)
        order_detail = [
            {'text': line.name}
            for line in order.quote_line_ids if line.name
        ]
        if order_detail:
            resource['orderDetail'] = order_detail
        if order.state in fso_common.ENCOUNTER_STATES:
            resource['encounter'] = self.reference('Encounter', order.id)
        if order.create_date:
            resource['authoredOn'] = fhir_instant(order.create_date)
        if order.scheduled_datetime:
            resource['occurrenceDateTime'] = fhir_instant(order.scheduled_datetime)
        return resource
