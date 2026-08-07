# -*- coding: utf-8 -*-
"""AH-2 — the server-side contract behind the guided report wizard.

The wizard itself is OWL and is proved by the browser evidence pack. What is
proved HERE is everything the wizard hands to the server, because that is the
part a future refactor can silently break:

* ``test_01`` — the exact ``config_json`` the wizard writes (including a
  relative date range) compiles through ``bi.chart._to_query_request()`` and
  runs on the engine. If the wizard's slot mapping ever drifts from
  ``explore_action.js``'s, this is what goes red.
* ``test_02`` — the save flow a creator actually performs: chart → dashboard →
  ``add_chart``, twice, plus the "create() returns a LIST" shape that caused
  the ``5e91455e`` crash.
* ``test_03`` — the refusal the wizard's Save button must CATCH rather than
  crash on.
* ``test_04`` — the AI probe answers cleanly in both directions.
* ``test_05`` — the auto-grant that closes the "user created after install has
  no BI group" gap Phase 1 measured live.
* ``test_06`` — the upgrade landed at 19.0.1.1.0 and its migration converged
  the database (the 1.0.0 script never ran; Phase-1 report §6).

Fixture note (§5.50 / §5.95 / §5.124): this suite runs against a deployment
with its own workspaces, roles and users. It brings its OWN dataset (biz_bi's
``BiCase``) and its own throwaway users, and every assertion is about the
presence or absence of its own records — except ``test_06``, which is
deliberately a statement about the deployment, because convergence is what the
migration is for.
"""
import json
import os
import re
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.biz_bi.models.bi_query_engine import RELATIVE_RANGES
from odoo.addons.biz_bi.tests.common import BiCase
from odoo.addons.biz_bi_cms.hooks import gated_role_ids

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install')
class TestReportWizard(BiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.creator_group = env.ref('biz_bi.group_bi_creator')
        cls.base_group = env.ref('base.group_user')

        cls.creator = cls._bi_user('wiz_creator_ah2', 'Wizard Creator')
        cls.other_creator = cls._bi_user('wiz_other_ah2', 'Wizard Other')

        # A workspace only `other_creator` may see — the exact shape the UI
        # has to survive when a creator picks somebody else's dashboard.
        cls.foreign_ws = env['bi.workspace'].create({
            'name': 'AH2 Foreign Workspace',
            'is_default': False,
            'member_ids': [(6, 0, [cls.other_creator.id])],
        })
        cls.foreign_dashboard = env['bi.dashboard'].with_user(
            cls.other_creator).create({
                'name': 'AH2 Foreign Dashboard',
                'workspace_id': cls.foreign_ws.id,
            })

    # -- fixture helpers -------------------------------------------------
    @classmethod
    def _bi_user(cls, login, name):
        return cls.env['res.users'].create({
            'name': name,
            'login': login,
            'password': login + 'x' * 4,
            'group_ids': [(6, 0, [cls.base_group.id, cls.creator_group.id])],
        })

    @classmethod
    def _role(cls, name):
        """The deployment's own role row where it exists, else a new one."""
        Role = cls.env['access.role'].sudo()
        role = Role.search([('name', '=', name)], limit=1)
        return role or Role.create({'name': name})

    # -- the wizard's own serializer, transcribed from report_wizard.js ---
    def _wizard_config(self, chart_type='bar', group_by=None, grain=None,
                       split_by=None, date_range=None):
        """`buildConfigJson()` as JSON.stringify hands it to the server.

        Undefined keys never reach the wire, so a non-date group-by carries no
        ``grain`` — that asymmetry is part of the shape being pinned.
        """
        group_by = group_by if group_by is not None else self.f_country_name
        x_entry = {'field_id': group_by.id}
        if grain:
            x_entry['grain'] = grain
        config = {
            'version': 1,
            'chart_type': chart_type,
            'slots': {
                'x': [x_entry],
                'values': [{'field_id': self.f_latitude.id, 'agg': 'sum'}],
                'series': ([{'field_id': split_by.id}] if split_by else []),
            },
            'filters': [],
            'sort': [],
            'limit': 500,
            'display': {},
        }
        if date_range:
            config['filters'] = [{
                'field_id': self.f_create_date.id,
                'op': 'relative',
                'value': date_range,
            }]
        return config

    # ------------------------------------------------------------------
    # T1 — the saved config compiles and runs
    # ------------------------------------------------------------------
    def test_01_wizard_config_roundtrip(self):
        config = self._wizard_config(date_range='last_12_months')
        # the payload must survive a JSON round trip unchanged: this is what
        # the browser actually sends
        self.assertEqual(json.loads(json.dumps(config)), config)

        chart = self.env['bi.chart'].create({
            'name': 'AH2 Roundtrip',
            'dataset_id': self.dataset.id,
            'chart_type': config['chart_type'],
            'config_json': config,
        })
        request = chart._to_query_request()

        self.assertEqual(request['dataset_id'], self.dataset.id)
        self.assertEqual(request['dimensions'],
                         [{'field_id': self.f_country_name.id, 'grain': None}])
        self.assertEqual(request['measures'],
                         [{'field_id': self.f_latitude.id, 'agg': 'sum'}])
        self.assertEqual(request['filters'], [{
            'field_id': self.f_create_date.id,
            'op': 'relative',
            'value': 'last_12_months',
        }])
        self.assertEqual(request['limit'], 500)

        envelope = self.engine.run(request)
        self.assertNotIn('error', envelope)
        self.assertEqual([col['ref'] for col in envelope['columns']],
                         ['d0', 'm0'])
        self.assertTrue(envelope['rows'],
                        'the fixture partners were created just now, so a '
                        'last_12_months window must contain them')

        # ... and the same shape with a grained date axis + a split-by, which
        # is what the wizard writes for a trend.
        trend = self._wizard_config(
            chart_type='line', group_by=self.f_create_date, grain='month',
            split_by=self.f_country_name)
        trend_chart = self.env['bi.chart'].create({
            'name': 'AH2 Roundtrip Trend',
            'dataset_id': self.dataset.id,
            'chart_type': 'line',
            'config_json': trend,
        })
        trend_envelope = self.engine.run(trend_chart._to_query_request())
        self.assertNotIn('error', trend_envelope)
        self.assertEqual([col['ref'] for col in trend_envelope['columns']],
                         ['d0', 'd1', 'm0'])

    def test_01b_relative_range_vocabulary_is_shared(self):
        """The wizard's date chips come from biz_bi's `RELATIVE_RANGES` JS
        table; the engine has its own python table. A value in one that is
        missing from the other is a chip that raises UserError on click."""
        js_path = os.path.join(
            os.path.dirname(MODULE_DIR), 'biz_bi',
            'static', 'src', 'core', 'range_labels.js')
        with open(js_path, encoding='utf-8') as handle:
            source = handle.read()
        js_keys = set(re.findall(r'\[\s*"([a-z0-9_]+)"\s*,', source))
        self.assertTrue(js_keys, 'the RELATIVE_RANGES table could not be read')
        self.assertFalse(
            js_keys - set(RELATIVE_RANGES),
            'every chip the wizard offers must be a range the engine knows')

    # ------------------------------------------------------------------
    # T2 — the save flow, as a creator
    # ------------------------------------------------------------------
    def test_02_wizard_save_flow(self):
        Chart = self.env['bi.chart'].with_user(self.creator)
        Dashboard = self.env['bi.dashboard'].with_user(self.creator)

        # `orm.create` returns a LIST of ids — the wizard destructures it, and
        # handing the list on unchanged is the 5e91455e bug.
        chart_ids = Chart.create([{
            'name': 'AH2 Saved Report',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': self._wizard_config(),
        }]).ids
        self.assertEqual(len(chart_ids), 1)
        chart_id = chart_ids[0]

        dashboard = Dashboard.create({
            'name': 'AH2 New Dashboard',
            'workspace_id': self.workspace.id,
        })
        widget_id = dashboard.add_chart(chart_id)
        self.assertTrue(widget_id)

        widgets = self.env['bi.dashboard.widget'].search(
            [('dashboard_id', '=', dashboard.id)])
        self.assertEqual(len(widgets), 1)
        self.assertEqual(widgets.chart_id.id, chart_id)

        data = dashboard.get_dashboard_data()
        self.assertIn(chart_id, [w['chart_id'] for w in data['widgets']])
        self.assertTrue(data['can_edit'],
                        'the creator owns this dashboard, so the dashboard '
                        'screen must offer them its edit path')

        # add_chart tolerates the raw list the web ORM hands back, and a
        # second call is a second widget, not a crash.
        second = dashboard.add_chart([chart_id])
        self.assertTrue(second)
        self.assertEqual(self.env['bi.dashboard.widget'].search_count(
            [('dashboard_id', '=', dashboard.id)]), 2)

    # ------------------------------------------------------------------
    # T3 — the refusal the Save button must catch
    # ------------------------------------------------------------------
    def test_03_creator_cannot_add_to_foreign_dashboard(self):
        chart = self.env['bi.chart'].with_user(self.creator).create({
            'name': 'AH2 Chart For Foreign Dashboard',
            'dataset_id': self.dataset.id,
            'chart_type': 'bar',
            'config_json': self._wizard_config(),
        })
        # fixture guard: the foreign dashboard really is out of reach
        self.assertFalse(
            self.env['bi.dashboard'].with_user(self.creator).search_count(
                [('id', '=', self.foreign_dashboard.id)]))
        with self.assertRaises(AccessError):
            self.env['bi.dashboard'].with_user(self.creator).browse(
                self.foreign_dashboard.id).add_chart(chart.id)
        # ... and nothing was written on the way out
        self.assertFalse(self.env['bi.dashboard.widget'].sudo().search_count(
            [('dashboard_id', '=', self.foreign_dashboard.id)]))

    # ------------------------------------------------------------------
    # T4 — the AI probe
    # ------------------------------------------------------------------
    def test_04_nlq_unavailable_is_clean(self):
        Provider = type(self.env['bi.ai.provider'])

        def _no_provider(self):
            return self.browse()

        # A plain function, never `autospec=True` — a re-patched autospec mock
        # silently stops binding `self` (§5.76).
        with patch.object(Provider, 'get_default', _no_provider):
            self.assertIs(self.env['bi.ai'].is_available(), False)

        # And for a creator the probe answers False instead of raising, which
        # is what lets the wizard call it with no guard (Phase-1 D4 / §5.127).
        self.assertFalse(
            self.creator.has_group('biz_bi.group_bi_modeler'),
            'fixture guard: the persona must not be able to read the '
            'provider table, or this proves nothing')
        self.assertIs(
            self.env['bi.ai'].with_user(self.creator).is_available(), False)

    # ------------------------------------------------------------------
    # T5 — the auto-grant on role assignment
    # ------------------------------------------------------------------
    def test_05_auto_grant_on_role_assign(self):
        gated = self._role('Operations Manager')
        ungated = self._role('Nurse')
        group = self.creator_group

        # (a) created WITH a gated role
        born_gated = self.env['res.users'].create({
            'name': 'AH2 Born Gated', 'login': 'ah2_born_gated',
            'password': 'ah2_born_gatedx', 'access_role_id': gated.id})
        self.assertIn(group, born_gated.all_group_ids,
                      'a user created with an Analytics role must not have to '
                      'wait for the next upgrade to get BI access')

        # (b) re-roled later
        promoted = self.env['res.users'].create({
            'name': 'AH2 Promoted', 'login': 'ah2_promoted',
            'password': 'ah2_promotedx'})
        self.assertNotIn(group, promoted.all_group_ids)
        promoted.write({'access_role_id': gated.id})
        self.assertIn(group, promoted.all_group_ids)

        # (c) idempotent
        before = set(promoted.group_ids.ids)
        promoted.write({'access_role_id': gated.id})
        self.assertEqual(set(promoted.group_ids.ids), before)

        # (d) an ungated role grants nothing
        nurse = self.env['res.users'].create({
            'name': 'AH2 Nurse', 'login': 'ah2_nurse',
            'password': 'ah2_nursexx', 'access_role_id': ungated.id})
        self.assertNotIn(group, nurse.all_group_ids)

        # (e) ADD-ONLY: moving off an Analytics role never revokes. Removing
        # BI access stays a deliberate act, exactly as access_roles refuses to
        # un-grant the groups a role added.
        promoted.write({'access_role_id': ungated.id})
        self.assertIn(group, promoted.all_group_ids)

    # ------------------------------------------------------------------
    # T6 — the upgrade ran, and the database converged
    # ------------------------------------------------------------------
    def test_06_migration_reruns_gates(self):
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'biz_bi_cms')], limit=1)
        self.assertEqual(
            module.latest_version, '19.0.1.1.0',
            'the installed version must have moved, or no migration script '
            'runs at all (Phase-1 report §6)')
        self.assertTrue(
            os.path.isdir(os.path.join(MODULE_DIR, 'migrations', '19.0.1.1.0')),
            'the migration directory must be named for the version Odoo is '
            'upgrading TO')

        role_ids = gated_role_ids(self.env)
        self.assertTrue(role_ids, 'fixture guard: this database has Analytics '
                                  'roles to gate on')
        users = self.env['res.users'].sudo().search([
            ('access_role_id', 'in', role_ids),
            ('share', '=', False),
            ('active', '=', True),
        ])
        self.assertTrue(users, 'fixture guard: somebody holds one')
        missing = users.filtered(
            lambda u: self.creator_group not in u.all_group_ids)
        self.assertFalse(
            missing.mapped('login'),
            'every Analytics-role user must hold the BI creator group after '
            'the upgrade — that convergence is the migration\'s whole job')

        # the leaf is still gated to exactly the roles that exist here
        item = self.env.ref('biz_bi_cms.item_analytics_hub')
        self.assertEqual(set(item.role_ids.ids), set(role_ids))
