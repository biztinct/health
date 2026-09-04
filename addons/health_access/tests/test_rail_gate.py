# -*- coding: utf-8 -*-
"""One gate on the left menu, and what it opens.

THIS FILE USED TO BE ABOUT TWO GATES. While the previous access application was
still installed the menu was read as an OR of its list and this one, so that
nothing could be lost while the first was carried into the second. That is done;
there is one list now, and these are the properties it has to have:

  * an entry gated to a role opens for somebody who holds that role IN FULL and
    for nobody else;
  * holding PART of a role is not holding it — a bundle is a job, not a
    shopping list;
  * an archived role opens nothing, and an entry gated only on archived roles is
    HIDDEN rather than open to everybody — the failure mode that would turn a
    tidy-up into a leak;
  * an entry with no gate anywhere above it is open to everybody with a login;
  * a gate on a block flows down, a gate on a parent entry flows down, and a
    child under a hidden parent is not drawn at all;
  * the Access home draws EXACTLY what the menu draws, because both ask the
    same method.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class RailGateCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Item = cls.env['cms.sidebar.item']
        cls.Section = cls.env['cms.sidebar.section']
        cls.internal = cls.env.ref('base.group_user')

        cls.section = cls.Section.create({
            'name': 'RL block', 'technical_key': 'rl_block', 'sequence': 990})

        group = cls.env['res.groups'].create({'name': 'RL permission'})
        ability = cls.env['biz.access.ability'].create({
            'technical_key': 'rl-thing', 'name': 'RL thing',
            'group_ids': [(6, 0, group.ids)]})
        cls.bundle = cls.env['biz.access.role'].create({
            'name': 'RL bundle', 'ability_ids': [(6, 0, ability.ids)]})
        cls.group = group

        cls.holder = cls.env['res.users'].create({
            'name': 'RL holder', 'login': 'rl.holder@example.test',
            'group_ids': [(4, cls.internal.id), (4, group.id)]})
        cls.stranger = cls.env['res.users'].create({
            'name': 'RL stranger', 'login': 'rl.stranger@example.test',
            'group_ids': [(4, cls.internal.id)]})

    def drawn_for(self, user, ungated_only=False):
        """The entries this person is actually DRAWN, by name."""
        Item = self.Item.with_user(user).sudo()
        if ungated_only:
            Item = Item.with_context(health_access_no_biz_lane=True)
        out = set()
        for section in Item.get_sidebar_data() or []:
            for item in section.get('items') or []:
                out.add(item['name'])
                for kid in item.get('children') or []:
                    out.add(kid['name'])
        return out


@tagged('post_install', '-at_install')
class TestTheGate(RailGateCase):

    def test_an_entry_gated_to_a_role_opens_for_a_holder(self):
        self.Item.create({
            'name': 'RL gated entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.assertIn('RL gated entry', self.drawn_for(self.holder))
        self.assertNotIn('RL gated entry', self.drawn_for(self.stranger))

    def test_holding_part_of_a_role_is_not_holding_it(self):
        """A bundle is a job, not a shopping list."""
        other = self.env['res.groups'].create({'name': 'RL other permission'})
        extra = self.env['biz.access.ability'].create({
            'technical_key': 'rl-other', 'name': 'RL other',
            'group_ids': [(6, 0, other.ids)]})
        self.bundle.write({'ability_ids': [(4, extra.id)]})
        self.Item.create({
            'name': 'RL two-part entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.assertNotIn('RL two-part entry', self.drawn_for(self.holder))

    def test_an_archived_role_opens_nothing_and_does_not_open_everything(self):
        """THE FAILURE MODE THIS GUARDS. "No gate at all" means open to
        everybody; if archiving the last role on an entry counted as no gate,
        putting a role away would hand its screens to the whole clinic."""
        item = self.Item.create({
            'name': 'RL archived-gate entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.bundle.write({'active': False})
        item.invalidate_recordset()
        self.assertNotIn('RL archived-gate entry', self.drawn_for(self.holder))
        self.assertNotIn('RL archived-gate entry',
                         self.drawn_for(self.stranger))

    def test_an_ungated_entry_is_open_to_everybody(self):
        self.Item.create({'name': 'RL open entry',
                          'section_id': self.section.id})
        self.assertIn('RL open entry', self.drawn_for(self.stranger))

    def test_get_sidebar_data_keeps_its_model_marker(self):
        """F46: `@api.model` is not inherited, and an override that drops it
        turns a call the browser makes into a call that needs a record."""
        method = type(self.env['cms.sidebar.item']).get_sidebar_data
        self.assertTrue(getattr(method, '_api_model', False)
                        or getattr(method, '_api', None) == 'model',
                        'get_sidebar_data lost its @api.model marker')


@tagged('post_install', '-at_install')
class TestInheritance(RailGateCase):

    def test_a_gate_on_the_block_flows_down(self):
        self.section.write({'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.Item.create({'name': 'RL inherited entry',
                          'section_id': self.section.id})
        self.assertIn('RL inherited entry', self.drawn_for(self.holder))
        self.assertNotIn('RL inherited entry', self.drawn_for(self.stranger))

    def test_a_gate_on_a_parent_flows_down(self):
        parent = self.Item.create({
            'name': 'RL parent', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.Item.create({
            'name': 'RL child', 'section_id': self.section.id,
            'parent_id': parent.id})
        self.assertIn('RL child', self.drawn_for(self.holder))
        self.assertNotIn('RL child', self.drawn_for(self.stranger))

    def test_an_entry_widens_what_its_block_allows(self):
        """The union, never an override: a leaf can name a role of its own and
        keep the people who own the block."""
        second = self.env['res.groups'].create({'name': 'RL second permission'})
        ability = self.env['biz.access.ability'].create({
            'technical_key': 'rl-second', 'name': 'RL second',
            'group_ids': [(6, 0, second.ids)]})
        other_bundle = self.env['biz.access.role'].create({
            'name': 'RL second bundle', 'ability_ids': [(6, 0, ability.ids)]})
        self.section.write({'biz_role_ids': [(6, 0, self.bundle.ids)]})
        item = self.Item.create({
            'name': 'RL widened entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, other_bundle.ids)]})
        self.assertEqual(set(item.effective_biz_role_ids.ids),
                         set((self.bundle | other_bundle).ids))
        self.assertIn('RL widened entry', self.drawn_for(self.holder))

    def test_a_child_under_a_hidden_parent_is_not_drawn(self):
        """The menu gathers children under VISIBLE parents, so a child under a
        hidden one is not drawn at all — and the Access home has to say the same
        thing, or a passport would show somebody a screen they cannot reach.

        Both surfaces are asked here, about the same person, and compared. That
        is the only assertion worth making about it: the numbers agreeing is not
        the point, the two answers being the same code is.
        """
        parent = self.Item.create({
            'name': 'RL hidden parent', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        child = self.Item.create({'name': 'RL orphan child',
                                  'section_id': self.section.id,
                                  'parent_id': parent.id})
        self.assertNotIn('RL orphan child', self.drawn_for(self.stranger))
        seen = self.env['biz.access.rail'].visibility_for(self.stranger)
        self.assertEqual(seen['items'].get(child.id), 'hidden')


@tagged('post_install', '-at_install')
class TestTheAdminIsNotEverybody(RailGateCase):

    def test_only_the_platform_administrator_sees_past_every_gate(self):
        """The previous access application's admin privilege used to open the
        whole menu too. It has gone with that application, deliberately: seven
        people held it and two of them were not owners, and they now see the
        menu their own roles open — which is what everybody else has always
        seen. Constructed with a throwaway permission so the assertion does not
        depend on that group still existing."""
        throwaway = self.env['res.groups'].create({'name': 'RL ex-admin'})
        pretender = self.env['res.users'].create({
            'name': 'RL pretender', 'login': 'rl.pretender@example.test',
            'group_ids': [(4, self.internal.id), (4, throwaway.id)]})
        self.Item.create({
            'name': 'RL admin-only entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.assertNotIn('RL admin-only entry', self.drawn_for(pretender))

    def test_the_access_home_entry_is_gated_once_the_module_has_landed(self):
        """The data file ships it ungated because a `ref()` cannot point at a
        role that does not exist yet; the hook writes the gate afterwards."""
        item = self.env.ref('health_access.item_admin_access',
                            raise_if_not_found=False)
        if not item:
            self.skipTest('this database has no Access home entry')
        self.assertTrue(item.biz_role_ids,
                        'the Access home entry is open to everybody')
        self.assertEqual(
            set(item.biz_role_ids.mapped('name')), {'Owner', 'Admin'})
