# -*- coding: utf-8 -*-
"""What the platform link promises, asserted rather than assumed.

Every decision this module makes is a pure function (rail R6), so the whole of
the interesting half is reachable without a registry. The three that are not —
the settings read, the route and the session seam — get one test each.
"""
import json

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.biz_tenancy.models.tenancy import (
    P_BRAND, P_FEATURES, P_NOTICE, P_NOTICE_FROM, P_NOTICE_KIND, P_NOTICE_TO,
    P_RELEASE, P_RELEASES, P_SLUG, P_SUPPORT_ALLOWED, features_signature,
    notice_phase, read_feature_details, read_features, read_notice,
    read_releases,
)


# =========================================================================
#  THE PURE HALF
# =========================================================================
@tagged('post_install', '-at_install')
class TestNoticeRules(TransactionCase):

    NOW = '2026-09-04 12:00:00'

    def test_a_window_that_has_not_started_is_before(self):
        self.assertEqual(
            notice_phase('2026-09-04 22:00:00', '2026-09-05 01:00:00',
                         self.NOW), 'before')

    def test_a_window_we_are_inside_is_during(self):
        self.assertEqual(
            notice_phase('2026-09-04 11:00:00', '2026-09-04 13:00:00',
                         self.NOW), 'during')

    def test_a_window_that_has_finished_is_over(self):
        self.assertEqual(
            notice_phase('2026-09-04 08:00:00', '2026-09-04 09:00:00',
                         self.NOW), 'over')

    def test_a_message_with_no_window_at_all_stands_until_it_is_cleared(self):
        self.assertEqual(notice_phase('', '', self.NOW), 'during')

    def test_a_finished_message_leaves_the_screen_without_anybody_clearing_it(self):
        """The platform is not expected to come back — the reader's side ends
        it. This is the whole reason the end time is read on every load."""
        self.assertIsNone(read_notice(
            'We are updating tonight.', 'maintenance',
            '2026-09-04 08:00:00', '2026-09-04 09:00:00', self.NOW))

    def test_an_empty_message_is_no_message(self):
        self.assertIsNone(read_notice('   ', 'info', '', '', self.NOW))

    def test_an_unknown_kind_is_read_as_information_not_guessed_at(self):
        row = read_notice('Something.', 'shouting', '', '', self.NOW)
        self.assertEqual(row['kind'], 'info')

    def test_a_maintenance_window_we_are_inside_is_happening_now(self):
        row = read_notice('We are updating.', 'maintenance',
                          '2026-09-04 11:00:00', '2026-09-04 13:00:00',
                          self.NOW)
        self.assertTrue(row['live'],
                        'a window we are inside has to say it is happening now')

    def test_a_maintenance_window_still_ahead_is_not_happening_now(self):
        row = read_notice('We are updating.', 'maintenance',
                          '2026-09-04 22:00:00', '2026-09-05 01:00:00',
                          self.NOW)
        self.assertFalse(row['live'])

    def test_an_informational_message_is_never_happening_now(self):
        """"Happening now" is about a pause in the service. A message inside
        its own window is just a message."""
        row = read_notice('New screens are live.', 'info',
                          '2026-09-04 11:00:00', '2026-09-04 13:00:00',
                          self.NOW)
        self.assertFalse(row['live'])

    def test_a_different_message_gets_a_different_identity(self):
        """So that closing one does not close the next."""
        a = read_notice('One.', 'info', '', '', self.NOW)
        b = read_notice('Two.', 'info', '', '', self.NOW)
        self.assertNotEqual(a['id'], b['id'])


@tagged('post_install', '-at_install')
class TestReleaseRules(TransactionCase):

    def test_damage_is_read_as_no_history_and_never_raises(self):
        self.assertEqual(read_releases('{ not json', '2026.09.04'), [])

    def test_two_releases_cut_on_one_day_come_out_in_the_order_they_happened(self):
        rows = read_releases(json.dumps([
            {'name': '2026.09.04', 'date': '2026-09-04'},
            {'name': '2026.09.04-2', 'date': '2026-09-04'},
        ]), '')
        self.assertEqual([r['name'] for r in rows],
                         ['2026.09.04-2', '2026.09.04'])

    def test_the_one_being_run_is_marked_and_only_that_one(self):
        rows = read_releases(json.dumps([
            {'name': '2026.09.04', 'date': '2026-09-04'},
            {'name': '2026.09.01', 'date': '2026-09-01'},
        ]), '2026.09.01')
        self.assertEqual([r['current'] for r in rows], [False, True])

    def test_a_row_with_no_name_is_dropped_rather_than_drawn_blank(self):
        rows = read_releases(json.dumps([{'notes': 'orphan'}]), '')
        self.assertEqual(rows, [])


@tagged('post_install', '-at_install')
class TestFeatureSeam(TransactionCase):
    """SAAS H4c §3.4 — the two directions this fails in, and they differ.

    ⚠ THE DAMAGED CASE CHANGED IN H4c, AND ON PURPOSE. H4a built the seam
    failing OPEN on damage, which is the right instinct for a guard and the
    wrong answer for this question: a settings value that is not readable means
    "I do not know which parts this customer has bought", and answering "all of
    them" hands out a product nobody may have paid for, silently, for as long
    as the damage lasts. Absent still fails open — nobody has said anything
    yet, and that is not damage. Both say which in the log (F53).
    """

    def test_nothing_said_means_everything_is_switched_on(self):
        self.assertEqual(read_features(''), {})
        self.assertEqual(read_feature_details('')['_state'], 'open')

    def test_damage_means_everything_is_switched_OFF(self):
        got = read_features('{{{')
        self.assertNotEqual(got, {},
                            'an unreadable value must not read as "nothing '
                            'is switched off"')
        self.assertFalse(all(got.values()))
        self.assertEqual(read_feature_details('{{{')['_state'], 'closed')

    def test_the_wrong_shape_also_fails_closed(self):
        self.assertEqual(read_feature_details('[1, 2]')['_state'], 'closed')
        self.assertEqual(read_feature_details('"hello"')['_state'], 'closed')

    def test_the_short_form_and_the_long_form_are_both_accepted(self):
        got = read_features(json.dumps({'a': False, 'b': {'on': True}}))
        self.assertEqual(got, {'a': False, 'b': True})

    def test_the_long_form_carries_the_words_the_customer_reads(self):
        detail = read_feature_details(json.dumps(
            {'telehealth': {'on': False, 'name': 'Telehealth',
                            'blurb': 'Video visits.'}}))
        self.assertEqual(detail['telehealth']['name'], 'Telehealth')
        self.assertEqual(detail['telehealth']['blurb'], 'Video visits.')

    def test_the_signature_moves_only_when_the_answer_moves(self):
        """⚠ Ledger F47. The browser watches this string, not the map — a map
        rebuilt on every poll is a new object every minute and would repaint
        the whole left menu once a minute for ever."""
        a = features_signature(read_feature_details(
            json.dumps({'x': {'on': True}, 'y': {'on': False}})))
        b = features_signature(read_feature_details(
            json.dumps({'y': {'on': False}, 'x': {'on': True}})))
        self.assertEqual(a, b, 'the same answer written differently')
        c = features_signature(read_feature_details(
            json.dumps({'x': {'on': False}, 'y': {'on': False}})))
        self.assertNotEqual(a, c)

    def test_the_signature_says_when_it_could_not_tell(self):
        self.assertTrue(
            features_signature(read_feature_details('{{{')).startswith('closed'))


# =========================================================================
#  THE THREE THAT NEED A DATABASE
# =========================================================================
@tagged('post_install', '-at_install')
class TestTenancyState(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Param = self.env['ir.config_parameter'].sudo()
        self.Tenancy = self.env['biz.tenancy']

    def _set(self, key, value):
        row = self.Param.search([('key', '=', key)], limit=1)
        if row:
            row.value = value
        else:
            self.Param.create({'key': key, 'value': value})

    def test_a_key_set_to_empty_is_not_the_same_as_a_key_that_is_absent(self):
        """Ledger F24. `get_param` answers False for both, which is why this
        module never uses it."""
        self.Param.search([('key', '=', P_RELEASE)]).unlink()
        self.assertIsNone(self.Tenancy._row(P_RELEASE),
                          'an absent key must read as None')
        self._set(P_RELEASE, '')
        self.assertEqual(self.Tenancy._row(P_RELEASE), '',
                         'a key set to empty must read as an empty string')

    def test_the_brand_is_a_setting_and_never_a_literal(self):
        self._set(P_BRAND, 'Some Clinic Group')
        self.assertEqual(self.Tenancy.brand(), 'Some Clinic Group')

    def test_a_system_with_no_brand_set_is_described_and_not_named(self):
        self.Param.search([('key', '=', P_BRAND)]).unlink()
        brand = self.Tenancy.brand()
        self.assertTrue(brand)
        for banned in ('Odoo', 'Payobook', 'Viet Uc'):
            self.assertNotIn(banned, brand)

    def test_the_state_carries_every_key_the_browser_starts_from(self):
        state = self.Tenancy.state()
        for key in ('brand', 'release', 'release_notes', 'release_at',
                    'releases', 'notice', 'pushed_at', 'platform_url',
                    'support_email', 'is_platform'):
            self.assertIn(key, state)

    def test_a_message_the_platform_sent_reaches_the_state(self):
        self._set(P_NOTICE, 'We are updating this evening.')
        self._set(P_NOTICE_KIND, 'maintenance')
        self._set(P_NOTICE_FROM, '')
        self._set(P_NOTICE_TO, '')
        notice = self.Tenancy.state()['notice']
        self.assertTrue(notice)
        self.assertEqual(notice['text'], 'We are updating this evening.')
        self.assertEqual(notice['kind'], 'maintenance')

    def test_clearing_the_message_takes_the_bar_away(self):
        self._set(P_NOTICE, 'Something.')
        self.assertTrue(self.Tenancy.state()['notice'])
        self._set(P_NOTICE, '')
        self.assertIsNone(self.Tenancy.state()['notice'])

    def test_the_release_history_comes_back_as_rows(self):
        self._set(P_RELEASE, '2026.09.04')
        self._set(P_RELEASES, json.dumps([
            {'name': '2026.09.04', 'date': '2026-09-04', 'notes': '- One'},
        ]))
        rows = self.Tenancy.state()['releases']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['current'])

    def test_a_system_nobody_provisioned_says_it_is_the_platform(self):
        self.Param.search([('key', '=', P_SLUG)]).unlink()
        self.assertTrue(self.Tenancy.state()['is_platform'])
        self._set(P_SLUG, 'hhh')
        self.assertFalse(self.Tenancy.state()['is_platform'])

    def test_the_features_seam_answers_and_fails_open(self):
        self.Param.search([('key', '=', P_FEATURES)]).unlink()
        self.assertEqual(self.Tenancy.features(), {})


@tagged('post_install', '-at_install')
class TestTenancyRoute(HttpCase):
    """The poll route. An HttpCase here needs `--workers=0` and a
    `--db-filter` naming this database (ledger H32/H55); the deploy wrapper
    adds both."""

    def test_the_poll_route_answers_the_signed_in_reader(self):
        user = self.env['res.users'].sudo().create({
            'name': 'Poll reader', 'login': 'bztn_poll_reader',
            'password': 'bztn-poll-reader-1',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.authenticate(user.login, 'bztn-poll-reader-1')
        res = self.url_open(
            '/biz_tenancy/state',
            data='{"jsonrpc":"2.0","method":"call","params":{}}',
            headers={'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 200, res.text[:400])
        body = res.json()
        self.assertIn('result', body, str(body)[:400])
        self.assertIn('release', body['result'])

    def test_the_route_is_declared_readonly_and_jsonrpc(self):
        """`type='json'` is a deprecated alias on this build (F21), and a route
        that only reads ten settings should say so."""
        from odoo.addons.biz_tenancy.controllers.main import BizTenancyController
        routing = BizTenancyController.tenancy_state.original_routing
        self.assertEqual(routing['type'], 'jsonrpc')
        self.assertTrue(routing['readonly'])
        self.assertEqual(routing['auth'], 'user')
