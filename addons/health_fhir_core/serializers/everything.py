# -*- coding: utf-8 -*-
"""Patient ``$everything`` — whole-record clinical export (composes the
existing serializers; no new resource serializers, no new clinical models).

The FHIR ``Patient/$everything`` operation returns a patient's complete
clinical record in one interoperable, single-consent ``searchset`` Bundle
(the Circular-13 EMR-handoff / referral use case). It is the READ-facade
analog of ``fhir.adapter.vn.build_patient_bundle`` (the OUTBOUND VN MOH
bundle): both walk the patient compartment by reusing each serializer's own
``search_params['patient']['domain']('Patient/<id>')`` callable — one
canonical field path, no per-field guessing and no per-serializer hook.

Safety: this operation is AT LEAST as strict as the per-resource facade.
It runs under the caller's env (record rules apply) and makes ONE
whole-record ``data_sharing`` consent decision (logged once, source
``fhir_everything``); a denial returns ``FHIRNotFound`` (no existence
reveal). A whole-record export is the highest PHI-leak blast radius in the
system, so it never widens beyond the patient's own compartment and never
silently truncates a medical record — if a cap is hit, an OperationOutcome
``information`` entry declares it.
"""

from urllib.parse import urlencode

from odoo.exceptions import AccessError

from . import REGISTRY
from .base import (
    CONSENT_SHARING_TYPE,
    FHIRBadRequest, FHIRNotFound,
    consent_enforced, parse_date_search_value,
)

# Whole-record export returns a large page by default (a referral pulls the
# complete record, not a 50-row page). Hard-capped so a huge record can never
# freeze the server; past the cap, truncation is DECLARED, never silent.
EVERYTHING_COUNT_DEFAULT = 200
EVERYTHING_COUNT_MAX = 1000

CONSENT_CHECK_SOURCE = 'fhir_everything'


def patient_compartment(env, patient_id):
    """Yield ``(serializer, forward_domain)`` for every REGISTRY resource in
    the patient's compartment EXCEPT ``Patient`` itself (the compartment
    ROOT, added explicitly by the caller — the Patient serializer has no
    ``patient`` search param, it IS the patient).

    Reuses each serializer's own ``patient`` (or ``subject``) search-param
    domain callable — the same convention ``build_patient_bundle`` relies on.
    A serializer with no such param is non-PHI (Organization / Location /
    Practitioner / Questionnaire template) and is excluded automatically; its
    ``patient_ids_of`` is empty (asserted by the compartment-coverage test)."""
    ref = 'Patient/%d' % patient_id
    for rtype in sorted(REGISTRY):
        if rtype == 'Patient':
            continue
        serializer = REGISTRY[rtype]
        spec = (serializer.search_params.get('patient')
                or serializer.search_params.get('subject'))
        if not spec:
            continue
        yield serializer, list(spec['domain'](ref))


def _parse_type(params):
    """``_type=Observation,Encounter`` (repeatable, comma-joined) → set|None."""
    raw = params.get('_type')
    if not raw:
        return None
    types = set()
    for value in raw:
        for token in value.split(','):
            token = token.strip()
            if token:
                types.add(token)
    return types or None


def _parse_since(params):
    """``_since=<instant>`` → a ``write_date >=`` domain fragment (``[]`` if
    absent). FHIR ``_since`` is a lower bound on ``meta.lastUpdated``."""
    raw = (params.get('_since') or [None])[0]
    if raw is None:
        return []
    _op, dt = parse_date_search_value(raw)
    return [('write_date', '>=', dt)]


def _parse_cap(params):
    """``_count`` bounds the TOTAL entries (default 200, hard max 1000)."""
    raw = (params.get('_count') or [None])[0]
    if raw is None:
        return EVERYTHING_COUNT_DEFAULT
    try:
        count = int(raw)
    except (TypeError, ValueError):
        raise FHIRBadRequest("Invalid _count value: %r" % raw)
    if count <= 0:
        raise FHIRBadRequest("_count must be a positive integer")
    return min(count, EVERYTHING_COUNT_MAX)


def _self_url(base_url, patient_id, params):
    url = '%s/fhir/r4/Patient/%s/$everything' % (base_url, patient_id)
    pairs = [(name, value)
             for name, values in params.items()
             if name != '_cursor'
             for value in values]
    query = urlencode(pairs)
    return '%s?%s' % (url, query) if query else url


def _truncation_outcome(returned, total, cap):
    return {
        'resourceType': 'OperationOutcome',
        'issue': [{
            'severity': 'information',
            'code': 'incomplete',
            'diagnostics': (
                'This $everything response is TRUNCATED: %d of %d matching '
                'resources were returned (cap _count=%d). The record is NOT '
                'complete — narrow the request with _type/_since or raise '
                '_count (max %d) to retrieve the remainder.'
                % (returned, total, cap, EVERYTHING_COUNT_MAX)),
        }],
    }


def _suppressed_outcome(resource_types):
    return {
        'resourceType': 'OperationOutcome',
        'issue': [{
            'severity': 'warning',
            'code': 'suppressed',
            'diagnostics': (
                'This $everything response OMITS resource types the caller is '
                'not authorized to read (%s). The record may be incomplete '
                'for this consumer — no data was leaked, but a complete '
                'export requires broader read authorization.'
                % ', '.join(sorted(resource_types))),
        }],
    }


def build_everything_bundle(env, patient_id, params, base_url='', enforced=None):
    """Build the ``Patient/$everything`` searchset Bundle under the CALLER'S
    env (record rules already applied by the controller).

    Returns ``(bundle, patient_record)``. Raises ``FHIRNotFound`` when the
    patient does not exist, is hidden by record rules, or — under enforcement
    — has no active ``data_sharing`` consent (no existence reveal in any
    case). The consent check is made ONCE for the whole record and always
    logged (source ``fhir_everything``); in log-only mode nothing is withheld
    but the release is still audited."""
    if enforced is None:
        enforced = consent_enforced(env)

    patient_serializer = REGISTRY['Patient']
    patient_record = patient_serializer.read_record(env, patient_id)
    if not patient_record:
        raise FHIRNotFound('No Patient resource with id %s' % patient_id)

    # ONE whole-record consent decision — always logged (the release audit
    # trail), deny-by-default only when enforcement is on.
    Consent = env['health.consent'].with_context(
        consent_check_source=CONSENT_CHECK_SOURCE)
    allowed = Consent.check_consent(patient_id, CONSENT_SHARING_TYPE)
    if enforced and not allowed:
        # Match the per-resource read's 404-on-deny: never confirm the record
        # exists to a caller without consent.
        raise FHIRNotFound('No Patient resource with id %s' % patient_id)

    type_filter = _parse_type(params)
    since_dom = _parse_since(params)
    cap = _parse_cap(params)

    # Deterministic order: Patient first (search.mode 'match'), then the
    # compartment sorted by resource type ('include').
    sources = [(patient_serializer, [('id', '=', patient_id)], 'match')]
    for serializer, dom in patient_compartment(env, patient_id):
        sources.append((serializer, dom, 'include'))

    total = 0
    entries = []
    remaining = cap
    truncated = False
    suppressed = []
    for serializer, dom, mode in sources:
        if type_filter is not None and serializer.resource_type not in type_filter:
            continue
        full_domain = list(serializer.base_domain(env)) + dom + since_dom
        Model = env[serializer.odoo_model]
        try:
            count = Model.search_count(full_domain)
        except AccessError:
            # A compartment model the caller is not authorized to read (e.g. a
            # model with no ir.model.access for the token's groups). Keep the
            # export resilient — OMIT the type but DECLARE it below, never
            # hard-fail the whole record and never leak. Patient (mode 'match')
            # is the root: the caller already passed its read, so this only
            # trips for 'include' compartment resources.
            suppressed.append(serializer.resource_type)
            continue
        total += count
        if count == 0:
            continue
        if remaining <= 0:
            truncated = True
            continue
        records = Model.search(full_domain, order='id asc', limit=remaining + 1)
        if len(records) > remaining:
            truncated = True
            records = records[:remaining]
        for resource in serializer.serialize_batch(records):
            entries.append({
                'fullUrl': '%s/fhir/r4/%s/%s' % (
                    base_url, serializer.resource_type, resource['id']),
                'resource': resource,
                'search': {'mode': mode},
            })
        remaining -= len(records)

    if truncated:
        # Never let a consumer believe a truncated record is complete.
        entries.append({
            'resource': _truncation_outcome(len(entries), total, cap),
            'search': {'mode': 'outcome'},
        })
    if suppressed:
        # Declared authorization omission — the counterpart of "no silent
        # truncation" for record scoping.
        entries.append({
            'resource': _suppressed_outcome(suppressed),
            'search': {'mode': 'outcome'},
        })

    bundle = {
        'resourceType': 'Bundle',
        'type': 'searchset',
        'total': total,
        'link': [{'relation': 'self',
                  'url': _self_url(base_url, patient_id, params)}],
        'entry': entries,
    }
    return bundle, patient_record
