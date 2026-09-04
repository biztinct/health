#!/usr/bin/env bash
#
# FHIR post-deploy conformance smoke — control C3 (register item G4).
#
# Runs ON the Odoo server, against localhost, immediately after the restart
# step of the deploy procedure (HANDOVER-CONVENTIONS §2). It answers the one
# question a green test run cannot: did the release that just started up
# actually come up conformant, and is it the release we think it is?
#
#   Usage:  tools/fhir_deploy_smoke.sh <expected-software-version>
#   e.g.    tools/fhir_deploy_smoke.sh 19.0.1.5.0
#
#   Optional environment:
#     FHIR_SMOKE_TOKEN  a gateway bearer token (hg_…) with system/*.read.
#                       When set, the authenticated half runs too. The token
#                       comes from a client OPS activates — this script never
#                       creates or activates one (see
#                       docs/conformance/deploy-smoke.md).
#     FHIR_SMOKE_BASE   base URL           (default http://localhost:8069)
#     FHIR_SMOKE_DB     database for the audit check (default carejiox,
#                       the master; name a tenant's database to smoke that one)
#     FHIR_MIN_RESOURCES  minimum capability resource count (default 22)
#
# Exit status: 0 = conformant, non-zero = one line on stderr saying why.
# Never mutates anything. The authenticated reads DO write api.audit.log
# rows — that is the audit trail working, not a side effect to avoid.

set -uo pipefail

BASE="${FHIR_SMOKE_BASE:-http://localhost:8069}"
DB="${FHIR_SMOKE_DB:-carejiox}"
MIN_RESOURCES="${FHIR_MIN_RESOURCES:-22}"
EXPECTED_VERSION="${1:-}"

fail() { echo "FHIR-SMOKE FAIL: $*" >&2; exit 1; }
ok()   { echo "FHIR-SMOKE ok:   $*"; }

if [ -z "$EXPECTED_VERSION" ]; then
  fail "no expected software version given (usage: $0 <version>, e.g. 19.0.1.5.0)"
fi

command -v python3 >/dev/null 2>&1 || fail "python3 not found on PATH"

# ---------------------------------------------------------------------------
# 1. Capability — public, no token needed. This is the release's self-report.
# ---------------------------------------------------------------------------
META_BODY="$(mktemp)"
trap 'rm -f "$META_BODY"' EXIT
META_CODE="$(curl -s -o "$META_BODY" -w '%{http_code}' \
  -H 'Accept: application/fhir+json' "$BASE/fhir/r4/metadata")" \
  || fail "curl to $BASE/fhir/r4/metadata failed (is the server up?)"

[ "$META_CODE" = "200" ] || fail "/fhir/r4/metadata returned HTTP $META_CODE"

CAPABILITY_SUMMARY="$(python3 - "$META_BODY" "$EXPECTED_VERSION" "$MIN_RESOURCES" 2>&1 <<'PY'
import json, sys

path, expected_version, min_resources = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    with open(path, encoding='utf-8') as handle:
        statement = json.load(handle)
except Exception as error:
    sys.exit('metadata is not JSON (%s)' % error)

if statement.get('resourceType') != 'CapabilityStatement':
    sys.exit('metadata is a %r, not a CapabilityStatement'
             % statement.get('resourceType'))

version = statement.get('fhirVersion')
if version != '4.0.1':
    sys.exit('fhirVersion is %r, expected 4.0.1' % version)

software = statement.get('software') or {}
if not software.get('name'):
    sys.exit('no software element (register item G3 regressed)')
if software.get('version') != expected_version:
    sys.exit('software.version is %r but this deploy was %r — the server is '
             'NOT running the release you think it is'
             % (software.get('version'), expected_version))

resources = (statement.get('rest') or [{}])[0].get('resource') or []
if len(resources) < min_resources:
    sys.exit('capability declares %s resources, expected at least %s'
             % (len(resources), min_resources))

# Types a client can actually read/search — the ones worth probing below.
interaction_bearing = sorted(
    r['type'] for r in resources if r.get('interaction'))
print('%s %s %s' % (len(resources), len(interaction_bearing),
                    ','.join(interaction_bearing)))
PY
)" || fail "metadata: $(echo "$CAPABILITY_SUMMARY" | tail -1)"

read -r RESOURCE_COUNT INTERACTION_COUNT INTERACTION_TYPES <<<"$CAPABILITY_SUMMARY"
ok "metadata: fhirVersion 4.0.1, software.version $EXPECTED_VERSION, \
$RESOURCE_COUNT resources ($INTERACTION_COUNT interaction-bearing)"

# ---------------------------------------------------------------------------
# 2. Authenticated half — only when OPS has handed over a token.
# ---------------------------------------------------------------------------
if [ -z "${FHIR_SMOKE_TOKEN:-}" ]; then
  echo "FHIR-SMOKE note: FHIR_SMOKE_TOKEN is unset — metadata-only run. The \
authenticated half (search + audit attribution) was NOT executed."
  ok "smoke passed (metadata only)"
  exit 0
fi

BODY="$(mktemp)"
trap 'rm -f "$META_BODY" "$BODY"' EXIT

# Every type is probed even after one fails, and the audit check below still
# runs: stopping at the first bad type reports ONE problem and hides the rest,
# and "which types are broken" is the whole diagnostic value of this step.
BAD_TYPES=''
IFS=',' read -r -a TYPES <<<"$INTERACTION_TYPES"
for rtype in "${TYPES[@]}"; do
  [ -n "$rtype" ] || continue
  code="$(curl -s -o "$BODY" -w '%{http_code}' \
    -H "Authorization: Bearer $FHIR_SMOKE_TOKEN" \
    -H 'Accept: application/fhir+json' \
    "$BASE/fhir/r4/$rtype?_count=1")" \
    || { BAD_TYPES="$BAD_TYPES $rtype(curl-failed)"; continue; }
  if [ "$code" != "200" ]; then
    echo "FHIR-SMOKE type $rtype: HTTP $code $(head -c 200 "$BODY")" >&2
    BAD_TYPES="$BAD_TYPES $rtype(HTTP$code)"
    continue
  fi
  python3 - "$BODY" "$rtype" <<'PY' || BAD_TYPES="$BAD_TYPES $rtype(not-a-searchset)"
import json, sys
path, rtype = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as handle:
    payload = json.load(handle)
if payload.get('resourceType') != 'Bundle':
    sys.exit('%s returned a %r' % (rtype, payload.get('resourceType')))
if payload.get('type') != 'searchset':
    sys.exit('%s returned a Bundle of type %r' % (rtype, payload.get('type')))
PY
done
if [ -z "$BAD_TYPES" ]; then
  ok "searched $INTERACTION_COUNT interaction-bearing types, all 200 Bundles"
else
  echo "FHIR-SMOKE: $INTERACTION_COUNT types probed, failures:$BAD_TYPES" >&2
fi

# ---------------------------------------------------------------------------
# 3. ONE audit check — those reads were audited, and the rows name the CLIENT.
#    (GC-2 review M2: the controller read a request attribute that was never
#    assigned, so every /fhir/r4 audit row had empty attribution. A breach
#    investigation needs the partner integration, not just the service user.)
# ---------------------------------------------------------------------------
AUDIT_SQL="SELECT COALESCE(key_or_client,'') || '|' || COALESCE(auth_kind,'') \
FROM api_audit_log WHERE route LIKE '/fhir/r4/%' ORDER BY ts DESC, id DESC LIMIT 1;"
AUDIT_ROW="$(sudo su - postgres -c "psql -d $DB -tAc \"$AUDIT_SQL\"" 2>/dev/null | tr -d '[:space:]')"

[ -n "$AUDIT_ROW" ] || fail "no api.audit.log row for /fhir/r4/ — the reads \
above were not audited at all"
AUDIT_CLIENT="${AUDIT_ROW%%|*}"
AUDIT_KIND="${AUDIT_ROW##*|}"
[ -n "$AUDIT_CLIENT" ] || fail "newest /fhir/r4 audit row has an empty \
key_or_client — the caller is not attributable (GC-2 review M2 regressed)"
[ -n "$AUDIT_KIND" ] || fail "newest /fhir/r4 audit row has an empty auth_kind"
ok "audit attribution: key_or_client=$AUDIT_CLIENT auth_kind=$AUDIT_KIND"

[ -z "$BAD_TYPES" ] \
  || fail "these types did not return a searchset Bundle:$BAD_TYPES"

ok "smoke passed (metadata + $INTERACTION_COUNT searches + audit attribution)"
exit 0
