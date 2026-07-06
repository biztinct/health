# -*- coding: utf-8 -*-
"""Organization ← health.facility (legal entity view; Location is the site)."""

from .base import FHIRSerializer


def _identifier_domain(value):
    value = (value or '').strip()
    if '|' in value:
        value = value.rsplit('|', 1)[1]
    domain = [('code', '=', value)]
    if value.isdigit():
        domain = ['|', ('id', '=', int(value))] + domain
    return domain


class OrganizationSerializer(FHIRSerializer):
    resource_type = 'Organization'
    odoo_model = 'health.facility'

    search_params = {
        'name': {'type': 'string',
                 'domain': lambda v: [('name', 'ilike', v)]},
        'identifier': {'type': 'token', 'domain': _identifier_domain},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return []

    def to_fhir(self, facility):
        resource = {
            'resourceType': 'Organization',
            'id': str(facility.id),
            'meta': self.meta(facility),
            'active': bool(facility.active),
            'identifier': self._identifiers(facility),
            'name': facility.name or '',
        }
        telecom = []
        if facility.phone:
            telecom.append({'system': 'phone', 'value': facility.phone})
        if facility.email:
            telecom.append({'system': 'email', 'value': facility.email})
        if facility.website:
            telecom.append({'system': 'url', 'value': facility.website})
        if telecom:
            resource['telecom'] = telecom
        address = facility_address(facility)
        if address:
            resource['address'] = [address]
        return resource

    def _identifiers(self, facility):
        identifiers = [{'system': 'urn:health19:facility', 'value': str(facility.id)}]
        if facility.code:
            identifiers.append({
                'system': 'urn:health19:facility-code',
                'value': facility.code,
            })
        return identifiers


def facility_address(facility):
    """Shared by Organization + Location serializers."""
    address = {}
    lines = [line for line in (facility.street, facility.street2) if line]
    if lines:
        address['line'] = lines
    if facility.city:
        address['city'] = facility.city
    if facility.state_id:
        address['state'] = facility.state_id.name
    if facility.zip:
        address['postalCode'] = facility.zip
    if not address:
        return None
    address['country'] = (facility.country_id.code or 'VN') \
        if facility.country_id else 'VN'
    return address
