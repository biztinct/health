# biz-common.sh — shared reading + validation for the three platform scripts.
#
# Sourced, never executed. Installed at /usr/local/bin/biz-common.sh, root-owned
# 0644. It is NOT in the sudoers list because it is not a command; the three
# scripts that ARE in that list source it from an absolute path, so nothing the
# odoo user can write is ever read as code by a root process.
#
# Managed by the platform.

BIZ_CONF="${BIZ_CONF:-/etc/biz-tenants.conf}"

biz_die() { echo "$1" >&2; exit "${2:-1}"; }

# Read the config file WITHOUT sourcing it: a root process must not execute
# lines out of a file, even a root-owned one. Only KEY=VALUE lines are taken,
# only for keys we know, and every value is re-validated below.
biz_conf_get() {
    local key="$1" default="${2:-}" val=""
    if [[ -r "$BIZ_CONF" ]]; then
        val=$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*([^#[:space:]]*).*/\1/p" \
              "$BIZ_CONF" | tail -n 1)
    fi
    printf '%s' "${val:-$default}"
}

biz_load_conf() {
    APEX_DOMAIN=$(biz_conf_get APEX_DOMAIN "")
    BLOCK_PREFIX=$(biz_conf_get BLOCK_PREFIX "biz-tenant-")
    STATUS_DIR=$(biz_conf_get STATUS_DIR "/var/www/status")
    CUSTOM_DOMAIN_PINNING=$(biz_conf_get CUSTOM_DOMAIN_PINNING "0")
    PIN_HEADER=$(biz_conf_get PIN_HEADER "X-Odoo-dbfilter")

    # The apex is interpolated into a guard, so a malformed one would WIDEN the
    # guard rather than narrow it. Refuse to run at all.
    biz_valid_hostname "$APEX_DOMAIN" \
        || biz_die "biz-tenants.conf: APEX_DOMAIN is not a hostname: '${APEX_DOMAIN}'" 2
    [[ "$BLOCK_PREFIX" =~ ^[a-z0-9]([a-z0-9-]*)$ ]] \
        || biz_die "biz-tenants.conf: BLOCK_PREFIX is not a safe filename prefix" 2
    [[ "$STATUS_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] \
        || biz_die "biz-tenants.conf: STATUS_DIR is not an absolute path" 2
}

# Strict validation — these values are interpolated into a root-owned config.
biz_valid_hostname() {
    [[ "$1" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]] \
        && [[ ${#1} -le 253 ]]
}

# A slug is also a PostgreSQL database name and a hostname label, so it is the
# intersection of both: lowercase, starts with a letter, no underscores (they
# are illegal in hostnames), no trailing dash.
biz_valid_slug() {
    [[ "$1" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]] && [[ ${#1} -le 63 ]]
}

biz_require_args() {
    biz_valid_hostname "${1:-}" || biz_die "invalid hostname" 2
}
