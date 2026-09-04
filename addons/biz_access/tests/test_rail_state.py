# -*- coding: utf-8 -*-
"""`rail_state` — the whole visibility rule, tested on its own.

WHY THIS IS A UNIT TEST AND NOT PART OF THE LENS SUITES. The rule is the one
piece of this module that several surfaces, a product's provider and the real
left menu all have to agree about. Everywhere else it is exercised THROUGH
something — a lens, a passport, a miniature — and a test that reaches it that way
proves the surface as much as the rule. Here it is a pure function of four
arguments, so every branch can be stated in one line, and a change to any of
them fails HERE first, in the only file that names the branch by its own words.

The failure mode this guards against is never a blank screen. It is a gate that
quietly opens: an OR where the role lane needs an AND, an archived role treated
as no gate at all, a teaser reported as hidden. Each of those shows a screen
somebody was not meant to reach, and shows it confidently.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import rail_state


def _entry(groups=(), roles=(), restricted=False):
    """One row of a left menu, in the shape a provider hands over."""
    return {'id': 1, 'group_ids': list(groups), 'role_ids': list(roles),
            'restricted': restricted}


@tagged('post_install', '-at_install')
class TestTheRule(TransactionCase):

    # -------------------------------------------------- nothing written on it
    def test_an_entry_with_no_gate_at_all_is_open_to_everybody(self):
        self.assertEqual(rail_state(_entry(), False, set(), {}), (True, False))

    def test_and_it_is_open_even_to_somebody_holding_nothing(self):
        self.assertEqual(
            rail_state(_entry(), False, set(), {1: {10}}), (True, False))

    # ------------------------------------------------------------- the admin
    def test_an_administrator_gets_through_every_gate(self):
        """`base.group_system` short-circuits the real menu, so it has to
        short-circuit this too — or a passport would show an administrator a
        menu their colleague does not have."""
        entry = _entry(groups=[10], roles=[1], restricted=True)
        self.assertEqual(rail_state(entry, True, set(), {}), (True, False))

    # --------------------------------------------------- the permission lane
    def test_the_permission_lane_needs_any_one_of_them(self):
        entry = _entry(groups=[10, 11])
        self.assertEqual(rail_state(entry, False, {11}, {}), (True, False))

    def test_and_holding_none_of_them_is_not_enough(self):
        entry = _entry(groups=[10, 11])
        self.assertEqual(rail_state(entry, False, {12}, {}), (False, False))

    # --------------------------------------------------------- the role lane
    def test_the_role_lane_needs_all_of_the_bundle(self):
        """A ROLE IS A JOB, NOT A SHOPPING LIST. This is the assertion that
        matters most in the file: an OR here instead of an AND would make every
        role-gated entry on every menu quietly wider than its sentence
        promises, and nothing on any screen would look wrong."""
        entry = _entry(roles=[7])
        role_groups = {7: {10, 11}}
        self.assertEqual(
            rail_state(entry, False, {10, 11}, role_groups), (True, False))
        self.assertEqual(
            rail_state(entry, False, {10}, role_groups), (False, False))

    def test_holding_any_one_of_several_roles_is_enough(self):
        entry = _entry(roles=[7, 8])
        role_groups = {7: {10, 11}, 8: {20}}
        self.assertEqual(
            rail_state(entry, False, {20}, role_groups), (True, False))

    def test_a_role_with_no_permissions_is_held_by_nobody(self):
        """Never by everybody, which is what an empty subset test would say and
        what would turn a half-written role into an open door."""
        entry = _entry(roles=[7])
        self.assertEqual(rail_state(entry, False, set(), {7: set()}),
                         (False, False))
        self.assertEqual(rail_state(entry, False, {10, 11}, {7: set()}),
                         (False, False))

    def test_the_two_lanes_are_an_or(self):
        """Either way in. That is what makes re-gating a live menu safe: nobody
        loses a door on the day the roles arrive."""
        entry = _entry(groups=[99], roles=[7])
        role_groups = {7: {10}}
        self.assertEqual(
            rail_state(entry, False, {99}, role_groups), (True, False))
        self.assertEqual(
            rail_state(entry, False, {10}, role_groups), (True, False))

    # ------------------------------------------------------------ the teaser
    def test_a_teaser_is_shown_locked_and_never_hidden(self):
        entry = _entry(groups=[10], restricted=True)
        self.assertEqual(rail_state(entry, False, set(), {}), (True, True))

    def test_and_somebody_who_can_open_it_sees_it_unlocked(self):
        entry = _entry(groups=[10], restricted=True)
        self.assertEqual(rail_state(entry, False, {10}, {}), (True, False))

    # ----------------------------------------------------- the archived role
    def test_an_archived_role_opens_nothing(self):
        """An archived role is absent from `role_groups`, so nobody gets through
        it — and, crucially, the entry does NOT fall back to "no gate, so
        everybody", because the first branch counts what is WRITTEN. A gate that
        widened when its role was archived would be a gate that fails open."""
        entry = _entry(roles=[7])
        self.assertEqual(rail_state(entry, False, {10, 11}, {}), (False, False))

    def test_an_entry_gated_only_on_an_archived_role_is_reachable_by_an_admin(self):
        """Somebody has to be able to fix it, and the Screens lens names it as
        dead so they know to."""
        entry = _entry(roles=[7])
        self.assertEqual(rail_state(entry, True, set(), {}), (True, False))

    def test_an_archived_role_beside_a_live_one_still_leaves_the_live_lane(self):
        entry = _entry(roles=[7, 8])
        self.assertEqual(
            rail_state(entry, False, {20}, {8: {20}}), (True, False))
