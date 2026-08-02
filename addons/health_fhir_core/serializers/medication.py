# -*- coding: utf-8 -*-
"""MedicationRequest ← health.medication.order,
MedicationAdministration ← health.medication.administration (health_emar)."""

from .base import (
    FHIRSerializer, FHIRBadRequest, fhir_date, fhir_instant, date_param_domain,
    token_status_domain, RXNORM_SYSTEM, DAV_SYSTEM,
)
from . import fso_common


def _medication_concept(med):
    """medicationCodeableConcept from a health.medication master row —
    display name text plus RxNorm / DAV codings when present."""
    concept = {'text': med.name or ''}
    coding = []
    if med.rxnorm_code:
        coding.append({
            'system': RXNORM_SYSTEM,
            'code': med.rxnorm_code,
            'display': med.name or '',
        })
    if med.dav_reg_no:
        coding.append({'system': DAV_SYSTEM, 'code': med.dav_reg_no})
    if coding:
        concept['coding'] = coding
    return concept


def _selection_label(record, field):
    return dict(record._fields[field]._description_selection(record.env)).get(
        record[field])


def _reverse_status_domain(fhir_to_states):
    """{fhir_status: [odoo states]} → token search callable (full token
    syntax via ``token_status_domain``, §3.1)."""
    def _domain(value):
        states = fhir_to_states.get(value)
        if not states:
            raise FHIRBadRequest("Unknown status token: %r" % value)
        return [('state', 'in', states)]
    return token_status_domain(_domain)


# ---------------------------------------------------------------------------
# MedicationRequest
# ---------------------------------------------------------------------------

_REQUEST_STATUS = {
    'draft': 'draft',
    'active': 'active',
    'on_hold': 'on-hold',
    'completed': 'completed',
    'cancelled': 'cancelled',
}
_REQUEST_STATUS_SEARCH = {v: [k] for k, v in _REQUEST_STATUS.items()}


class MedicationRequestSerializer(FHIRSerializer):
    resource_type = 'MedicationRequest'
    odoo_model = 'health.medication.order'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'status': {'type': 'token',
                   'domain': _reverse_status_domain(_REQUEST_STATUS_SEARCH)},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def _synthesize_text(self, order):
        parts = []
        if order.dose_quantity:
            dose = ('%g' % order.dose_quantity)
            if order.dose_unit:
                dose = '%s %s' % (dose, order.dose_unit)
            parts.append(dose)
        if order.route:
            parts.append(_selection_label(order, 'route'))
        if order.frequency:
            parts.append(_selection_label(order, 'frequency'))
        return ' '.join(part for part in parts if part)

    def to_fhir(self, order):
        resource = {
            'resourceType': 'MedicationRequest',
            'id': str(order.id),
            'meta': self.meta(order),
            'status': _REQUEST_STATUS.get(order.state, 'active'),
            'intent': 'order',
            'medicationCodeableConcept': _medication_concept(
                order.medication_id),
            'subject': self.reference('Patient', order.client_id.id,
                                      display=order.client_id.name),
        }
        requester = order.prescriber_id.name or order.prescriber_name
        if requester:
            resource['requester'] = {'display': requester}
        if order.create_date:
            resource['authoredOn'] = fhir_date(order.create_date)
        dosage = self._dosage(order)
        if dosage:
            resource['dosageInstruction'] = [dosage]
        return resource

    def _dosage(self, order):
        dosage = {}
        text = order.instructions or self._synthesize_text(order)
        if text:
            dosage['text'] = text
        if order.instructions:
            dosage['patientInstruction'] = order.instructions
        if order.route:
            dosage['route'] = {'text': _selection_label(order, 'route')}
        # asNeededBoolean and asNeededCodeableConcept are mutually exclusive.
        if order.prn_reason:
            dosage['asNeededCodeableConcept'] = {'text': order.prn_reason}
        elif order.is_prn:
            dosage['asNeededBoolean'] = True
        timing = {}
        if order.frequency:
            timing['code'] = {'text': _selection_label(order, 'frequency')}
        bounds = {}
        if order.start_date:
            bounds['start'] = fhir_date(order.start_date)
        if order.end_date:
            bounds['end'] = fhir_date(order.end_date)
        if bounds:
            timing['repeat'] = {'boundsPeriod': bounds}
        if timing:
            dosage['timing'] = timing
        if order.dose_quantity:
            dose_quantity = {'value': order.dose_quantity}
            if order.dose_unit:
                dose_quantity['unit'] = order.dose_unit
            dosage['doseAndRate'] = [{'doseQuantity': dose_quantity}]
        return dosage


# ---------------------------------------------------------------------------
# MedicationAdministration
# ---------------------------------------------------------------------------

_ADMIN_STATUS = {
    'given': 'completed',
    'not_given': 'not-done',
    'refused': 'not-done',
    'cancelled': 'stopped',
}
_ADMIN_STATUS_SEARCH = {
    'completed': ['given'],
    'not-done': ['not_given', 'refused'],
    'stopped': ['cancelled'],
}


class MedicationAdministrationSerializer(FHIRSerializer):
    resource_type = 'MedicationAdministration'
    odoo_model = 'health.medication.administration'

    search_params = {
        # client_id is a stored related (store=True on the model) — a plain
        # domain on it is index-backed.
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'status': {'type': 'token',
                   'domain': _reverse_status_domain(_ADMIN_STATUS_SEARCH)},
        'date': {'type': 'date',
                 'domain': date_param_domain('actual_datetime')},
    }

    def base_domain(self, env):
        # A planned slot is not an event yet — never surfaced on the facade.
        return [('state', '!=', 'planned')]

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, admin):
        resource = {
            'resourceType': 'MedicationAdministration',
            'id': str(admin.id),
            'meta': self.meta(admin),
            'status': _ADMIN_STATUS.get(admin.state, 'completed'),
            'medicationCodeableConcept': _medication_concept(
                admin.medication_id),
            'subject': self.reference('Patient', admin.client_id.id,
                                      display=admin.client_id.name),
            'effectiveDateTime': fhir_instant(
                admin.actual_datetime or admin.planned_datetime),
        }
        if admin.state in ('not_given', 'refused'):
            resource['statusReason'] = [{
                'text': (admin.reason_id.name if admin.reason_id
                         else 'refused'),
            }]
        context = fso_common.encounter_ref_if_qualifies(self, admin.fso_id)
        if context:
            resource['context'] = context
        performer = []
        if admin.nurse_id:
            performer.append({'actor': {'display': admin.nurse_id.name}})
        if admin.witness_id:
            performer.append({'actor': {'display': admin.witness_id.name}})
        if performer:
            resource['performer'] = performer
        if admin.order_id:
            resource['request'] = self.reference(
                'MedicationRequest', admin.order_id.id)
        if admin.dose_given:
            dose = {'value': admin.dose_given}
            if admin.dose_unit:
                dose['unit'] = admin.dose_unit
            resource['dosage'] = {'dose': dose}
        if admin.notes:
            resource['note'] = [{'text': admin.notes}]
        return resource
