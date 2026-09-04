# -*- coding: utf-8 -*-
"""The adapter, and the promise it makes to the Access home.

THE PROMISE IS "NO DRIFT". The Screens lens, a person's passport and the real
left menu all have to give the same answer, and the only way to guarantee that
is for there to be one answer. So `visibility_for` is not a second reading of
the rule written to agree with `get_sidebar_data`: it is the same method, and
this file proves it by asking both and comparing, person by person.

The rest is the protocol, kept honest:

  * this menu has no locked preview, and says so in a sentence instead of
    inventing a state it cannot draw;
  * reordering numbers in tens, so the next entry somebody adds by hand has
    somewhere to land;
  * every write hands back the event that makes the real menu re-read itself,
    because a rail still showing the answer the editor beside it has just
    changed is the screen contradicting itself;
  * the entries carry what is WRITTEN, archived roles included, because "is it
    gated at all" and "who gets through" are different questions.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import rail_provider
from odoo.addons.health_access.models.cms_sidebar import RELOAD_EVENT


@tagged('post_install', '-at_install')
class ProviderCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rail = cls.env['biz.access.rail']
        cls.Item = cls.env['cms.sidebar.item']
        cls.section = cls.env['cms.sidebar.section'].create({
            'name': 'PR block', 'technical_key': 'pr_block', 'sequence': 991})
        group = cls.env['res.groups'].create({'name': 'PR permission'})
        ability = cls.env['biz.access.ability'].create({
            'technical_key': 'pr-thing', 'name': 'PR thing',
            'group_ids': [(6, 0, group.ids)]})
        cls.bundle = cls.env['biz.access.role'].create({
            'name': 'PR bundle', 'ability_ids': [(6, 0, ability.ids)]})
        cls.holder = cls.env['res.users'].create({
            'name': 'PR holder', 'login': 'pr.holder@example.test',
            'group_ids': [(4, cls.env.ref('base.group_user').id),
                          (4, group.id)]})
        cls.stranger = cls.env['res.users'].create({
            'name': 'PR stranger', 'login': 'pr.stranger@example.test',
            'group_ids': [(4, cls.env.ref('base.group_user').id)]})


@tagged('post_install', '-at_install')
class TestItIsRegisteredAndDescribesThisMenu(ProviderCase):

    def test_this_clinic_has_a_left_menu_and_the_home_can_see_it(self):
        provider = rail_provider()
        self.assertTrue(provider, 'no left menu is registered')
        self.assertEqual(provider.key, 'cms_sidebar')
        self.assertTrue(self.rail.available())

    def test_the_blocks_and_the_rows_come_across(self):
        self.assertTrue(self.rail.sections())
        self.assertTrue(self.rail.entries())
        for row in self.rail.sections():
            self.assertIn('role_ids', row)
        for row in self.rail.entries():
            for key in ('id', 'section_id', 'parent_id', 'name', 'icon',
                        'sequence', 'active', 'group_ids', 'restricted',
                        'role_ids', 'legacy_note'):
                self.assertIn(key, row)

    def test_it_names_the_plain_table_and_the_reload_event(self):
        self.assertEqual(self.rail.reload_event(), RELOAD_EVENT)
        self.assertTrue(self.rail.advanced_action())
        self.assertTrue(self.env.ref(self.rail.advanced_action(),
                                     raise_if_not_found=False))

    def test_what_is_written_comes_across_archived_roles_included(self):
        item = self.Item.create({
            'name': 'PR archived-gate row', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.bundle.write({'active': False})
        row = next(r for r in self.rail.entries(include_inactive=True)
                   if r['id'] == item.id)
        self.assertEqual(row['role_ids'], self.bundle.ids)


@tagged('post_install', '-at_install')
class TestNoDrift(ProviderCase):

    def drawn(self, user):
        out = set()
        for section in self.Item.with_user(user).sudo().get_sidebar_data():
            for item in section.get('items') or []:
                out.add(item['id'])
                for kid in item.get('children') or []:
                    out.add(kid['id'])
        return out

    def test_the_home_draws_exactly_what_the_menu_draws(self):
        self.Item.create({
            'name': 'PR gated row', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.Item.create({'name': 'PR open row',
                          'section_id': self.section.id})
        for user in (self.holder, self.stranger, self.env.ref(
                'base.user_admin')):
            drawn = self.drawn(user)
            seen = self.rail.visibility_for(user)['items']
            on = {i for i, state in seen.items() if state == 'on'}
            self.assertEqual(
                on, drawn,
                'the Access home and the real menu disagree about %s'
                % user.login)


@tagged('post_install', '-at_install')
class TestTheWrites(ProviderCase):

    def setUp(self):
        super().setUp()
        self.item = self.Item.create({
            'name': 'PR editable row', 'section_id': self.section.id})
        self.keeper = self.env['res.users'].create({
            'name': 'PR keeper', 'login': 'pr.keeper@example.test',
            'group_ids': [
                (4, self.env.ref('base.group_user').id),
                (4, self.env.ref('biz_access.group_access_manager').id)]})
        self.facade = self.env['biz.access'].with_user(self.keeper)

    def test_setting_a_gate_writes_the_new_lane_and_asks_for_a_reload(self):
        res = self.facade.set_screen_roles(self.item.id, self.bundle.ids)
        self.assertTrue(res['ok'])
        self.assertEqual(res['reload_event'], RELOAD_EVENT)
        self.item.invalidate_recordset()
        self.assertEqual(self.item.biz_role_ids.ids, self.bundle.ids)

    def test_the_older_lane_is_never_written_from_this_screen(self):
        """Taking a role off a gate the lens does not draw would take a door
        away from people it never showed."""
        if 'role_ids' not in self.item._fields:
            self.skipTest('this database has no older lane')
        before = self.item.role_ids.ids
        self.facade.set_screen_roles(self.item.id, self.bundle.ids)
        self.item.invalidate_recordset()
        self.assertEqual(self.item.role_ids.ids, before)

    def test_there_is_no_locked_preview_and_it_says_so(self):
        with self.assertRaises(UserError) as caught:
            self.facade.set_screen_flags(self.item.id, restricted=True)
        self.assertIn('shown or hidden', str(caught.exception))

    def test_reordering_numbers_in_tens(self):
        second = self.Item.create({
            'name': 'PR second row', 'section_id': self.section.id})
        self.facade.reorder_screens(self.section.id,
                                    [second.id, self.item.id])
        second.invalidate_recordset()
        self.item.invalidate_recordset()
        self.assertEqual(second.sequence, 10)
        self.assertEqual(self.item.sequence, 20)

    def test_switching_an_entry_off_and_back_on(self):
        self.facade.set_screen_flags(self.item.id, active=False)
        self.item.invalidate_recordset()
        self.assertFalse(self.item.active)
        self.facade.set_screen_flags(self.item.id, active=True)
        self.item.invalidate_recordset()
        self.assertTrue(self.item.active)


@tagged('post_install', '-at_install')
class TestTheOlderGateIsShownAsContext(ProviderCase):

    def setUp(self):
        super().setUp()
        if 'access.role' not in self.env:
            self.skipTest('the previous access application is not installed')

    def test_a_gate_only_the_older_lane_names_is_reported_quietly(self):
        old = self.env['access.role'].create({
            'name': 'PR older role',
            'groups_ids': [(6, 0, self.env.ref('base.group_user').ids)]})
        item = self.Item.create({
            'name': 'PR one-lane row', 'section_id': self.section.id,
            'role_ids': [(6, 0, old.ids)]})
        row = next(r for r in self.rail.entries() if r['id'] == item.id)
        self.assertIn('PR older role', row['legacy_note'])

    def test_when_the_two_agree_there_is_nothing_to_say(self):
        old = self.env['access.role'].create({
            'name': 'PR bundle',            # the same name as the bundle
            'groups_ids': [(6, 0, self.env.ref('base.group_user').ids)]})
        item = self.Item.create({
            'name': 'PR two-lane row', 'section_id': self.section.id,
            'role_ids': [(6, 0, old.ids)],
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        row = next(r for r in self.rail.entries() if r['id'] == item.id)
        self.assertEqual(row['legacy_note'], '')


@tagged('post_install', '-at_install')
class TestTheMenuMethodKeepsItsMarker(ProviderCase):
    """`get_sidebar_data` is called from the browser and MUST stay `@api.model`.

    A method the web client calls by name on a model rather than on a record is
    an `@api.model` method, and the decorator is the only thing that says so. It
    has been lost to a refactor before — on a surface where the failure is not a
    traceback in a test but an empty left menu for everybody, which is why it is
    pinned here rather than trusted to review.
    """

    def test_get_sidebar_data_is_still_a_model_method(self):
        method = type(self.Item).get_sidebar_data
        self.assertTrue(getattr(method, '_api', None) == 'model'
                        or getattr(method, '_api_model', False),
                        'get_sidebar_data has lost its @api.model marker')

    def test_the_browser_can_still_call_it_without_a_record(self):
        """The proof that matters, whatever the marker is spelled as."""
        self.assertIsInstance(
            self.env['cms.sidebar.item'].get_sidebar_data(), list)
