# -*- coding: utf-8 -*-
"""Role gating for the ANALYTICS leaf, and the BI group that makes it useful.

Two separate jobs, both written in python rather than XML, and both idempotent:

1. ``apply_role_gates`` writes ``cms.sidebar.item.role_ids`` on the Analytics
   leaf. ``access.role`` rows on this deployment are **database rows with no
   xml-id** (measured: Owner, Operations Manager, Branch Manager, Banker,
   Nurse, Doctor, Accountant, Admin, CRM — none appear in ``ir_model_data``),
   so the relation cannot be seeded with ``ref()``. This is exactly how
   health_cms_coverage gates its nineteen leaves, and how the 34 leaves that
   predate it are gated.

2. ``grant_creator_group`` gives those same roles' users
   ``biz_bi.group_bi_creator``. **A sidebar item is visibility, not
   permission**: every BI record rule is keyed on the ``group_bi_viewer →
   creator → modeler → admin`` ladder, so without the group the leaf draws
   and the hub answers "no analytics access". Before this module ran, exactly
   two accounts on vietuat held any BI group at all.

Both run from ``post_init_hook`` AND from the 19.0.1.0.0 migration script, so
an upgrade of an already-installed copy converges on the same state as a fresh
install (and re-applies after someone edits the roles).

Never blinding, never removing:

* a role name this deployment does not have is SKIPPED, never written as
  ``[(6, 0, [])]`` — gating a leaf to nobody hides a feature from everyone,
  which is worse than showing it to a role whose ACL will refuse the data;
* the group grant only ever LINKS (``Command.link``). It never removes a
  group from anyone, never touches users with no ``access_role_id``, and
  skips any user who already reaches the group through the implication
  closure (``all_group_ids`` — Odoo 19 computes it at read time, ledger
  §5.114, so holding ``group_bi_admin`` already counts).
"""
import logging

from odoo.fields import Command

_logger = logging.getLogger(__name__)

# The four business roles that get Analytics. One tuple, two consumers: the
# sidebar gate and the BI group grant must never drift apart — a role that can
# see the leaf but cannot read a workspace is the defect this module exists to
# avoid.
ANALYTICS_ROLE_NAMES = ('Owner', 'Operations Manager', 'Branch Manager',
                        'Accountant')

# leaf xml-id -> role NAMES that may see it. Absent from this map ⇒ ungated.
ROLE_GATES = {
    'item_analytics_hub': ANALYTICS_ROLE_NAMES,
}

CREATOR_GROUP_XMLID = 'biz_bi.group_bi_creator'


def apply_role_gates(env):
    """Write ``role_ids`` on the gated leaves. Idempotent, and never blinding."""
    by_name = {r.name: r.id for r in env['access.role'].sudo().search([])}
    gated = skipped = 0
    for xmlid, names in ROLE_GATES.items():
        item = env.ref('biz_bi_cms.%s' % xmlid, raise_if_not_found=False)
        if not item:
            continue
        role_ids = [by_name[name] for name in names if name in by_name]
        if not role_ids:
            skipped += 1
            _logger.warning(
                'biz_bi_cms: none of the roles %s exist on this database — '
                'leaving %s visible to every role rather than hiding it from '
                'everyone', list(names), xmlid)
            continue
        item.sudo().write({'role_ids': [Command.set(role_ids)]})
        gated += 1
    _logger.info('biz_bi_cms: role-gated %s sidebar leaves (%s left ungated '
                 'for want of a role)', gated, skipped)
    return gated


def grant_creator_group(env):
    """Give every gated-role user ``biz_bi.group_bi_creator``.

    Additive only. Returns the number of users who gained the group, so the
    caller (and the tests) can assert that a second run adds nothing.
    """
    group = env.ref(CREATOR_GROUP_XMLID, raise_if_not_found=False)
    if not group:
        _logger.warning('biz_bi_cms: %s does not exist — no BI group granted',
                        CREATOR_GROUP_XMLID)
        return 0

    roles = env['access.role'].sudo().search(
        [('name', 'in', list(ANALYTICS_ROLE_NAMES))])
    if not roles:
        _logger.warning('biz_bi_cms: none of the roles %s exist on this '
                        'database — no BI group granted',
                        list(ANALYTICS_ROLE_NAMES))
        return 0

    users = env['res.users'].sudo().search([
        ('access_role_id', 'in', roles.ids),
        ('share', '=', False),
        ('active', '=', True),
    ])
    granted = 0
    for user in users:
        # all_group_ids is the READ-TIME closure (§5.114): a user already
        # holding group_bi_admin reaches creator transitively and must not be
        # handed a redundant direct row.
        if group in user.all_group_ids:
            continue
        user.write({'group_ids': [Command.link(group.id)]})
        granted += 1
    _logger.info('biz_bi_cms: granted %s to %s of %s role users',
                 CREATOR_GROUP_XMLID, granted, len(users))
    return granted


def post_init_hook(env):
    apply_role_gates(env)
    grant_creator_group(env)
