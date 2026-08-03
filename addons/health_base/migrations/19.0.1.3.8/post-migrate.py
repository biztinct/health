# -*- coding: utf-8 -*-
"""Phase SH-2 — T-001: the inverted `base.group_user → group_healthcare_base`
implication, the Doctor role it was masking, and the seven unused accounts.

WHY A MIGRATION AND NOT XML
---------------------------
`health_base/data/menu_access.xml` already carries the correct
`<field name="implied_ids" eval="[(3, ref('group_healthcare_base'))]"/>` on a
`base.group_user` record (commit 8be03c5e). It is **permanently dead code**:
`base.group_user`'s own `ir_model_data.noupdate` is `true`, and
`odoo/orm/models.py` skips `to_update` when `update and d_noupdate`, so the
unlink is silently dropped on every upgrade. The row can only be removed by
writing the database — which is what this script does, idempotently, so any
other database converges instead of relying on a one-off shell poke.
(Ledger: the noupdate seed-cutover gotcha; precedent commit a201b3d1, which
deleted the DB-only implied row 356→4 by hand for the same reason.)

WHY THE ROLE REPAIR IS IN THE SAME SCRIPT
-----------------------------------------
Deleting the edge alone locks out 21 active users, ten of whom are doctors:
`access.role` id 6 "Doctor" grants `base.group_user` and **nothing else** —
not even `health_base.group_healthcare_doctor` (id 350), which exists, is
correctly wired in XML (`security/health_security.xml:52`, 350 → 346) and is
what the role should always have granted. Those ten clinicians reach every
healthcare menu, the landing dashboard and the FSO wizards solely through the
defect. The repair is therefore part of the fix, not a follow-up, and it runs
FIRST so no window exists in which a doctor has no healthcare access.

The repair goes through `access.role.write()` — the access_roles module's own
API — because `_update_users_groups()` is what reconciles the role's groups
onto its linked users. Hand-writing `access_role_res_groups_rel` would leave
the users untouched and the `granted_group_ids` sync snapshot stale.

Odoo 19 note: `res.users.all_group_ids` is a NON-STORED compute over
`group_ids.all_implied_ids` (`base/models/res_users.py:446-449`), so writing a
group onto a user does NOT expand implications into `res_groups_users_rel`.
Granting group 350 adds exactly one relation row per user and 346 arrives
transitively — which is precisely why the ten doctors survive the edge
deletion, and why no doctor picks up `base.group_no_one` as a DIRECT group
(`health_user_admin` checks that one on direct containment only —
`res_users_saas.py:23-28`).

SCOPE DISCIPLINE
----------------
Exactly ONE row is removed: `(gid=1, hid=346)`. The other eleven forward edges
of `base.group_user` are the legitimate Odoo settings-toggle mechanism, and
`1 → 7` (`base.group_no_one`) in particular is load-bearing for the rationale
documented in `health_user_admin/models/res_users_saas.py:23-28` and
`access_role_saas.py:32-38`. Re-inserting the single deleted row restores the
previous state exactly — that is the rollback plan.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.fields import Command

_logger = logging.getLogger(__name__)

DOCTOR_ROLE_NAME = 'Doctor'
DOCTOR_GROUP_XMLID = 'health_base.group_healthcare_doctor'
HEALTHCARE_BASE_XMLID = 'health_base.group_healthcare_base'

# §5.5, ANSWERED BY THE USER 2026-08-03: all seven are unused. They lose
# healthcare access along with everyone else — nothing is granted, nothing is
# preserved — and 2026-08-03 the user additionally authorised archiving them.
# Archive only. NEVER delete a user row: they own audit-log, mail-message and
# create_uid references, and an orphaned create_uid makes historical evidence
# unattributable. Their res.partner records are deliberately left ACTIVE,
# because the partner is referenced by historical documents.
UNUSED_LOGINS = (
    'nam.lh', 'anh.pd', 'mai.vt', 'tuan.hm', 'ha.dt', 'huong.nt', 'bao.tq',
)


def _closure_of(cr, group_id):
    """Groups reachable from `group_id` through the LIVE implication table.

    Ledger §5.88 rule (a): a closure computed from the security XML is a claim
    about the addons; the one that governs access is in
    `res_groups_implied_rel`.
    """
    cr.execute("""
        WITH RECURSIVE closure(gid) AS (
            SELECT %s
            UNION
            SELECT rel.hid
              FROM res_groups_implied_rel rel
              JOIN closure ON closure.gid = rel.gid
        )
        SELECT gid FROM closure
    """, (group_id,))
    return {row[0] for row in cr.fetchall()}


def _repair_doctor_role(env):
    """Give `access.role` "Doctor" the healthcare group it never had."""
    doctor_group = env.ref(DOCTOR_GROUP_XMLID, raise_if_not_found=False)
    if not doctor_group:
        _logger.warning(
            "SH-2: %s not found — Doctor role repair SKIPPED", DOCTOR_GROUP_XMLID)
        return

    Role = env['access.role'].sudo()
    role = Role.search([('name', '=', DOCTOR_ROLE_NAME)], limit=1)
    if not role:
        _logger.info(
            "SH-2: no access.role named %r on this database — role repair is a "
            "no-op", DOCTOR_ROLE_NAME)
        return

    if doctor_group in role.groups_ids:
        _logger.info(
            "SH-2: access.role %r (id %s) already grants %s — no change",
            role.name, role.id, DOCTOR_GROUP_XMLID)
        return

    users = role.user_ids
    # access_roles' own API: write() -> _update_users_groups() links the role's
    # groups onto every linked user and refreshes the granted_group_ids sync
    # snapshot. It only LINKs here (nothing is being removed from the role).
    role.write({'groups_ids': [Command.link(doctor_group.id)]})
    env.flush_all()

    still_missing = users.filtered(lambda u: doctor_group not in u.group_ids)
    _logger.info(
        "SH-2: granted %s (id %s) to access.role %r (id %s); %s linked user(s) "
        "reconciled: %s",
        DOCTOR_GROUP_XMLID, doctor_group.id, role.name, role.id, len(users),
        ', '.join(sorted(users.mapped('login'))) or '(none)')
    if still_missing:
        _logger.error(
            "SH-2: %s user(s) did NOT receive the doctor group: %s",
            len(still_missing), ', '.join(sorted(still_missing.mapped('login'))))


def _delete_inverted_implication(env):
    """Remove the one row `(base.group_user → group_healthcare_base)`."""
    base_user = env.ref('base.group_user')
    healthcare_base = env.ref(HEALTHCARE_BASE_XMLID, raise_if_not_found=False)
    if not healthcare_base:
        _logger.warning(
            "SH-2: %s not found — edge deletion SKIPPED", HEALTHCARE_BASE_XMLID)
        return

    if healthcare_base not in base_user.implied_ids:
        _logger.info(
            "SH-2: base.group_user does not imply %s — already converged",
            HEALTHCARE_BASE_XMLID)
        return

    before = _closure_of(env.cr, base_user.id)
    # ORM rather than raw SQL: res.groups.write() clears the 'groups' registry
    # cache and ir.model.access's cache-clearing methods, which a DELETE would
    # not (base/models/res_groups.py:180-197).
    base_user.write({'implied_ids': [Command.unlink(healthcare_base.id)]})
    env.flush_all()
    env.registry.clear_cache('groups')

    after = _closure_of(env.cr, base_user.id)
    _logger.info(
        "SH-2: deleted res_groups_implied_rel (gid=%s, hid=%s); "
        "base.group_user closure %s -> %s groups, removed: %s",
        base_user.id, healthcare_base.id, len(before), len(after),
        sorted(before - after))
    if healthcare_base.id in after:
        _logger.error(
            "SH-2: group %s is STILL reachable from base.group_user after the "
            "deletion — another edge grants it", healthcare_base.id)


def _archive_unused_accounts(env):
    """Archive (never delete) the seven accounts authorised on 2026-08-03."""
    Users = env['res.users'].sudo().with_context(active_test=False)
    for login in UNUSED_LOGINS:
        user = Users.search([('login', '=', login)], limit=1)
        if not user:
            _logger.info("SH-2: login %r not present — skipped", login)
            continue
        if not user.active:
            _logger.info(
                "SH-2: login %r (id %s) is already archived — skipped",
                login, user.id)
            continue
        partner = user.partner_id
        user.write({'active': False})
        env.flush_all()
        _logger.info(
            "SH-2: archived res.users %r (id %s); res.partner %r (id %s) left "
            "active=%s",
            login, user.id, partner.name, partner.id, partner.active)


def migrate(cr, version):
    if not version:
        # Fresh install: the inverted edge never existed, and access.role rows
        # are user data that no fresh database carries.
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("SH-2: starting T-001 group-implication repair")
    # Order is load-bearing: repair the role BEFORE deleting the edge, so the
    # ten doctors never pass through a state with no healthcare access. The
    # archive runs last (§5.5a) so the access change is complete first.
    _repair_doctor_role(env)
    _delete_inverted_implication(env)
    _archive_unused_accounts(env)
    _logger.info("SH-2: T-001 repair complete")
