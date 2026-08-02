#!/usr/bin/env bash
#
# Local / self-hosted twin of the FHIR conformance gate — control C1's
# fallback path (gap register item G4).
#
# Runs exactly the suite `.github/workflows/fhir-conformance.yml` runs, and
# applies exactly the same gates, against a local Odoo 19 checkout and
# a local PostgreSQL. Use it when:
#
#   - GitHub Actions is unavailable, disabled for the repo, or blocked (the
#     hosted runner cannot reach a dependency the deployment has);
#   - you want the gate BEFORE pushing;
#   - you are diagnosing a red CI run and want the same log locally.
#
#   Usage:
#     ODOO_BIN=/path/to/odoo-bin \
#     ODOO_ADDONS=/path/to/odoo/addons \
#       tools/ci_fhir_local.sh [database-name]
#
#   Everything is overridable by environment; sane defaults below. The
#   database is DROPPED and recreated on every run — never point this at a
#   database you care about, and never at `vietuat`.
#
# See docs/conformance/ci-runbook.md for the whole picture.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DB="${1:-${CI_DB:-fhir_ci_local}}"
ODOO_BIN="${ODOO_BIN:-odoo-bin}"
ODOO_ADDONS="${ODOO_ADDONS:-}"
LOG="${CI_LOG:-/tmp/fhir-conformance-local.log}"
MODULES="${CI_MODULES:-health_fhir_core,health_fhir_terminology,health_condition}"
TEST_TAGS="${CI_TEST_TAGS:-/health_fhir_core,/health_fhir_terminology,/health_condition}"
MIN_EXECUTED="${CI_MIN_EXECUTED:-50}"
DB_HOST="${CI_DB_HOST:-localhost}"
DB_USER="${CI_DB_USER:-odoo}"
DB_PASSWORD="${CI_DB_PASSWORD:-odoo}"

fail() { echo "FHIR-CI FAIL: $*" >&2; exit 1; }
note() { echo "FHIR-CI: $*"; }

case "$DB" in
  vietuat|*prod*|*production*)
    fail "refusing to run against $DB — this script DROPS the database" ;;
esac

command -v "$ODOO_BIN" >/dev/null 2>&1 || [ -x "$ODOO_BIN" ] \
  || fail "odoo-bin not found (set ODOO_BIN=/path/to/odoo-bin)"
[ -n "$ODOO_ADDONS" ] \
  || fail "set ODOO_ADDONS to your Odoo 19 checkout's addons directory"
[ -d "$ODOO_ADDONS" ] || fail "ODOO_ADDONS=$ODOO_ADDONS is not a directory"

python3 -c 'import fhir.resources' 2>/dev/null \
  || fail "fhir.resources is not importable — pip install 'fhir.resources==8.3.0'"
PINNED="$(python3 -c \
  "import importlib.metadata as m; print(m.version('fhir.resources'))")"
case "$PINNED" in
  8.*) note "fhir.resources $PINNED" ;;
  *) fail "fhir.resources is $PINNED; the R4/R4B equivalence claim is scoped \
to 8.3.0 (docs/conformance/r4-r4b-equivalence.md)" ;;
esac

# `addons` FIRST — the repo tracks patched copies of several core modules and
# those are what the deployment runs. See the workflow for the same note.
ADDONS_PATH="$REPO_ROOT/addons,$ODOO_ADDONS"

note "dropping and recreating $DB"
dropdb --if-exists -h "$DB_HOST" -U "$DB_USER" "$DB" >/dev/null 2>&1
createdb -h "$DB_HOST" -U "$DB_USER" "$DB" \
  || fail "could not create $DB (is PostgreSQL up, and does $DB_USER exist?)"

note "installing $MODULES and running $TEST_TAGS"
rm -f "$LOG"
"$ODOO_BIN" \
  -d "$DB" \
  --addons-path="$ADDONS_PATH" \
  -i "$MODULES" \
  --test-enable \
  --test-tags "$TEST_TAGS" \
  --stop-after-init \
  --workers=0 \
  --without-demo=all \
  --db_host="$DB_HOST" \
  --db_user="$DB_USER" \
  --db_password="$DB_PASSWORD" \
  --log-level=test \
  --logfile="$LOG"
ODOO_EXIT=$?

[ -s "$LOG" ] || fail "no odoo log at $LOG — the run did not start"
echo "--- last 40 log lines ---"
tail -40 "$LOG"
echo "-------------------------"

# Gate 1 — the process itself.
if [ "$ODOO_EXIT" -ne 0 ]; then
  grep -a 'ERROR' "$LOG" | tail -40
  fail "odoo exited $ODOO_EXIT (an EXIT:1 with FAIL:0 means read the ERROR \
lines — conventions §5.75)"
fi

# Gate 2 — there must BE a result line, and it must be clean.
RESULT="$(grep -a 'odoo.tests.result' "$LOG" | tail -1)"
[ -n "$RESULT" ] || fail "no 'odoo.tests.result' line — no test suite ran"
note "result: $RESULT"
case "$RESULT" in
  *"0 failed, 0 error(s)"*) ;;
  *) fail "$RESULT" ;;
esac

# Gate 3 — §5.83: green over zero executed tests is not green.
EXECUTED="$(grep -ac 'Starting Test.*\.test_' "$LOG" || true)"
note "executed test methods: $EXECUTED"
[ "${EXECUTED:-0}" -ge "$MIN_EXECUTED" ] \
  || fail "only $EXECUTED test methods executed (expected ≥ $MIN_EXECUTED) — \
the suite did not run"

note "conformance gate PASSED — $RESULT over $EXECUTED tests"
exit 0
