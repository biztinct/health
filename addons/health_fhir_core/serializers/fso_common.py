# -*- coding: utf-8 -*-
"""Shared helpers for the three FSO-backed resources.

One health.fieldservice.order maps to three linked resources
(architecture-interop.md §1.1):
- Appointment  — the planned slot (all scheduling states incl. draft/cancelled)
- Encounter    — the actual visit (assigned and later states only)
- ServiceRequest — the order itself (+ sale order lines as orderDetail)
"""

from .base import FHIRBadRequest, parse_reference_value, date_param_domain

FSO_MODEL = 'health.fieldservice.order'


def encounter_ref_if_qualifies(serializer, fso):
    """Encounter reference for a linked FSO, but ONLY when that FSO is in
    an Encounter-qualifying state (binding decision 3): a draft/confirmed/
    cancelled visit surfaces as an Appointment, not an Encounter, so a
    reference to Encounter/<id> there would dangle. Returns None otherwise,
    so callers omit the key entirely."""
    if fso and fso.state in ENCOUNTER_STATES:
        return serializer.reference('Encounter', fso.id)
    return None


def patient_ref_domain(field):
    """Search-param callable translating a ``patient`` reference value into
    a domain on the given related path (``client_id``,
    ``careplan_id.client_id`` …)."""
    def _domain(value):
        return [(field, '=', parse_reference_value(value, 'Patient'))]
    return _domain

# state → Encounter.status (design-platform-services.md §C.3)
ENCOUNTER_STATUS_MAP = {
    'draft': 'planned',
    'confirmed': 'planned',
    'assigned': 'planned',
    'in_progress': 'in-progress',
    'completed': 'finished',
    'completed_pending_invoice': 'finished',
    'closed': 'finished',
    'cancelled': 'cancelled',
}

# Encounter exists only once a visit is real (assigned onwards); scheduling
# states (draft/confirmed/cancelled) surface on Appointment instead.
ENCOUNTER_STATES = (
    'assigned', 'in_progress', 'completed', 'completed_pending_invoice', 'closed',
)

# state → Appointment.status
APPOINTMENT_STATUS_MAP = {
    'draft': 'proposed',
    'confirmed': 'booked',
    'assigned': 'booked',
    'in_progress': 'arrived',
    'completed': 'fulfilled',
    'completed_pending_invoice': 'fulfilled',
    'closed': 'fulfilled',
    'cancelled': 'cancelled',
}

# state → ServiceRequest.status
SERVICE_REQUEST_STATUS_MAP = {
    'draft': 'draft',
    'confirmed': 'active',
    'assigned': 'active',
    'in_progress': 'active',
    'completed': 'completed',
    'completed_pending_invoice': 'completed',
    'closed': 'completed',
    'cancelled': 'revoked',
}


def patient_reference_domain(value):
    return [('patient_id', '=', parse_reference_value(value, 'Patient'))]


def scheduled_date_domain():
    return date_param_domain('scheduled_datetime')


def status_token_domain(status_map, restrict_states=None):
    """Reverse a state→fhir-status map into a token search callable."""
    def _domain(value):
        states = [
            state for state, fhir_status in status_map.items()
            if fhir_status == value
            and (restrict_states is None or state in restrict_states)
        ]
        if not states:
            raise FHIRBadRequest("Unknown status token: %r" % value)
        return [('state', 'in', states)]
    return _domain


def service_code_text(order):
    """code.text = service type name (specific appointment type wins)."""
    if order.appointment_type_id:
        return order.appointment_type_id.name
    field = order._fields['service_type']
    labels = dict(field._description_selection(order.env))
    return labels.get(order.service_type) or (order.service_type or '')


def practitioner_participants(order):
    """assignment_ids → list of (employee, role_label) for participant arrays."""
    result = []
    role_field = order.env['health.staff.assignment']._fields['assignment_role']
    role_labels = dict(role_field._description_selection(order.env))
    for assignment in order.assignment_ids:
        if assignment.staff_id:
            result.append((
                assignment.staff_id,
                role_labels.get(assignment.assignment_role,
                                assignment.assignment_role or ''),
            ))
    return result
