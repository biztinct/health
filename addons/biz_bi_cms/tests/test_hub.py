# -*- coding: utf-8 -*-
"""biz_bi_cms — the hub payload, the role gate, the group grant, the wiring.

Three of these tests exist because of a defect that was live in the old BI
Home and must not survive into the hub:

* ``test_01`` puts 45 dashboards in one workspace. The old Home fetched a
  single unscoped ``searchRead('bi.dashboard', [], limit=40)`` and then
  filtered client-side, so the workspaces whose dashboards sorted past the
  fortieth row read "No dashboards yet" while holding plenty. A cap is
  invisible on a small database — 45 is deliberately just over it.
* ``test_02`` proves the payload is still built as the CURRENT user: no
  ``sudo()`` anywhere in this module, so the workspace record rules are what
  decide what a user is shown.
* ``test_04`` proves the second half of "a sidebar item is visibility, not
  permission" — a leaf without the BI group is a leaf that opens an empty
  hub.

Fixture note (§5.50 / §5.124): this suite runs against a deployment that
already has four workspaces, nine business roles and its own users. Every
assertion is therefore about the presence or absence of THIS test's own
records, never about an absolute count, and the roles are resolved
get-or-create by name so the fixture binds to the deployment's real rows
where they exist instead of shadowing them with duplicates.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_bi_cms import hooks
from odoo.addons.biz_bi_cms.hooks import (
    ANALYTICS_ROLE_XMLIDS,
    apply_role_gates,
    gated_roles,
)


@tagged('post_install', '-at_install')
class TestAnalyticsHub(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.creator_group = env.ref('biz_bi.group_bi_creator')
        cls.item = env.ref('biz_bi_cms.item_analytics_hub')
        cls.section = env.ref('biz_bi_cms.section_analytics')

        cls.role_gated = cls._role('health_access.role_operations_manager',
                                   'Operations Manager')
        cls.role_ungated = cls._role('health_access.role_nurse', 'Nurse')

        # The gate is (re-)applied here rather than trusted from install: on a
        # database whose roles were created after the module was installed the
        # post_init_hook found nothing to gate, and the whole point of shipping
        # the migration script is that this call is safe to repeat.
        apply_role_gates(env)

        # --- workspaces --------------------------------------------------
        # `open_ws` has no members and no groups, so every BI viewer sees it.
        cls.open_ws = env['bi.workspace'].create({
            'name': 'HUB Open Workspace', 'is_default': False, 'color': 2,
            'icon': 'credit-card', 'description': 'visible to everyone'})
        cls.outsider = cls._user('bihub_outsider', 'HUB Outsider',
                                 groups=cls.creator_group)
        # `restricted_ws` is member-scoped to the outsider ONLY.
        cls.restricted_ws = env['bi.workspace'].create({
            'name': 'HUB Restricted Workspace', 'is_default': False,
            'color': 4, 'icon': 'target',
            'member_ids': [(6, 0, [cls.outsider.id])]})

        cls.open_dashboards = env['bi.dashboard'].create([
            {'name': 'HUB Open Dashboard %02d' % i,
             'description': 'hub fixture %02d' % i,
             'workspace_id': cls.open_ws.id}
            for i in range(45)
        ])
        cls.secret_dashboard = env['bi.dashboard'].create({
            'name': 'HUB Secret Dashboard',
            'workspace_id': cls.restricted_ws.id})

        cls.creator = cls._user('bihub_creator', 'HUB Creator',
                                groups=cls.creator_group)

    # -- fixture helpers -------------------------------------------------
    @classmethod
    def _role(cls, xmlid, name):
        """The deployment's own role where it exists, else a throwaway one.

        Given a PERMISSION of its own when it has to be invented, because
        holding a role is what opens an entry now and a bundle of nothing is
        held by nobody.
        """
        role = cls.env.ref(xmlid, raise_if_not_found=False)
        if role:
            return role
        group = cls.env['res.groups'].create({'name': 'HUB %s permission' % name})
        ability = cls.env['biz.access.ability'].create({
            'technical_key': 'hub-%s' % name.lower().replace(' ', '-'),
            'name': name, 'group_ids': [(6, 0, group.ids)]})
        return cls.env['biz.access.role'].create({
            'name': name, 'ability_ids': [(6, 0, ability.ids)]})

    @classmethod
    def _user(cls, login, name, groups=None, role=None):
        vals = {'name': name, 'login': login, 'password': login + 'x' * 4}
        user = cls.env['res.users'].create(vals)
        links = []
        if groups:
            links.append((4, groups.id))
        if role:
            # HOLDING the role is what a gate reads, so the persona is built by
            # giving them its permissions rather than by pointing a field at it.
            links += [(4, gid) for gid in role.sudo().group_ids.ids]
        if links:
            user.sudo().write({'group_ids': links})
        return user

    @staticmethod
    def _section_keys(sidebar_data):
        return {section.get('key') for section in sidebar_data}

    @staticmethod
    def _item_names(sidebar_data):
        names = set()
        for section in sidebar_data:
            for item in section.get('items', []):
                names.add(item.get('name'))
                for child in item.get('children') or []:
                    names.add(child.get('name'))
        return names

    def _hub(self, user):
        return self.env['bi.workspace'].with_user(user).get_hub_data()

    # ------------------------------------------------------------------
    # T1 — the payload shape, and the 40-limit defect that must be dead
    # ------------------------------------------------------------------
    def test_hub_data_shape(self):
        data = self._hub(self.creator)

        for key in ('workspaces', 'recents', 'is_creator', 'is_modeler',
                    'is_admin', 'ai_available'):
            self.assertIn(key, data, 'get_hub_data must expose %r' % key)

        self.assertTrue(data['is_creator'])
        self.assertIsInstance(data['recents'], list)
        self.assertIsInstance(data['ai_available'], bool)

        by_id = {ws['id']: ws for ws in data['workspaces']}
        for workspace in data['workspaces']:
            self.assertIn('dashboards', workspace,
                          'every workspace entry carries its dashboard list')
            self.assertIsInstance(workspace['dashboards'], list)

        self.assertIn(self.open_ws.id, by_id)
        mine = by_id[self.open_ws.id]
        self.assertEqual(
            len(mine['dashboards']), 45,
            'all 45 dashboards must come back — the old Home capped the '
            'single dashboard read at 40 and the overflow read as '
            '"No dashboards yet"')
        self.assertEqual(
            {row['id'] for row in mine['dashboards']},
            set(self.open_dashboards.ids))
        self.assertEqual(mine['dashboard_count'], 45)
        # sorted by name, and every entry carries what the card renders
        names = [row['name'] for row in mine['dashboards']]
        self.assertEqual(names, sorted(names))
        for row in mine['dashboards']:
            self.assertEqual(set(row), {'id', 'name', 'description'})

    # ------------------------------------------------------------------
    # T2 — the payload is built as the caller; record rules still rule
    # ------------------------------------------------------------------
    def test_hub_data_respects_workspace_rules(self):
        data = self._hub(self.creator)
        ids = {ws['id'] for ws in data['workspaces']}

        self.assertNotIn(
            self.restricted_ws.id, ids,
            'a member-scoped workspace must not reach a non-member — there '
            'is no sudo() in this module and the record rule is the boundary')
        self.assertIn(self.open_ws.id, ids)

        every_dashboard = {row['id']
                           for ws in data['workspaces']
                           for row in ws['dashboards']}
        self.assertNotIn(self.secret_dashboard.id, every_dashboard)

        # ... and the member DOES see it, so the absence above is scoping and
        # not a fixture that never existed.
        member_data = self._hub(self.outsider)
        member_ids = {ws['id'] for ws in member_data['workspaces']}
        self.assertIn(self.restricted_ws.id, member_ids)
        member_dashboards = {row['id']
                             for ws in member_data['workspaces']
                             for row in ws['dashboards']}
        self.assertIn(self.secret_dashboard.id, member_dashboards)

    # ------------------------------------------------------------------
    # T3 — the gate is idempotent, and a missing role never blinds a leaf
    # ------------------------------------------------------------------
    def test_role_gate_idempotent(self):
        apply_role_gates(self.env)
        first = set(self.item.biz_role_ids.ids)
        apply_role_gates(self.env)
        second = set(self.item.biz_role_ids.ids)

        self.assertEqual(first, second)
        self.assertEqual(len(self.item.biz_role_ids), len(first),
                         'the gate must hold no duplicates')

        present = gated_roles(self.env, ANALYTICS_ROLE_XMLIDS)
        self.assertTrue(present, 'fixture guard: at least one gated role')
        self.assertEqual(first, set(present.ids))
        self.assertNotIn(self.role_ungated.id, first)

        # A ROLE_GATES entry naming a role this database does not have is
        # SKIPPED — never written as [(6, 0, [])], which would gate the leaf
        # to nobody and hide the feature from everyone.
        with patch.dict(hooks.ROLE_GATES,
                        {'item_analytics_hub': ('no_such.role_here',)},
                        clear=True):
            gated = apply_role_gates(self.env)
        self.assertEqual(gated, 0)
        self.assertEqual(set(self.item.biz_role_ids.ids), first,
                         'the leaf keeps its previous gate rather than being '
                         'blinded')

    # ------------------------------------------------------------------
    # T4 — the permission behind the entry comes from the ROLE now
    # ------------------------------------------------------------------
    def test_the_permission_comes_from_the_role_rather_than_a_sweep(self):
        """WHAT THIS TEST USED TO BE, AND WHY IT IS SHORTER.

        This module used to hand the reporting permission out itself: a sweep
        at install time, and a per-record hook so new hires did not miss it.
        Both existed because the four roles had to be matched by NAME and there
        was nowhere to write "this role may build reports".

        There is now. "Build reports" is an ability on those four bundles, so
        the permission arrives the way every other permission does — by holding
        a role — and there is nothing left here to sweep. What has to be true
        is that somebody who holds a gated role reaches the reporting group,
        and somebody who does not, does not.
        """
        ability = self.env['biz.access.ability'].sudo().with_context(
            active_test=False).search(
                [('technical_key', '=', 'analytics-build')], limit=1)
        if not ability:
            self.skipTest('the "build reports" ability is not on this database')
        for role in gated_roles(self.env, ANALYTICS_ROLE_XMLIDS):
            with self.subTest(role=role.name):
                self.assertIn(ability, role.ability_ids)
                self.assertIn(self.creator_group, role.group_ids)

        gated_user = self._user('bihub_om', 'HUB Ops Manager',
                                role=self.role_gated)
        ungated_user = self._user('bihub_nurse', 'HUB Nurse',
                                  role=self.role_ungated)
        if self.role_gated in gated_roles(self.env, ANALYTICS_ROLE_XMLIDS):
            self.assertIn(self.creator_group, gated_user.all_group_ids)
        self.assertNotIn(
            self.creator_group, ungated_user.all_group_ids,
            'somebody employed as a nurse must not be handed reporting access')

    # ------------------------------------------------------------------
    # T6 — the AI probe never raises at a creator
    # ------------------------------------------------------------------
    def test_ai_probe_degrades_for_a_creator(self):
        """Found by driving the phase's own CTA, not by reading code.

        ``bi.ai.is_available()`` searched ``bi.ai.provider``, whose ACL starts
        at ``group_bi_modeler``, and ``explore_action.js`` fired it in
        ``onWillStart`` with no ``.catch`` — so a creator-only user opening
        Explore got a raw "You are not allowed to access 'BI AI Provider'"
        modal. Pre-existing in biz_bi, unreachable until this module granted
        the creator group to ten business users.

        AH-3 fixed the cause rather than the symptom: the probe resolves the
        provider under ``sudo`` (biz_bi §4.1), so a creator now gets the
        CONFIGURATION answer — True on a database with a usable provider —
        instead of a permission answer. What this test pins is unchanged in
        substance and is the thing that actually mattered: for a user who
        cannot read one provider row, the probe RETURNS rather than raises,
        and the whole landing survives whatever it returns.
        """
        self.assertFalse(
            self.creator.has_group('biz_bi.group_bi_modeler'),
            'fixture guard: the persona must NOT be able to read the '
            'provider table, or this test proves nothing')
        with self.assertRaises(AccessError):
            self.env['bi.ai.provider'].with_user(self.creator).search([])

        answer = self.env['bi.ai'].with_user(self.creator).is_available()
        self.assertIsInstance(answer, bool)
        self.assertIs(self._hub(self.creator)['ai_available'], answer)

        # ... and this module's defensive override (AH-1 D4) still turns any
        # future AccessError on that path into an honest "no" rather than a
        # modal — it is vestigial now, deliberately kept, so it is tested.
        Provider = type(self.env['bi.ai.provider'])

        def _denied(self):
            raise AccessError('provider table is out of reach')

        with patch.object(Provider, 'get_default', _denied):
            self.assertIs(
                self.env['bi.ai'].with_user(self.creator).is_available(), False)
            self.assertIs(self._hub(self.creator)['ai_available'], False)

    # ------------------------------------------------------------------
    # T5 — the sidebar wiring: chrome persistence + role visibility
    # ------------------------------------------------------------------
    def test_sidebar_wiring(self):
        keys = self.env['cms.sidebar.item'].get_match_keys()
        for tag in ('biz_bi.hub', 'biz_bi.dashboard', 'biz_bi.explore'):
            self.assertIn(
                tag, keys['tags'],
                '%s must be a match key or the CMS shell drops the user into '
                'the bare backend when the hub navigates there' % tag)
        self.assertIn('biz_bi_cms.action_bi_hub', keys['xmlids'])
        self.assertFalse(
            self.item.match_models,
            'match_models is last-wins and would steal another leaf\'s '
            'highlight (§5.94)')
        self.assertFalse(self.item.parent_id, 'the leaf must be a root (§5.69a)')
        self.assertFalse(
            self.env['cms.sidebar.item'].search([('parent_id', '=', self.item.id)]),
            'and must have no children, for the same reason')

        action = self.env.ref('biz_bi_cms.action_bi_hub')
        self.assertEqual(action._name, 'ir.actions.client')
        self.assertEqual(action.tag, 'biz_bi.hub')
        self.assertEqual(self.item.action_xmlid, 'biz_bi_cms.action_bi_hub')

        # Sequence: after FINANCE, before ADMIN, and nothing already there
        # moves.
        finance = self.env.ref('health_cms_sidebar.section_finance')
        admin = self.env.ref('health_cms_sidebar.section_admin')
        self.assertGreater(self.section.sequence, finance.sequence)
        self.assertLess(self.section.sequence, admin.sequence)

        Item = self.env['cms.sidebar.item']
        gated_user = self._user('bihub_om_side', 'HUB Ops Side',
                                role=self.role_gated)
        ungated_user = self._user('bihub_nurse_side', 'HUB Nurse Side',
                                  role=self.role_ungated)

        gated_data = Item.with_user(gated_user).get_sidebar_data()
        self.assertIn('analytics', self._section_keys(gated_data))
        self.assertIn('Analytics', self._item_names(gated_data))

        ungated_data = Item.with_user(ungated_user).get_sidebar_data()
        self.assertNotIn(
            'analytics', self._section_keys(ungated_data),
            'the ANALYTICS section must not be drawn for a role that has no '
            'BI group — it would open an empty hub')
        self.assertNotIn('Analytics', self._item_names(ungated_data))
