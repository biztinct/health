# -*- coding: utf-8 -*-
"""Request/response schemas for the /api/v1 surface.

Spec B.3 calls for pydantic v2 models; for the v1 surface plain JSON-schema
dict fragments are sufficient (and keep the module importable when pydantic
is absent), so the schemas below are dicts. ``build_openapi()`` accepts
either form transparently, and the ``@api_route`` wrapper enforces the
``required`` keys of request schemas (422 envelope on violation).
"""


def _obj(properties, required=None):
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = list(required)
    return schema


def _str(desc=''):
    return {'type': 'string', 'description': desc}


def _num(desc=''):
    return {'type': 'number', 'description': desc}


def _int(desc=''):
    return {'type': 'integer', 'description': desc}


def _bool(desc=''):
    return {'type': 'boolean', 'description': desc}


def _arr(items):
    return {'type': 'array', 'items': items}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

BookingStartRequest = _obj({}, required=None)

BookingCompleteRequest = _obj({
    'payment_choice': _str("'pay_now' or 'pay_later'"),
    'payment_method': _str("'cash', 'bank_transfer', 'credit_card', ..."),
    'service_notes': _str('Free-text nurse notes'),
    'create_invoice_now': _bool('Create+post the invoice from the quote'),
})

BookingCancelRequest = _obj({
    'cancellation_reason_id': _int('health.booking.cancellation.reason id'),
    'cancellation_notes': _str('Optional free-text notes'),
}, required=['cancellation_reason_id'])

ClinicalNoteRequest = _obj({
    'clinical_notes': _str(),
    'diagnosis': _str(),
    'treatment_performed': _str(),
    'medications_prescribed': _str(),
    'vital_signs': _str(),
    'patient_condition_before': _str(),
    'patient_condition_after': _str(),
    'injection_count': _int(),
    'medication_count': _int(),
    'wound_count': _int(),
    'iv_fluid_count': _int(),
})

# ---------------------------------------------------------------------------
# Response `data` schemas (field-by-field from the health_pwa serializers)
# ---------------------------------------------------------------------------

PatientSummary = _obj({
    'id': _int(), 'name': _str(), 'patient_code': _str(), 'phone': _str(),
    'email': _str(), 'age': _int(), 'gender': _str(), 'blood_group': _str(),
    'patient_status': _str(), 'last_visit_date': _str(), 'next_visit_date': _str(),
    'address': _str(), 'image_url': _str(), 'visit_count': _int(),
    'primary_facility': _str(),
})

PatientListResponse = _obj({
    'patients': _arr(PatientSummary),
    'total_count': _int(), 'limit': _int(), 'offset': _int(), 'has_more': _bool(),
})

PatientDetailResponse = _obj({
    'id': _int(), 'name': _str(), 'patient_code': _str(),
    'birth_date': _str(), 'age': _int(), 'gender': _str(), 'blood_group': _str(),
    'phone': _str(), 'mobile': _str(), 'email': _str(),
    'street': _str(), 'city': _str(), 'country': _str(),
    'patient_status': _str(), 'allergies': _str(), 'medical_history': _str(),
    'insurance_provider': _str(), 'insurance_number': _str(),
    'primary_facility': _str(), 'recent_orders': _arr({'type': 'object'}),
})

BookingSummary = _obj({
    'id': _int(), 'fso_id': _int(), 'fso_name': _str(),
    'patient_name': _str(), 'patient_id': _int(), 'patient_code': _str(),
    'patient_phone': _str(), 'service_type': _str(),
    'scheduled_datetime': _str(), 'scheduled_time': _str(),
    'scheduled_duration': _int(), 'status': _str(), 'status_display': _str(),
    'location': _str(), 'priority': _str(), 'lead_staff_name': _str(),
    'assignment_role': _str(), 'notes': _str(),
})

BookingListResponse = _obj({
    'orders': _arr(BookingSummary),
    'total_count': _int(), 'limit': _int(), 'offset': _int(), 'has_more': _bool(),
})

BookingDetailResponse = _obj({
    'id': _int(), 'name': _str(), 'state': _str(),
    'patient': {'type': 'object'}, 'primary_contact': {'type': 'object'},
    'scheduled_datetime': _str(), 'scheduled_duration': _int(),
    'actual_start_datetime': _str(), 'actual_end_datetime': _str(),
    'service_type': _str(), 'priority': _str(),
    'quote_items': _arr({'type': 'object'}),
    'clinical_notes': _arr({'type': 'object'}),
})

BookingStartResponse = _obj({
    'actual_start_datetime': _str(), 'state': _str(), 'message': _str(),
})

BookingCompleteResponse = _obj({
    'actual_end_datetime': _str(), 'actual_duration': _num(), 'state': _str(),
    'payment_choice': _str(), 'payment_method': _str(), 'message': _str(),
})

BookingCancelResponse = _obj({
    'state': _str(), 'message': _str(), 'cancellation_reason': _str(),
})

ClinicalNoteResponse = _obj({
    'note_id': _int(), 'clinical_notes_submitted': _bool(),
    'clinical_note_count': _int(), 'message': _str(),
})

QuoteResponse = _obj({
    'id': _int(), 'name': _str(), 'state': _str(),
    'amount_total': _num(), 'amount_untaxed': _num(), 'amount_tax': _num(),
    'currency': _str(), 'order_lines': _arr({'type': 'object'}),
})

AssignmentsTodayResponse = _obj({
    'bookings': _arr(BookingSummary), 'total_count': _int(),
    'staff_name': _str(), 'staff_id': _int(), 'date': _str(),
    'requested_date': _str(),
})

ProductCatalogResponse = _obj({
    'products': _arr(_obj({
        'id': _int(), 'name': _str(), 'code': _str(), 'description': _str(),
        'price': _num(), 'currency': _str(), 'category': _str(), 'uom': _str(),
        'image_url': _str(),
    })),
    'total_count': _int(), 'limit': _int(), 'offset': _int(), 'has_more': _bool(),
})

FutureBookingsResponse = _obj({
    'bookings_by_date': {'type': 'object'},
})

TokenResponse = _obj({
    'access_token': _str(), 'token_type': _str(),
    'expires_in': _int(), 'scope': _str(),
}, required=['access_token', 'token_type', 'expires_in'])
