# -*- coding: utf-8 -*-
"""ACCESS REVAMP AR-1 — the clinic administrator becomes a whole access manager,
and the Owner role becomes one only its holders may give.

WHY A MIGRATION FOR SOMETHING THE XML ALREADY SAYS. The implication is in
`security/health_access_security.xml`, which an upgrade does load. It is
asserted again here anyway, and the people it reached are written to the log,
because "who can now give and take roles" is the question somebody will ask
about this release, and the log is where the answer is kept.

THE GUARD IS SET ONCE. `post_init_hook` does not fire on an upgrade (ledger A2),
so the live path is this file; the fresh path is the seed. After today nothing
sets it again, so somebody who holds Owner can deliberately switch it off and
the next upgrade leaves that decision alone.
"""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_access.hooks import ensure_guarded

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    clinic = env.ref('health_access.group_clinic_admin', raise_if_not_found=False)
    team = env.ref('biz_access.group_access_manager', raise_if_not_found=False)
    if clinic and team:
        if team not in clinic.implied_ids:
            clinic.sudo().write({'implied_ids': [(4, team.id)]})
        clinic.invalidate_recordset()
        team.invalidate_recordset()
        # Everybody who now reaches the access team through the clinic tier,
        # minus the two built-in accounts that always had it by name.
        reached = (clinic.sudo().all_user_ids & team.sudo().all_user_ids)
        reached = reached.filtered(lambda u: u.active and not u.share)
        named = team.sudo().user_ids
        gained = reached - named
        _logger.info(
            'health_access 19.0.1.3.0: %s people now manage access through '
            'the clinic administrator tier: %s', len(gained),
            ', '.join('%s (%s)' % (u.name, u.login) for u in gained))
    marked = ensure_guarded(env)
    _logger.info('health_access 19.0.1.3.0: guarded roles marked: %s',
                 ', '.join(marked) or 'none needed')
