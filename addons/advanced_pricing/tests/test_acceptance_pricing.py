from odoo.tests import common, tagged


@tagged('post_install', '-at_install', 'uat_pricing')
class TestAcceptancePricing(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.engine = self.env['advanced.pricing.engine'].create({'name': 'UAT regression'})
        self.rule = self.env['advanced.pricing.rule'].create({
            'name': 'UAT charge', 'engine_id': self.engine.id,
            'action_type': 'add', 'action_value': 50000,
        })

    def test_existing_unit_charge_unchanged(self):
        self.assertEqual(self.rule.apply_action(150000, {'quantity': 2}), 200000)

    def test_once_per_line(self):
        self.rule.action_scope = 'line'
        self.assertEqual(self.rule.apply_action(150000, {'quantity': 2}) * 2, 350000)

    def test_subsequent_units_keep_home_fee(self):
        self.rule.write({'action_type': 'subsequent_fixed', 'action_value': 50000})
        # 90k base ×2 + 70k home fee; replace only the second base unit.
        self.assertEqual(self.rule.apply_action(125000, {
            'quantity': 2, 'base_unit_price': 90000}) * 2, 210000)

    def test_subsequent_single_unit_unchanged(self):
        self.rule.write({'action_type': 'subsequent_fixed', 'action_value': 50000})
        self.assertEqual(self.rule.apply_action(90000, {'quantity': 1, 'base_unit_price': 90000}), 90000)

    def test_booking_fee_allocated_once(self):
        self.rule.action_scope = 'booking'
        ctx = {'quantity': 2, 'booking_lines': [
            {'line_id': 10, 'product_id': 1}, {'line_id': 11, 'product_id': 1}]}
        self.assertEqual(self.rule.apply_action(100000, dict(ctx, line_id=10)) * 2, 250000)
        self.assertEqual(self.rule.apply_action(100000, dict(ctx, line_id=11)) * 2, 200000)

    def test_extra_bottles_fee_once_per_line(self):
        self.rule.write({'action_scope': 'line', 'action_type': 'per_unit',
                         'per_unit_field': 'iv_fluid_count', 'iv_fluid_count_min': 2,
                         'action_value': 150000})
        self.assertEqual(self.rule.apply_action(275000, {'quantity': 2, 'iv_fluid_count': 2}) * 2, 700000)

    def test_base_discount_and_invoice_agree(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'UAT discount basis', 'discount_on_base_only': True})
        order = self.env['sale.order'].new({'pricelist_id': pricelist.id})
        line = self.env['sale.order.line'].new({
            'order_id': order.id, 'base_price': 600000, 'price_unit': 800000,
            'product_uom_qty': 1, 'discount': 10})
        self.assertEqual(line._base_discount_tax_values(), {'price_unit': 740000, 'discount': 0})
        pricelist.discount_on_base_only = False
        self.assertEqual(line._base_discount_tax_values(), {})
