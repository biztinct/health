# -*- coding: utf-8 -*-
"""Two doors, gated to the right people, and one of them switched off where it
would open nothing.

WHY A HOOK AND NOT A `ref=` IN THE DATA FILE. The roles both entries are gated
to are created by ANOTHER module's own install hook, which runs after this
module's data file is read — and a `ref()` can only point at a row that already
exists. So the entries ship ungated and the gate is written here, exactly as
`health_access` does with its own.

WHY "CUSTOMERS" IS DECIDED EVERY TIME RATHER THAN ONCE. Its action lives in a
module a customer's system never receives. On the platform's own system it
resolves and the door works; on a customer's it does not, and an entry that
opens nothing is a dead end — worse than an absence, because somebody clicks it
and gets an error. Deciding it on every run rather than once means the door
comes back on its own the day the cockpit is installed somewhere, and goes away
again if it is ever removed.
"""
import logging

_logger = logging.getLogger(__name__)

#: The entry, the action behind it, and the roles it is open to.
#:
#: OWNER AND ADMIN FOR "ABOUT", because the question it answers — which release
#: are we on, what changed, who do we ring — is one the people who run a clinic
#: ask and nobody else needs.
#:
#: OWNER ALONE FOR "CUSTOMERS", because it creates, copies and removes other
#: people's systems.
DOORS = (
    {
        'xmlid': 'health_tenancy.item_admin_about',
        'action': 'biz_tenancy.action_biz_tenancy_about',
        'roles': ('Owner', 'Admin'),
    },
    {
        'xmlid': 'health_tenancy.item_admin_customers',
        'action': 'biz_tenants.action_biz_tenants',
        'roles': ('Owner',),
    },
)


def _role_ids(env, names):
    """The bundles with these names, archived ones included."""
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    ids = []
    for name in names:
        role = Role.search([('name', '=', name)], limit=1)
        if role:
            ids.append(role.id)
        else:
            _logger.info("health_tenancy: there is no role called \"%s\" on "
                         "this system, so it was not put on the gate.", name)
    return ids


def wire_doors(env):
    """Gate both entries and switch off any whose action is not here.

    Idempotent, and safe to run again by hand or from a later migration —
    which is the point: an install hook does not fire on an upgrade, and a
    migration does not fire on an install, so anything that must be true on
    BOTH paths has to be reachable from both.
    """
    report = {'gated': [], 'switched_on': [], 'switched_off': [], 'missing': []}
    for door in DOORS:
        item = env.ref(door['xmlid'], raise_if_not_found=False)
        if not item:
            report['missing'].append(door['xmlid'])
            continue
        resolves = bool(env.ref(door['action'], raise_if_not_found=False))
        vals = {}
        if item.active != resolves:
            vals['active'] = resolves
            (report['switched_on'] if resolves
             else report['switched_off']).append(door['xmlid'])
        ids = _role_ids(env, door['roles'])
        if ids and set(item.biz_role_ids.ids) != set(ids):
            vals['biz_role_ids'] = [(6, 0, ids)]
            report['gated'].append(door['xmlid'])
        if vals:
            item.sudo().write(vals)
    _logger.info(
        "health_tenancy: doors wired — %d gated, %d switched on, %d switched "
        "off, %d missing", len(report['gated']), len(report['switched_on']),
        len(report['switched_off']), len(report['missing']))
    return report


def post_init_hook(env):
    wire_doors(env)
