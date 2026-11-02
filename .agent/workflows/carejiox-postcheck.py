# carejiox-postcheck — the deploy wrapper's check after every upgrade.
#
# Installed as /usr/local/lib/carejiox/postcheck.py and run by
# `carejiox-deploy` through `odoo-bin shell` (fed on stdin, so `env` is the
# superuser's environment on the database just upgraded), WITH THE SERVICE
# STILL DOWN, only after an upgrade that succeeded. Engineers read its output;
# it may name modules and models.
#
# WHAT IT PRINTS, in this order:
#   ==> studio: checked <n> layouts, broken <m>, host problems <k>, encrypted values <v>
#       broken: <model> layout <id> — <reason>          (one line each)
#       host: <name> — <problem>                        (one line each)
#       encrypted: <model> <field> — <n> values         (template only)
#   ==> jobs: <a> active (template: switched off <n> → <after>)   | ==> jobs: <a> active
#
# WHAT IT CHECKS
#   * Form Studio (`fs.studio.validate_all`, as the superuser): every published
#     layout is re-drawn against today's screen; one that no longer fits is
#     switched off by the validator itself (a safe state: the screen draws
#     without the Studio fields). Broken layouts or host problems -> exit 3.
#   * Encrypted values: on the GOLDEN TEMPLATE any value is a failure. Each
#     database encrypts with its own `database.secret` (no HEALTH_PHI_KEY on the
#     box), and a clinic made from the template gets a NEW secret, so it could
#     never read a token made on the template.
#   * Scheduled jobs: an upgrade switches the template's jobs back on. On the
#     template (the wrapper says so with CAREJIOX_IS_TEMPLATE=1) they are
#     switched off through the platform's own routine
#     (`biz.tenants._quiet_template`, which also writes down what was on so a
#     new clinic gets them back); still on afterwards -> exit 3. Anywhere else
#     the count is only printed.
#
# EXIT CODE: 0 healthy, 3 something above needs reading. It never raises: an
# error prints `==> studio: check failed — <error>` (or `jobs:`) and exits 3.
# It writes nothing but the validator's own switch-offs and the job quieting.
import os
import sys

from odoo import SUPERUSER_ID, api
from odoo.modules.registry import Registry


def _say(text):
    print(text, flush=True)


def _studio(env, is_template):
    rc = 0
    if 'fs.studio' not in env.registry:
        _say('==> studio: not installed')
        return rc
    res = env(user=SUPERUSER_ID)['fs.studio'].validate_all()
    env.cr.commit()   # the validator's switch-offs are the intended result
    broken = res.get('broken') or []
    hosts = res.get('hosts') or []
    problems = [(h.get('name') or h.get('model'), p)
                for h in hosts for p in (h.get('problems') or [])]
    enc = res.get('encrypted_values')
    _say('==> studio: checked %s layouts, broken %d, host problems %d, '
         'encrypted values %s' % (res.get('checked'), len(broken),
                                  len(problems),
                                  'unknown' if enc is None else enc))
    for item in broken:
        _say('    broken: %s layout %s — %s' % (
            item.get('model'), item.get('layout_id'), item.get('reason')))
    for name, problem in problems:
        _say('    host: %s — %s' % (name, problem))
    if broken or hosts:
        rc = 3
    if is_template:
        for item in res.get('encrypted_fields') or []:
            if item.get('values'):
                _say('    encrypted: %s %s — %s values (a clinic made from '
                     'the template could never read them)' % (
                         item.get('model'), item.get('name'),
                         item.get('values')))
        if enc is None or enc > 0:
            rc = 3
    return rc


def _active_jobs(env):
    env.cr.rollback()   # a fresh snapshot: another cursor may have written
    env.cr.execute('SELECT count(*) FROM ir_cron WHERE active')
    return env.cr.fetchone()[0]


def _quiet(env, master):
    """`biz.tenants._quiet_template(<this database>, say)` — from this
    database's registry when it has the platform module, else from the
    master's (the template itself does not carry it). The routine opens its
    own cursor on this database, commits, and records the job list in this
    database's `biz_tenants.template_active_crons`."""
    lines = []

    def say(text, level='info'):
        lines.append(text)

    dbname = env.cr.dbname
    env.cr.commit()
    if 'biz.tenants' in env.registry:
        count = env['biz.tenants'].sudo()._quiet_template(dbname, say)
        return count, 'this database', lines
    registry = Registry(master)
    with registry.cursor() as mcr:
        menv = api.Environment(mcr, SUPERUSER_ID, {})
        if 'biz.tenants' not in menv.registry:
            raise RuntimeError('biz.tenants is installed neither here nor '
                               'on %s' % master)
        count = menv['biz.tenants']._quiet_template(dbname, say)
        mcr.rollback()   # nothing is written on the master
    return count, master, lines


def _jobs(env, is_template, master):
    rc = 0
    active = _active_jobs(env)
    if not is_template:
        _say('==> jobs: %d active' % active)
        return rc
    count, _via, _lines = _quiet(env, master)
    after = _active_jobs(env)
    _say('==> jobs: %d active (template: switched off %d → %d)'
         % (active, count, after))
    if after:
        rc = 3
    return rc


def main(env):
    is_template = os.environ.get('CAREJIOX_IS_TEMPLATE') == '1'
    master = os.environ.get('CAREJIOX_MASTER_DB') or 'carejiox'
    rc = 0
    try:
        rc = max(rc, _studio(env, is_template))
    except Exception as exc:  # noqa: BLE001 — a check never raises past itself
        env.cr.rollback()
        _say('==> studio: check failed — %s' % exc)
        rc = 3
    try:
        rc = max(rc, _jobs(env, is_template, master))
    except Exception as exc:  # noqa: BLE001
        env.cr.rollback()
        _say('==> jobs: check failed — %s' % exc)
        rc = 3
    env.cr.commit()
    return rc


sys.exit(main(env))  # noqa: F821 — `env` is given by `odoo-bin shell`
