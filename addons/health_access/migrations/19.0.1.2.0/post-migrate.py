# -*- coding: utf-8 -*-
"""Everything that has to be true before the previous access application goes.

A HOOK DOES NOT FIRE ON AN UPGRADE, which is the whole reason this file exists.
`post_init_hook` ran the day this module landed and will not run again; the
database that matters is the one that already has it. So the same functions are
called from here, and they are the SAME functions — not a copy written to
agree, because a copy written to agree is a copy that stops agreeing.

WHAT IT DOES, IN THIS ORDER, AND WHY THE ORDER IS THE ARGUMENT.

  1. **The carry-over, once more.** Anything the old application has gained
     since (a role somebody added, a menu somebody hid) is written across
     before it goes. Idempotent; on a converged database it writes nothing.
  2. **The retirement.** What each role counts as, everybody's JOB, the
     clinic's own administrator tier, and who may build a report — the four
     facts that were still only in the old shape.
  3. **The doors.** The gate on the Access home entry and on every entry added
     because the bar above the screen is now the platform administrator's.

Every step runs correctly on a database that never had the old application:
this same code is what a brand-new clinic runs on the day it is created.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.biz_access.hooks import ensure_catalogue
from odoo.addons.health_access.hooks import (_gate_admin_item, _gate_new_items,
                                             _release_borrowed_matches,
                                             migrate_legacy, retire_legacy)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info('health_access 19.0.1.2.0: retiring the previous access '
                 'application — starting')
    ensure_catalogue(env)
    migrate_legacy(env)
    summary = retire_legacy(env)
    _gate_admin_item(env)
    _gate_new_items(env)
    _release_borrowed_matches(env)
    _logger.info(
        'health_access 19.0.1.2.0: %s role(s) classified, %s job(s) written, '
        '%s administrator(s) moved, %s role(s) given "build reports"',
        summary.get('kinds'), summary.get('jobs'), summary.get('admins'),
        summary.get('analytics'))
