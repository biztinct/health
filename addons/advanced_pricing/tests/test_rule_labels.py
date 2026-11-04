# -*- coding: utf-8 -*-
"""UAT video item 13 (2026-11-04): the Pricing tab named an extra-unit rule
"589" — the last part of "Client UAT - Subsequent units - 589", a product id.
A rule is explained by its words, never by a bare number."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRuleLabels(TransactionCase):

    def _rule(self, name, action_type='add', value=0.0):
        return self.env['advanced.pricing.rule'].with_context(lang='en_US').new({
            'name': name, 'action_type': action_type, 'action_value': value})

    def test_1_trailing_number_is_not_the_label(self):
        rule = self._rule('Client UAT - Subsequent units - 589', 'subsequent_fixed', 50000)
        self.assertEqual(rule._pricing_rule_short_label(), 'Subsequent units')
        self.assertEqual(rule._pricing_rule_action_desc(), '50,000 đ from the 2nd unit')

    def test_2_region_prefix_still_dropped(self):
        rule = self._rule('Hanoi - Ultrasound - Is Service at home', 'add', 200000)
        self.assertEqual(rule._pricing_rule_short_label(), 'Is Service at home')
        self.assertEqual(rule._pricing_rule_action_desc(), '+200,000 đ')

    def test_3_only_a_number_falls_back_to_the_action(self):
        rule = self._rule('593', 'subsequent_fixed', 50000)
        self.assertEqual(rule._pricing_rule_short_label(), 'Set Price for Subsequent Units')


@tagged('post_install', '-at_install')
class TestBreakdownUnits(TransactionCase):
    """UAT 2026-11-04 round 5: quotes show the unit (Wound, Visit…) like invoices."""

    def test_breakdown_carries_the_unit(self):
        uom = self.env['uom.uom'].search([], limit=1)
        product = self.env['product.product'].create({
            'name': 'Unit Probe', 'type': 'service', 'list_price': 100.0, 'uom_id': uom.id})
        engine = self.env['advanced.pricing.engine'].create({'name': 'Unit probe engine'})
        pricelist = self.env['product.pricelist'].create({'name': 'Unit probe list',
                                                          'advanced_engine_id': engine.id})
        partner = self.env['res.partner'].create({'name': 'Unit Probe Client'})
        order = self.env['sale.order'].create({
            'partner_id': partner.id, 'pricelist_id': pricelist.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 3})]})
        if not order.use_advanced_pricing:
            self.skipTest('advanced pricing is off for this quote')
        data = order._build_pricing_breakdown_data()
        line = next(iter(data['lines'].values()))
        self.assertEqual(line['uom'], uom.name)
        self.assertIn('3 %s' % uom.name, order._build_pricing_breakdown_html())

