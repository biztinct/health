# -*- coding: utf-8 -*-
"""AH-3 — the four contracts the polish phase changed underneath the UI.

* ``test_ah3_01`` — a plain creator can now ASK whether AI is available. The
  probe used to be an ACL question (``bi.ai.provider`` starts at
  ``group_bi_modeler``), so the whole audience of the wizard was told "no" by
  the permission system rather than by the configuration. The fixture guard
  proves the creator still cannot read a single provider row — the answer got
  through, the records did not.
* ``test_ah3_02`` — the shape of that permission after the sudo: the DATASET is
  still checked as the real user, and the refusal happens BEFORE any provider
  is resolved. The completion is mocked; no test may call an LLM.
* ``test_ah3_03`` — ``get_wizard_targets`` offers what the user may WRITE, using
  the predicate the dashboard screen already publishes as ``can_edit``
  (``biz_bi/models/bi_dashboard.py:213-216``), not what they may see.
* ``test_ah3_04`` — recents survive their dashboards: an append-only
  ``dashboard_view`` row outlives a deleted dashboard and one that moved out of
  reach, and neither may reach the landing.

Fixture note (§5.50 / §5.95 / §5.124): this runs against a deployment with its
own workspaces, dashboards, users and AI providers. Every assertion is about
the presence or absence of THIS test's own records — never an absolute count —
and the one statement about the deployment (that a usable provider exists) is
made true by the fixture rather than assumed.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.biz_bi.tests.common import BiCase


@tagged('post_install', '-at_install')
class TestAnalyticsHubAh3(BiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.base_group = env.ref('base.group_user')
        cls.creator_group = env.ref('biz_bi.group_bi_creator')
        cls.modeler_group = env.ref('biz_bi.group_bi_modeler')

        cls.creator = cls._make_user('ah3_creator', 'AH3 Creator',
                                     cls.creator_group)
        cls.peer = cls._make_user('ah3_peer', 'AH3 Peer', cls.creator_group)
        cls.modeler = cls._make_user('ah3_modeler', 'AH3 Modeler',
                                     cls.modeler_group)

        # `cls.workspace` (BiCase) has no members and no groups, so every BI
        # viewer sees it. This one is member-scoped to the peer alone.
        cls.foreign_ws = env['bi.workspace'].create({
            'name': 'AH3 Foreign Workspace',
            'is_default': False,
            'member_ids': [(6, 0, [cls.peer.id])],
        })

        # own → writable; peer_dashboard → visible but NOT writable (shared
        # workspace, somebody else's row); foreign → not even visible.
        cls.own_dashboard = env['bi.dashboard'].with_user(cls.creator).create({
            'name': 'AH3 Own Dashboard', 'workspace_id': cls.workspace.id})
        cls.peer_dashboard = env['bi.dashboard'].with_user(cls.peer).create({
            'name': 'AH3 Peer Dashboard', 'workspace_id': cls.workspace.id})
        cls.foreign_dashboard = env['bi.dashboard'].with_user(cls.peer).create({
            'name': 'AH3 Foreign Dashboard', 'workspace_id': cls.foreign_ws.id})

    # -- fixture helpers -------------------------------------------------
    @classmethod
    def _make_user(cls, login, name, group):
        return cls.env['res.users'].create({
            'name': name,
            'login': login,
            'password': login + 'x' * 4,
            'group_ids': [(6, 0, [cls.base_group.id, group.id])],
        })

    def _seen(self, user, dashboard_id):
        """An append-only `dashboard_view` row, as get_dashboard_data writes."""
        self.env['bi.audit.log'].sudo().create({
            'user_id': user.id,
            'event': 'dashboard_view',
            'res_model': 'bi.dashboard',
            'res_id': dashboard_id,
        })

    # ------------------------------------------------------------------
    # T1 — the AI probe answers a creator honestly
    # ------------------------------------------------------------------
    def test_ah3_01_ai_available_for_creator(self):
        self.assertFalse(
            self.creator.has_group('biz_bi.group_bi_modeler'),
            'fixture guard: the persona must be a PLAIN creator, or this test '
            'proves nothing about the ACL it is here to route around')
        with self.assertRaises(AccessError):
            self.env['bi.ai.provider'].with_user(self.creator).search([])

        # A usable provider exists on this database: `ollama` is usable with no
        # key at all, so the fixture never has to fabricate key material.
        self.env['bi.ai.provider'].sudo().create({
            'name': 'AH3 Local Ollama',
            'provider': 'ollama',
            'endpoint': 'http://127.0.0.1:11434/api/chat',
            'model_name': 'llama3',
        })

        answer = self.env['bi.ai'].with_user(self.creator).is_available()
        self.assertIs(answer, True,
                      'a plain creator must get the CONFIGURATION answer, not '
                      'the permission one')
        self.assertIsInstance(answer, bool,
                              'the probe returns a boolean and nothing else — '
                              'no provider record crosses the RPC boundary')

        # ... and it is still an honest "no" when there is nothing to use. A
        # plain function, never `autospec=True` (§5.76).
        Provider = type(self.env['bi.ai.provider'])

        def _no_provider(self):
            return self.browse()

        with patch.object(Provider, 'get_default', _no_provider):
            self.assertIs(
                self.env['bi.ai'].with_user(self.creator).is_available(), False)

    # ------------------------------------------------------------------
    # T2 — what the sudo did NOT widen
    # ------------------------------------------------------------------
    def test_ah3_02_nlq_permission_shape(self):
        reached = []

        def _fake_complete(self, dataset, system, prompt, kind, validate):
            """Stands in for the LLM round trip — no test calls a provider."""
            reached.append(dataset.id)
            return {'version': 1, 'chart_type': 'bar', 'slots': {},
                    'filters': [], 'limit': 500, 'display': {}}, None

        Ai = type(self.env['bi.ai'])

        # (a) a dataset the creator may read: no AccessError anywhere, and the
        #     completion is reached with that dataset.
        with patch.object(Ai, '_complete_validated', _fake_complete):
            result = self.env['bi.ai'].with_user(self.creator).nlq_chart(
                self.dataset.id, 'latitude by country')
        self.assertNotIn('error', result)
        self.assertIn('config', result)
        self.assertEqual(reached, [self.dataset.id])

        # (b) a dataset they may NOT read: it raises, and it raises BEFORE any
        #     provider is resolved — the sudo widened the provider lookup, not
        #     the data boundary.
        foreign_dataset = self.env['bi.dataset'].create({
            'name': 'AH3 Foreign Dataset',
            'workspace_id': self.foreign_ws.id,
        })
        reached.clear()
        with patch.object(Ai, '_complete_validated', _fake_complete):
            with self.assertRaises(AccessError):
                self.env['bi.ai'].with_user(self.creator).nlq_chart(
                    foreign_dataset.id, 'anything at all')
        self.assertEqual(
            reached, [],
            'the dataset refusal must come first: nothing about the provider '
            'may be touched on behalf of a user who cannot read the data')

    # ------------------------------------------------------------------
    # T3 — the wizard offers what can be WRITTEN
    # ------------------------------------------------------------------
    def test_ah3_03_wizard_targets(self):
        Dashboard = self.env['bi.dashboard']

        # fixture guard: the peer's dashboard IS visible to the creator (same
        # open workspace), which is exactly why the old read-scoped list
        # offered it.
        visible = Dashboard.with_user(self.creator).search([]).ids
        self.assertIn(self.peer_dashboard.id, visible)
        self.assertIn(self.own_dashboard.id, visible)
        self.assertNotIn(self.foreign_dashboard.id, visible)

        targets = Dashboard.with_user(self.creator).get_wizard_targets()
        ids = [row['id'] for row in targets]
        self.assertIn(self.own_dashboard.id, ids)
        self.assertNotIn(
            self.peer_dashboard.id, ids,
            'a dashboard the creator can see but not write must not be '
            'offered — that refusal used to arrive at Save time')
        self.assertNotIn(self.foreign_dashboard.id, ids)
        for row in targets:
            self.assertEqual(set(row), {'id', 'name'},
                             'the payload is [{id, name}] and nothing more')

        # the predicate IS can_edit: everything offered says can_edit True on
        # the dashboard screen, and the one that is refused says False.
        for dashboard_id in ids:
            data = Dashboard.with_user(self.creator).browse(
                dashboard_id).get_dashboard_data()
            self.assertTrue(data['can_edit'],
                            'get_wizard_targets and can_edit must be the same '
                            'predicate, not two opinions')
        peer_data = Dashboard.with_user(self.creator).browse(
            self.peer_dashboard.id).get_dashboard_data()
        self.assertFalse(peer_data['can_edit'])

        # a modeler may write everything, including the foreign row
        modeler_ids = [row['id'] for row
                       in Dashboard.with_user(self.modeler).get_wizard_targets()]
        for dashboard in (self.own_dashboard, self.peer_dashboard,
                          self.foreign_dashboard):
            self.assertIn(dashboard.id, modeler_ids)

        # a plain viewer may write nothing at all
        viewer = self._make_user('ah3_viewer', 'AH3 Viewer',
                                 self.env.ref('biz_bi.group_bi_viewer'))
        self.assertEqual(
            Dashboard.with_user(viewer).get_wizard_targets(), [])

    # ------------------------------------------------------------------
    # T4 — recents outlive their dashboards; the landing must not
    # ------------------------------------------------------------------
    def test_ah3_04_recents_pruned(self):
        doomed = self.env['bi.dashboard'].with_user(self.creator).create({
            'name': 'AH3 Doomed Dashboard', 'workspace_id': self.workspace.id})
        doomed_id = doomed.id

        for dashboard_id in (self.own_dashboard.id, doomed_id,
                             self.foreign_dashboard.id):
            self._seen(self.creator, dashboard_id)

        doomed.unlink()
        # get_recents is raw SQL over bi_audit_log: flush first (§5.9).
        self.env.flush_all()

        data = self.env['bi.workspace'].with_user(self.creator).get_hub_data()
        recent_ids = [row['id'] for row in data['recents']]

        self.assertIn(self.own_dashboard.id, recent_ids,
                      'fixture guard: a live, readable dashboard IS a recent')
        self.assertNotIn(doomed_id, recent_ids,
                         'a deleted dashboard must not survive as a chip')
        self.assertNotIn(
            self.foreign_dashboard.id, recent_ids,
            'nor may a dashboard the user can no longer read — the audit row '
            'is append-only and outlives the entitlement')
        for row in data['recents']:
            self.assertEqual(set(row), {'id', 'name', 'workspace'})

    # ------------------------------------------------------------------
    # T4b — a recents strip may never take the landing down
    # ------------------------------------------------------------------
    def test_ah3_04b_recents_accesserror_does_not_kill_the_hub(self):
        """Found by DRIVING the first-run state, not by reading code.

        ``bi.audit.log.get_recents`` ends with ``d.workspace_id.name``, and a
        dashboard can be readable while its workspace is not (the dashboard
        rule grants ``owner_id = user`` on its own; the workspace rule has no
        such clause). On vietuat, group-scoping the workspaces turned the
        user's own recent dashboard into an AccessError on the WORKSPACE read
        and the whole hub fell back to "analytics access has not been set up
        for your account" — over one stale chip.
        """
        Log = type(self.env['bi.audit.log'])

        def _refuse(self, limit=10):
            raise AccessError('workspace of a recent dashboard is out of reach')

        with patch.object(Log, 'get_recents', _refuse):
            data = self.env['bi.workspace'].with_user(
                self.creator).get_hub_data()

        self.assertEqual(data['recents'], [])
        self.assertTrue(
            any(ws['id'] == self.workspace.id for ws in data['workspaces']),
            'the workspaces the user CAN see must still be listed — the '
            'refusal belongs to the recents compartment alone (§5.47)')
