# -*- coding: utf-8 -*-
"""RT-2 — the server-side contract behind the wizard's Records list path.

The picker itself is OWL and is proved by the browser evidence pack. What is
proved HERE is everything the Records path hands to the server, because that
is the part a refactor can silently break without anybody noticing until an
export comes back with the wrong columns:

* ``test_records_config_shape`` — the exact ``config_json`` the wizard writes
  compiles through ``bi.chart._to_query_request()`` into a **detail** request
  with the columns in the order they were ticked, runs on the engine as one
  row per record, and still accepts a dashboard global filter on top.
* ``test_records_save_flow`` — a creator saves a records chart onto a NEW
  dashboard through the same ``get_wizard_targets`` path the UI uses; the
  widget exists and ``get_dashboard_data`` returns it.
* ``test_records_column_order_preserved`` — columns saved ``[c, a, b]`` come
  back ``[c, a, b]``, through the config, the request AND the envelope.

Fixture note (§5.50 / §5.95 / §5.124): the suite brings biz_bi's own
``BiCase`` dataset and its own throwaway user, and every assertion is about
its own records. It also widens ``res.partner`` visibility inside the
transaction (§ RT-1 report §2): vietuat's live rules pin a plain internal user
to their own partner, which would make a row assertion vacuously true.
"""
import json

from odoo.tests import tagged

from odoo.addons.biz_bi.tests.common import BiCase


@tagged('post_install', '-at_install')
class TestWizardRecords(BiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.creator_group = env.ref('biz_bi.group_bi_creator')
        cls.base_group = env.ref('base.group_user')

        # a many2one column: this is what makes "names, not ids" reachable
        # from the wizard at all (the label resolution is RT-1's, per reader).
        cls.f_country_id = cls.dataset.field_ids.filtered(
            lambda f: f.technical_name == 'country_id'
            and f.node_id == cls.node_root)
        cls.f_country_id.visibility = 'visible'
        cls.f_name.visibility = 'visible'

        cls.creator = env['res.users'].create({
            'name': 'RT2 Wizard Creator',
            'login': 'rt2_wiz_creator',
            'password': 'rt2_wiz_creatorx',
            'group_ids': [(6, 0, [cls.base_group.id, cls.creator_group.id])],
        })

    # -- the wizard's own serializer, transcribed from report_wizard.js -----
    def _records_config(self, columns, date_range=None, limit=5000):
        """``buildConfigJson()``'s records branch as JSON.stringify hands it
        to the server. Ordered ``slots.columns``, empty aggregate slots, no
        measure, ``mode: 'detail'``."""
        config = {
            'version': 1,
            'chart_type': 'table',
            'mode': 'detail',
            'slots': {
                'x': [],
                'values': [],
                'series': [],
                'columns': [{'field_id': field.id} for field in columns],
            },
            'filters': [],
            'sort': [],
            'limit': limit,
            'display': {},
        }
        if date_range:
            config['filters'] = [{
                'field_id': self.f_create_date.id,
                'op': 'relative',
                'value': date_range,
            }]
        return config

    def _allow_all_partners(self):
        """vietuat's live `res.partner` rules pin a plain internal user to
        their OWN partner, so the fixture rows would be invisible and a row
        assertion would pass by being empty (RT-1 report §2)."""
        self.env['ir.rule'].create({
            'name': 'RT2 wizard records test: read every partner',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'domain_force': "[(1, '=', 1)]",
            'groups': [(4, self.env.ref('base.group_user').id)],
            'perm_read': True, 'perm_write': False,
            'perm_create': False, 'perm_unlink': False,
        })
        self.env.registry.clear_cache()

    def _fixture_filter(self):
        """Scope a run to this fixture's three partners — the dataset sits on
        res.partner and vietuat holds thousands of them."""
        return {'field_id': self.f_name.id, 'op': 'like_i',
                'value': 'BI Test'}

    # ------------------------------------------------------------------
    # T1 — the saved config compiles to a detail request and runs
    # ------------------------------------------------------------------
    def test_records_config_shape(self):
        columns = [self.f_name, self.f_country_id, self.f_latitude]
        config = self._records_config(columns, date_range='last_12_months')
        # the payload must survive a JSON round trip unchanged: this is what
        # the browser actually sends
        self.assertEqual(json.loads(json.dumps(config)), config)

        chart = self.env['bi.chart'].create({
            'name': 'RT2 Records Shape',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': config,
        })
        request = chart._to_query_request()

        self.assertEqual(request['mode'], 'detail',
                         'a records config must compile to a DETAIL request '
                         'or the engine silently answers as an aggregate')
        self.assertEqual(request['measures'], [])
        self.assertEqual(request['dimensions'],
                         [{'field_id': field.id} for field in columns])
        # a detail dimension carries no grain at all — records already hold
        # the real date
        for dimension in request['dimensions']:
            self.assertNotIn('grain', dimension)
        self.assertEqual(request['filters'], [{
            'field_id': self.f_create_date.id,
            'op': 'relative',
            'value': 'last_12_months',
        }])
        self.assertEqual(request['limit'], 5000)

        # ... and it runs, one row per record
        run_request = dict(request)
        run_request['filters'] = [self._fixture_filter()]
        envelope = self.engine.run(run_request)
        self.assertNotIn('error', envelope)
        self.assertEqual([col['ref'] for col in envelope['columns']],
                         ['d0', 'd1', 'd2'])
        self.assertEqual(envelope['meta']['mode'], 'detail')
        self.assertEqual(len(envelope['rows']), 3,
                         'three fixture partners, three rows — an aggregate '
                         'would have collapsed them')
        self.assertEqual(sorted(row[0] for row in envelope['rows']),
                         ['BI Test Alpha', 'BI Test Beta', 'BI Test Gamma'])
        # raw latitudes, never a 60.0 sum
        self.assertEqual(sorted(row[2] for row in envelope['rows']),
                         [10.0, 20.0, 30.0])
        # the many2one column resolves to a NAME for this reader, which is
        # what the wizard's preview and the export both render
        labels = envelope['columns'][1].get('value_labels') or {}
        self.assertTrue(labels, 'the country column must carry value_labels')
        self.assertIn(self.country_a.name, labels.values())

        # a dashboard GLOBAL filter still appends on the detail path
        extra = self._fixture_filter()
        with_extra = chart._to_query_request([extra])
        self.assertEqual(with_extra['filters'][-1], extra)
        self.assertEqual(len(with_extra['filters']), 2)
        self.assertEqual(with_extra['mode'], 'detail')

    # ------------------------------------------------------------------
    # T2 — a creator saves a records report onto a new dashboard
    # ------------------------------------------------------------------
    def test_records_save_flow(self):
        Chart = self.env['bi.chart'].with_user(self.creator)
        Dashboard = self.env['bi.dashboard'].with_user(self.creator)

        # step 3 offers only what the user may WRITE; a fresh creator owns
        # nothing, so "New dashboard" is the only honest target.
        targets = Dashboard.get_wizard_targets()
        self.assertEqual(
            [entry for entry in targets if entry['name'] == 'RT2 Records Dash'],
            [], 'fixture guard: the dashboard this test creates must not '
                'already exist')

        # `orm.create` returns a LIST of ids — the wizard destructures it.
        chart_ids = Chart.create([{
            'name': 'RT2 Saved Records',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': self._records_config(
                [self.f_name, self.f_country_id]),
        }]).ids
        self.assertEqual(len(chart_ids), 1)
        chart_id = chart_ids[0]

        dashboard = Dashboard.create({
            'name': 'RT2 Records Dash',
            'workspace_id': self.workspace.id,
        })
        widget_id = dashboard.add_chart(chart_id)
        self.assertTrue(widget_id)

        # ... and the dashboard the wizard now navigates to really carries it
        widgets = self.env['bi.dashboard.widget'].search(
            [('dashboard_id', '=', dashboard.id)])
        self.assertEqual(len(widgets), 1)
        self.assertEqual(widgets.chart_id.id, chart_id)

        data = dashboard.get_dashboard_data()
        self.assertIn(chart_id, [w['chart_id'] for w in data['widgets']])
        saved = [w for w in data['widgets'] if w['chart_id'] == chart_id][0]
        self.assertEqual(saved['chart_type'], 'table')
        self.assertEqual((saved.get('config') or {}).get('mode'), 'detail')

        # the newly-owned dashboard is now an offered target, which is the
        # state the user comes back to on their second report
        names = [entry['name']
                 for entry in Dashboard.get_wizard_targets()]
        self.assertIn('RT2 Records Dash', names)

        # and the saved chart still compiles and runs as a records query for
        # the creator themself, not merely for an administrator
        self._allow_all_partners()
        creator_chart = Chart.browse(chart_id)
        request = creator_chart._to_query_request([self._fixture_filter()])
        envelope = self.env['bi.query.engine'].with_user(
            self.creator).run(request)
        self.assertNotIn('error', envelope)
        self.assertEqual(len(envelope['rows']), 3)

    # ------------------------------------------------------------------
    # T3 — the column ORDER is the report
    # ------------------------------------------------------------------
    def test_records_column_order_preserved(self):
        # ticked as [country, name, latitude], deliberately not alphabetical
        # and deliberately not the dataset's own field order
        ordered = [self.f_country_id, self.f_name, self.f_latitude]
        chart = self.env['bi.chart'].create({
            'name': 'RT2 Records Order',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': self._records_config(ordered),
        })
        # (a) it survives the write/read round trip through the jsonb column
        stored = chart.config_json['slots']['columns']
        self.assertEqual([entry['field_id'] for entry in stored],
                         [field.id for field in ordered])

        # (b) the compiled request keeps it
        request = chart._to_query_request()
        self.assertEqual([entry['field_id'] for entry in request['dimensions']],
                         [field.id for field in ordered])

        # (c) and so does the envelope the preview and the export are built
        # from — d0/d1/d2 must be country, name, latitude in THAT order
        request['filters'] = [self._fixture_filter()]
        envelope = self.engine.run(request)
        self.assertNotIn('error', envelope)
        self.assertEqual([col['field_id'] for col in envelope['columns']],
                         [field.id for field in ordered])
        self.assertEqual([col['label'] for col in envelope['columns']],
                         [field.name for field in ordered])
        # the country column is first, so every row starts with an id that
        # resolves through value_labels, never with the partner name
        labels = envelope['columns'][0].get('value_labels') or {}
        self.assertTrue(labels)
        for row in envelope['rows']:
            self.assertIn(str(row[0]), labels)

        # (d) a column ticked twice is still one column (the engine dedupes
        # keep-first), and that must not disturb the order either
        duplicated = self._records_config(
            [self.f_country_id, self.f_name, self.f_country_id,
             self.f_latitude])
        dup_chart = self.env['bi.chart'].create({
            'name': 'RT2 Records Order Dup',
            'dataset_id': self.dataset.id,
            'chart_type': 'table',
            'config_json': duplicated,
        })
        self.assertEqual(
            [entry['field_id']
             for entry in dup_chart._to_query_request()['dimensions']],
            [field.id for field in ordered])


    # ------------------------------------------------------------------
    # T4 — one truncation notice, not two
    # ------------------------------------------------------------------
    def test_records_preview_states_the_truncation_once(self):
        """RT-2 shipped the same sentence twice on the same screen.

        The wizard's banner sits ABOVE the table, next to the Excel button —
        where the decision is made — and RT-1's ``DataTable`` also writes the
        overflow as its last row, at the bottom of a 100-row scroll area.
        Both are honest; together they read as a bug. The banner stays and the
        table is told to keep quiet, but ONLY while the banner is actually
        rendered: `suppressOverflowRow` is bound to the same getter the banner
        is, so there is no arrangement in which neither of them speaks.
        """
        import pathlib

        import odoo.addons.biz_bi as biz_bi_module

        template = pathlib.Path(__file__).parent.parent.joinpath(
            'static/src/components/wizard/report_wizard.xml').read_text()
        self.assertIn('suppressOverflowRow="!!recordsTruncation"', template,
                      "the wizard must pass the opt-in, bound to the banner")
        self.assertIn('t-if="recordsTruncation" class="bi-wizard-banner"',
                      template, "…and the banner must still be the one that "
                                "states it")

        # the prop it is passing has to exist on the component receiving it,
        # and it has to be optional — every other host must keep the row
        data_table = pathlib.Path(biz_bi_module.__file__).parent.joinpath(
            'static/src/components/explore/data_table.js').read_text()
        self.assertIn('suppressOverflowRow: { type: Boolean, optional: true }',
                      data_table)
