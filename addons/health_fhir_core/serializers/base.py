# -*- coding: utf-8 -*-
"""Base serializer for the health19 FHIR R4 facade (read-only, Phase 1).

Design (docs/strategy/design-platform-services.md §C.2):
- one serializer class per resource, registered in ``serializers/__init__.py``;
- FHIR ``id`` is the Odoo record id (stable);
- ``meta.lastUpdated`` is ``write_date`` serialized as UTC with explicit offset;
- search params are translated to ORM domains through per-param callables;
- unsupported search params raise a strict 400 ``OperationOutcome``
  (``issue.code='not-supported'``) — never silently ignored;
- pagination is cursor-based: ``_count`` (default 50, max 200) +
  ``_cursor=<last id>`` with ``order id asc`` and ``('id', '>', cursor)``.
"""

import importlib
import logging
import random
import re
from datetime import date, datetime

_logger = logging.getLogger(__name__)

COUNT_DEFAULT = 50
COUNT_MAX = 200

# Coding-system URIs shared across Phase 2 serializers (handover §2.4).
LOINC_SYSTEM = 'http://loinc.org'
UCUM_SYSTEM = 'http://unitsofmeasure.org'
RXNORM_SYSTEM = 'http://www.nlm.nih.gov/research/umls/rxnorm'
DAV_SYSTEM = 'https://dav.gov.vn/so-dang-ky'

# Query params handled by the framework itself (not per-resource search params).
RESERVED_PARAMS = ('_count', '_cursor', '_format')

_DATE_PREFIX_OPS = {
    'ge': '>=',
    'le': '<=',
    'gt': '>',
    'lt': '<',
    'eq': '=',
}

_DATE_RE = re.compile(
    r'^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?'
    r'(?:T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?'
    r'(Z|[+-]\d{2}:\d{2})?)?$'
)


# ---------------------------------------------------------------------------
# Errors → OperationOutcome
# ---------------------------------------------------------------------------

class FHIRError(Exception):
    """Base error carrying an HTTP status + OperationOutcome issue code."""
    status = 500
    issue_code = 'exception'

    def __init__(self, diagnostics=''):
        super().__init__(diagnostics)
        self.diagnostics = diagnostics

    def to_operation_outcome(self):
        return {
            'resourceType': 'OperationOutcome',
            'issue': [{
                'severity': 'error',
                'code': self.issue_code,
                'diagnostics': self.diagnostics or self.__class__.__name__,
            }],
        }


class FHIRNotFound(FHIRError):
    status = 404
    issue_code = 'not-found'


class FHIRBadRequest(FHIRError):
    status = 400
    issue_code = 'invalid'


class FHIRNotSupported(FHIRError):
    status = 400
    issue_code = 'not-supported'


class FHIRUnauthorized(FHIRError):
    status = 401
    issue_code = 'login'


class FHIRForbidden(FHIRError):
    status = 403
    issue_code = 'forbidden'


# ---------------------------------------------------------------------------
# Datetime / value helpers
# ---------------------------------------------------------------------------

def fhir_instant(dt):
    """Naive-UTC Odoo datetime → FHIR instant string with explicit offset."""
    if not dt:
        return None
    if isinstance(dt, str):  # already formatted / odoo str datetime
        dt = datetime.fromisoformat(dt)
    return dt.replace(microsecond=0).isoformat() + '+00:00'


def fhir_date(d):
    """Odoo Date → FHIR date string (YYYY-MM-DD)."""
    if not d:
        return None
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def parse_date_search_value(value):
    """Parse one FHIR date search value ``[prefix]YYYY[-MM[-DD[Thh:mm...]]]``.

    Returns ``(odoo_operator, datetime)``. Raises FHIRBadRequest on garbage.
    Naive comparison against Odoo's naive-UTC datetimes; an explicit offset in
    the search value is honoured by normalizing to UTC.
    """
    prefix = 'eq'
    raw = value or ''
    if len(raw) >= 2 and raw[:2] in _DATE_PREFIX_OPS:
        prefix, raw = raw[:2], raw[2:]
    m = _DATE_RE.match(raw)
    if not m:
        raise FHIRBadRequest("Invalid date search value: %r" % value)
    year, month, day, hour, minute, second, tz = m.groups()
    dt = datetime(
        int(year), int(month or 1), int(day or 1),
        int(hour or 0), int(minute or 0), int(second or 0),
    )
    if tz and tz != 'Z':
        # normalize explicit offset to UTC
        sign = 1 if tz[0] == '+' else -1
        oh, om = int(tz[1:3]), int(tz[4:6])
        from datetime import timedelta
        dt -= sign * timedelta(hours=oh, minutes=om)
    return _DATE_PREFIX_OPS[prefix], dt


def date_param_domain(field_name):
    """Build a search-param domain callable for a FHIR ``date`` param."""
    def _domain(value):
        op, dt = parse_date_search_value(value)
        if op == '=':
            # eq on a (partial) date == the enclosing day for datetimes
            from datetime import timedelta
            return ['&', (field_name, '>=', dt),
                    (field_name, '<', dt + timedelta(days=1))]
        return [(field_name, op, dt)]
    return _domain


def token_domain(field_name, system_uri=None):
    """FHIR token search: accept `code`, `system|code`, `|code`.
    A non-matching explicit system yields ZERO matches (FHIR semantics:
    not an error), via an impossible domain."""
    def _domain(value):
        raw = (value or '').strip()
        if '|' in raw:
            system, _, code = raw.rpartition('|')
            if system and system_uri and system != system_uri:
                return [('id', '=', 0)]
            raw = code
        return [(field_name, '=', raw)]
    return _domain


#: field name used only to carry a parsed token value out of ``token_domain``
#: (see ``token_status_domain``) — it is never part of a real domain.
_TOKEN_SINK = '__token__'


def token_status_domain(translate, system_uri=None):
    """Adapt a bare-value token callable to the full token syntax.

    The status params do not map one code onto one column — they reverse a
    state→status table into ``('state', 'in', [...])`` — so they cannot use
    ``token_domain`` directly. They still must accept `system|code` and
    `|code` (G17). The grammar itself is parsed by ``token_domain`` over a
    throwaway field name, so there is ONE implementation of the token syntax
    in this module, not two: either the parse rejects the system (the
    impossible domain is returned verbatim) or its parsed code is handed to
    the caller's bare-value ``translate``.
    """
    parse = token_domain(_TOKEN_SINK, system_uri)

    def _domain(value):
        parsed = parse(value)
        if parsed[0][0] != _TOKEN_SINK:  # explicit, non-matching system
            return parsed
        return translate(parsed[0][2])
    return _domain


#: FHIR `string` search-param modifiers this facade implements. Anything else
#: is a strict 400 (`FHIRNotSupported`) — never silently ignored.
STRING_MODIFIERS = ('exact', 'contains')


def escape_like(value):
    """Escape SQL LIKE wildcards in a user-supplied search value, so a `%` or
    `_` inside a name cannot act as a wildcard in the generated pattern."""
    return ((value or '')
            .replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_'))


def string_param_domain(field_name):
    """FHIR `string` search-param semantics (R4 §3.1.1.6 "string"):

    - no modifier → case-insensitive **starts-with** (the spec default; the
      facade previously did a substring match, which is `:contains`);
    - `:contains` → case-insensitive anywhere in the field;
    - `:exact`    → exact value, case- and accent-sensitive.
    """
    def _domain(value, modifier=None):
        raw = (value or '').strip()
        if modifier == 'exact':
            return [(field_name, '=', raw)]
        if modifier == 'contains':
            return [(field_name, 'ilike', raw)]
        return [(field_name, '=ilike', escape_like(raw) + '%')]
    return _domain


def parse_reference_value(value, expected_type):
    """``Patient/123`` or ``123`` → int id. Strict on type mismatch."""
    raw = (value or '').strip()
    if '/' in raw:
        rtype, _, rid = raw.rpartition('/')
        rtype = rtype.rpartition('/')[2] or rtype  # tolerate absolute URLs
        if rtype != expected_type:
            raise FHIRBadRequest(
                "Reference search value %r does not target %s" % (value, expected_type))
        raw = rid
    if not raw.isdigit():
        raise FHIRBadRequest("Invalid reference search value: %r" % value)
    return int(raw)


def strip_html(html_text):
    """Odoo Html field → plain text (lazy import to keep py_compile clean)."""
    if not html_text:
        return ''
    from odoo.tools import html2plaintext
    return html2plaintext(html_text)


# ---------------------------------------------------------------------------
# fhir.resources (pydantic v2) validation
# ---------------------------------------------------------------------------

def validate_resource(resource_dict):
    """Construct-and-validate ``resource_dict`` via the ``fhir.resources``
    pydantic classes (R4B when available). Returns the pydantic instance;
    raises ``pydantic.ValidationError`` on invalid content and ImportError
    when the library is missing.

    Used by tests on every serialized resource, and optionally at runtime
    behind the ``health_fhir_core.validate_responses`` config parameter.
    """
    rtype = resource_dict.get('resourceType')
    if not rtype:
        raise ValueError('resource dict has no resourceType')
    mod_name = rtype.lower()
    try:
        module = importlib.import_module('fhir.resources.R4B.%s' % mod_name)
    except ImportError:
        module = importlib.import_module('fhir.resources.%s' % mod_name)
    cls = getattr(module, rtype)
    return cls.model_validate(resource_dict)


def validation_enabled(env):
    """Optional runtime validation flag (§C spec: 'optionally behind a config flag').

    All-or-nothing: validate EVERY response. Correct for a staging box, too
    expensive to be the only setting a production deployment has — which is
    why it was simply left off, and why G10 stayed open. See
    ``validation_sample_hit`` for the two settings that make it affordable."""
    try:
        value = env['ir.config_parameter'].sudo().get_param(
            'health_fhir_core.validate_responses')
        return str(value).lower() in ('1', 'true', 'yes', 'on')
    except Exception:  # pragma: no cover - never break serving on flag lookup
        return False


#: Sampled runtime validation (control C4 / register item G10).
VALIDATE_SAMPLE_PCT_PARAM = 'health_fhir_core.validate_sample_pct'
VALIDATE_CANARY_CLIENT_PARAM = 'health_fhir_core.validate_canary_client'


def validation_sample_pct(env):
    """``health_fhir_core.validate_sample_pct`` as an int in [0, 100].

    Parsed defensively and clamped: an unset, blank or garbage value means 0
    (off). A config-parameter typo must not become an outage — and it must
    not silently mean 100 either."""
    try:
        raw = env['ir.config_parameter'].sudo().get_param(
            VALIDATE_SAMPLE_PCT_PARAM)
    except Exception:  # pragma: no cover — never break serving on a lookup
        return 0
    if raw in (None, False, ''):
        return 0
    try:
        pct = int(float(str(raw).strip()))
    except (TypeError, ValueError):
        _logger.warning('%s is not a number (%r) — sampling treated as 0',
                        VALIDATE_SAMPLE_PCT_PARAM, raw)
        return 0
    return max(0, min(100, pct))


def validation_sample_hit(env, client_label=None):
    """True when THIS response should be validated even though the global
    ``validate_responses`` flag is off (control C4, register item G10).

    Two independent triggers, both read per request:

    - ``health_fhir_core.validate_canary_client`` names ONE client label —
      the key/client id the gateway already stamps on every audit row
      (``request.gateway_auth['key_ref']``). Every response to that client is
      validated, which is what an integration partner mid-onboarding actually
      needs, and it costs nothing for everyone else;
    - ``health_fhir_core.validate_sample_pct`` validates that percentage of
      everything else, drawn per response.

    Never raises: a failure to read the flags means "do not validate", not
    "500 the caller".
    """
    try:
        canary = env['ir.config_parameter'].sudo().get_param(
            VALIDATE_CANARY_CLIENT_PARAM)
    except Exception:  # pragma: no cover
        canary = None
    canary = (canary or '').strip()
    if canary and client_label and canary == str(client_label).strip():
        return True
    pct = validation_sample_pct(env)
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    return random.random() * 100 < pct


# Consent-aware access (architecture §6.6). The FHIR facade must not serve a
# patient's PHI to an external system without an active `data_sharing` consent.
# Independent flag (separate from `health_consent.enforce`) so the facade can be
# gated on its own: default OFF = LOG-ONLY (every check is written to
# health.consent.check.log for the audit trail, but nothing is withheld);
# ON = deny-by-default (un-consented patients' resources are filtered/hidden).
CONSENT_SHARING_TYPE = 'data_sharing'


def consent_enforced(env):
    try:
        value = env['ir.config_parameter'].sudo().get_param(
            'health_fhir_core.consent_enforced')
        return str(value).lower() in ('1', 'true', 'yes', 'on')
    except Exception:  # pragma: no cover
        return False


def consent_allowed_records(env, serializer, records, enforced):
    """Return the subset of `records` whose patient(s) have active
    `data_sharing` consent. ALWAYS runs the per-patient check (each writes a
    health.consent.check.log row — the audit trail of what was/would-be shared).
    In log-only mode (`enforced=False`) returns `records` unchanged. Non-PHI
    resources (patient_ids_of == []) are never gated. A record is kept only if
    EVERY patient it carries is consented (deny-by-default)."""
    all_pids = set(serializer.patient_ids_of(records))
    if not all_pids:
        return records  # non-PHI resource — never consent-gated
    Consent = env['health.consent'].with_context(
        consent_check_source='fhir_facade')
    consented = {
        pid for pid in all_pids
        if Consent.check_consent(pid, CONSENT_SHARING_TYPE)}
    if not enforced or consented == all_pids:
        return records
    return records.filtered(
        lambda r: set(serializer.patient_ids_of(r)) <= consented)


# ---------------------------------------------------------------------------
# Base serializer
# ---------------------------------------------------------------------------

class FHIRSerializer:
    """One instance per resource type, registered in ``serializers.REGISTRY``."""

    resource_type = None      # e.g. 'Patient'
    odoo_model = None         # e.g. 'res.partner'

    #: name -> {'type': 'token|string|date|reference', 'domain': callable(value)->domain}
    search_params = {}

    #: optional explicit prefetch list; None = all stored non-relational-heavy
    #: fields (legacy behaviour). Serializers over models with group-gated
    #: fields (res.partner!) MUST declare this (§5.47 corollary).
    prefetch_fields = None

    @property
    def scope(self):
        return 'system/%s.read' % self.resource_type

    # -- to implement per resource ------------------------------------------

    def base_domain(self, env):
        """Domain selecting the records that exist as this resource."""
        return []

    def to_fhir(self, record):
        """One prefetched record → FHIR resource dict."""
        raise NotImplementedError

    def patient_ids_of(self, records):
        """res.partner ids of the patients whose PHI these records carry."""
        return []

    # -- shared helpers -------------------------------------------------------

    def meta(self, record):
        return {'lastUpdated': fhir_instant(record.write_date)}

    def reference(self, resource_type, rid, display=None):
        ref = {'reference': '%s/%s' % (resource_type, rid)}
        if display:
            ref['display'] = display
        return ref

    def serialize_batch(self, records):
        """N+1-safe batch serialization: warm the prefetch cache with one
        read, then serialize each record (relational traversals hit the
        per-recordset prefetch, not per-record queries).

        The blanket "every stored field" fetch is a G14 defect on any model
        carrying group-gated fields (``res.partner`` drags accounting's
        ``credit_limit`` / ``signup_type``, so a minimally-scoped service user
        got an AccessError on ANY Patient serialization). A serializer over
        such a model declares ``prefetch_fields`` and only those are read.
        """
        if records:
            if self.prefetch_fields is not None:
                names = [f for f in self.prefetch_fields
                         if f in records._fields and records._fields[f].store]
            else:
                names = [fname for fname, f in records._fields.items()
                         if f.store and f.type not in (
                             'binary', 'image', 'one2many', 'many2many')]
            records.fetch(names)
        return [self.to_fhir(rec) for rec in records]

    # -- search translation ---------------------------------------------------

    def build_domain(self, env, params):
        """``params`` is a dict of name -> list[str] (repeats allowed, ANDed).

        A param name may carry a modifier (`name:contains=…`). Modifiers are
        accepted on `string`-typed params only, and only the two this facade
        implements (``STRING_MODIFIERS``); everything else — an unknown param,
        an unknown modifier, a modifier on a non-string param — is a strict
        400 FHIRNotSupported (architecture §1.2: never silently ignored).
        """
        domain = list(self.base_domain(env))
        for raw_name, values in params.items():
            if raw_name in RESERVED_PARAMS:
                continue
            name, _sep, modifier = raw_name.partition(':')
            if name == '_lastUpdated':
                param_type = 'date'
                translate = date_param_domain('write_date')
            elif name in self.search_params:
                spec = self.search_params[name]
                param_type = spec['type']
                translate = spec['domain']
            else:
                raise FHIRNotSupported(
                    "Search parameter %r is not supported on %s"
                    % (raw_name, self.resource_type))
            if modifier and (param_type != 'string'
                             or modifier not in STRING_MODIFIERS):
                raise FHIRNotSupported(
                    "Search modifier %r is not supported on %s.%s"
                    % (modifier, self.resource_type, name))
            for value in values:
                domain += (translate(value, modifier) if param_type == 'string'
                           else translate(value))
        return domain

    @staticmethod
    def parse_count(params):
        raw = (params.get('_count') or [None])[0]
        if raw is None:
            return COUNT_DEFAULT
        try:
            count = int(raw)
        except (TypeError, ValueError):
            raise FHIRBadRequest("Invalid _count value: %r" % raw)
        if count <= 0:
            raise FHIRBadRequest("_count must be a positive integer")
        return min(count, COUNT_MAX)

    @staticmethod
    def parse_cursor(params):
        raw = (params.get('_cursor') or [None])[0]
        if raw is None:
            return None
        if not str(raw).isdigit():
            raise FHIRBadRequest("Invalid _cursor value: %r" % raw)
        return int(raw)

    def search_records(self, env, params):
        """Translate + execute a FHIR search.

        Returns ``(records, total, next_cursor)`` where ``next_cursor`` is
        the id to pass as ``_cursor`` for the next page, or None when the
        result set is exhausted.
        """
        if '_format' in params:
            fmt = params['_format'][0]
            if fmt not in ('json', 'application/json', 'application/fhir+json'):
                raise FHIRNotSupported("_format %r is not supported" % fmt)
        domain = self.build_domain(env, params)
        count = self.parse_count(params)
        cursor = self.parse_cursor(params)
        total = env[self.odoo_model].search_count(domain)
        page_domain = domain + [('id', '>', cursor)] if cursor else domain
        records = env[self.odoo_model].search(
            page_domain, order='id asc', limit=count + 1)
        next_cursor = None
        if len(records) > count:
            records = records[:count]
            next_cursor = records[-1].id
        return records, total, next_cursor

    def read_record(self, env, rid):
        """Read one record honouring base_domain + record rules; None if absent."""
        return env[self.odoo_model].search(
            self.base_domain(env) + [('id', '=', rid)], limit=1)

    def search_bundle(self, env, params, base_url='', record_filter=None):
        """Full searchset Bundle for the controller (and tests). `record_filter`
        (the consent gate, when the controller passes one) is applied to the
        fetched page BEFORE serialization; `total` is adjusted down by whatever
        it dropped on this page (approximate across pages, but never over-counts
        what is actually returned — safe for a deny-by-default filter)."""
        records, total, next_cursor = self.search_records(env, params)
        if record_filter is not None:
            kept = record_filter(records)
            total = max(0, total - (len(records) - len(kept)))
            records = kept
        resources = self.serialize_batch(records)
        self_url = self._page_url(base_url, params, None)
        bundle = {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': total,
            'link': [{'relation': 'self', 'url': self_url}],
            'entry': [{
                'fullUrl': '%s/fhir/r4/%s/%s' % (base_url, self.resource_type, res['id']),
                'resource': res,
                'search': {'mode': 'match'},
            } for res in resources],
        }
        if next_cursor is not None:
            bundle['link'].append({
                'relation': 'next',
                'url': self._page_url(base_url, params, next_cursor),
            })
        return bundle, records

    def _page_url(self, base_url, params, cursor):
        from urllib.parse import urlencode
        pairs = []
        for name, values in params.items():
            if name == '_cursor':
                continue
            for value in values:
                pairs.append((name, value))
        if cursor is not None:
            pairs.append(('_cursor', str(cursor)))
        query = urlencode(pairs)
        url = '%s/fhir/r4/%s' % (base_url, self.resource_type)
        return '%s?%s' % (url, query) if query else url
