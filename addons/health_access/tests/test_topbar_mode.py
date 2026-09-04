# -*- coding: utf-8 -*-
"""The bar above the screen, in administrator-only mode.

WHAT IS BEING PROVED. In this mode a colleague keeps exactly one entry above
their left menu — the home the product names — and the person who owns the box
keeps everything. And the floor under it: NOBODY is ever left with a blank bar,
whatever the setting says or fails to say. A tidy shell is worth having; a
colleague signing in to a screen with no way out never is.

The by-role mode is still the generic default and is still tested in
`biz_access`; the last case here checks that switching back restores it, so the
mode is a switch rather than a one-way door.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TopBarModeCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Menu = cls.env['ir.ui.menu']
        cls.Param = cls.env['ir.config_parameter'].sudo()
        cls.internal = cls.env.ref('base.group_user')
        cls.nurse = cls.env['res.users'].create({
            'name': 'TB nurse', 'login': 'tb.nurse@example.test',
            'group_ids': [(4, cls.internal.id)]})
        cls.admin = cls.env['res.users'].create({
            'name': 'TB administrator', 'login': 'tb.admin@example.test',
            'group_ids': [(4, cls.internal.id),
                          (4, cls.env.ref('base.group_system').id)]})
        cls.home = cls.env.ref('health_cms_sidebar.menu_cms_root',
                               raise_if_not_found=False)

    def setUp(self):
        super().setUp()
        self.env.registry.clear_cache()

    def _set(self, mode, homes):
        self.Param.set_param('biz_access.topbar_mode', mode)
        self.Param.set_param('biz_access.topbar_home_xmlids', homes)
        self.env.registry.clear_cache()

    def _visible(self, user):
        return set(self.Menu.with_user(user).sudo()._visible_menu_ids(
            debug=False))


@tagged('post_install', '-at_install')
class TestAdministratorOnly(TopBarModeCase):

    def test_a_colleague_keeps_the_home_and_nothing_else(self):
        if not self.home:
            self.skipTest('this database has no left-menu root')
        self._set('admin_only', 'health_cms_sidebar.menu_cms_root')
        seen = self._visible(self.nurse)
        self.assertEqual(seen, {self.home.id})

    def test_the_platform_administrator_is_untouched(self):
        if not self.home:
            self.skipTest('this database has no left-menu root')
        self._set('by_role', '')
        before = self._visible(self.admin)
        self._set('admin_only', 'health_cms_sidebar.menu_cms_root')
        self.assertEqual(self._visible(self.admin), before)

    def test_naming_nothing_still_leaves_one_way_in(self):
        """ZERO DEAD ENDS, STATED AS A TEST. An empty setting is a mistake
        somebody will make; the answer is one entry and a warning in the log,
        never a blank screen."""
        self._set('admin_only', '')
        seen = self._visible(self.nurse)
        self.assertEqual(len(seen), 1,
                         'a colleague was left with %s entries' % len(seen))

    def test_naming_an_entry_they_cannot_see_still_leaves_one_way_in(self):
        self._set('admin_only', 'base.menu_administration')
        seen = self._visible(self.nurse)
        self.assertEqual(len(seen), 1)
        self.assertNotIn(self.env.ref('base.menu_administration').id, seen)

    def test_naming_something_that_is_not_a_menu_is_ignored_not_fatal(self):
        self._set('admin_only', 'health_access.role_nurse,not.a.thing')
        seen = self._visible(self.nurse)
        self.assertEqual(len(seen), 1)

    def test_switching_back_restores_the_bar(self):
        """A switch, not a one-way door."""
        self._set('admin_only', 'health_cms_sidebar.menu_cms_root')
        narrow = self._visible(self.nurse)
        self._set('by_role', '')
        wide = self._visible(self.nurse)
        self.assertGreater(len(wide), len(narrow))

    def test_writing_the_setting_forgets_the_old_answer(self):
        """The framework clears the menu cache when a MENU changes; it cannot
        know about these two rows, so they clear it themselves."""
        self._set('by_role', '')
        wide = self._visible(self.nurse)
        # No explicit cache clear this time: the write itself must do it.
        self.Param.set_param('biz_access.topbar_mode', 'admin_only')
        self.Param.set_param('biz_access.topbar_home_xmlids',
                             'health_cms_sidebar.menu_cms_root')
        self.assertLess(len(self._visible(self.nurse)), len(wide))


@tagged('post_install', '-at_install')
class TestTheProductShipsItOn(TopBarModeCase):

    def test_this_clinic_runs_in_administrator_only_mode(self):
        """The decision, asserted where somebody would look for it."""
        mode = self.env['ir.ui.menu']._biz_access_topbar_mode()
        self.assertEqual(mode, 'admin_only')

    def test_and_the_role_form_says_its_list_is_not_being_used(self):
        role = self.env['biz.access.role'].search([], limit=1)
        if not role:
            self.skipTest('this database has no roles')
        self.assertTrue(role.topbar_inert)
