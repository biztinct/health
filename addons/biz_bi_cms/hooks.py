# -*- coding: utf-8 -*-
"""Who sees the Analytics entries on the left menu.

WHAT THIS FILE USED TO BE, AND WHY IT IS SHORTER NOW. It used to do two jobs.
It gated the Analytics leaf by MATCHING THE WORDS "Owner", "Operations
Manager", "Branch Manager" and "Accountant" against rows in a table — because
the roles on this deployment were database rows with no fixed name to point at
— and it then handed those same people the reporting permission, because a menu
entry is visibility and never permission.

Both of those are now said once, properly, somewhere else. The roles have fixed
names (`health_access.role_*`), so the gate is written with `ref()` like every
other gate. And "build reports" is an ABILITY on four role bundles, so the
permission arrives the way every other permission does — by holding a role —
rather than by a second sweep that had to be re-run to catch new hires.

WHAT IS LEFT is the one thing that genuinely cannot be done in XML: these
entries are `noupdate="1"`, so an upgrade of an already-installed copy does not
re-assert what the file says. The gate has to be WRITTEN. It runs from
``post_init_hook`` and from the migration, so a fresh install and an upgrade
converge on the same menu.

Never blinding: a role this database does not have is skipped, never written as
an empty set. Gating an entry to nobody hides a feature from everyone, which is
worse than showing it to somebody whose permissions will refuse the data.
"""
import logging

from odoo.fields import Command

# THE DOOR CHECK, BORROWED RATHER THAN COPIED. "Can somebody holding this role
# actually open that screen" is asked in exactly one place, and this module
# asks it of the same code the Access overlay does — a second copy would be a
# second answer the day one of them is corrected.
from odoo.addons.health_access.hooks import model_behind, role_can_read

_logger = logging.getLogger(__name__)

# The four roles that get Analytics, by their fixed names. One tuple, one
# consumer: the ABILITY on the bundles decides the permission, and this decides
# only what is drawn — the two cannot drift, because there is no longer a
# second list to drift from.
ANALYTICS_ROLE_XMLIDS = (
    'health_access.role_owner',
    'health_access.role_operations_manager',
    'health_access.role_branch_manager',
    'health_access.role_accountant',
)

# leaf xml-id -> the roles that open it. Absent from this map ⇒ ungated.
#
# ONLY THE TOP-MOST ROWS ARE NAMED. A gate on an entry flows down to everything
# under it, so gating seven data screens one by one would be seven chances for
# them to disagree with each other.
ROLE_GATES = {
    'item_analytics_hub': ANALYTICS_ROLE_XMLIDS,
    'item_analytics_explore': ANALYTICS_ROLE_XMLIDS,
    'item_analytics_dashboards': ANALYTICS_ROLE_XMLIDS,
    'item_analytics_data': ANALYTICS_ROLE_XMLIDS,
    'item_analytics_settings': ANALYTICS_ROLE_XMLIDS,
}


def gated_roles(env, xmlids=ANALYTICS_ROLE_XMLIDS):
    """The role rows behind those names, on THIS database."""
    roles = env['biz.access.role'].sudo().browse()
    for xmlid in xmlids:
        role = env.ref(xmlid, raise_if_not_found=False)
        if role:
            roles |= role
    return roles


def apply_role_gates(env):
    """Write the gate on the Analytics entries. Idempotent, never blinding.

    AND SWITCH OFF WHAT NOBODY CAN OPEN. Several of these screens are governed
    by the reporting ladder's upper rungs — the semantic model, the access
    rules, the AI providers — and no role on this clinic carries them. An entry
    that draws for somebody and then refuses them the data is a dead end, so it
    is not drawn. It comes back the day a role is given the permission, because
    this is re-decided on every run.
    """
    Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
    gated = skipped = 0
    for xmlid, role_xmlids in ROLE_GATES.items():
        item = env.ref('biz_bi_cms.%s' % xmlid, raise_if_not_found=False)
        if not item:
            continue
        roles = gated_roles(env, role_xmlids)
        if not roles:
            skipped += 1
            _logger.warning(
                'biz_bi_cms: none of the roles %s exist on this database — '
                'leaving %s open to everybody rather than hidden from '
                'everybody', list(role_xmlids), xmlid)
            continue
        if set(item.biz_role_ids.ids) != set(roles.ids):
            item.sudo().write({'biz_role_ids': [Command.set(roles.ids)]})
        gated += 1

    # Children first: a heading is alive exactly when something under it is.
    rows = env['ir.model.data'].sudo().search([
        ('module', '=', 'biz_bi_cms'), ('model', '=', 'cms.sidebar.item')])
    ours = Item.browse([r.res_id for r in rows]).exists()
    closed = []
    for item in ours.filtered(lambda i: i.action_xmlid):
        model = model_behind(env, item)
        audience = item.effective_biz_role_ids.filtered('active')
        opens = bool(env.ref(item.action_xmlid, raise_if_not_found=False))
        if opens and model and audience:
            opens = any(role_can_read(env, r, model) for r in audience)
        if item.active != opens:
            item.write({'active': opens})
            if not opens:
                closed.append('%s (%s)' % (item.name, model))
    for item in ours.filtered(lambda i: not i.action_xmlid):
        alive = bool(Item.search_count(
            [('parent_id', '=', item.id), ('active', '=', True)]))
        if item.active != alive:
            item.write({'active': alive})
            if not alive:
                closed.append(item.name)

    _logger.info('biz_bi_cms: role-gated %s left-menu entries (%s left ungated '
                 'for want of a role)%s', gated, skipped,
                 ('; switched off because nobody can open them: '
                  + ', '.join(closed)) if closed else '')
    return gated


def post_init_hook(env):
    apply_role_gates(env)
