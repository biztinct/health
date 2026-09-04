# -*- coding: utf-8 -*-
"""The top bar, decided by the roles somebody holds.

THE ONE THING THIS FILE IS ABOUT is that holding MORE never shows LESS. Every
other property here follows from it, and the day somebody "simplifies" the
intersection into a union it is the test that will say so — because a union
looks perfectly reasonable until the first person is promoted and loses the
screens they had.

The refusals worth pinning, in the order they matter:

  * two roles are reconciled by INTERSECTION, so a second role can only ever
    give screens back;
  * a role with an EMPTY list HIDES NOTHING, and takes the intersection with
    it — the first version of this rule read that as "no opinion" and took 489
    top-bar screens off one real doctor, whose job hides nothing and who happens
    to carry a branch manager's one permission;
  * naming an application hides everything under it, worked out at read time,
    so a screen a module adds tomorrow is hidden with its parent rather than
    left showing;
  * a role somebody holds only PART of has no opinion about them at all;
  * the system administrator is never touched;
  * this SUBTRACTS. A menu the framework already refuses somebody does not come
    back because a role forgot to mention it.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TopBarCase(TransactionCase):
    """A little menu tree of our own, and three roles with opinions about it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Real leaves with a real action: the framework drops a menu that has
        # neither an action nor a visible child, and a test tree it had already
        # dropped would pass whatever this rule did.
        action = cls.env['ir.actions.act_window'].create({
            'name': 'TB people', 'res_model': 'res.partner',
            'view_mode': 'list,form'})
        cls.action_ref = 'ir.actions.act_window,%s' % action.id

        Menu = cls.env['ir.ui.menu']
        cls.app_a = Menu.create({'name': 'TB App A'})
        cls.a_one = Menu.create({'name': 'TB A one', 'parent_id': cls.app_a.id})
        cls.a_two = Menu.create({'name': 'TB A two', 'parent_id': cls.app_a.id,
                                 'action': cls.action_ref})
        cls.a_deep = Menu.create({'name': 'TB A deep',
                                  'parent_id': cls.a_one.id,
                                  'action': cls.action_ref})
        cls.app_b = Menu.create({'name': 'TB App B'})
        cls.b_one = Menu.create({'name': 'TB B one', 'parent_id': cls.app_b.id,
                                 'action': cls.action_ref})

        Group = cls.env['res.groups']
        cls.g_one = Group.create({'name': 'TB permission one'})
        cls.g_two = Group.create({'name': 'TB permission two'})
        #: Held by nobody in this file, on purpose — it is what makes
        #: `role_both` a role that can only ever be PARTLY held here.
        cls.g_three = Group.create({'name': 'TB permission three'})
        #: The permission behind the role that hides nothing.
        cls.g_open = Group.create({'name': 'TB permission open'})

        Ability = cls.env['biz.access.ability']
        cls.ab_one = Ability.create({
            'technical_key': 'tb-one', 'name': 'TB one',
            'group_ids': [(6, 0, cls.g_one.ids)]})
        cls.ab_two = Ability.create({
            'technical_key': 'tb-two', 'name': 'TB two',
            'group_ids': [(6, 0, cls.g_two.ids)]})
        cls.ab_three = Ability.create({
            'technical_key': 'tb-three', 'name': 'TB three',
            'group_ids': [(6, 0, cls.g_three.ids)]})
        cls.ab_open = Ability.create({
            'technical_key': 'tb-open', 'name': 'TB open',
            'group_ids': [(6, 0, cls.g_open.ids)]})

        Role = cls.env['biz.access.role']
        # Hides the whole of App A. Named by the branch head only: the branch is
        # worked out at read time, which is the behaviour under test.
        cls.role_one = Role.create({
            'name': 'TB hides A', 'ability_ids': [(6, 0, cls.ab_one.ids)],
            'hidden_menu_ids': [(6, 0, cls.app_a.ids)]})
        # Hides one leaf of App A and the whole of App B.
        cls.role_two = Role.create({
            'name': 'TB hides A-one and B',
            'ability_ids': [(6, 0, cls.ab_two.ids)],
            'hidden_menu_ids': [(6, 0, (cls.a_one | cls.app_b).ids)]})
        # Hides nothing at all — the job that keeps the whole bar.
        cls.role_open = Role.create({
            'name': 'TB hides nothing',
            'ability_ids': [(6, 0, cls.ab_open.ids)]})
        # Needs a permission nobody in this file holds, so it can only ever be
        # PARTLY held here — which is what makes it a test of "all of it".
        cls.role_both = Role.create({
            'name': 'TB needs both',
            'ability_ids': [(6, 0, (cls.ab_one | cls.ab_three).ids)],
            'hidden_menu_ids': [(6, 0, cls.app_b.ids)]})

        cls.person = cls.env['res.users'].create({
            'name': 'TB person', 'login': 'tb.person@example.test',
            'group_ids': [(4, cls.env.ref('base.group_user').id)]})

    def hidden_for(self, user):
        return set(self.env['ir.ui.menu'].with_user(
            user).sudo()._biz_access_hidden_menu_ids())

    def hold(self, user, *groups):
        ids = []
        for group in groups:
            ids.append((4, group.id))
        user.sudo().write({'group_ids': ids})
        user.invalidate_recordset()
        self.env.registry.clear_cache()


@tagged('post_install', '-at_install')
class TestOneRole(TopBarCase):

    def test_naming_an_application_hides_everything_inside_it(self):
        """The list holds branch HEADS; the branch is worked out on the way out.

        Storing every descendant would be a list that is wrong the day a module
        adds a screen underneath one of them.
        """
        self.hold(self.person, self.g_one)
        hidden = self.hidden_for(self.person)
        for menu in (self.app_a, self.a_one, self.a_two, self.a_deep):
            self.assertIn(menu.id, hidden, menu.name)
        self.assertNotIn(self.app_b.id, hidden)

    def test_a_role_somebody_only_partly_holds_has_no_opinion_about_them(self):
        """Holding a role means holding ALL of it — the same test the roles
        board, the passport and the left menu use.

        `role_both` needs two permissions and hides App B. Somebody with one of
        them is not doing the job its sentence describes, so its opinion about
        the bar is not about them — and App B's fate is decided by the roles
        they DO hold.
        """
        self.hold(self.person, self.g_one)
        self.assertNotIn(self.app_b.id, self.hidden_for(self.person))

    def test_a_role_that_hides_nothing_hides_nothing(self):
        """`role_quiet` is held in full and names no menus, so this person keeps
        the whole bar however much their other roles hide.

        THE REGRESSION THIS PINS. Read as "no opinion" instead, a real doctor on
        a real clinic lost 489 top-bar screens to a role they had never been
        given: their own job hides nothing, and the reading that ignored that
        let the other one decide.
        """
        self.hold(self.person, self.g_two)
        self.assertTrue(self.hidden_for(self.person),
                        'the fixture is not testing anything')
        self.hold(self.person, self.g_open)     # …and now a job that hides none
        self.assertEqual(self.hidden_for(self.person), set())


@tagged('post_install', '-at_install')
class TestTwoRoles(TopBarCase):

    def test_holding_more_never_shows_less(self):
        """THE PROPERTY THIS WHOLE RULE EXISTS TO KEEP.

        One role hides all of App A. The other hides one leaf of it and all of
        App B. Somebody who holds both sees everything either of them leaves
        them — so App A comes BACK apart from the leaf they both hide, and App B
        stays hidden only if both hide it, which they do not.
        """
        self.hold(self.person, self.g_one)
        one_role = self.hidden_for(self.person)
        self.hold(self.person, self.g_two)
        both_roles = self.hidden_for(self.person)

        self.assertTrue(both_roles <= one_role,
                        'a second role took something away')
        # Only what BOTH hide: the A-one leaf and its child.
        self.assertEqual(both_roles, set((self.a_one | self.a_deep).ids))
        self.assertNotIn(self.app_a.id, both_roles)
        self.assertNotIn(self.app_b.id, both_roles)

    def test_an_unheld_role_changes_nothing(self):
        outsider = self.env['res.users'].create({
            'name': 'TB outsider', 'login': 'tb.outsider@example.test',
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.assertEqual(self.hidden_for(outsider), set())


@tagged('post_install', '-at_install')
class TestTheRails(TopBarCase):

    def test_the_system_administrator_is_never_touched(self):
        admin = self.env.ref('base.user_admin')
        self.assertEqual(self.hidden_for(admin), set())

    def test_it_only_ever_subtracts(self):
        """A menu the framework already refuses does not come back."""
        self.hold(self.person, self.g_one)
        Menu = self.env['ir.ui.menu'].with_user(self.person).sudo()
        with_rule = set(Menu._visible_menu_ids(debug=False))
        without = set(Menu.with_context(
            biz_access_no_menu_rule=True)._visible_menu_ids(debug=False))
        self.assertTrue(with_rule <= without)

    def test_the_menu_still_loads(self):
        """The override runs inside `load_menus`, which is cached and which
        every page in the product asks for. It has to come back."""
        self.hold(self.person, self.g_one)
        menus = self.env['ir.ui.menu'].with_user(self.person).sudo().load_menus(
            False)
        self.assertIn('root', menus)
        self.assertNotIn(self.app_a.id, menus)

    def test_changing_what_a_role_hides_is_seen_at_once(self):
        """The answer is cached on the permissions somebody holds, and the
        framework cannot know that a ROLE changed. The role model forgets it."""
        self.hold(self.person, self.g_one)
        self.assertIn(self.app_a.id, self.hidden_for(self.person))
        self.role_one.write({'hidden_menu_ids': [(6, 0, [])]})
        self.assertNotIn(self.app_a.id, self.hidden_for(self.person))
