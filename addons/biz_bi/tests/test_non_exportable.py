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
