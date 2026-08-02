# -*- coding: utf-8 -*-
"""CapabilityStatement generated from the serializer registry (§C.5).

Never hand-list resources: everything is derived from
``health_fhir_core.serializers.REGISTRY`` (interaction-bearing types) and
``serializers.OPERATIONS`` / ``serializers.OPERATION_ONLY_RESOURCES`` (the
operations each type exposes). The statement is cached at module level (the
registry is import-time static; a server restart — which is also what reloads
the registry — invalidates the cache).

Conformance rules encoded here (GC-1 / G2, G3, G12):
- an operation is declared where it is IMPLEMENTED, from the registry, so a
  route and its declaration cannot drift (asserted by the route-diff test);
- ``_count`` is a framework paging control, NOT a SearchParameter, so it is
  not listed (``_lastUpdated`` is a real search param and stays);
- every searchParam that maps onto a base-spec SearchParameter carries its
  canonical ``definition``; where no canonical is known the key is OMITTED
  (legal) — a guessed canonical is worse than none.
"""

from datetime import datetime, timezone

from .serializers import OPERATIONS, OPERATION_ONLY_RESOURCES, REGISTRY

SECURITY_SERVICE_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/restful-security-service')

SEARCH_PARAM_BASE = 'http://hl7.org/fhir/SearchParameter/'

#: resource type -> {param name: canonical SearchParameter id}. Only params
#: whose semantics match the base-spec definition are listed; anything absent
#: is emitted without a ``definition`` key.
SEARCH_PARAM_DEFINITIONS = {
    'AdverseEvent': {
        # base-spec AdverseEvent has `subject`, not `patient` — no canonical
        # for our spelling, so the key is omitted (review fix, GC-1).
        'date': 'AdverseEvent-date',
        # 'severity' has no base-spec equivalent here — omitted deliberately.
    },
    'Appointment': {
        # Appointment is NOT in the clinical-* common groups — it defines its
        # own patient/date params (review fix, GC-1).
        'patient': 'Appointment-patient',
        'date': 'Appointment-date',
        'status': 'Appointment-status',
    },
    'CarePlan': {
        'patient': 'clinical-patient',
        'date': 'clinical-date',
        'status': 'CarePlan-status',
    },
    'CodeSystem': {
        'url': 'CodeSystem-url',
        # 'name' — base CodeSystem-name is a STRING param on .name; ours is an
        # exact token on the code — semantics differ, so no canonical is
        # claimed (review fix, GC-2).
    },
    'Condition': {
        'patient': 'clinical-patient',
        'code': 'clinical-code',
        'clinical-status': 'Condition-clinical-status',
        'recorded-date': 'Condition-recorded-date',
    },
    'Consent': {
        'patient': 'clinical-patient',
        'status': 'Consent-status',
    },
    'DocumentReference': {
        'patient': 'clinical-patient',
        'encounter': 'clinical-encounter',
        'date': 'DocumentReference-date',
    },
    'Encounter': {
        'patient': 'clinical-patient',
        'date': 'clinical-date',
        'status': 'Encounter-status',
    },
    'Flag': {
        'patient': 'clinical-patient',
    },
    'Goal': {
        'patient': 'clinical-patient',
        'lifecycle-status': 'Goal-lifecycle-status',
    },
    'Location': {
        'name': 'Location-name',
        'organization': 'Location-organization',
    },
    'MedicationAdministration': {
        'patient': 'clinical-patient',
        'status': 'medications-status',
        # 'date' — MedicationAdministration's base param is 'effective-time';
        # no canonical is asserted for our 'date' spelling.
    },
    'MedicationRequest': {
        'patient': 'clinical-patient',
        'status': 'medications-status',
    },
    'Observation': {
        'patient': 'clinical-patient',
        'date': 'clinical-date',
        'code': 'clinical-code',
        'status': 'Observation-status',
    },
    'Organization': {
        'name': 'Organization-name',
        'identifier': 'Organization-identifier',
    },
    'Patient': {
        'identifier': 'Patient-identifier',
        'name': 'Patient-name',
        'birthdate': 'individual-birthdate',
        'phone': 'individual-phone',
        'telecom': 'individual-telecom',
    },
    'Practitioner': {
        'identifier': 'Practitioner-identifier',
        'name': 'Practitioner-name',
    },
    'Questionnaire': {
        # 'name' — base Questionnaire-name is a STRING param; ours is an exact
        # token on the template code (a deliberate deviation, documented in
        # the serializer) — no canonical claimed (review fix, GC-2).
        'status': 'Questionnaire-status',
    },
    'QuestionnaireResponse': {
        # QR is not in clinical-patient — it defines its own (review fix).
        'patient': 'QuestionnaireResponse-patient',
        'status': 'QuestionnaireResponse-status',
        'authored': 'QuestionnaireResponse-authored',
        'questionnaire': 'QuestionnaireResponse-questionnaire',
    },
    'ServiceRequest': {
        'patient': 'clinical-patient',
        'status': 'ServiceRequest-status',
    },
    'Task': {
        # Task is not in the clinical-* groups — own params (review fix).
        'patient': 'Task-patient',
        'status': 'Task-status',
        'encounter': 'Task-encounter',
    },
}

_CAPABILITY_CACHE = {}


def _operations_for(rtype, source):
    """Copy the declared operation dicts (callers must never mutate the
    registry through the statement)."""
    return [dict(operation) for operation in source.get(rtype, ())]


def build_capability(env, base_url=''):
    cache_key = base_url or '-'
    cached = _CAPABILITY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    resources = []
    for resource_type in sorted(REGISTRY):
        serializer = REGISTRY[resource_type]
        definitions = SEARCH_PARAM_DEFINITIONS.get(resource_type, {})
        search_params = []
        for name, spec in sorted(serializer.search_params.items()):
            param = {'name': name, 'type': spec['type']}
            canonical = definitions.get(name)
            if canonical:
                param['definition'] = SEARCH_PARAM_BASE + canonical
            search_params.append(param)
        search_params.append({'name': '_lastUpdated', 'type': 'date'})
        resource = {
            'type': resource_type,
            'interaction': [{'code': 'read'}, {'code': 'search-type'}],
            'searchParam': search_params,
        }
        operations = _operations_for(resource_type, OPERATIONS)
        if operations:
            resource['operation'] = operations
        resources.append(resource)

    # Operation-only types (no serializer → no read/search-type, no
    # searchParam): declaring an interaction we do not serve would be a lie.
    for resource_type in sorted(OPERATION_ONLY_RESOURCES):
        resources.append({
            'type': resource_type,
            'operation': _operations_for(
                resource_type, OPERATION_ONLY_RESOURCES),
        })

    # Version of the deployed facade (G3). Read once per cached statement —
    # the value only changes with an upgrade, which also restarts the process
    # and therefore drops this module-level cache.
    module_version = env['ir.module.module'].sudo().search(
        [('name', '=', 'health_fhir_core')], limit=1).latest_version or 'unknown'

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
        'software': {'name': 'health19 / CarejioX', 'version': module_version},
        'fhirVersion': '4.0.1',
        'format': ['application/fhir+json'],
        'implementation': {
            'description': 'health19 FHIR R4 facade',
            'url': '%s/fhir/r4' % base_url if base_url else '/fhir/r4',
        },
        'rest': [{
            'mode': 'server',
            # Applies across every resource served here (R4: rest.documentation
            # is "capabilities that apply across all applications"). GC-2/G17:
            # string params default to case-insensitive starts-with, and the
            # two modifiers below are the ONLY ones accepted — any other is a
            # 400 not-supported, never silently ignored.
            'documentation': (
                'Read-only. Supported string modifiers: :exact, :contains.'),
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
