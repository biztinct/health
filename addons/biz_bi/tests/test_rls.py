# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestRls(BiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.restricted_user = env['res.users'].create({
            'name': 'BI Restricted', 'login': 'bi_restricted',
            'group_ids': [(6, 0, [
                env.ref('base.group_user').id,
                env.ref('biz_bi.group_bi_viewer').id,
            ])],
        })
        cls.admin_user = env['res.users'].create({
            'name': 'BI Admin User', 'login': 'bi_admin_user',
            'group_ids': [(6, 0, [
                env.ref('base.group_user').id,
                env.ref('biz_bi.group_bi_admin').id,
            ])],
        })

    def test_row_rule_filters_rows(self):
        """A row rule limiting the viewer to VN partners must halve totals."""
        self.env['bi.access.rule'].create({
            'name': 'VN only',
            'dataset_id': self.dataset.id,
            'rule_type': 'row',
            'user_ids': [(6, 0, [self.restricted_user.id])],
            'domain_json': [[self.f_country_name.id, 'eq',
                             self.country_a.name]],
        })
        engine = self.engine.with_user(self.restricted_user)
        result = engine.run(self._base_request(dimensions=[]))
        self.assertEqual(result['rows'][0][0], 30.0)  # VN partners only

        # unrestricted admin still sees everything
        admin_result = self.engine.with_user(self.admin_user).run(
            self._base_request(dimensions=[]))
        self.assertEqual(admin_result['rows'][0][0], 60.0)

    def test_rls_users_never_share_cache(self):
        self.env['bi.access.rule'].create({
            'name': 'VN only',
            'dataset_id': self.dataset.id,
            'rule_type': 'row',
            'user_ids': [(6, 0, [self.restricted_user.id])],
            'domain_json': [[self.f_country_name.id, 'eq',
                             self.country_a.name]],
        })
        request = self._base_request(dimensions=[])
        unrestricted = self.engine.run(request)
        restricted = self.engine.with_user(self.restricted_user).run(request)
        self.assertEqual(unrestricted['rows'][0][0], 60.0)
        self.assertEqual(restricted['rows'][0][0], 30.0)

    def test_column_mask_hide(self):
        self.env['bi.access.rule'].create({
            'name': 'Mask latitude',
            'dataset_id': self.dataset.id,
            'rule_type': 'column',
            'mask_mode': 'hide',
            'user_ids': [(6, 0, [self.restricted_user.id])],
            'field_ids': [(6, 0, [self.f_latitude.id])],
        })
        # explicit reference errors
        with self.assertRaises(UserError):
            self.engine.with_user(self.restricted_user).run(
                self._base_request())
        # metadata excludes the field
        metadata = self.dataset.with_user(
            self.restricted_user).get_builder_metadata()
        field_ids = [f['id'] for f in metadata['fields']]
        self.assertNotIn(self.f_latitude.id, field_ids)
        # admins unaffected
        result = self.engine.with_user(self.admin_user).run(
            self._base_request())
        self.assertNotIn('error', result)

    def test_column_mask_null(self):
        self.env['bi.access.rule'].create({
            'name': 'Null latitude',
            'dataset_id': self.dataset.id,
            'rule_type': 'column',
            'mask_mode': 'null',
            'user_ids': [(6, 0, [self.restricted_user.id])],
            'field_ids': [(6, 0, [self.f_latitude.id])],
        })
        result = self.engine.with_user(self.restricted_user).run(
            self._base_request(dimensions=[]))
        self.assertEqual(result['rows'][0][0], None)

    def test_variable_substitution(self):
        """user.id substitution compiles and filters (no partner matches the
        restricted user's id as latitude — zero rows aggregate to None)."""
        self.env['bi.access.rule'].create({
            'name': 'Own rows only',
            'dataset_id': self.dataset.id,
            'rule_type': 'row',
            'user_ids': [(6, 0, [self.restricted_user.id])],
            'domain_json': [[self.f_latitude.id, 'eq', 'user.id']],
        })
        result = self.engine.with_user(self.restricted_user).run(
            self._base_request(dimensions=[]))
        self.assertEqual(result['rows'][0][0], None)

    def test_sensitive_fields_excluded_from_dataset_card(self):
        self.f_latitude.visibility = 'sensitive'
        card = self.dataset.get_dataset_card()
        refs = [f['ref'] for f in card['fields']]
        self.assertNotIn(self.f_latitude.id, refs)
