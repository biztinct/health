# -*- coding: utf-8 -*-
"""Two-ring access control tests.

Ring 0 = platform admin (base.group_system + access_roles administrator):
owns role/permission design.
Ring 1 = tenant admin (group_health_user_admin): creates users, assigns
PREDEFINED non-privileged roles, never touches role design.
Ring 2 = everyone else: read-only on the access_roles models.

Covers the two escalation holes closed this phase:
E1 — a role whose groups merely IMPLY base.group_system (the Owner-role
     escalation rode a DB-only implied_ids row);
E2 — assigning access_roles.access_role_group_administrator (the module's
     own admin group) through a role.
And the group-sync rework: reconcile-not-set, so a role edit never wipes
groups a user holds outside the role.
"""

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccessRings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.group_system = env.ref('base.group_system')
        cls.group_user = env.ref('base.group_user')
        cls.group_role_admin = env.ref(
            'access_roles.access_role_group_administrator')
        cls.group_tenant_admin = env.ref(
            'health_user_admin.group_health_user_admin')

        Users = env['res.users'].with_context(no_reset_password=True)
        # Ring 0: direct group_system (the saas layer keys on DIRECT
        # membership) + the access_roles admin group.
        cls.ring0 = Users.create({
            'name': 'Ring0 Platform Admin', 'login': 'test_ring0',
            'group_ids': [Command.link(cls.group_user.id),
                          Command.link(cls.group_system.id),
                          Command.link(cls.group_role_admin.id)],
        })
        # Ring 1: tenant admin, explicitly WITHOUT group_system.
        cls.ring1 = Users.create({
            'name': 'Ring1 Tenant Admin', 'login': 'test_ring1',
            'group_ids': [Command.link(cls.group_user.id),
                          Command.link(cls.group_tenant_admin.id)],
        })
        # Ring 2: plain internal user.
        cls.ring2 = Users.create({
            'name': 'Ring2 Plain User', 'login': 'test_ring2',
            'group_ids': [Command.link(cls.group_user.id)],
        })

        # A harmless business group and a safe role carrying it.
        cls.group_safe = env['res.groups'].create({'name': 'Ring Test Safe'})
        cls.role_safe = env['access.role'].with_user(cls.ring0).create({
            'name': 'Ring Test Safe Role',
            'groups_ids': [Command.set([cls.group_user.id,
                                        cls.group_safe.id])],
        })

        # E1 fixture: an ordinary-looking wrapper group that IMPLIES
        # group_system, and a role containing it (created by ring 0, whom
        # the saas validation intentionally exempts).
        cls.group_wrapper = env['res.groups'].create({
            'name': 'Ring Test Wrapper',
            'implied_ids': [Command.link(cls.group_system.id)],
        })
        cls.role_privileged = env['access.role'].with_user(cls.ring0).create({
            'name': 'Ring Test Privileged Role',
            'groups_ids': [Command.set([cls.group_wrapper.id])],
        })

    # ---- ACL: write surfaces are ring 0 only ----

    def test_ring1_cannot_write_access_role(self):
        role = self.role_safe.with_user(self.ring1)
        with self.assertRaises(AccessError):
            role.write({'name': 'renamed by tenant admin'})

    def test_ring1_cannot_create_access_role(self):
        with self.assertRaises(AccessError):
            self.env['access.role'].with_user(self.ring1).create(
                {'name': 'tenant made role'})

    def test_ring1_cannot_write_role_management(self):
        rm = self.env['role.management'].with_user(self.ring0).create(
            {'name': 'Ring Test Profile'})
        with self.assertRaises(AccessError):
            rm.with_user(self.ring1).write({'name': 'renamed'})

    def test_ring2_read_only_everywhere(self):
        as_ring2 = self.role_safe.with_user(self.ring2)
        self.assertEqual(as_ring2.name, 'Ring Test Safe Role')  # read OK
        with self.assertRaises(AccessError):
            as_ring2.write({'name': 'plain user write'})
        with self.assertRaises(AccessError):
            self.env['access.role'].with_user(self.ring2).create(
                {'name': 'plain user role'})
        with self.assertRaises(AccessError):
            self.env['domain.model'].with_user(self.ring2).create(
                {'name': "[('id','=',1)]"})

    def test_ring0_keeps_full_write(self):
        role = self.role_safe.with_user(self.ring0)
        role.write({'name': 'Ring Test Safe Role (r0 edit)'})
        self.assertEqual(role.name, 'Ring Test Safe Role (r0 edit)')

    # ---- E1: implication-aware validation ----

    def test_privileged_role_flag(self):
        self.assertTrue(self.role_privileged.is_privileged)
        self.assertFalse(self.role_safe.is_privileged)

    def test_e1_assign_privileged_role_blocked(self):
        target = self.ring2.with_user(self.ring1)
        with self.assertRaises(UserError):
            target.action_saas_assign_role(self.role_privileged.id)
        # and the direct field write path
        with self.assertRaises(UserError):
            target.write({'access_role_id': self.role_privileged.id})

    def test_e1_wizard_refuses_privileged_role(self):
        wizard = self.env['health.create.user.wizard'].with_user(
            self.ring1).create({
                'name': 'Sneaky User', 'login': 'test_sneaky@x.com',
                'access_role_id': self.role_privileged.id,
            })
        with self.assertRaises(UserError):
            wizard.action_create_user()

    def test_privileged_role_hidden_from_ring1(self):
        visible = self.env['access.role'].with_user(self.ring1).search([])
        self.assertNotIn(self.role_privileged, visible)
        self.assertIn(self.role_safe, visible)

    def test_e1_guard_blocks_implying_group_on_user(self):
        with self.assertRaises(AccessError):
            self.ring2.with_user(self.ring1).write({
                'group_ids': [Command.link(self.group_wrapper.id)]})

    # ---- E2: the module's own admin group is forbidden ----

    def test_e2_role_admin_group_blocked_in_role(self):
        # ring 1 cannot even write roles (ACL) — E2's guard must ALSO hold
        # for any non-direct-system-admin who has write, so exercise the
        # validation layer via sudo-with-user semantics: a hypothetical
        # editor without direct group_system.
        editor = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Role Editor No System', 'login': 'test_editor',
                'group_ids': [Command.link(self.group_user.id),
                              Command.link(self.group_role_admin.id)],
            })
        with self.assertRaises(AccessError):
            self.role_safe.with_user(editor).write({
                'groups_ids': [Command.link(self.group_role_admin.id)]})

    def test_e2_assign_role_carrying_role_admin_group(self):
        role = self.env['access.role'].with_user(self.ring0).create({
            'name': 'Ring Test E2 Role',
            'groups_ids': [Command.set([self.group_role_admin.id])],
        })
        self.assertTrue(role.is_privileged)
        with self.assertRaises(UserError):
            self.ring2.with_user(self.ring1).action_saas_assign_role(role.id)

    # ---- group sync: reconcile, never set ----

    def test_snapshot_seeded_on_create(self):
        self.assertEqual(self.role_safe.granted_group_ids,
                         self.role_safe.groups_ids)

    def test_role_edit_preserves_outside_groups(self):
        group_extra = self.env['res.groups'].create({'name': 'Ring Extra'})
        group_new = self.env['res.groups'].create({'name': 'Ring New'})
        user = self.ring2
        # user holds the role AND an unrelated direct group
        self.role_safe.with_user(self.ring0).write(
            {'user_ids': [Command.link(user.id)]})
        user.write({'group_ids': [Command.link(self.group_safe.id),
                                  Command.link(group_extra.id)]})
        # ring 0 swaps the role's business group
        self.role_safe.with_user(self.ring0).write({
            'groups_ids': [Command.unlink(self.group_safe.id),
                           Command.link(group_new.id)],
        })
        user.invalidate_recordset()
        self.assertIn(group_new, user.group_ids,
                      "role's new group must be granted")
        self.assertNotIn(self.group_safe, user.group_ids,
                         "group the role no longer contains is reconciled off")
        self.assertIn(group_extra, user.group_ids,
                      "groups held OUTSIDE the role must never be wiped")
        self.assertEqual(self.role_safe.granted_group_ids,
                         self.role_safe.groups_ids,
                         "snapshot follows the role")

    def test_prestage_gains_only_role_groups(self):
        """A user smuggled into user_ids gains the role's groups at most —
        with the ACL lockdown they cannot even do the smuggling, but the
        sync must stay bounded regardless."""
        group_extra = self.env['res.groups'].create({'name': 'Ring Extra 2'})
        self.ring2.write({'group_ids': [Command.link(group_extra.id)]})
        self.role_safe.with_user(self.ring0).write(
            {'user_ids': [Command.link(self.ring2.id)]})
        self.role_safe.with_user(self.ring0).write(
            {'groups_ids': [Command.link(self.env.ref(
                'base.group_multi_currency').id)]})
        self.ring2.invalidate_recordset()
        self.assertIn(group_extra, self.ring2.group_ids)
        self.assertNotIn(self.group_system, self.ring2.group_ids)

    # ---- ring 1 keeps its legitimate powers ----

    def test_ring1_wizard_creates_user_with_safe_role(self):
        wizard = self.env['health.create.user.wizard'].with_user(
            self.ring1).create({
                'name': 'Legit New User', 'login': 'test_legit@x.com',
                'access_role_id': self.role_safe.id,
            })
        wizard.action_create_user()
        new_user = self.env['res.users'].sudo().search(
            [('login', '=', 'test_legit@x.com')])
        self.assertTrue(new_user)
        self.assertEqual(new_user.access_role_id, self.role_safe)
        self.assertIn(new_user, self.role_safe.sudo().user_ids)

    def test_ring1_assigns_safe_role(self):
        self.ring2.with_user(self.ring1).action_saas_assign_role(
            self.role_safe.id)
        self.assertEqual(self.ring2.access_role_id, self.role_safe)

    def test_ring1_can_edit_sidebar_items(self):
        item = self.env['cms.sidebar.item'].sudo().search([], limit=1)
        if not item:
            self.skipTest('no cms.sidebar.item installed/seeded')
        item.with_user(self.ring1).write({'sequence': item.sequence})

    # ---- watchdog ----

    def test_watchdog_screams_on_reverted_acl(self):
        acl = self.env.ref('access_roles.access_access_role')
        self.assertFalse(acl.perm_write,
                         'lockdown row must be read-only after upgrade')
        acl.sudo().write({'perm_write': True})
        try:
            with self.assertLogs(
                    'odoo.addons.health_user_admin.models.res_users_saas',
                    level='CRITICAL'):
                self.env['res.users']._register_hook()
        finally:
            acl.sudo().write({'perm_write': False})
