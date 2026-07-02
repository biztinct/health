# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase


class BiCase(TransactionCase):
    """Shared fixture: a 2-node dataset over res.partner joined to
    res.country, with a calculated field — exercises joins, roles,
    translation-free columns and the full publish path without depending
    on any business module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.workspace = env['bi.workspace'].create({
            'name': 'Test Workspace', 'is_default': False})

        cls.country_a = env['res.country'].search([('code', '=', 'VN')])
        cls.country_b = env['res.country'].search([('code', '=', 'AU')])
        cls.partners = env['res.partner'].create([
            {'name': 'BI Test Alpha', 'country_id': cls.country_a.id,
             'partner_latitude': 10.0},
            {'name': 'BI Test Beta', 'country_id': cls.country_a.id,
             'partner_latitude': 20.0},
            {'name': 'BI Test Gamma', 'country_id': cls.country_b.id,
             'partner_latitude': 30.0},
        ])

        cls.source_partner = env['bi.source'].create({
            'name': 'Partners', 'type': 'odoo_model',
            'model_id': env['ir.model']._get_id('res.partner')})
        cls.source_country = env['bi.source'].create({
            'name': 'Countries', 'type': 'odoo_model',
            'model_id': env['ir.model']._get_id('res.country')})

        cls.dataset = env['bi.dataset'].create({
            'name': 'Test Partners', 'workspace_id': cls.workspace.id})
        cls.node_root = env['bi.dataset.node'].create({
            'dataset_id': cls.dataset.id,
            'source_id': cls.source_partner.id, 'is_root': True})
        cls.node_country = env['bi.dataset.node'].create({
            'dataset_id': cls.dataset.id,
            'source_id': cls.source_country.id})
        env['bi.relationship'].create({
            'dataset_id': cls.dataset.id,
            'parent_node_id': cls.node_root.id,
            'child_node_id': cls.node_country.id,
            'parent_field': 'country_id', 'child_field': 'id',
            'cardinality': 'many2one', 'origin': 'manual'})

        (cls.node_root | cls.node_country).action_scan_fields()

        def field(node, technical_name):
            return cls.dataset.field_ids.filtered(
                lambda f: f.node_id == node
                and f.technical_name == technical_name)

        cls.f_name = field(cls.node_root, 'name')
        cls.f_latitude = field(cls.node_root, 'partner_latitude')
        cls.f_country_name = field(cls.node_country, 'name')
        cls.f_create_date = field(cls.node_root, 'create_date')

        # scanner may classify latitude as non-measure; force it for tests
        cls.f_latitude.write({'role': 'measure', 'default_agg': 'sum',
                              'visibility': 'visible'})
        cls.f_country_name.write({'visibility': 'visible'})

        cls.f_calc = env['bi.field'].create({
            'dataset_id': cls.dataset.id,
            'node_id': cls.node_root.id,
            'technical_name': 'calc_double_lat',
            'name': 'Double Latitude',
            'origin': 'calculated',
            'expression': '[partner_latitude] * 2',
            'data_type': 'float',
            'role': 'measure',
            'default_agg': 'sum',
        })

        cls.dataset.action_publish()
        cls.engine = env['bi.query.engine']

    def _base_request(self, **overrides):
        request = {
            'dataset_id': self.dataset.id,
            'dimensions': [{'field_id': self.f_country_name.id}],
            'measures': [{'field_id': self.f_latitude.id, 'agg': 'sum'}],
            'filters': [{'field_id': self.f_name.id, 'op': 'like_i',
                         'value': 'BI Test'}],
            'sort': [{'ref': 'm0', 'dir': 'desc'}],
            'limit': 100,
        }
        request.update(overrides)
        return request
