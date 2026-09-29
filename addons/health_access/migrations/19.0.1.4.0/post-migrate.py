# -*- coding: utf-8 -*-
"""ACCESS REVAMP AR-2 — the dark screens get abilities, and the hook that
switched them off stops deciding them twice.

TWO THINGS, BOTH ON THE LIVE PATH ONLY. `post_init_hook` does not fire on an
upgrade (ledger A2), so a database that already has this module learns both
here; a fresh one gets them from the seed and from the hook's first run.

  1. **Five abilities, given to nobody.** "Work the Zalo channel", "Set up the
     Zalo channel", "Handle calls", "Set up the phone system" and "Set up
     reporting" — each the one permission the switched-off screens behind it
     actually ask for. `ensure_catalogue` is create-only: it writes what is
     missing and changes nothing that exists. No role is given any of them;
     that is an owner's decision, made on the Access home.
  2. **The gate hook becomes create-only.** Every entry `_gate_new_items` has
     already decided is written down as handled, WITHOUT re-deciding it, so an
     Owner who later switches one of those entries on from the Screens lens is
     never switched off again by a later run.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.biz_access.hooks import ensure_catalogue
from odoo.addons.health_access.hooks import (DARK_SCREEN_ABILITIES,
                                             mark_gate_handled)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_catalogue(env)
    Ability = env['biz.access.ability'].sudo().with_context(active_test=False)
    found = Ability.search([('technical_key', 'in', list(DARK_SCREEN_ABILITIES))])
    carried = env['biz.access.role'].sudo().with_context(
        active_test=False).search([('ability_ids', 'in', found.ids)])
    _logger.info(
        'health_access 19.0.1.4.0: %s of %s dark-screen abilities on this '
        'database (%s); roles carrying any of them: %s',
        len(found), len(DARK_SCREEN_ABILITIES),
        ', '.join(found.mapped('technical_key')) or 'none',
        ', '.join(carried.mapped('name')) or 'none')
    marked = mark_gate_handled(env)
    _logger.info('health_access 19.0.1.4.0: %s left-menu entries marked as '
                 'decided — the gate hook will leave them as they are', marked)
