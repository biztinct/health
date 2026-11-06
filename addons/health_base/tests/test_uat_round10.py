# -*- coding: utf-8 -*-
"""UAT round 10, item 3: the Audit Log knows which values are date-times, so
the list shows them in the viewer's time zone (widget `audit_value`); the
stored From/To text stays UTC."""
from datetime import datetime

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAuditLogTimes(TransactionCase):

    def test_datetime_rows_carry_their_type_and_utc_text(self):
        partner = self.env['res.partner'].create({'name': 'R10 Audit Probe'})
        dt_field = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('ttype', '=', 'datetime')], limit=1)
        char_field = self.env['ir.model.fields']._get('res.partner', 'mobile')
        self.env['mail.message'].create({
            'model': 'res.partner', 'res_id': partner.id,
            'message_type': 'notification', 'body': '',
            'tracking_value_ids': [
                Command.create({'field_id': dt_field.id,
                                'old_value_datetime': False,
                                'new_value_datetime': datetime(2026, 11, 12, 2, 0)}),
                Command.create({'field_id': char_field.id,
                                'old_value_char': '', 'new_value_char': '0900000999'}),
            ],
        })
        self.env.flush_all()
        rows = self.env['health.audit.log.view'].search(
            [('model', '=', 'res.partner'), ('res_id', '=', partner.id)])
        by_type = {r.field_type: r for r in rows}
        self.assertIn('datetime', by_type)
        self.assertEqual(by_type['datetime'].new_value, '2026-11-12 02:00:00',
                         'stored text unchanged (UTC); the list converts it')
        self.assertEqual(by_type['char'].new_value, '0900000999')

    def test_list_uses_the_time_zone_widget(self):
        arch = self.env.ref('health_base.view_health_audit_log_list').arch
        self.assertIn('widget="audit_value"', arch)
        self.assertIn('name="field_type"', arch)
