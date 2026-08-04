# -*- coding: utf-8 -*-
"""Silver-SQL lifecycle predicate: when the root model carries the health
lifecycle `deleted` flag, soft-deleted rows must never enter the dataset —
while archived rows stay (BI's active_test=False contract is untouched)."""
import unittest

from odoo.tests import tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestLifecyclePredicate(BiCase):

    def test_silver_sql_excludes_deleted_root_rows(self):
        deleted_field = self.env['res.partner']._fields.get('deleted')
        if deleted_field is None or not deleted_field.store:
            raise unittest.SkipTest(
                'health_base lifecycle mixin not installed on res.partner')
        # a soft-deleted partner drops out of the silver view…
        self.partners[0].write({'deleted': True})
        # …while an archived one stays (BI counts archived records)
        self.partners[1].write({'active': False})
        self.dataset._recreate_silver_view()
        self.env.cr.execute(
            'SELECT _bi_row_key FROM %s' % self.dataset._silver_view_name())
        rows = {r[0] for r in self.env.cr.fetchall()}
        self.assertNotIn(self.partners[0].id, rows)
        self.assertIn(self.partners[1].id, rows)
        self.assertIn(self.partners[2].id, rows)
