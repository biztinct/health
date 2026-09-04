# -*- coding: utf-8 -*-
"""The Access home on a database that has no left menu at all.

THIS IS THE PROOF THAT THE SEAM IS A SEAM. This module ships no left menu and no
provider for one; a product plugs its own in. So the state this file describes —
nothing registered — is the state the module is INSTALLED in, not a degraded one
to apologise for, and everything about it has to be deliberate:

  * every read answers empty rather than raising;
  * the Screens lens says, in words a person can act on, that there is no left
    menu here yet — never a blank pane and never a traceback;
  * every write refuses with the same sentence, so somebody who reaches one
    through an old bookmark is told why rather than shown a stack trace;
  * the other three lenses are completely unaffected, because they were never
    about a menu.

It also pins the REFUSAL as behaviour. A write that silently did nothing would
report success on a screen where success means "the gate has changed", and that
is the one wrong answer this module cannot afford.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import (rail_provider,
                                                         register_rail)


@tagged('post_install', '-at_install')
class NoRailCase(TransactionCase):
    """No provider, whatever the rest of the suite may have registered."""

    def setUp(self):
        super().setUp()
        previous = rail_provider()
        register_rail(None)
        self.addCleanup(register_rail, previous)
        self.access = self.env['biz.access']
        self.rail = self.env['biz.access.rail']


@tagged('post_install', '-at_install')
class TestTheRailAnswersEmpty(NoRailCase):

    def test_there_is_no_menu_and_it_says_so_rather_than_guessing(self):
        self.assertFalse(self.rail.available())

    def test_every_read_hands_back_nothing(self):
        self.assertEqual(self.rail.sections(), [])
        self.assertEqual(self.rail.entries(), [])
        self.assertEqual(self.rail.sections(include_inactive=True), [])
        self.assertEqual(self.rail.entries(include_inactive=True), [])

    def test_nobody_sees_anything_because_there_is_nothing_to_see(self):
        seen = self.rail.visibility_for(self.env.user)
        self.assertEqual(seen, {'items': {}, 'sections': {}})

    def test_there_is_no_advanced_screen_and_no_reload_event(self):
        """Both are drawn only where they exist. A link to nowhere and an event
        nothing listens for are two ways of shipping a dead control."""
        self.assertEqual(self.rail.advanced_action(), '')
        self.assertFalse(self.rail.reload_event())

    def test_asking_for_one_entry_is_refused_in_words(self):
        with self.assertRaises(UserError):
            self.rail.entry(1)


@tagged('post_install', '-at_install')
class TestEveryWriteRefusesInWords(NoRailCase):
    """A REFUSAL, NEVER A NO-OP. A write that quietly did nothing would report
    success on a screen where success means the gate has changed."""

    def _refusal(self, fn):
        with self.assertRaises(UserError) as caught:
            fn()
        said = str(caught.exception)
        self.assertIn('left menu', said,
                      'the refusal has to name the reason, not just say no')
        return said

    def test_the_rail_itself_refuses_every_write(self):
        self._refusal(lambda: self.rail.set_roles(1, [1]))
        self._refusal(lambda: self.rail.set_active(1, False))
        self._refusal(lambda: self.rail.set_restricted(1, True, ''))
        self._refusal(lambda: self.rail.reorder(1, [1]))

    def test_the_facade_refuses_too_and_writes_nothing(self):
        """The facade looks the entry up first, so it refuses one step earlier —
        which is the same outcome said in the same vocabulary."""
        with self.assertRaises(UserError):
            self.access.set_screen_roles(1, [])
        with self.assertRaises(UserError):
            self.access.set_screen_flags(1, active=False)
        with self.assertRaises(UserError):
            self.access.reorder_screens(1, [1])


@tagged('post_install', '-at_install')
class TestTheHomeStillOpens(NoRailCase):
    """THE HERO OF THE EMPTY STATE. All four lenses answer; two of them have
    nothing to draw and say so; nothing anywhere raises."""

    def test_the_screens_lens_says_why_it_is_empty(self):
        board = self.access.screens_board()
        self.assertEqual(board['sections'], [])
        self.assertFalse(board['any_gated'])
        self.assertEqual(board['counts'],
                         {'entries': 0, 'gated': 0, 'everyone': 0})
        self.assertEqual(board['advanced_action'], '')
        self.assertFalse(board['reload_event'])
        self.assertEqual(board['headline'],
                         'There is no left menu on this system yet.')

    def test_the_passport_draws_an_empty_menu_with_honest_counts(self):
        pack = self.access.passport()
        self.assertEqual(pack['rail'], [])
        self.assertEqual(pack['header']['of_y'], 0)
        self.assertEqual(pack['header']['sees_x'], 0)
        self.assertEqual(pack['header']['locked_n'], 0)
        self.assertFalse(pack['any_gated'])

    def test_the_roles_board_still_counts_and_still_speaks(self):
        board = self.access.get_board()
        self.assertEqual(board['kpis']['entries'], 0)
        self.assertTrue(board['headline'],
                        'an empty board still has to say something')

    def test_the_builder_offers_a_menu_shaped_hole_rather_than_failing(self):
        options = self.access.composer_options()
        self.assertEqual(options['rail'], [])
        self.assertFalse(options['any_gated'])
        preview = self.access.preview_rail([])
        self.assertEqual(preview['sections'], [])
        self.assertEqual(preview['lit'], 0)

    def test_a_role_opens_out_with_an_empty_screens_column(self):
        ability = self.env['biz.access.ability'].create({
            'technical_key': 'zz-norail-ability',
            'name': 'ZZ A throwaway ability',
            'description': 'A throwaway ability for a test.',
            'group_ids': [(6, 0, self.env.ref('base.group_user').ids)],
        })
        role = self.env['biz.access.role'].create({
            'name': 'ZZ No-rail role',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, ability.ids)],
        })
        detail = self.access.role_detail(role.id)
        self.assertEqual(detail['opens'], [])
        self.assertEqual(detail['everyone'], [])
        # Nothing is gated, so the screen's "why is this empty" branch is the
        # honest one: there is no menu, rather than this role opening none of
        # it. Two different sentences, and this is the flag that picks.
        self.assertFalse(detail['any_gated'])
