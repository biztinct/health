# -*- coding: utf-8 -*-
"""The vocabulary, and the roles written down out of what already existed.

THE ONE THING WORTH PROVING is that the carry-over is EXACT. Not "close", not
"the same roles by name" — exact, permission for permission, for every role the
clinic runs on. A role that came across a little smaller is a role that quietly
takes something away from everybody who holds it, and nobody would notice until
somebody could not open a screen they opened yesterday.

Everything else in this file exists to protect that:

  * every permission any role carries has an ability, or the carry-over REFUSES
    rather than writing a smaller role;
  * nothing in the vocabulary reaches the administrator permission for the box,
    over the whole implied closure;
  * every role has a fixed name of its own, so no module ever has to find one by
    matching the word "Nurse" again;
  * the role of nothing but signing in is put away, because a role held by
    everybody would open every entry it is put on to everybody.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import forbidden_in_closure
from odoo.addons.health_access import hooks


@tagged('post_install', '-at_install')
class CatalogueCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Role = cls.env['biz.access.role'].with_context(active_test=False)
        cls.Ability = cls.env['biz.access.ability'].with_context(
            active_test=False)
        cls.has_old = 'access.role' in cls.env


@tagged('post_install', '-at_install')
class TestTheVocabulary(CatalogueCase):

    def test_every_ability_it_could_write_is_written(self):
        """Skipped only where the permission itself is not on this database —
        which is a fact about the database, not a gap in the catalogue."""
        for key, _area, _seq, _name, _desc, xmlids in hooks.ABILITIES:
            present = all(self.env.ref(x, raise_if_not_found=False)
                          for x in xmlids)
            found = self.Ability.search_count([('technical_key', '=', key)])
            if present:
                self.assertEqual(found, 1, 'missing ability %s' % key)
            else:
                self.assertEqual(found, 0,
                                 '%s was written for a permission that is not '
                                 'on this database' % key)

    def test_nothing_in_it_reaches_the_keys_to_the_building(self):
        """Rail B, over the REGISTERED catalogue rather than over a list.

        The constraint on the model refuses one being created; this asks the
        other way round — of everything that actually exists — because the
        routes that get past a constraint are data files, imports and raw SQL,
        and none of them is watching.
        """
        for ability in self.Ability.search([]):
            bad = forbidden_in_closure(ability.group_ids, self.env)
            self.assertFalse(
                bad, '"%s" reaches %s' % (ability.name,
                                          ', '.join(bad.mapped('name'))))
        for role in self.Role.search([]):
            bad = forbidden_in_closure(role.group_ids, self.env)
            self.assertFalse(
                bad, '"%s" reaches %s' % (role.name,
                                          ', '.join(bad.mapped('name'))))

    def test_a_deliberately_bad_ability_is_refused(self):
        wrapper = self.env['res.groups'].create({
            'name': 'HA test wrapper',
            'implied_ids': [(4, self.env.ref('base.group_system').id)]})
        with self.assertRaises(ValidationError):
            self.Ability.create({
                'technical_key': 'ha-test-bad', 'name': 'HA bad',
                'group_ids': [(6, 0, wrapper.ids)]})

    def test_every_area_a_role_sits_in_is_one_of_the_clinics(self):
        keys = {key for key, _label in hooks.AREAS}
        for role in self.Role.search([]):
            self.assertIn(role.area, keys)


@tagged('post_install', '-at_install')
class TestTheRoles(CatalogueCase):

    def test_all_nine_are_written_down_with_a_fixed_name(self):
        for name, key in hooks.ROLE_XMLIDS.items():
            role = self.env.ref('health_access.%s' % key,
                                raise_if_not_found=False)
            self.assertTrue(role, 'no fixed name for the "%s" role' % name)
            self.assertEqual(role.name, name)

    def test_the_bundle_carries_exactly_what_the_old_role_carried(self):
        """EXACT, permission for permission. The whole carry-over is this."""
        if not self.has_old:
            self.skipTest('the previous access application is not installed')
        for old in self.env['access.role'].with_context(
                active_test=False).search([]):
            role = hooks.role_by_name(self.env, old.name or '')
            self.assertTrue(role, 'no bundle for "%s"' % old.name)
            self.assertEqual(
                set(role.group_ids.ids), set(old.groups_ids.ids),
                'the "%s" bundle is not what the old role carried' % old.name)

    def test_the_role_of_nothing_but_signing_in_is_put_away(self):
        """A role every colleague holds would open every entry it is put on to
        every colleague, which is the opposite of a gate."""
        banker = hooks.role_by_name(self.env, 'Banker')
        if not banker:
            self.skipTest('this database has no Banker role')
        self.assertFalse(banker.active)

    def test_a_permission_with_no_ability_stops_the_carry_over(self):
        """It REFUSES rather than writing a smaller role, and it names what is
        missing so somebody can fix it in one go."""
        if not self.has_old:
            self.skipTest('the previous access application is not installed')
        stray = self.env['res.groups'].create({'name': 'HA stray permission'})
        self.env['access.role'].create({
            'name': 'HA throwaway role',
            'groups_ids': [(6, 0, stray.ids)]})
        with self.assertRaises(UserError) as caught:
            hooks._carry_roles(self.env)
        self.assertIn('HA stray permission', str(caught.exception))


@tagged('post_install', '-at_install')
class TestTheHolders(CatalogueCase):

    def test_everybody_keeps_what_they_had(self):
        """After the carry-over, somebody with an old role holds the bundle of
        the same name IN FULL — which is what the board, the rail and the top
        bar all read."""
        if not self.has_old:
            self.skipTest('the previous access application is not installed')
        users = self.env['res.users'].search(
            [('active', '=', True), ('share', '=', False),
             ('access_role_id', '!=', False)])
        for user in users:
            role = hooks.role_by_name(self.env, user.access_role_id.name or '')
            if not role or not role.group_ids:
                continue
            self.assertTrue(
                set(role.group_ids.ids) <= set(user.all_group_ids.ids),
                '%s does not hold the "%s" bundle in full'
                % (user.login, role.name))

    def test_the_history_says_how_anybody_who_gained_something_got_it(self):
        rows = self.env['biz.access.delegation'].sudo().search(
            [('reason', '=', hooks.CARRY_REASON)])
        for row in rows:
            self.assertTrue(row.applied_group_ids,
                            'a carry-over row that recorded no change')
            self.assertEqual(row.origin, 'board')
