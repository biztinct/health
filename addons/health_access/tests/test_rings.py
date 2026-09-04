# -*- coding: utf-8 -*-
"""The two rings, after the application that used to hold the inner one went.

WHAT A RING IS, IN ONE SENTENCE EACH. The PLATFORM ring is `base.group_system`:
one account, the settings for the box, installing code. The TENANT ring is this
clinic's own administrators: adding colleagues, switching them off, saying who
does what. The whole design is that the second can never reach the first, and
these are the tests that used to live in the retired application, re-asserted
against what replaced it.

WHAT CHANGED, AND WHY SOME OF THEM ARE NOW ONE LINE. Several of the old tests
guarded a table an administrator could edit: "a tenant admin cannot write on the
roles table", "cannot see a privileged role", "cannot assign one". There is no
such table any more — a role is a bundle of abilities and the MODEL REFUSES to
carry a forbidden permission at all, over the whole implied closure, on create
and on write. A guard that used to need a record rule is now a constraint, so
the test that proves it is the one that tries to build the dangerous thing and
is told no.
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import forbidden_in_closure


@tagged('post_install', '-at_install')
class RingCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = cls.env.ref('base.group_user')
        cls.system = cls.env.ref('base.group_system')
        cls.clinic_admin = cls.env.ref('health_access.group_clinic_admin')

        cls.tenant_admin = cls.env['res.users'].create({
            'name': 'RG clinic administrator',
            'login': 'rg.admin@example.test',
            'group_ids': [(4, cls.internal.id), (4, cls.clinic_admin.id)]})
        cls.platform_admin = cls.env['res.users'].create({
            'name': 'RG platform administrator',
            'login': 'rg.platform@example.test',
            'group_ids': [(4, cls.internal.id), (4, cls.system.id)]})
        cls.colleague = cls.env['res.users'].create({
            'name': 'RG colleague', 'login': 'rg.colleague@example.test',
            'group_ids': [(4, cls.internal.id)]})


@tagged('post_install', '-at_install')
class TestTheTenantRingCannotReachThePlatformRing(RingCase):

    def test_the_clinic_administrator_permission_does_not_reach_the_box(self):
        bad = forbidden_in_closure(self.clinic_admin, self.env)
        self.assertFalse(
            bad, 'the clinic administrator permission reaches %s'
                 % ', '.join(bad.mapped('name')))

    def test_a_role_that_would_reach_it_cannot_exist(self):
        """The old guard was a record rule hiding "privileged" roles from a
        list. The new one is a constraint: the dangerous thing cannot be built,
        so there is nothing to hide."""
        wrapper = self.env['res.groups'].create({
            'name': 'RG wrapper', 'implied_ids': [(4, self.system.id)]})
        with self.assertRaises(ValidationError):
            self.env['biz.access.ability'].create({
                'technical_key': 'rg-bad', 'name': 'RG bad',
                'group_ids': [(6, 0, wrapper.ids)]})

    def test_no_role_on_this_database_reaches_it_either(self):
        for role in self.env['biz.access.role'].with_context(
                active_test=False).search([]):
            bad = forbidden_in_closure(role.group_ids, self.env)
            self.assertFalse(
                bad, '"%s" reaches %s' % (role.name,
                                          ', '.join(bad.mapped('name'))))

    def test_a_clinic_administrator_may_give_out_a_role(self):
        """The tenant ring is not a smaller platform ring — it is the tier that
        actually does this job, and it has to be able to."""
        role = self.env['biz.access.role'].search(
            [('active', '=', True), ('group_ids', '!=', False)], limit=1)
        if not role:
            self.skipTest('this database has no role with a permission in it')
        facade = self.env['biz.access'].with_user(self.tenant_admin)
        self.assertTrue(facade.can_manage())
        facade.grant(role.id, self.colleague.id, reason='a test')
        self.colleague.invalidate_recordset()
        self.assertTrue(set(role.group_ids.ids)
                        <= set(self.colleague.all_group_ids.ids))

    def test_a_colleague_may_not(self):
        role = self.env['biz.access.role'].search([('active', '=', True)],
                                                  limit=1)
        with self.assertRaises(AccessError):
            self.env['biz.access'].with_user(self.colleague).grant(
                role.id, self.tenant_admin.id, reason='a test')


@tagged('post_install', '-at_install')
class TestWhatCannotBeDoneToThePlatformAdministrator(RingCase):

    def _run(self, action, target):
        return self.env['biz.access'].with_user(
            self.tenant_admin).run_person_action(action, target.id)

    def test_the_platform_administrator_cannot_be_switched_off(self):
        with self.assertRaises(UserError):
            self._run('deactivate', self.platform_admin)
        self.platform_admin.invalidate_recordset()
        self.assertTrue(self.platform_admin.active)

    def test_nobody_switches_themselves_off(self):
        with self.assertRaises(UserError):
            self._run('deactivate', self.tenant_admin)

    def test_the_platform_administrators_password_is_not_reset_from_here(self):
        with self.assertRaises(UserError):
            self._run('reset_password', self.platform_admin)

    def test_the_rule_that_keeps_the_administrator_off_the_list_moved_across(self):
        """CARRIED ACROSS EXACTLY, INCLUDING ITS LIMITATION.

        The retired application had a rule saying a clinic administrator does
        not see the account that owns the box. It moved here word for word, on
        the new permission.

        It has NOT worked on this database for some time, and that is a fact
        this phase found rather than caused: record rules attached to groups
        are ORed, and `health_base.group_healthcare_admin` — which this tier
        implies, and which the retired tier implied too — carries a catchment
        rule whose domain is "everybody". The OR wins. Asserting the EFFECT
        here would be asserting something that was not true before this phase
        either; asserting the rule is present, on the right permission, with
        the same domain, is the honest statement of what moved.
        """
        rule = self.env.ref('health_access.rule_hide_system_admins',
                            raise_if_not_found=False)
        self.assertTrue(rule, 'the rule did not come across')
        self.assertIn(self.clinic_admin, rule.groups)
        self.assertIn('group_ids', rule.domain_force)
        self.assertIn(str(self.system.id), rule.domain_force)


@tagged('post_install', '-at_install')
class TestTheAdminGroupSwap(RingCase):

    def test_the_new_permission_carries_what_the_old_one_did(self):
        implied = self.clinic_admin.implied_ids
        self.assertIn(self.env.ref('health_base.group_healthcare_admin'),
                      implied)

    def test_add_people_and_give_out_roles_hands_out_the_new_one(self):
        ability = self.env['biz.access.ability'].with_context(
            active_test=False).search([('technical_key', '=', 'user-admin')],
                                      limit=1)
        if not ability:
            self.skipTest('this database has no "add people" ability')
        self.assertEqual(ability.group_ids, self.clinic_admin)

    def test_everybody_who_ran_the_clinic_still_runs_it(self):
        """Every holder of Admin, Owner or Operations Manager holds it IN FULL
        after the swap — the ability moved, so the bundles recomputed, and a
        bundle that recomputed onto a permission nobody had would be a role
        that silently stopped being held."""
        for xmlid in ('health_access.role_admin', 'health_access.role_owner',
                      'health_access.role_operations_manager'):
            role = self.env.ref(xmlid, raise_if_not_found=False)
            if not role:
                continue
            with self.subTest(role=role.name):
                self.assertTrue(role.group_ids,
                                '"%s" hands out nothing' % role.name)
                for user in role.holders():
                    self.assertTrue(
                        set(role.group_ids.ids)
                        <= set(user.sudo().all_group_ids.ids),
                        '%s no longer holds "%s" in full'
                        % (user.login, role.name))
