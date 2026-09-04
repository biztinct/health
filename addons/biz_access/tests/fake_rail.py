# -*- coding: utf-8 -*-
"""A left menu, in memory, for the tests to gate and re-gate.

WHY THE TESTS NEED ONE AT ALL. This module ships no left menu — a product plugs
its own in through `access_common.register_rail`. So the suites that prove the
Screens lens, the person passport and the role builder all give the SAME answer
need a menu to be right about, and inventing one here is the only honest way to
have it: a test that borrowed whatever menu a database happened to have would
pass or fail on how that database was gated last Tuesday.

AND IT IS BUILT ON `rail_state`, WHICH IS THE POINT.

`visibility_for` below is not a second implementation of the visibility rule
written to agree with the first. It CALLS the rule — the one function in
`access_common` that a real provider will call too — so every no-drift proof in
this suite is a proof about the code the product will run, and the fake's only
job is to hold rows.

The fake is registered in `setUp` and cleared in `addCleanup`, because the
registry is process-wide: a provider left behind by one test class would answer
the next one's questions, and it would answer them about rows that no longer
exist inside a rolled-back transaction.
"""

from odoo.addons.biz_access.models.access_common import (RailProvider,
                                                         rail_state,
                                                         register_areas,
                                                         register_rail)

# =============================================================================
# THE AREAS THESE TESTS GROUP THEIR ROLES UNDER.
#
# The module ships one neutral area and nothing else, exactly as a generic
# module should. A product registers its own words; so does this suite, because
# several tests are about the area being WORKED OUT from what was ticked, and
# that question cannot be asked of a system with only one answer.
#
# Neutral words on purpose: a test fixture that spoke one industry's vocabulary
# would be the first place the next product's port went wrong.
# =============================================================================
TEST_AREAS = [
    ('general', 'General'),
    ('records', 'Records'),
    ('people', 'People'),
    ('money', 'Money'),
]
register_areas(TEST_AREAS, default='general')


class FakeRail(RailProvider):
    """A left menu held in two lists of dicts.

    It is deliberately not a model. A provider is an ADAPTER over whatever the
    product already keeps; making the test's one a model would test a shape no
    product has to have, and would hide the fact that this module never touches
    a menu row directly.
    """

    key = 'fake'

    def __init__(self):
        self.sections_rows = []
        self.entries_rows = []
        self._seq = 0

    # ------------------------------------------------------------- fixtures
    def add_section(self, name, sequence=900, active=True, key=''):
        self._seq += 1
        row = {'id': self._seq, 'name': name, 'sequence': sequence,
               'active': bool(active), 'key': key or 'sec_%s' % self._seq,
               'show_label': True}
        self.sections_rows.append(row)
        return row

    def add_entry(self, section, name, sequence=1, icon='zap', parent=None,
                  groups=None, roles=None, restricted=False, active=True,
                  reason=''):
        """One row of the menu.

        `groups` and `roles` are recordsets or lists of ids, because that is
        what a test has in its hand; they are stored as plain id lists, because
        that is what the protocol says a provider hands over.
        """
        self._seq += 1
        row = {
            'id': self._seq,
            'section_id': section['id'],
            'parent_id': parent['id'] if parent else 0,
            'name': name,
            'icon': icon,
            'sequence': sequence,
            'active': bool(active),
            'group_ids': _ids(groups),
            'restricted': bool(restricted),
            'restriction_reason': reason,
            'role_ids': _ids(roles),
        }
        self.entries_rows.append(row)
        return row

    def _entry(self, entry_id):
        for row in self.entries_rows:
            if row['id'] == int(entry_id):
                return row
        raise AssertionError('no fake menu entry %s' % entry_id)

    # ------------------------------------------------------------------ reads
    def available(self, env):
        return True

    def sections(self, env, include_inactive=False):
        rows = [dict(s) for s in self.sections_rows
                if include_inactive or s['active']]
        return sorted(rows, key=lambda s: (s['sequence'], s['id']))

    def entries(self, env, include_inactive=False):
        rows = [dict(e) for e in self.entries_rows
                if include_inactive or e['active']]
        return sorted(rows, key=lambda e: (e['section_id'], e['sequence'],
                                           e['id']))

    def advanced_action(self, env):
        return ''

    def reload_event(self):
        return 'FAKE_RAIL:RELOAD'

    def visibility_for(self, env, user):
        """THE RULE, ASKED OF THE FUNCTION THAT IS THE RULE.

        A sub-entry is judged on its own gates here — a product whose menu makes
        children inherit their parent's would say so in ITS provider, and this
        one is deliberately the simple case so the tests are about the rule and
        not about an inheritance the module does not own.
        """
        is_admin = user.sudo().has_group('base.group_system')
        held = set(user.sudo().all_group_ids.ids)
        role_groups = {}
        for role in env['biz.access.role'].sudo().search(
                [('active', '=', True)]):
            role_groups[role.id] = set(role.group_ids.ids)

        items = {}
        for entry in self.entries_rows:
            if not entry['active']:
                items[entry['id']] = 'hidden'
                continue
            visible, locked = rail_state(entry, is_admin, held, role_groups)
            items[entry['id']] = (
                'locked' if locked else ('on' if visible else 'hidden'))
        sections = {}
        for section in self.sections_rows:
            sections[section['id']] = 'on' if section['active'] else 'hidden'
        return {'items': items, 'sections': sections}

    # ----------------------------------------------------------------- writes
    def set_roles(self, env, entry_id, role_ids):
        self._entry(entry_id)['role_ids'] = [int(r) for r in role_ids or []]

    def set_active(self, env, entry_id, active):
        self._entry(entry_id)['active'] = bool(active)

    def set_restricted(self, env, entry_id, restricted, reason):
        entry = self._entry(entry_id)
        entry['restricted'] = bool(restricted)
        entry['restriction_reason'] = reason or ''

    def reorder(self, env, section_id, entry_ids):
        """Numbered in TENS, so the next entry somebody adds by hand has
        somewhere to land between two of them without renumbering the block."""
        for index, entry_id in enumerate(entry_ids):
            self._entry(entry_id)['sequence'] = (index + 1) * 10


def _ids(value):
    if not value:
        return []
    if hasattr(value, 'ids'):
        return list(value.ids)
    return [int(v) for v in value]


class FakeRailMixin:
    """`setUp` registers a fake menu; the cleanup takes it away again.

    The registry is process-wide and the transaction is not, so a provider left
    behind would answer the NEXT test class's questions about rows that have
    been rolled back out of existence.
    """

    def use_fake_rail(self):
        rail = FakeRail()
        register_rail(rail)
        self.addCleanup(register_rail, None)
        return rail

    def menu_states(self, user):
        """{label: state} over the menu, drawn as that person sees it.

        Only what they SEE, exactly as a real left menu hands back only what it
        draws — so "not in this dict" is the test's way of saying "not on their
        menu", which is what the original proof asserted.
        """
        seen = self.rail.visibility_for(self.env, user)['items']
        out = {}
        for entry in self.rail.entries_rows:
            state = seen.get(entry['id'], 'hidden')
            if state != 'hidden':
                out[entry['name']] = state
        return out
