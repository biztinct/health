# -*- coding: utf-8 -*-
"""Two gates on one menu, read as an OR — and nobody loses a screen.

THE SAFETY ARGUMENT OF THIS WHOLE PHASE IS ONE SENTENCE: the new lane can only
ever ADD. Everything here is that sentence, checked from several directions,
because it is the sentence that lets a live clinic take this change on a
Thursday.

  * a person who could see an entry yesterday can see it today, whatever the
    carry-over did — proved against every real colleague on the database, not
    against three invented ones;
  * an entry gated only on the NEW lane opens for somebody who holds that role
    and for nobody else;
  * an entry gated only on the OLD lane still opens for the person whose old
    role it names, even if nothing has been carried over for them;
  * an archived role opens nothing, and an entry gated only on archived roles
    is HIDDEN rather than open to everybody — the failure mode that would turn
    a tidy-up into a leak;
  * a gate on a block flows down; a gate on a parent entry flows down; and the
    two lanes inherit identically, so an entry's audience never depends on
    which lane somebody happened to use.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class RailLaneCase(TransactionCase):

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

        #: A permission nobody in this file holds. It is what an OLD gate is
        #: written on when a test needs the older lane SHUT so the newer one can
        #: be seen at all — see `shut_on_the_older_lane`.
        cls.unheld = cls.env['res.groups'].create({'name': 'RL unheld'})

        cls.holder = cls.env['res.users'].create({
            'name': 'RL holder', 'login': 'rl.holder@example.test',
            'group_ids': [(4, cls.internal.id), (4, group.id)]})
        cls.stranger = cls.env['res.users'].create({
            'name': 'RL stranger', 'login': 'rl.stranger@example.test',
            'group_ids': [(4, cls.internal.id)]})

    def drawn_for(self, user, legacy_only=False):
        """The entries this person is actually DRAWN, by name."""
        Item = self.Item.with_user(user).sudo()
        if legacy_only:
            Item = Item.with_context(health_access_no_biz_lane=True)
        out = set()
        for section in Item.get_sidebar_data() or []:
            for item in section.get('items') or []:
                out.add(item['name'])
                for kid in item.get('children') or []:
                    out.add(kid['name'])
        return out

    def shut_on_the_older_lane(self, *records):
        """Close the OLDER gate on these rows so the newer one can be seen.

        THIS IS WHAT AN ISOLATED TEST OF THE NEW LANE COSTS WHILE THERE ARE TWO.
        The two lanes are read as an OR, and the older one says "no roles written
        = open to everybody" — so an entry gated ONLY on the newer lane is open
        to the whole clinic, correctly, and no test of the newer lane's REFUSAL
        can mean anything until the older one is shut.

        That is not a workaround. It is the phase's central fact, stated as
        code: nothing this phase writes can narrow anybody's menu. The newer
        lane can only ever be a second way IN, and these tests can only ever
        show it opening a door, never closing one — until the older lane is
        closed first, which is what this does with an old role nobody holds.
        """
        old = self.env['access.role'].create({
            'name': 'RL gate nobody holds',
            'groups_ids': [(6, 0, self.unheld.ids)]})
        for record in records:
            record.write({'role_ids': [(6, 0, old.ids)]})
        return old


@tagged('post_install', '-at_install')
class TestTheNewLane(RailLaneCase):

    def setUp(self):
        super().setUp()
        if 'access.role' not in self.env:
            self.skipTest('the previous access application is not installed')

    def test_an_entry_gated_on_the_new_lane_opens_for_a_holder(self):
        item = self.Item.create({
            'name': 'RL new-lane entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.shut_on_the_older_lane(item)
        self.assertIn('RL new-lane entry', self.drawn_for(self.holder))
        self.assertNotIn('RL new-lane entry', self.drawn_for(self.stranger))

    def test_holding_part_of_a_role_is_not_holding_it(self):
        """A bundle is a job, not a shopping list."""
        other = self.env['res.groups'].create({'name': 'RL other permission'})
        extra = self.env['biz.access.ability'].create({
            'technical_key': 'rl-other', 'name': 'RL other',
            'group_ids': [(6, 0, other.ids)]})
        self.bundle.write({'ability_ids': [(4, extra.id)]})
        item = self.Item.create({
            'name': 'RL two-part entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.shut_on_the_older_lane(item)
        self.assertNotIn('RL two-part entry', self.drawn_for(self.holder))

    def test_an_archived_role_opens_nothing_and_does_not_open_everything(self):
        """THE FAILURE MODE THIS GUARDS. "No gate at all" means open to
        everybody; if archiving the last role on an entry counted as no gate,
        putting a role away would hand its screens to the whole clinic."""
        item = self.Item.create({
            'name': 'RL archived-gate entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.shut_on_the_older_lane(item)
        self.bundle.write({'active': False})
        item.invalidate_recordset()
        self.assertNotIn('RL archived-gate entry', self.drawn_for(self.holder))
        self.assertNotIn('RL archived-gate entry',
                         self.drawn_for(self.stranger))

    def test_an_ungated_entry_is_open_to_everybody(self):
        self.Item.create({'name': 'RL open entry',
                          'section_id': self.section.id})
        self.assertIn('RL open entry', self.drawn_for(self.stranger))

    def test_a_new_lane_gate_alone_takes_nothing_away_from_anybody(self):
        """THE SAFETY PROPERTY, STATED DIRECTLY.

        An entry gated ONLY on the newer lane stays open to everybody, because
        the older lane still says it is ungated. That is what makes this phase
        deployable on a Thursday: writing a gate cannot close a door until
        somebody deliberately closes the older one too.
        """
        self.Item.create({
            'name': 'RL one-lane entry', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        self.assertIn('RL one-lane entry', self.drawn_for(self.stranger))


@tagged('post_install', '-at_install')
class TestInheritance(RailLaneCase):

    def setUp(self):
        super().setUp()
        if 'access.role' not in self.env:
            self.skipTest('the previous access application is not installed')

    def test_a_gate_on_the_block_flows_down(self):
        self.section.write({'biz_role_ids': [(6, 0, self.bundle.ids)]})
        item = self.Item.create({'name': 'RL inherited entry',
                                 'section_id': self.section.id})
        self.shut_on_the_older_lane(item)
        self.assertIn('RL inherited entry', self.drawn_for(self.holder))
        self.assertNotIn('RL inherited entry', self.drawn_for(self.stranger))

    def test_a_gate_on_a_parent_flows_down(self):
        parent = self.Item.create({
            'name': 'RL parent', 'section_id': self.section.id,
            'biz_role_ids': [(6, 0, self.bundle.ids)]})
        child = self.Item.create({
            'name': 'RL child', 'section_id': self.section.id,
            'parent_id': parent.id})
        self.shut_on_the_older_lane(parent, child)
        self.assertIn('RL child', self.drawn_for(self.holder))
        self.assertNotIn('RL child', self.drawn_for(self.stranger))

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
        self.shut_on_the_older_lane(parent, child)
        self.assertNotIn('RL orphan child', self.drawn_for(self.stranger))
        seen = self.env['biz.access.rail'].visibility_for(self.stranger)
        self.assertEqual(seen['items'].get(child.id), 'hidden')


@tagged('post_install', '-at_install')
class TestTheOlderLaneStillWorks(RailLaneCase):

    def setUp(self):
        super().setUp()
        if 'access.role' not in self.env:
            self.skipTest('the previous access application is not installed')

    def test_an_entry_gated_only_on_the_older_lane_still_opens(self):
        """Somebody whose carry-over has not happened keeps their screens."""
        old = self.env['access.role'].create({
            'name': 'RL older role',
            'groups_ids': [(6, 0, self.internal.ids)]})
        self.stranger.sudo().write({'access_role_id': old.id})
        self.Item.create({
            'name': 'RL old-lane entry', 'section_id': self.section.id,
            'role_ids': [(6, 0, old.ids)]})
        self.assertIn('RL old-lane entry', self.drawn_for(self.stranger))
        self.assertNotIn('RL old-lane entry', self.drawn_for(self.holder))

    def test_the_new_lane_only_ever_adds(self):
        """THE SAFETY ARGUMENT, AGAINST EVERY REAL COLLEAGUE ON THIS DATABASE.

        Three invented users prove the rule. The seventy real ones prove the
        clinic — and it is the second that decides whether this can be deployed.
        """
        users = self.env['res.users'].search(
            [('active', '=', True), ('share', '=', False)])
        for user in users:
            before = self.drawn_for(user, legacy_only=True)
            after = self.drawn_for(user)
            lost = before - after
            self.assertFalse(
                lost, '%s lost %s' % (user.login, ', '.join(sorted(lost))))

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
