# -*- coding: utf-8 -*-
"""DocumentReference ← health.clinical.note.

The free-text note is compiled into one labeled plain-text document
(base64 in content[0].attachment.data); each attached image adds one more
content[] entry whose URL points at /web/content/<id> (separate Odoo auth —
documented in the CapabilityStatement description and README).

Narrative fields are computed encrypted fields (health_phi_encryption); they
decrypt transparently when read through the ORM.
"""

import base64

from .base import (
    FHIRSerializer, fhir_instant, date_param_domain,
    parse_reference_value, strip_html,
)


def _patient_domain(value):
    return [('order_id.patient_id', '=', parse_reference_value(value, 'Patient'))]


def _encounter_domain(value):
    return [('order_id', '=', parse_reference_value(value, 'Encounter'))]


class DocumentReferenceSerializer(FHIRSerializer):
    resource_type = 'DocumentReference'
    odoo_model = 'health.clinical.note'

    search_params = {
        'patient': {'type': 'reference', 'domain': _patient_domain},
        'encounter': {'type': 'reference', 'domain': _encounter_domain},
        'date': {'type': 'date', 'domain': date_param_domain('create_date')},
    }

    # labeled sections concatenated into the plain-text document
    TEXT_SECTIONS = (
        ('Clinical Notes', 'clinical_notes', True),      # Html field
        ('Diagnosis', 'diagnosis', False),
        ('Treatment Performed', 'treatment_performed', False),
        ('Medications Prescribed', 'medications_prescribed', False),
        ('Vital Signs', 'vital_signs', False),
        ('Patient Condition (Before)', 'patient_condition_before', False),
        ('Patient Condition (After)', 'patient_condition_after', False),
    )
    COUNT_SECTIONS = (
        ('Injections Given', 'injection_count'),
        ('Medications Given', 'medication_count'),
        ('Wounds Treated', 'wound_count'),
        ('IV Fluid Bags', 'iv_fluid_count'),
    )

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('order_id.patient_id').ids

    def to_fhir(self, note):
        order = note.order_id
        resource = {
            'resourceType': 'DocumentReference',
            'id': str(note.id),
            'meta': self.meta(note),
            'status': 'current',
            'type': {'text': 'Clinical visit note'},
            'subject': self.reference('Patient', order.patient_id.id,
                                      display=order.patient_id.name),
            'context': {
                'encounter': [self.reference('Encounter', order.id)],
            },
            'content': self._content(note),
        }
        if note.create_date:
            resource['date'] = fhir_instant(note.create_date)
        author = self._author(note)
        if author:
            resource['author'] = [author]
        # EMR record-spine reflection (health_emr — optional module). Read the
        # fields defensively so health_fhir_core never depends on health_emr,
        # exactly like the `'employee_id' in user._fields` guard in _author.
        if 'emr_state' in note._fields:
            resource['docStatus'] = (
                'final' if note.emr_state == 'final' else 'preliminary')
            authenticator = self._authenticator(note)
            if authenticator:
                resource['authenticator'] = authenticator
            if note.amends_note_id:
                resource['relatesTo'] = [{
                    'code': 'appends',
                    'target': self.reference(
                        'DocumentReference', note.amends_note_id.id),
                }]
        return resource

    def _authenticator(self, note):
        """The clinician who signed the finalized note (DocumentReference.
        authenticator). Mirrors _author's Practitioner resolution."""
        user = note.signed_by_id
        if not user:
            return None
        employee = user.employee_id if 'employee_id' in user._fields else False
        if employee and employee.healthcare_facility_id:
            return self.reference('Practitioner', employee.id,
                                  display=employee.name)
        if user.name:
            return {'display': user.name}
        return None

    def _author(self, note):
        user = note.author_id
        if user:
            employee = user.employee_id if 'employee_id' in user._fields else False
            if employee and employee.healthcare_facility_id:
                return self.reference('Practitioner', employee.id,
                                      display=employee.name)
        if note.author_name:
            return {'display': note.author_name}
        return None

    def _content(self, note):
        content = [{
            'attachment': {
                'contentType': 'text/plain; charset=utf-8',
                'data': base64.b64encode(
                    self.compile_text(note).encode('utf-8')).decode('ascii'),
                'title': note.display_name or 'Clinical visit note',
            },
        }]
        base_url = note.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or ''
        for attachment in note.image_ids:
            content.append({
                'attachment': {
                    'contentType': attachment.mimetype or 'application/octet-stream',
                    'url': '%s/web/content/%s' % (base_url, attachment.id),
                    'title': attachment.name or '',
                },
            })
        return content

    def compile_text(self, note):
        """Concatenate the populated labeled sections (vi diacritics preserved)."""
        parts = []
        for label, field_name, is_html in self.TEXT_SECTIONS:
            value = note[field_name]
            if is_html:
                value = strip_html(value)
            if value:
                parts.append('%s:\n%s' % (label, str(value).strip()))
        counts = [
            '%s: %s' % (label, note[field_name])
            for label, field_name in self.COUNT_SECTIONS
            if note[field_name]
        ]
        if counts:
            parts.append('Counts:\n' + '\n'.join(counts))
        return '\n\n'.join(parts)
