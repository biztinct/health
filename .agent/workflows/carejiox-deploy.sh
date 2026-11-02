#!/usr/bin/env bash
# carejiox-deploy — the ONLY safe way to deploy/upgrade on this box.
#
# (Was `vietuat-deploy` until SAAS H3, 2026-09-04, when the master database was
# renamed vietuat -> carejiox and the box became a platform. `vietuat-deploy`
# survives as a symlink for one phase; it runs this same script against the
# same database.)
#
# WHY THIS EXISTS
# ---------------
# One Odoo instance, one addons directory. Two people (or two Claude sessions)
# deploying at once means `service odoo-server stop` lands under someone else's
# upgrade. Odoo commits per module, so an interrupted upgrade leaves a
# HALF-MIGRATED database — on 2026-08-13 that cost us four aborted runs, a
# deadlock, and a column of live crm.lead data.
#
# THE ADDONS TREE IS SHARED BY EVERY DATABASE ON THIS CLUSTER. Since H3 there
# is more than one: the master `carejiox`, the golden template
# `carejiox_template`, and one database per tenant. Copying files with -d
# changes the code under ALL of them at once, while -m/-i only migrate the ONE
# named by -D. Adding a `depends` to a module is therefore a deploy step on
# every database, not only this one — loop -D over them (see docs/SAAS_RUNBOOK.md).
#
# Everything here runs inside one flock, so concurrent callers queue instead of
# colliding. It is a drop-in replacement for the manual
# stop -> odoo-bin -u -> start sequence. Always use it.
#
# USAGE (run ON the server, or via ssh VietUcUAT)
#   carejiox-deploy -m health_base,health_crm
#   carejiox-deploy -m health_base -t /health_base:TestLookupValues
#   carejiox-deploy -m health_base -d          # deploy files from /tmp only
#   carejiox-deploy -i biz_kit,biz_access -d   # install modules not on the DB yet
#   carejiox-deploy -i health_access -m health_cms_sidebar -d
#   carejiox-deploy -s                         # just restart, no upgrade
#   carejiox-deploy -x /tmp/uninstall.py       # run a shell script with the
#                                              # service down, then bring it back
#   carejiox-deploy -D carejiox_template -m health_theme   # the golden template
#
# OPTIONS
#   -m  comma-separated module list to upgrade (-u)
#   -i  comma-separated module list to INSTALL (-i) — for a module the database
#       does not have yet. May be given with or without -m; one of the two is
#       required unless -s or -x.
#   -t  --test-tags value; implies --test-enable
#   -d  copy modules from /tmp/<module> into the addons dir first — every module
#       named on -m AND -i, because a first install has to be copied too and
#       forgetting one of the two lists is a run that installs yesterday's code
#   -s  skip the upgrade, only stop/start
#   -x  a python file to run in `odoo-bin shell`, WITH THE SERVICE STOPPED and
#       started again afterwards, inside this same lock. It exists so that the
#       one thing this wrapper could not do — uninstalling a module, which
#       rewrites the registry underneath every worker — stops being a reason to
#       reach past it and call `service odoo-server` by hand. Its stdout is
#       shown rather than swallowed: a script run this way is a script somebody
#       is watching. Runs AFTER any -m/-i upgrade in the same invocation.
#   -D  the database to upgrade (default carejiox, the master). The template
#       and every tenant share this box and this addons tree, so the wrapper
#       has to be able to name one; without it the only way to upgrade the
#       template was to reach past the wrapper, which is the habit -x was
#       added to end. -d (copy files) is independent of -D and affects them all.
#   -w  lock wait in seconds (default 3600)
#
# THE POST-UPGRADE CHECK (since FS-H5, 2026-11-03). After every -m/-i upgrade
# that succeeded, and after any -x script, WITH THE SERVICE STILL DOWN, the
# wrapper runs /usr/local/lib/carejiox/postcheck.py (source:
# .agent/workflows/carejiox-postcheck.py) in an odoo shell on the same
# database and shows its lines:
#   ==> studio: checked <n> layouts, broken <m>, host problems <k>, encrypted values <v>
#       broken: <model> layout <id> — <reason>      (Form Studio switched it off)
#       host: <name> — <problem>
#   ==> jobs: <a> active                              (any database but the template)
#   ==> jobs: <a> active (template: switched off <a> → 0)   (the golden template)
# The template is the database named by `biz_tenants.template_db` on the
# master (the registered default `carejiox_template` when the master has no
# such setting); the check switches ITS scheduled jobs off through the
# platform's own routine, so nobody has to remember the UPDATE any more. On
# the template any encrypted value is a failure too: a clinic made from it gets
# a new database secret and could never read it. Set CAREJIOX_IS_TEMPLATE=1 in
# the caller's environment to treat another database as the template (a
# rehearsal on a clone).
#
# EXIT CODE is odoo-bin's, so `|| echo FAILED` works. The service is restarted
# even when the upgrade fails — a broken registry is better diagnosed with the
# log than with a dead port. When the upgrade succeeded but the post-check did
# not, the wrapper prints `==> POSTCHECK FAILED (exit=3) — read the lines
# above` and exits 3 — and STILL starts the service: a switched-off Studio
# layout is a safe state, a stopped clinic is not.
#
# REHEARSAL: CAREJIOX_DEPLOY_CONF=<file> runs odoo-bin with another config
# file (a clone's private addons tree). Never set it for a live deploy.
set -uo pipefail

MODULES=""; INSTALL=""; TESTTAGS=""; DO_DEPLOY=0; SKIP_UPGRADE=0; LOCK_WAIT=3600
SHELLFILE=""
ADDONS=/odoo/odoo-server/addons
CONF=${CAREJIOX_DEPLOY_CONF:-/etc/odoo-server.conf}
DB=carejiox
# The master: the only database that knows which one is the template.
MASTER_DB=carejiox
# What the product registers as the template when the master has no setting
# (health_tenancy/models/registrations.py).
DEFAULT_TEMPLATE=carejiox_template
POSTCHECK=/usr/local/lib/carejiox/postcheck.py
IS_TEMPLATE=${CAREJIOX_IS_TEMPLATE:-}
LOCK=/tmp/carejiox-deploy.lock
# The hostname the post-restart health check asks for. Since H3 the server
# routes by hostname (dbfilter = ^%d$), so the old check — plain
# localhost:8069 — asks for a database called "localhost" and gets a 303 to
# the database selector no matter how healthy the service is. It answers "did
# the service come back", so it asks for the apex, not for $DB: the golden
# template's name contains an underscore and is deliberately unreachable by
# hostname, which is a property to preserve, not to work around.
HEALTH_HOST=carejiox.com

while getopts "m:i:t:w:x:D:ds" opt; do
  case "$opt" in
    m) MODULES="$OPTARG" ;;
    i) INSTALL="$OPTARG" ;;
    t) TESTTAGS="$OPTARG" ;;
    w) LOCK_WAIT="$OPTARG" ;;
    x) SHELLFILE="$OPTARG" ;;
    D) DB="$OPTARG" ;;
    d) DO_DEPLOY=1 ;;
    s) SKIP_UPGRADE=1 ;;
    *) echo "see the header of $0 for usage" >&2; exit 2 ;;
  esac
done

if [ -n "$SHELLFILE" ] && [ ! -r "$SHELLFILE" ]; then
  echo "carejiox-deploy: cannot read $SHELLFILE" >&2
  exit 2
fi

if [ "$SKIP_UPGRADE" -eq 0 ] && [ -z "$MODULES" ] && [ -z "$INSTALL" ] \
   && [ -z "$SHELLFILE" ]; then
  echo "carejiox-deploy: -m <modules>, -i <modules> or -x <script> is required (or -s to just restart)" >&2
  exit 2
fi

# -x on its own is not an upgrade; do not build odoo-bin upgrade args for it.
if [ -n "$SHELLFILE" ] && [ -z "$MODULES" ] && [ -z "$INSTALL" ]; then
  SKIP_UPGRADE=1
fi

# An upgrade without its post-check is the old habit this file replaces:
# refuse before anything is stopped.
if [ "$SKIP_UPGRADE" -eq 0 ] && [ ! -r "$POSTCHECK" ]; then
  echo "carejiox-deploy: the post-upgrade check $POSTCHECK is missing —" \
       "install it from .agent/workflows/carejiox-postcheck.py first" >&2
  exit 2
fi

run() {
  local rc=0

  # A typo in -D is otherwise an upgrade that silently does nothing: odoo-bin
  # would create the database rather than refuse it.
  if ! sudo -u postgres psql -Atc \
        "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
    echo "carejiox-deploy: no database named '$DB' on this cluster" >&2
    return 2
  fi
  echo "==> database: $DB"

  # Which database is the golden template? Only the master knows, and it
  # must be asked BEFORE the service stops (psql, not the ORM). A caller may
  # force it (CAREJIOX_IS_TEMPLATE=1) for a rehearsal on a clone.
  local template
  template=$(sudo -u postgres psql -d "$MASTER_DB" -Atc \
    "SELECT value FROM ir_config_parameter WHERE key='biz_tenants.template_db'" \
    2>/dev/null | head -1)
  template=${template:-$DEFAULT_TEMPLATE}
  if [ "$IS_TEMPLATE" = "1" ]; then
    echo "==> $DB is treated as the golden template (CAREJIOX_IS_TEMPLATE=1)"
  else
    IS_TEMPLATE=0
    if [ "$DB" = "$template" ]; then
      IS_TEMPLATE=1
      echo "==> $DB is the golden template"
    fi
  fi

  # EVERY module named on EITHER list. A first install copied from nowhere is
  # a first install of whatever happened to be on the box already.
  local to_copy
  to_copy=$(echo "$MODULES,$INSTALL" | tr ',' ' ')

  if [ "$DO_DEPLOY" -eq 1 ]; then
    echo "==> deploying $to_copy from /tmp"
    for m in $to_copy; do
      if [ ! -d "/tmp/$m" ]; then
        echo "    MISSING /tmp/$m — scp it first" >&2
        return 2
      fi
      sudo rm -rf "${ADDONS:?}/$m" && sudo cp -r "/tmp/$m" "$ADDONS/$m"
      sudo chown -R odoo:odoo "$ADDONS/$m"
    done
  fi

  echo "==> stopping odoo"
  sudo service odoo-server stop >/dev/null 2>&1
  sleep 8
  # The LSB script returns before the socket is released; odoo-bin then dies
  # with "Address already in use" — silently, because it logs to the conf's
  # logfile and not to stdout.
  for _ in $(seq 1 30); do
    ss -ltn | grep -q ':8069 ' || break
    sleep 2
  done

  local upgraded=0 checkrc=0
  if [ "$SKIP_UPGRADE" -eq 0 ]; then
    local args="-c $CONF -d $DB --stop-after-init"
    [ -n "$MODULES" ] && args="$args -u $MODULES"
    [ -n "$INSTALL" ] && args="$args -i $INSTALL"
    if [ -n "$TESTTAGS" ]; then
      # HttpCase needs a real http server AND workers=0; --no-http is only
      # safe when we are not running tests.
      # --db-filter is not optional since H3 made routing hostname-based.
      # An HttpCase calls http://127.0.0.1:<port>, and `dbfilter = ^%d$` reads
      # the first label of that Host — "127" — which is not a database, so
      # every probe comes back 404 from a request that never reached the app.
      # It looks exactly like a broken feature and is a broken test harness:
      # three security tests in health_fieldservice "failed" this way, and the
      # log gives it away by naming the database `?` instead of the real one.
      # Pinning it here also protects a run against a clone (ledger H32).
      args="$args --test-enable --test-tags $TESTTAGS --workers=0 --db-filter=^${DB}\$"
      echo "==> upgrading ${MODULES:-none} / installing ${INSTALL:-none}  [$TESTTAGS]"
    else
      args="$args --no-http"
      echo "==> upgrading ${MODULES:-none} / installing ${INSTALL:-none}"
    fi
    sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin $args" >/dev/null 2>&1
    rc=$?
    echo "==> odoo-bin exit=$rc"
    [ "$rc" -eq 0 ] && upgraded=1
  fi

  # THE SERVICE IS STILL DOWN HERE, WHICH IS THE POINT. A script that rewrites
  # the registry — an uninstall, above all — must not run against a database
  # two live workers are serving from a registry that is about to stop being
  # true. Its output is NOT swallowed: this is the one thing the wrapper runs
  # that somebody is reading line by line.
  if [ -n "$SHELLFILE" ] && [ "$rc" -eq 0 ]; then
    echo "==> running $SHELLFILE in an odoo shell (service down)"
    sudo su - odoo -s /bin/bash -c \
      "/odoo/odoo-server/odoo-bin shell -c $CONF -d $DB --no-http \
        --logfile=/var/log/odoo/odoo-shell.log < $SHELLFILE"
    rc=$?
    echo "==> shell exit=$rc"
  elif [ -n "$SHELLFILE" ]; then
    echo "==> SKIPPING $SHELLFILE — the upgrade before it failed (exit=$rc)"
  fi

  # THE POST-UPGRADE CHECK — still with the service down, only after an
  # upgrade that succeeded. Its lines are shown, never swallowed.
  if [ "$upgraded" -eq 1 ]; then
    echo "==> post-upgrade check (service down)"
    sudo su - odoo -s /bin/bash -c \
      "CAREJIOX_IS_TEMPLATE=$IS_TEMPLATE CAREJIOX_MASTER_DB=$MASTER_DB \
        /odoo/odoo-server/odoo-bin shell -c $CONF -d $DB --no-http \
        --logfile=/var/log/odoo/odoo-shell.log < $POSTCHECK"
    checkrc=$?
    if [ "$checkrc" -ne 0 ]; then
      echo "==> POSTCHECK FAILED (exit=$checkrc) — read the lines above"
    fi
  fi

  echo "==> starting odoo"
  sudo service odoo-server start >/dev/null 2>&1
  sleep 14
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' \
           -H "Host: $HEALTH_HOST" http://127.0.0.1:8069/web/login)
  echo "==> http=$code ($HEALTH_HOST) procs=$(pgrep -cf '^python3 /odoo/odoo-server/odoo-bin' || echo 0)"

  if [ "$rc" -ne 0 ]; then
    echo "==> LAST ERRORS -----------------------------------------"
    sudo grep -aE 'ParseError|does not exist|Failed to load registry|CRITICAL|FAIL:|ERROR: test' \
      /var/log/odoo/odoo-server.log | tail -8
  fi
  # odoo-bin's (or the -x script's) failure wins; otherwise the check's 3.
  if [ "$rc" -eq 0 ] && [ "$checkrc" -ne 0 ]; then
    rc=3
  fi
  return $rc
}

echo "==> waiting for the deploy lock (up to ${LOCK_WAIT}s)"
flock -w "$LOCK_WAIT" "$LOCK" bash -c "$(declare -f run); MODULES='$MODULES' INSTALL='$INSTALL' \
  TESTTAGS='$TESTTAGS' DO_DEPLOY=$DO_DEPLOY SKIP_UPGRADE=$SKIP_UPGRADE ADDONS='$ADDONS' \
  CONF='$CONF' DB='$DB' SHELLFILE='$SHELLFILE' HEALTH_HOST='$HEALTH_HOST' \
  MASTER_DB='$MASTER_DB' DEFAULT_TEMPLATE='$DEFAULT_TEMPLATE' POSTCHECK='$POSTCHECK' \
  IS_TEMPLATE='$IS_TEMPLATE' run"
RC=$?
[ $RC -eq 1 ] && echo "==> NOTE: exit 1 with tests enabled usually means a test failed."
[ $RC -eq 3 ] && echo "==> NOTE: exit 3 is the post-upgrade check; the service was started."
exit $RC
