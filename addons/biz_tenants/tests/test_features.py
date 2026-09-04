# -*- coding: utf-8 -*-
"""The feature switches, from the platform's side. SAAS H4c §5.6 and §5.7.

The interesting half is what is WRITTEN and what is SENT: the answer lives on
the platform and reaches the customer as one setting through the single door.
So the customer's own database is stood in for by a patch on `push_settings`,
and everything else here is real.
"""
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import tenants_common as common


@tagged('post_install', '-at_install')
class TestFeatureCatalogue(TransactionCase):

    def test_the_catalogue_is_the_product_s_and_it_is_seeded(self):
        rows = self.env['biz.feature'].catalogue()
        keys = set(rows.mapped('key'))
        self.assertEqual(keys, {f['key'] for f in common.features()},
                         'the table and the registration have drifted apart')

    def test_seeding_twice_creates_nothing_the_second_time(self):
        Feature = self.env['biz.feature']
        Feature.ensure_seeded()
        before = Feature.search_count([])
        self.assertFalse(Feature.ensure_seeded())
        self.assertEqual(Feature.search_count([]), before)

    def test_every_switch_says_what_a_customer_would_lose(self):
        """The blurb is the sentence somebody in the clinic reads when they
        follow an old link to a screen that is closed, so an empty one is a
        page that says nothing."""
        for row in self.env['biz.feature'].catalogue():
            self.assertTrue(row.name)
            self.assertGreater(len(row.blurb or ''), 40, row.key)
            self.assertNotIn('odoo', (row.blurb or '').lower(), row.key)
            self.assertNotIn('odoo', (row.name or '').lower(), row.key)

    def test_two_switches_cannot_share_a_name(self):
        """⚠ Ledger H63: `_sql_constraints` as a LIST is inert on this build
        and fails silently, so the constraint is asserted in the catalogue as
        well as by the refusal — a refusal can come from somewhere else and
        look identical."""
        self.env.cr.execute(
            "SELECT conname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = 'biz_feature' AND c.contype = 'u'")
        self.assertTrue(self.env.cr.fetchall(),
                        'biz.feature has no unique constraint in the database')

    def test_the_data_file_calls_a_method_that_carries_the_model_marker(self):
        """⚠ Ledger F45. A `<function>` with no arguments reads the FIRST
        argument as the records to call the method on unless the method carries
        `@api.model`; without it the upgrade dies naming the XML line, not the
        method."""
        method = type(self.env['biz.feature']).ensure_seeded
        self.assertTrue(getattr(method, '_api_model', False)
                        or getattr(method, '_api', None) == 'model',
                        'ensure_seeded has lost its @api.model marker')


@tagged('post_install', '-at_install')
class TestFeatureSwitches(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['biz.feature'].ensure_seeded()
        self.tenant = self.env['biz.tenant'].create({
            'name': 'A customer', 'slug': 'fxprobe', 'state': 'live',
        })
        self.key = self.env['biz.feature'].catalogue()[0].key
        self.pushed = []

        def fake_push(target, values):
            self.pushed.append((target, dict(values)))
            return {'ok': True, 'database': 'fxprobe', 'label': 'A customer',
                    'reason': '', 'keys': sorted(values)}

        patcher = patch.object(type(self.env['biz.tenants']), 'push_settings',
                               side_effect=fake_push)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.service = self.env['biz.tenants']

    # ------------------------------------------------------------ the answer
    def test_a_customer_with_no_row_has_everything(self):
        data = self.service.features_data()
        answers = data['answers'][str(self.tenant.id)]
        self.assertTrue(all(a['on'] for a in answers.values()))
        self.assertFalse(any(a['decided'] for a in answers.values()),
                         'nobody has decided anything yet')

    def test_switching_one_off_is_recorded_and_sent(self):
        res = self.service.feature_set(self.tenant.id, self.key, False,
                                       'not on their plan')
        self.assertTrue(res['changed'])
        self.assertFalse(res['answers'][self.key]['on'])
        self.assertEqual(res['answers'][self.key]['reason'],
                         'not on their plan')
        self.assertEqual(len(self.pushed), 1)
        _target, values = self.pushed[0]
        payload = json.loads(values[common.T_FEATURES])
        self.assertFalse(payload[self.key]['on'])
        self.assertTrue(payload[self.key]['name'],
                        'the customer is sent the NAME as well as the answer, '
                        'so their own switched-off page can say it')

    def test_the_reason_is_written_on_their_own_log(self):
        self.service.feature_set(self.tenant.id, self.key, False, 'trial ended')
        self.assertIn('trial ended', self.tenant.provision_log)

    def test_switching_it_back_on_sends_again(self):
        self.service.feature_set(self.tenant.id, self.key, False, '')
        self.service.feature_set(self.tenant.id, self.key, True, '')
        self.assertEqual(len(self.pushed), 2)
        payload = json.loads(self.pushed[-1][1][common.T_FEATURES])
        self.assertTrue(payload[self.key]['on'])

    def test_setting_the_same_answer_twice_changes_nothing_but_still_tells_them(self):
        """The push happens anyway, on purpose: pressing it again is what
        somebody does when they think a customer did not get the message."""
        self.service.feature_set(self.tenant.id, self.key, False, 'x')
        second = self.service.feature_set(self.tenant.id, self.key, False, 'x')
        self.assertFalse(second['changed'])
        self.assertEqual(len(self.pushed), 2)

    def test_one_answer_per_customer_per_part(self):
        self.service.feature_set(self.tenant.id, self.key, False, '')
        self.service.feature_set(self.tenant.id, self.key, True, '')
        rows = self.env['biz.tenant.feature'].search([
            ('tenant_id', '=', self.tenant.id)])
        self.assertEqual(len(rows), 1)

    def test_a_closed_customer_is_refused_by_name(self):
        self.tenant.write({'state': 'decommissioned'})
        with self.assertRaises(UserError) as caught:
            self.service.feature_set(self.tenant.id, self.key, False, '')
        self.assertIn('closed down', str(caught.exception))

    def test_a_part_this_product_does_not_have_is_refused_by_name(self):
        with self.assertRaises(UserError) as caught:
            self.service.feature_set(self.tenant.id, 'no_such_part', False, '')
        self.assertIn('no_such_part', str(caught.exception))

    # ------------------------------------------------------------ bulk
    def test_a_whole_column_moves_at_once(self):
        res = self.service.feature_set_column(self.tenant.id, False, 'paused')
        self.assertEqual(res['changed'], len(self.env['biz.feature'].catalogue()))
        payload = json.loads(self.pushed[-1][1][common.T_FEATURES])
        self.assertTrue(all(not v['on'] for v in payload.values()))

    def test_a_whole_row_moves_across_every_live_customer(self):
        other = self.env['biz.tenant'].create({
            'name': 'Another', 'slug': 'fxprobetwo', 'state': 'live'})
        live = self.env['biz.tenant'].search_count([('state', '=', 'live')])
        res = self.service.feature_set_row(self.key, False, 'not sold')
        # EVERY live customer, not two: this machine may already have real
        # ones on it, and a test that counted only its own would pass while
        # the row action quietly skipped them.
        self.assertEqual(res['changed'], live)
        self.assertEqual(res['told'], live)
        answers = self.service._feature_answers(self.tenant | other)
        for tid in (self.tenant.id, other.id):
            self.assertFalse(answers[tid][self.key]['on'])

    def test_a_customer_that_could_not_be_told_is_reported_not_hidden(self):
        def refuses(target, values):
            return {'ok': False, 'database': 'fxprobe', 'label': 'A customer',
                    'reason': 'they do not have the platform link yet'}
        with patch.object(type(self.env['biz.tenants']), 'push_settings',
                          side_effect=refuses):
            res = self.service.feature_set_row(self.key, False, '')
        self.assertEqual(res['told'], 0)
        self.assertTrue(res['skipped'])
        self.assertIn('platform link', res['skipped'][0]['reason'])

    def test_the_repair_button_tells_everybody_again(self):
        res = self.service.features_push_all()
        self.assertGreaterEqual(res['sent'], 1)


@tagged('post_install', '-at_install')
class TestFeaturePreview(TransactionCase):
    """The miniature beside the matrix — the hero's right-hand side."""

    def setUp(self):
        super().setUp()
        self.env['biz.feature'].ensure_seeded()
        self.tenant = self.env['biz.tenant'].create({
            'name': 'A customer', 'slug': 'fxprev', 'state': 'live'})
        self.service = self.env['biz.tenants']

    def test_with_no_product_registered_it_says_so_rather_than_drawing_nothing(self):
        """An empty menu drawn without a word reads as a loss; a sentence
        saying nobody has described this product reads as the truth."""
        with patch.object(common, 'menu_preview', return_value=None):
            preview = self.service.feature_preview(self.tenant.id)
        self.assertFalse(preview['known'])
        self.assertTrue(preview['note'])

    def test_it_draws_what_the_product_hands_over(self):
        sections = [{'key': 'a', 'label': 'A', 'show_label': True,
                     'restricted': False,
                     'items': [{'id': 1, 'label': 'One', 'icon': '',
                                'state': 'on', 'children': []},
                               {'id': 2, 'label': 'Two', 'icon': '',
                                'state': 'hidden', 'children': []}]}]
        with patch.object(common, 'menu_preview', return_value=sections):
            preview = self.service.feature_preview(self.tenant.id)
        self.assertTrue(preview['known'])
        self.assertEqual(preview['hidden'], 1)

    def test_a_product_whose_preview_raises_does_not_take_the_screen_down(self):
        def boom(env, off):
            raise ValueError('the menu blew up')
        previous = common._MENU_PREVIEW[0]
        common._MENU_PREVIEW[0] = boom
        try:
            preview = self.service.feature_preview(self.tenant.id)
        finally:
            common._MENU_PREVIEW[0] = previous
        self.assertFalse(preview['known'],
                         'a broken preview is drawn as "not known", never as '
                         'a stack trace on the matrix')
