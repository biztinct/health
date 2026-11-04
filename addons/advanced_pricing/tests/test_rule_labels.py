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
