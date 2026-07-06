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
import re
from datetime import date, datetime

_logger = logging.getLogger(__name__)

COUNT_DEFAULT = 50
COUNT_MAX = 200

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
    """Optional runtime validation flag (§C spec: 'optionally behind a config flag')."""
    try:
        value = env['ir.config_parameter'].sudo().get_param(
            'health_fhir_core.validate_responses')
        return str(value).lower() in ('1', 'true', 'yes', 'on')
    except Exception:  # pragma: no cover - never break serving on flag lookup
        return False


# ---------------------------------------------------------------------------
# Base serializer
# ---------------------------------------------------------------------------

class FHIRSerializer:
    """One instance per resource type, registered in ``serializers.REGISTRY``."""

    resource_type = None      # e.g. 'Patient'
    odoo_model = None         # e.g. 'res.partner'

    #: name -> {'type': 'token|string|date|reference', 'domain': callable(value)->domain}
    search_params = {}

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
        per-recordset prefetch, not per-record queries)."""
        if records:
            # single batched fetch of all stored fields into cache
            records.fetch([
                fname for fname, f in records._fields.items()
                if f.store and f.type not in ('binary', 'image', 'one2many', 'many2many')
            ])
        return [self.to_fhir(rec) for rec in records]

    # -- search translation ---------------------------------------------------

    def build_domain(self, env, params):
        """``params`` is a dict of name -> list[str] (repeats allowed, ANDed).

        Raises FHIRNotSupported for any param outside the resource's table
        (strict handling per architecture §1.2).
        """
        domain = list(self.base_domain(env))
        for name, values in params.items():
            if name in RESERVED_PARAMS:
                continue
            if name == '_lastUpdated':
                translate = date_param_domain('write_date')
            elif name in self.search_params:
                translate = self.search_params[name]['domain']
            else:
                raise FHIRNotSupported(
                    "Search parameter %r is not supported on %s"
                    % (name, self.resource_type))
            for value in values:
                domain += translate(value)
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

    def search_bundle(self, env, params, base_url=''):
        """Full searchset Bundle for the controller (and tests)."""
        records, total, next_cursor = self.search_records(env, params)
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
