# -*- coding: utf-8 -*-
"""A field the product marked non-exportable is not analytics material.

Generic on purpose: no product, no particular module. The fixture's partner
dataset is scanned while `ref` is an ordinary column; the test then marks the
model field non-exportable (as a product does for health information) and
checks every door: discovery, rescan, the builder and the engine — for an
administrator too.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import BiCase


@tagged('post_install', '-at_install')
class TestNonExportableFields(BiCase):

    def _field(self, node, technical_name):
        return self.dataset.field_ids.filtered(
            lambda f: f.node_id == node and f.technical_name == technical_name)

    def test_55_non_exportable_fields_are_not_analytics_material(self):
        f_ref = self._field(self.node_root, 'ref')
        self.assertTrue(f_ref, 'the fixture scan should know the ref column')
        f_ref.visibility = 'visible'
        # an ordinary column: discovered, offered, queryable (and the result
        # is now in the cache — which must not serve it once refused)
        names = {c['name'] for c in self.source_partner._fetch_schema_odoo()}
        self.assertIn('ref', names)
        self.engine.run(self._base_request(
            dimensions=[{'field_id': f_ref.id}], filters=[]))

        self.patch(self.env['res.partner']._fields['ref'], 'exportable', False)
        # discovery skips it
        names = {c['name'] for c in self.source_partner._fetch_schema_odoo()}
        self.assertNotIn('ref', names)
        self.assertIn('name', names)
        # a rescan keeps the field (saved charts keep their references) but
        # marks it sensitive, and never adds it twice
        self.node_root.action_scan_fields()
        self.assertTrue(f_ref.exists())
        self.assertEqual(f_ref.visibility, 'sensitive')
        self.assertEqual(len(self._field(self.node_root, 'ref')), 1)
        # the builder does not offer it
        ids = {f['id'] for f in self.dataset.get_builder_metadata()['fields']}
        self.assertNotIn(f_ref.id, ids)
        self.assertIn(self.f_name.id, ids)
        # the engine refuses it by id, for an administrator too
        for request in (
                self._base_request(dimensions=[{'field_id': f_ref.id}],
                                   filters=[]),
                self._base_request(filters=[{'field_id': f_ref.id,
                                             'op': 'eq', 'value': 'x'}])):
            with self.assertRaisesRegex(
                    UserError, 'This field is not available to analytics.'):
                self.engine.run(request)
        # even put back to visible by hand, the live flag still refuses it
        f_ref.visibility = 'visible'
        with self.assertRaisesRegex(UserError, 'not available to analytics'):
            self.engine.run(self._base_request(
                dimensions=[{'field_id': f_ref.id}], filters=[]))

    def test_55b_a_sensitive_field_is_refused_by_the_engine(self):
        self.f_latitude.visibility = 'sensitive'
        with self.assertRaisesRegex(UserError, 'not available to analytics'):
            self.engine.run(self._base_request())


@tagged('post_install', '-at_install')
class TestSqlLayerCarriesOnlyAnalyticsMaterial(BiCase):
    """T71 (FS-H5) — the clean view of a pipeline and the silver view of a
    dataset carry neither a column the product marked non-exportable nor a
    field marked sensitive; the clean view's own schema and the editor's
    preview list neither; the end-migrate rebuilds a view made before."""

    def _columns(self, relation):
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND table_schema = current_schema()",
            (relation,))
        return {row[0] for row in self.env.cr.fetchall()}

    def _mark(self):
        """`ref` non-exportable (as a product marks an encrypted column),
        `partner_latitude` sensitive in the dataset."""
        self.patch(self.env['res.partner']._fields['ref'], 'exportable',
                   False)
        self.f_latitude.visibility = 'sensitive'
        self.f_ref = self.dataset.field_ids.filtered(
            lambda f: f.node_id == self.node_root
            and f.technical_name == 'ref')
        self.assertTrue(self.f_ref)

    def test_71_the_bi_sql_layer_carries_only_analytics_material(self):
        self._mark()
        # silver view (no pipeline): neither field is a column
        self.dataset._recreate_silver_view()
        silver = self._columns(self.dataset._silver_view_name())
        self.assertIn('f_%d' % self.f_name.id, silver)
        self.assertNotIn('f_%d' % self.f_ref.id, silver)
        self.assertNotIn('f_%d' % self.f_latitude.id, silver)
        self.assertIn(self.f_ref, self.dataset._silver_left_out_fields())
        # pipeline without steps: an explicit list, without both columns
        pipeline = self.env['bi.pipeline'].create({
            'source_id': self.source_partner.id})
        compiled, _schema = pipeline.compile_sql()
        text = self.env.cr.mogrify(compiled).decode()
        self.assertNotIn('SELECT *', text)
        pipeline.action_apply()
        clean = self._columns(pipeline._clean_view_name())
        self.assertIn('name', clean)
        self.assertIn('id', clean)
        self.assertNotIn('ref', clean)
        self.assertNotIn('partner_latitude', clean)
        # a physical column whose field is not stored is a leftover, not data
        self.env.cr.execute("SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'res_partner'")
        physical = {row[0] for row in self.env.cr.fetchall()}
        leftovers = {name for name, field in
                     self.env['res.partner']._fields.items()
                     if not field.store and name in physical}
        self.assertFalse(leftovers & clean)
        # `has_active_pipeline` is computed without dependencies: it was
        # cached (False) by the silver view above, before the pipeline existed
        self.source_partner.invalidate_recordset(['has_active_pipeline'])
        self.assertTrue(self.source_partner.has_active_pipeline)
        names = {c['name'] for c in self.source_partner._fetch_schema()}
        self.assertIn('name', names)
        self.assertNotIn('ref', names)
        self.assertNotIn('partner_latitude', names)
        # the silver view now reads through the clean view and still works
        self.dataset._recreate_silver_view()
        self.env.cr.execute("SELECT count(*) FROM %s"
                            % self.dataset._silver_view_name())
        self.assertGreaterEqual(self.env.cr.fetchone()[0], 3)
        # the editor's preview
        data = self.env['bi.pipeline'].get_editor_data(self.source_partner.id)
        self.assertTrue(data['preview'])
        self.assertIn('name', data['preview']['columns'])
        self.assertNotIn('ref', data['preview']['columns'])
        self.assertNotIn('partner_latitude', data['preview']['columns'])
        # steps: a filter and a calculation keep the list; a step cannot
        # name a column left out
        pipeline.steps_json = {'version': 1, 'steps': [
            {'id': 's1', 'type': 'filter',
             'params': {'conditions': [['name', 'neq', 'nobody']]}},
            {'id': 's2', 'type': 'calc',
             'params': {'as': 'lat_twice', 'expression': '[id] * 2'}},
        ]}
        pipeline.action_apply()
        clean = self._columns(pipeline._clean_view_name())
        self.assertIn('lat_twice', clean)
        self.assertIn('name', clean)
        self.assertNotIn('ref', clean)
        self.assertNotIn('partner_latitude', clean)
        for column in ('ref', 'partner_latitude'):
            pipeline.steps_json = {'version': 1, 'steps': [
                {'id': 's1', 'type': 'rename',
                 'params': {'map': {column: 'renamed'}}}]}
            with self.assertRaisesRegex(UserError, 'unknown column'):
                pipeline.compile_sql()

    def test_71b_an_old_clean_view_and_the_end_migrate(self):
        """A clean view made by the old `SELECT *`: its schema still never
        offers the non-exportable column, and the end-migrate re-applies the
        pipeline and re-creates the existing silver view without them."""
        import importlib.util
        import os
        from odoo.modules.module import get_module_path
        self._mark()
        pipeline = self.env['bi.pipeline'].create({
            'source_id': self.source_partner.id})
        pipeline.action_apply()
        view = pipeline._clean_view_name()
        self.dataset._recreate_silver_view()
        # put the old shape back by hand
        self.env.cr.execute('DROP VIEW %s CASCADE' % view)
        self.env.cr.execute('CREATE VIEW %s AS (SELECT * FROM res_partner)'
                            % view)
        self.assertIn('ref', self._columns(view))
        self.source_partner.invalidate_recordset(['has_active_pipeline'])
        names = {c['name'] for c in self.source_partner._fetch_schema()}
        self.assertNotIn('ref', names)
        self.dataset._recreate_silver_view()
        # the end-migrate
        path = os.path.join(get_module_path('biz_bi'), 'migrations',
                            '19.0.1.7.3', 'end-rebuild-sql-layer.py')
        spec = importlib.util.spec_from_file_location('fs5_bi_end', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.1.7.2')
        self.assertNotIn('ref', self._columns(view))
        self.assertNotIn('partner_latitude', self._columns(view))
        silver = self._columns(self.dataset._silver_view_name())
        self.assertNotIn('f_%d' % self.f_ref.id, silver)
        self.assertIn('f_%d' % self.f_name.id, silver)
        # a fresh install (no version) does nothing
        module.migrate(self.env.cr, None)
