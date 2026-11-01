from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestQuotationCatchment(TransactionCase):
    def test_sales_manager_cannot_read_other_catchment_quotes_or_lines(self):
        areas = self.env['health.catchment.province'].create([
            {'name': 'Quote scope A', 'code': 'QSA'},
            {'name': 'Quote scope B', 'code': 'QSB'},
        ])
        partners = self.env['res.partner'].create([
            {'name': 'Quote scope A', 'catchment_province_id': areas[0].id},
            {'name': 'Quote scope B', 'catchment_province_id': areas[1].id},
        ])
        orders = self.env['sale.order'].create([
            {'partner_id': p.id, 'order_line': [(0, 0, {
                'name': 'Scope test service', 'display_type': 'line_note',
            })]} for p in partners
        ])
        for index, area in enumerate(areas):
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'Quote scope manager', 'login': 'quote.scope.%s' % area.id,
                'catchment_province_id': area.id,
                'group_ids': [(6, 0, [
                    self.env.ref('health_base.group_healthcare_operations_manager').id,
                    self.env.ref('sales_team.group_sale_manager').id,
                ])],
            })
            own, other = orders[index], orders[1 - index]
            self.assertEqual(orders.with_user(user).search([
                ('id', 'in', orders.ids)]), own)
            own.with_user(user).read(['name'])
            own.with_user(user).write({'note': 'Allowed'})
            for record in (other, other.order_line):
                with self.assertRaises(AccessError):
                    record.with_user(user).read(['name'])
                with self.assertRaises(AccessError):
                    record.with_user(user).write({'name': 'Denied'})
