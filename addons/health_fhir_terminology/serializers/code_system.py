# -*- coding: utf-8 -*-
"""CodeSystem ← medical.coding.system (read + search on the R4 facade).

``content: 'fragment'`` signals a partial representation — concept[] is NOT
inlined (ICD-10 is 14k+ rows); use CodeSystem/$lookup and ValueSet/$expand
for the actual codes."""

from odoo.addons.health_fhir_core.serializers.base import (
    FHIRSerializer, token_domain,
)


class CodeSystemSerializer(FHIRSerializer):
    resource_type = 'CodeSystem'
    odoo_model = 'medical.coding.system'

    # Both params are identifiers of the code system itself, so no system_uri
    # is asserted — `|value` is accepted, an explicit system is not checked
    # against anything (handover §3.1).
    # `url` is declared `uri` per the base CodeSystem-url param (exact match —
    # which token_domain's bare path already is); a versioned `<uri>|<ver>`
    # query parses to the version and finds nothing, honest while we store no
    # versions. `name` stays a token: it exact-matches the system code, not
    # the base spec's string semantics (so no canonical is claimed for it).
    search_params = {
        'url': {'type': 'uri', 'domain': token_domain('uri')},
        'name': {'type': 'token', 'domain': token_domain('code')},
    }

    def base_domain(self, env):
        return [('active', '=', True)]

    def patient_ids_of(self, records):
        return []

    def to_fhir(self, record):
        resource = {
            'resourceType': 'CodeSystem',
            'id': str(record.id),
            'meta': self.meta(record),
            'url': record.uri,
            'name': record.code,
            'status': 'active',
            'content': 'fragment',
            'count': record.code_count,
        }
        if record.version:
            resource['version'] = record.version
        if record.name:
            resource['title'] = record.name
        return resource
