# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import BiCase


@tagged('biz_bi', 'post_install', '-at_install')
class TestAiCoerce(BiCase):
    """LLM proposals with junk-but-recoverable grain/agg sentinels must be
    cleaned by _coerce_config, not rejected wholesale (the "Invalid date
    grain 'none'" defect: the model emits grain "none" instead of omitting
    the key)."""

    def _proposal(self, **overrides):
        config = {
            'name': 'Leads by source',
            'chart_type': 'table',
            'slots': {
                'x': [{'field_id': self.f_country_name.id,
                       'grain': 'none'}],
                'values': [{'field_id': self.f_latitude.id, 'agg': 'none'}],
                'series': [],
            },
            'filters': [],
        }
        config.update(overrides)
        return config

    def test_junk_grain_and_agg_are_stripped(self):
        ai = self.env['bi.ai']
        config = ai._validate_chart_config(self.dataset, self._proposal())
        self.assertNotIn('grain', config['slots']['x'][0])
        self.assertNotIn('agg', config['slots']['values'][0])

    def test_junk_grain_on_date_dimension(self):
        # grain "none" on a real date field: strip it, keep the field
        ai = self.env['bi.ai']
        config = ai._validate_chart_config(self.dataset, self._proposal(
            slots={
                'x': [{'field_id': self.f_create_date.id, 'grain': 'null'}],
                'values': [{'field_id': self.f_latitude.id, 'agg': 'sum'}],
                'series': [],
            }))
        entry = config['slots']['x'][0]
        self.assertEqual(entry['field_id'], self.f_create_date.id)
        self.assertNotIn('grain', entry)

    def test_valid_grain_and_agg_survive(self):
        ai = self.env['bi.ai']
        config = ai._validate_chart_config(self.dataset, self._proposal(
            slots={
                'x': [{'field_id': self.f_create_date.id, 'grain': 'month'}],
                'values': [{'field_id': self.f_latitude.id,
                            'agg': 'count_distinct'}],
                'series': [],
            }))
        self.assertEqual(config['slots']['x'][0]['grain'], 'month')
        self.assertEqual(config['slots']['values'][0]['agg'],
                         'count_distinct')
