# -*- coding: utf-8 -*-
"""Patient ← res.partner (is_patient=True).

Mapping per architecture-interop.md §1.1 / design-platform-services.md §C.3.
`national_id` is a computed encrypted field (health_phi_encryption) that reads
transparently through the ORM but only supports exact-match search.
"""

from .base import (
    FHIRSerializer, fhir_date, date_param_domain, string_param_domain,
)

VNEID_SYSTEM = 'https://vneid.gov.vn/id'

_GENDER_MAP = {
    'male': 'male',
    'female': 'female',
    'other': 'other',
    'prefer_not_to_say': 'unknown',
}


def _identifier_domain(value):
    """token → odoo id | patient_code | national_id (exact match only)."""
    value = (value or '').strip()
    # tolerate `system|value` token syntax: match on the value part
    if '|' in value:
        value = value.rsplit('|', 1)[1]
    domain = ['|', ('patient_code', '=', value), ('national_id', '=', value)]
    if value.isdigit():
        domain = ['|', ('id', '=', int(value))] + domain
    return domain


def _phone_domain(value):
    digits = ''.join(ch for ch in (value or '') if ch.isdigit() or ch == '+')
    needle = digits or (value or '').strip()
    return ['|', ('phone', 'ilike', needle), ('mobile', 'ilike', needle)]


class PatientSerializer(FHIRSerializer):
    resource_type = 'Patient'
    odoo_model = 'res.partner'

    search_params = {
        'identifier': {'type': 'token', 'domain': _identifier_domain},
        'name': {'type': 'string', 'domain': string_param_domain('name')},
        'telecom': {'type': 'token', 'domain': _phone_domain},
        'phone': {'type': 'token', 'domain': _phone_domain},
        'birthdate': {'type': 'date', 'domain': date_param_domain('birth_date')},
    }

    # G14: res.partner carries group-gated accounting fields (credit_limit,
    # signup_type, …) that a blanket stored-field prefetch would read, 403-ing
    # any minimally-scoped service user. Only the fields `to_fhir` maps are
    # prefetched. The computed `national_id` / `catchment_province_name` are
    # intentionally absent — they compute transparently on access and the
    # store-filter in serialize_batch would drop them anyway.
    prefetch_fields = [
        'name', 'active', 'patient_code', 'insurance_number',
        'phone', 'mobile', 'email', 'zalo_user_id', 'gender', 'birth_date',
        'deceased', 'street', 'street2', 'vietnamese_address', 'city', 'zip',
        'district_id', 'state_id', 'country_id', 'primary_facility_id',
        'write_date',
    ]

    def base_domain(self, env):
        return [('is_patient', '=', True)]

    def patient_ids_of(self, records):
        return records.ids

    def to_fhir(self, partner):
        resource = {
            'resourceType': 'Patient',
            'id': str(partner.id),
            'meta': self.meta(partner),
            'active': bool(partner.active),
            'identifier': self._identifiers(partner),
            'name': [{'text': partner.name or ''}],
        }
        telecom = self._telecom(partner)
        if telecom:
            resource['telecom'] = telecom
        gender = _GENDER_MAP.get(partner.gender)
        if gender:
            resource['gender'] = gender
        if partner.birth_date:
            resource['birthDate'] = fhir_date(partner.birth_date)
        if partner.deceased:
            resource['deceasedBoolean'] = True
        address = self._address(partner)
        if address:
            resource['address'] = [address]
        if partner.primary_facility_id:
            resource['managingOrganization'] = self.reference(
                'Organization', partner.primary_facility_id.id,
                display=partner.primary_facility_id.name)
        return resource

    def _identifiers(self, partner):
        identifiers = [{'system': 'urn:health19:partner', 'value': str(partner.id)}]
        if partner.patient_code:
            identifiers.append({
                'system': 'urn:health19:patient-code',
                'value': partner.patient_code,
            })
        # national_id decrypts transparently via the ORM (health_phi_encryption)
        if partner.national_id:
            identifiers.append({
                'system': VNEID_SYSTEM,
                'value': partner.national_id,
            })
        if partner.insurance_number:
            identifiers.append({
                'system': 'urn:health19:bhyt',
                'value': partner.insurance_number,
            })
        return identifiers

    def _telecom(self, partner):
        telecom = []
        if partner.phone:
            telecom.append({'system': 'phone', 'value': partner.phone, 'use': 'home'})
        if partner.mobile:
            telecom.append({'system': 'phone', 'value': partner.mobile, 'use': 'mobile'})
        if partner.email:
            telecom.append({'system': 'email', 'value': partner.email})
        # zalo id comes from health_zalo when installed — guard on the field
        if 'zalo_user_id' in partner._fields and partner.zalo_user_id:
            telecom.append({
                'system': 'other',
                'value': partner.zalo_user_id,
                'extension': [{
                    'url': 'urn:health19:zalo',
                    'valueString': 'zalo_user_id',
                }],
            })
        return telecom

    def _address(self, partner):
        """Vietnamese address structure → FHIR Address (district/state kept)."""
        address = {}
        lines = [line for line in (partner.street, partner.street2) if line]
        if lines:
            address['line'] = lines
        if partner.vietnamese_address:
            address['text'] = partner.vietnamese_address
        if partner.city:
            address['city'] = partner.city
        if partner.district_id:
            address['district'] = partner.district_id.name
        state = partner.catchment_province_name or (
            partner.state_id.name if partner.state_id else None)
        if state:
            address['state'] = state
        if partner.zip:
            address['postalCode'] = partner.zip
        if not address:
            return None
        address['country'] = (partner.country_id.code or 'VN') \
            if partner.country_id else 'VN'
        return address
