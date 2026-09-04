#!/usr/bin/env bash
# tools/saas/test_scripts.sh — guard tests for the three platform scripts.
#
# These scripts interpolate their arguments into ROOT-OWNED nginx configuration
# and hand them to certbot, so the only interesting question about them is
# whether a bad argument is refused BEFORE anything is written or issued. Every
# case here asserts two things: the exit code (2 = refused by a guard), and that
# certbot / nginx / systemctl were never reached.
#
# The second half is what makes this runnable anywhere: PATH is pointed at stubs
# that record the call instead of making it, so a guard that silently stopped
# firing would show up as "TOUCHED certbot" rather than as a real certificate
# request against Let's Encrypt's rate limit.
#
# Run:  bash tools/saas/test_scripts.sh          (from the repo root, or anywhere)
# Exit: 0 all passed, 1 something failed.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------- stubs -----
STUBS="$TMP/bin"; mkdir -p "$STUBS"
TOUCHED="$TMP/touched"; : > "$TOUCHED"
for cmd in certbot nginx systemctl; do
    cat > "$STUBS/$cmd" <<EOF
#!/bin/sh
echo "TOUCHED $cmd \$*" >> "$TOUCHED"
exit 0
EOF
    chmod +x "$STUBS/$cmd"
done
export PATH="$STUBS:$PATH"

# --------------------------------------------------------------- fixture ----
CONF="$TMP/biz-tenants.conf"
cat > "$CONF" <<'EOF'
APEX_DOMAIN=carejiox.com
BLOCK_PREFIX=biz-tenant-
STATUS_DIR=/var/www/carejiox-status
CUSTOM_DOMAIN_PINNING=0
PIN_HEADER=X-Odoo-dbfilter
EOF
export BIZ_CONF="$CONF"

# By default the checkout's own copies are tested. Point BIZ_BIN at
# /usr/local/bin to run the same cases against what is actually INSTALLED on a
# server — which is the only version whose guards protect anything, and is
# worth doing after every deploy of these three.
BIZ_BIN="${BIZ_BIN:-$HERE}"
export BIZ_LIB="$BIZ_BIN"
echo "testing: $BIZ_BIN (lib: $BIZ_LIB, conf: $BIZ_CONF)"

CERT="$BIZ_BIN/biz-tenant-cert"
ATTACH="$BIZ_BIN/biz-domain-attach"
DETACH="$BIZ_BIN/biz-domain-detach"

PASS=0; FAIL=0

# expect <name> <wanted-exit> <allow-touch:yes|no> -- <command...>
expect() {
    local name="$1" want="$2" allow="$3"; shift 4
    : > "$TOUCHED"
    local out rc
    out=$(bash "$@" 2>&1); rc=$?
    local why=""
    [ "$rc" -eq "$want" ] || why="exit $rc, wanted $want"
    if [ "$allow" = "no" ] && [ -s "$TOUCHED" ]; then
        why="${why:+$why; }reached $(tr '\n' '|' < "$TOUCHED")"
    fi
    if [ -z "$why" ]; then
        PASS=$((PASS+1)); printf '  ok   %s\n' "$name"
    else
        FAIL=$((FAIL+1)); printf '  FAIL %s — %s\n         output: %s\n' "$name" "$why" "$(echo "$out" | head -3 | tr '\n' ' ')"
    fi
}

echo "== biz-tenant-cert =="
expect "bad hostname (uppercase)"        2 no -- "$CERT" "HHH.Carejiox.com" hhh
expect "bad hostname (single label)"     2 no -- "$CERT" "localhost" hhh
expect "bad hostname (path injection)"   2 no -- "$CERT" "a.com/../../etc" hhh
expect "bad hostname (shell metachars)"  2 no -- "$CERT" 'hhh.carejiox.com; rm -rf /' hhh
expect "bad hostname (empty)"            2 no -- "$CERT" "" hhh
expect "bad slug (underscore)"           2 no -- "$CERT" "hhh.carejiox.com" "h_h"
expect "bad slug (leading digit)"        2 no -- "$CERT" "hhh.carejiox.com" "1hh"
expect "bad slug (empty)"                2 no -- "$CERT" "hhh.carejiox.com" ""
expect "hostname not under the slug"     2 no -- "$CERT" "other.carejiox.com" hhh
expect "hostname under a foreign apex"   2 no -- "$CERT" "hhh.evil.com" hhh
expect "deep subdomain of the slug"      2 no -- "$CERT" "www.hhh.carejiox.com" hhh
expect "the apex itself"                 2 no -- "$CERT" "carejiox.com" hhh
expect "good pair passes the guards"     0 no -- "$CERT" "hhh.carejiox.com" hhh --check-only

echo "== biz-domain-attach =="
expect "bad hostname"                    2 no -- "$ATTACH" "NOPE" acme
expect "bad slug"                        2 no -- "$ATTACH" "clinic.example.com" "AC ME"
expect "apex hostname refused"           2 no -- "$ATTACH" "carejiox.com" acme
expect "apex subdomain refused"          2 no -- "$ATTACH" "acme.carejiox.com" acme
expect "apex sub-subdomain refused"      2 no -- "$ATTACH" "a.b.carejiox.com" acme
expect "lookalike apex NOT refused"      0 no -- "$ATTACH" "notcarejiox.com" acme --check-only
expect "good pair passes the guards"     0 no -- "$ATTACH" "clinic.example.com" acme --check-only
# The pinning refusal is exit 3, not 2: it is not a bad argument, it is a
# capability this build does not have. It must still reach nothing.
expect "unpinnable build refuses (3)"    3 no -- "$ATTACH" "clinic.example.com" acme

echo "== biz-domain-detach =="
expect "bad hostname"                    2 no -- "$DETACH" "../../etc/nginx"
expect "empty hostname"                  2 no -- "$DETACH" ""
expect "good hostname passes the guards" 0 no -- "$DETACH" "clinic.example.com" --check-only

# A broken config file must stop the scripts dead rather than widen a guard:
# APEX_DOMAIN is interpolated INTO the guard, so an empty one would turn
# "must be under carejiox.com" into "must end in a dot".
echo "== biz-tenants.conf validation =="
BADCONF="$TMP/bad.conf"
export BIZ_CONF="$BADCONF"
echo 'APEX_DOMAIN=' > "$BADCONF"
expect "empty APEX_DOMAIN refuses to run"  2 no -- "$CERT" "hhh.carejiox.com" hhh --check-only
printf 'APEX_DOMAIN=not_a_hostname\n' > "$BADCONF"
expect "malformed APEX_DOMAIN refuses"     2 no -- "$CERT" "hhh.carejiox.com" hhh --check-only
printf 'APEX_DOMAIN=carejiox.com\nBLOCK_PREFIX=../evil\n' > "$BADCONF"
expect "unsafe BLOCK_PREFIX refuses"       2 no -- "$CERT" "hhh.carejiox.com" hhh --check-only
export BIZ_CONF="$CONF"

echo
echo "passed $PASS, failed $FAIL"
[ "$FAIL" -eq 0 ]
