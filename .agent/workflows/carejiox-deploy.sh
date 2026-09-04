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
# EXIT CODE is odoo-bin's, so `|| echo FAILED` works. The service is restarted
# even when the upgrade fails — a broken registry is better diagnosed with the
# log than with a dead port.
set -uo pipefail

MODULES=""; INSTALL=""; TESTTAGS=""; DO_DEPLOY=0; SKIP_UPGRADE=0; LOCK_WAIT=3600
SHELLFILE=""
ADDONS=/odoo/odoo-server/addons
CONF=/etc/odoo-server.conf
DB=carejiox
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

  if [ "$SKIP_UPGRADE" -eq 0 ]; then
    local args="-c $CONF -d $DB --stop-after-init"
    [ -n "$MODULES" ] && args="$args -u $MODULES"
    [ -n "$INSTALL" ] && args="$args -i $INSTALL"
    if [ -n "$TESTTAGS" ]; then
      # HttpCase needs a real http server AND workers=0; --no-http is only
      # safe when we are not running tests.
      args="$args --test-enable --test-tags $TESTTAGS --workers=0"
      echo "==> upgrading ${MODULES:-none} / installing ${INSTALL:-none}  [$TESTTAGS]"
    else
      args="$args --no-http"
      echo "==> upgrading ${MODULES:-none} / installing ${INSTALL:-none}"
    fi
    sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin $args" >/dev/null 2>&1
    rc=$?
    echo "==> odoo-bin exit=$rc"
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
  return $rc
}

echo "==> waiting for the deploy lock (up to ${LOCK_WAIT}s)"
flock -w "$LOCK_WAIT" "$LOCK" bash -c "$(declare -f run); MODULES='$MODULES' INSTALL='$INSTALL' \
  TESTTAGS='$TESTTAGS' DO_DEPLOY=$DO_DEPLOY SKIP_UPGRADE=$SKIP_UPGRADE ADDONS='$ADDONS' \
  CONF='$CONF' DB='$DB' SHELLFILE='$SHELLFILE' HEALTH_HOST='$HEALTH_HOST' run"
RC=$?
[ $RC -eq 1 ] && echo "==> NOTE: exit 1 with tests enabled usually means a test failed."
exit $RC
