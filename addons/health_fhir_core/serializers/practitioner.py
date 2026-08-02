# -*- coding: utf-8 -*-
"""Practitioner ← hr.employee (healthcare_facility_id set).

Employment data stays out of Practitioner (belongs to PractitionerRole, Phase 2).
CCHN practising licence (license_number) uses the MOH system URI per §1.1.
"""

from .base import FHIRSerializer, string_param_domain

CCHN_SYSTEM = 'https://moh.gov.vn/cchn'


def _identifier_domain(value):
    value = (value or '').strip()
    if '|' in value:
        value = value.rsplit('|', 1)[1]
    domain = ['|', ('staff_code', '=', value), ('license_number', '=', value)]
    if value.isdigit():
        domain = ['|', ('id', '=', int(value))] + domain
    return domain


class PractitionerSerializer(FHIRSerializer):
    resource_type = 'Practitioner'
    odoo_model = 'hr.employee'

    search_params = {
        'identifier': {'type': 'token', 'domain': _identifier_domain},
        'name': {'type': 'string', 'domain': string_param_domain('name')},
    }

    #: G14, second instance — `hr.employee` is as group-gated as `res.partner`.
    #: The blanket "every stored field" prefetch dragged ~30 fields that
    #: `hr.employee` reserves for `hr.group_hr_user` (`private_phone`,
    #: `birthday`, `salary_distribution`, `hourly_cost`, `pin`, …), so ANY
    #: Practitioner serialization raised AccessError — "are not available for
    #: employee public profiles" — for a service user without an HR group.
    #: Identical defect to the one D1 fixed on Patient in GC-1; found live by
    #: the GC-3 deploy smoke. Only the fields `to_fhir`/`_identifiers` read.
    #:
    #: `healthcare_skill_ids` is deliberately ABSENT and the prefetch does not
    #: cure it: hr treats every field outside its public-profile whitelist as
    #: private, so reading it for `qualification` still needs an HR group.
    #: Exposing it belongs in health_base (not sanctioned by GC-3) — until
    #: then a Practitioner-reading token needs an HR-privileged service user.
    prefetch_fields = [
        'name', 'active', 'staff_code', 'license_number',
        'work_phone', 'work_email', 'healthcare_facility_id', 'write_date',
    ]

    def base_domain(self, env):
        return [('healthcare_facility_id', '!=', False)]

    def patient_ids_of(self, records):
        return []

    def to_fhir(self, employee):
        resource = {
            'resourceType': 'Practitioner',
            'id': str(employee.id),
            'meta': self.meta(employee),
            'active': bool(employee.active),
            'identifier': self._identifiers(employee),
            'name': [{'text': employee.name or ''}],
        }
        telecom = []
        if employee.work_phone:
            telecom.append({'system': 'phone', 'value': employee.work_phone,
                            'use': 'work'})
        if employee.work_email:
            telecom.append({'system': 'email', 'value': employee.work_email,
                            'use': 'work'})
        if telecom:
            resource['telecom'] = telecom
        qualifications = [
            {'code': {'text': skill.name}}
            for skill in employee.healthcare_skill_ids if skill.name
        ]
        if qualifications:
            resource['qualification'] = qualifications
        return resource

    def _identifiers(self, employee):
        identifiers = [{'system': 'urn:health19:employee', 'value': str(employee.id)}]
        if employee.staff_code:
            identifiers.append({
                'system': 'urn:health19:staff-code',
                'value': employee.staff_code,
            })
        if employee.license_number:
            identifiers.append({
                'system': CCHN_SYSTEM,
                'value': employee.license_number,
            })
        return identifiers
