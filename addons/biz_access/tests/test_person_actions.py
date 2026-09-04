# -*- coding: utf-8 -*-
"""The doors a product adds to the People lens, and the door they go through.

THE SLOTS ARE EMPTY HERE, ON PURPOSE. This module knows nothing about staff
records or joining dates, so a database with only it installed draws no extra
buttons — which is the honest screen and also the proof that the seam is a seam.

WHAT IS PINNED IS THE DISPATCHER, because it is the part that has to be right
however a product fills the slots:

  * the gate is asked on DISPATCH, not on drawing — a button that was never
    drawn is still refused if somebody calls for it;
  * an id that is not on THIS person's list is refused for THIS person, so an
    action offered on one passport cannot be pointed at another;
  * whatever arrives as an id reaches `getattr` as a plain word or not at all.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PersonActionCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.access = cls.env['biz.access']
        cls.internal = cls.env.ref('base.group_user')
        cls.manager_group = cls.env.ref('biz_access.group_access_manager')
        cls.someone = cls.env['res.users'].create({
            'name': 'PA someone', 'login': 'pa.someone@example.test',
            'group_ids': [(4, cls.internal.id)]})
        cls.keeper = cls.env['res.users'].create({
            'name': 'PA keeper', 'login': 'pa.keeper@example.test',
            'group_ids': [(4, cls.internal.id), (4, cls.manager_group.id)]})


@tagged('post_install', '-at_install')
class TestTheSlotsAreWellFormedWhoeverFillsThem(PersonActionCase):
    """Properties, never counts.

    Two tests in the suite this was ported from asserted a NUMBER that was only
    right on one database, and both broke the first time real data arrived. What
    is true on every database is the SHAPE: the slots answer with lists, every
    row carries what the browser needs to draw it, and every row's id is one the
    dispatcher will accept. A product that fills them and one that does not both
    satisfy that, and neither can satisfy it by accident.
    """

    def test_both_slots_answer_with_a_list(self):
        facade = self.access.with_user(self.keeper)
        self.assertIsInstance(facade.people_actions(), list)
        self.assertIsInstance(facade.person_actions(self.someone.id), list)

    def test_every_header_door_can_be_drawn_and_opened(self):
        for row in self.access.with_user(self.keeper).people_actions():
            self.assertTrue(row.get('id'))
            self.assertTrue(row.get('label'))
            self.assertTrue(row.get('action_xmlid'),
                            'a header door with nothing to open')
            self.assertTrue(
                self.env.ref(row['action_xmlid'], raise_if_not_found=False),
                'a header door pointing at a screen that is not here')

    def test_every_passport_door_dispatches_to_something(self):
        facade = self.access.with_user(self.keeper)
        for row in facade.person_actions(self.someone.id):
            self.assertTrue(row.get('id'))
            self.assertTrue(row.get('label'))
            key = facade._person_action_key(row['id'])
            self.assertTrue(key, 'an id the dispatcher would refuse')
            self.assertTrue(
                hasattr(facade, '_person_action_%s' % key),
                'a door offered with nothing behind it: %s' % row['id'])

    def test_a_passport_carries_the_list_so_the_header_can_draw_it(self):
        passport = self.access.with_user(self.keeper).passport(self.someone.id)
        self.assertIn('actions', passport)
        self.assertIsInstance(passport['actions'], list)

    def test_the_board_carries_the_header_doors(self):
        board = self.access.with_user(self.keeper).get_board()
        self.assertIn('people_actions', board)
        self.assertIsInstance(board['people_actions'], list)

    def test_somebody_who_cannot_manage_is_offered_nothing(self):
        facade = self.access.with_user(self.someone)
        self.assertEqual(facade.people_actions(), [])
        self.assertEqual(facade.person_actions(self.someone.id), [])


@tagged('post_install', '-at_install')
class TestTheDispatcherRefuses(PersonActionCase):

    def test_somebody_outside_the_access_team_is_refused(self):
        """Asked on DISPATCH. A button that was never drawn is not a rule."""
        with self.assertRaises(AccessError):
            self.access.with_user(self.someone).run_person_action(
                'deactivate', self.keeper.id)

    def test_an_action_nothing_offers_is_refused_in_words(self):
        """A name no product will ever use, so this is about the DISPATCHER
        rather than about which overlay happens to be on this database."""
        with self.assertRaises(UserError):
            self.access.with_user(self.keeper).run_person_action(
                'no_such_door', self.someone.id)

    def test_an_id_that_is_not_a_plain_word_never_reaches_a_lookup(self):
        facade = self.access.with_user(self.keeper)
        self.assertEqual(facade._person_action_key('open-staff'), 'open_staff')
        self.assertEqual(facade._person_action_key('  Deactivate '),
                         'deactivate')
        for bad in ('../../etc', 'a b', 'x;y', '', None, 'get_board()'):
            self.assertEqual(facade._person_action_key(bad), '',
                             'a lookup would have been attempted for %r' % bad)

    def test_only_people_with_a_login_can_be_acted_on(self):
        portal = self.env['res.users'].create({
            'name': 'PA portal', 'login': 'pa.portal@example.test',
            'group_ids': [(4, self.env.ref('base.group_portal').id)]})
        with self.assertRaises(UserError):
            self.access.with_user(self.keeper).run_person_action(
                'open_staff', portal.id)
