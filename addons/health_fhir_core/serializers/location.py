# -*- coding: utf-8 -*-
"""Location ← health.facility (physical site: position, timezone extension).

Same records as Organization; ``managingOrganization`` points at the facility's
own Organization resource. Timezone is exposed as extension urn:health19:timezone.
"""

from .base import FHIRSerializer, parse_reference_value
from .organization import facility_address

TIMEZONE_EXTENSION_URL = 'urn:health19:timezone'


def _organization_domain(value):
    return [('id', '=', parse_reference_value(value, 'Organization'))]


class LocationSerializer(FHIRSerializer):
    resource_type = 'Location'
    odoo_model = 'health.facility'

    search_params = {
        'name': {'type': 'string',
                 'domain': lambda v: [('name', 'ilike', v)]},
        'organization': {'type': 'reference', 'domain': _organization_domain},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return []

    def to_fhir(self, facility):
        resource = {
            'resourceType': 'Location',
            'id': str(facility.id),
            'meta': self.meta(facility),
            'status': 'active' if facility.active else 'inactive',
            'name': facility.name or '',
            'identifier': [
                {'system': 'urn:health19:facility', 'value': str(facility.id)},
            ],
            'managingOrganization': self.reference(
                'Organization', facility.id, display=facility.name),
        }
        if facility.latitude or facility.longitude:
            resource['position'] = {
                'latitude': facility.latitude,
                'longitude': facility.longitude,
            }
        address = facility_address(facility)
        if address:
            resource['address'] = address
        if facility.timezone:
            resource['extension'] = [{
                'url': TIMEZONE_EXTENSION_URL,
                'valueString': facility.timezone,
            }]
        telecom = []
        if facility.phone:
            telecom.append({'system': 'phone', 'value': facility.phone})
        if telecom:
            resource['telecom'] = telecom
        return resource
