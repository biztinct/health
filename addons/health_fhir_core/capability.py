# -*- coding: utf-8 -*-
"""CapabilityStatement generated from the serializer registry (§C.5).

Never hand-list resources: everything is derived from
``health_fhir_core.serializers.REGISTRY``. The statement is cached at module
level (the registry is import-time static; a server restart — which is also
what reloads the registry — invalidates the cache).
"""

from datetime import datetime, timezone

from .serializers import REGISTRY

SECURITY_SERVICE_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/restful-security-service')

_CAPABILITY_CACHE = {}


def build_capability(env, base_url=''):
    cache_key = base_url or '-'
    cached = _CAPABILITY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    resources = []
    for resource_type in sorted(REGISTRY):
        serializer = REGISTRY[resource_type]
        search_params = [
            {'name': name, 'type': spec['type']}
            for name, spec in sorted(serializer.search_params.items())
        ]
        search_params.append({'name': '_lastUpdated', 'type': 'date'})
        search_params.append({'name': '_count', 'type': 'number'})
        resources.append({
            'type': resource_type,
            'interaction': [{'code': 'read'}, {'code': 'search-type'}],
            'searchParam': search_params,
        })

    statement = {
        'resourceType': 'CapabilityStatement',
        'status': 'active',
        'date': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'kind': 'instance',
        'name': 'Health19FHIRFacade',
        'title': 'health19 FHIR R4 Facade (read-only, Phase 1)',
        'description': (
            'Read-only FHIR R4 facade over the health19 home-care platform. '
            'Auth: API gateway tokens with system/<Resource>.read scopes. '
            'Note: DocumentReference image content[].attachment.url entries '
            'point at Odoo /web/content endpoints which require separate '
            'Odoo authentication.'),
        'publisher': 'health19',
        'fhirVersion': '4.0.1',
        'format': ['application/fhir+json'],
        'implementation': {
            'description': 'health19 FHIR R4 facade',
            'url': '%s/fhir/r4' % base_url if base_url else '/fhir/r4',
        },
        'rest': [{
            'mode': 'server',
            'security': {
                'service': [{
                    'coding': [{
                        'system': SECURITY_SERVICE_SYSTEM,
                        'code': 'OAuth',
                    }],
                }],
            },
            'resource': resources,
        }],
    }
    _CAPABILITY_CACHE[cache_key] = statement
    return statement


def clear_capability_cache():
    _CAPABILITY_CACHE.clear()
