import unittest

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReadableHistory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'care.channel.audit' not in cls.env:
            raise unittest.SkipTest('Channel connections are optional for the workspace')
        cls.admin = cls.env.ref('base.user_admin')
        cls.workspace = cls.env['health.tenant.workspace'].with_user(cls.admin).with_context(lang='en_US')
        cls.connection = cls.env['care.channel.connection'].sudo().create({
            'channel': 'zalo', 'account_label': 'History QA account',
            'company_id': cls.admin.company_id.id,
        })

    def _event(self, **values):
        return self.env['care.channel.audit'].sudo().create({
            'event': 'webhook_ignored', 'channel': 'zalo',
            'connection_id': self.connection.id,
            'company_id': self.admin.company_id.id,
            'user_id': self.env.ref('base.public_user').id,
            'ts': '2098-01-01 12:00:00',
            'detail_redacted': 'state disabled',
            **values,
        })

    def test_readable_event_timestamp_and_actor(self):
        event = self._event()
        for source in ('channels', 'all'):
            rows = self.workspace.history(source=source, query='History QA account')['rows']
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['title'], 'Zalo (History QA account): Incoming update ignored because the connection is disabled')
            self.assertEqual(row['actor'], 'External service')
            self.assertEqual(row['date'], fields.Datetime.to_string(event.ts))
            self.assertFalse(row['detail'])
            self.assertNotIn('care.channel.audit', row['title'])

    def test_search_filters_before_the_page_limit(self):
        older = self._event()
        for _ in range(60):
            self._event(event='test_ok', ts='2098-01-02 12:00:00')
        rows = self.workspace.history(source='channels', query='ZALO disabled')['rows']
        self.assertEqual([row['key'] for row in rows], ['channels:%s' % older.id])
        first = self.workspace.history(source='channels', query='History QA passed')
        second = self.workspace.history(source='channels', query='History QA passed', offset=50)
        self.assertEqual(len(first['rows']), 50)
        self.assertTrue(first['more'])
        self.assertEqual(len(second['rows']), 10)
        self.assertFalse(second['more'])
        self.assertFalse({row['key'] for row in first['rows']} & {row['key'] for row in second['rows']})

    def test_provider_responses_and_unknown_codes_stay_private(self):
        self._event(event='health_check', user_id=1,
                    detail_redacted='failure #72: provider-private-response-marker')
        self._event(event='future_private_event_code', user_id=self.admin.id)
        rows = self.workspace.history(source='channels', query='History QA account')['rows']
        self.assertEqual(len(rows), 2)
        self.assertTrue(any(row['title'].endswith('Connection check failed') and row['actor'] == 'System' for row in rows))
        self.assertTrue(any(row['title'].endswith('Connection activity recorded') and row['actor'] == self.admin.name for row in rows))
        self.assertNotIn('provider-private-response-marker', str(rows))
        self.assertNotIn('future_private_event_code', str(rows))
        self.assertTrue(all(not row['detail'] for row in rows))

    def test_other_company_and_restricted_account_names_are_hidden(self):
        visible = self._event()
        other = self.env['res.company'].create({'name': 'History QA other company'})
        self._event(company_id=other.id)
        rows = self.workspace.history(source='channels', query='History QA account')['rows']
        self.assertEqual([row['key'] for row in rows], ['channels:%s' % visible.id])
        self.env['ir.rule'].create({
            'name': 'History QA hidden connection',
            'model_id': self.env['ir.model']._get_id('care.channel.connection'),
            'domain_force': "[('id', '!=', %d)]" % self.connection.id,
        })
        rows = self.workspace.history(source='channels', query='Zalo disabled')['rows']
        row = next(row for row in rows if row['key'] == 'channels:%s' % visible.id)
        self.assertEqual(row['title'], 'Zalo: Incoming update ignored because the connection is disabled')
        self.assertFalse(self.workspace.history(source='channels', query='History QA account')['rows'])

    def test_vietnamese_summary_and_search(self):
        if not self.env['res.lang'].search_count([('code', '=', 'vi_VN')]):
            self.skipTest('Vietnamese is not installed')
        event = self._event()
        rows = self.workspace.with_context(lang='vi_VN').history(source='channels', query='Zalo đã bị tắt')['rows']
        self.assertEqual([row['key'] for row in rows], ['channels:%s' % event.id])
        self.assertIn('Đã bỏ qua cập nhật đến vì kết nối đã bị tắt', rows[0]['title'])
        self.assertEqual(rows[0]['actor'], 'Dịch vụ bên ngoài')
