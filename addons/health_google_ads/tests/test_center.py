# -*- coding: utf-8 -*-
"""GA1-T01 … GA1-T03, GA1-T18, GA1-T19 — the acquisition card and the actions.

The card is the one thing every tenant sees before anything else works, so
these tests are about HONESTY as much as about presence: nothing may claim to
be connected, and nothing that is a secret anywhere may reach the browser.
"""
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.health_google_ads.models.google_ads_account import (
    FINAL_URL_SUFFIX_BASE,
)

from .common import CUSTOMER_A1, GoogleAdsCase


@tagged('post_install', '-at_install')
class TestGoogleAdsCenter(GoogleAdsCase):

    def _cards(self, user=None):
        Conn = self.Conn.with_user(user) if user else self.Conn
        return Conn.center_overview()

    # ==================================================================
    # GA1-T01 — the card is the 9th, after Facebook, and nothing else moved
    # ==================================================================
    def test_ga1_t01_card_is_appended_after_facebook(self):
        cards = self._cards()
        keys = [c['channel'] for c in cards]
        self.assertIn('google_ads', keys)
        self.assertEqual(keys[keys.index('fb') + 1], 'google_ads',
                         'the acquisition card sits immediately after fb')
        card = cards[keys.index('google_ads')]
        self.assertEqual(card['kind'], 'acquisition')
        self.assertEqual(len([c for c in cards
                              if c.get('kind') == 'acquisition']), 1)

        # The eight conversation cards must be BYTE-IDENTICAL to a run with
        # the hook neutralised. Patched with a PLAIN FUNCTION, never
        # `autospec` (ledger §5.76).
        def _no_extra_cards(self):
            return []

        Conn = type(self.env['care.channel.connection'])
        with patch.object(Conn, '_center_extra_cards', _no_extra_cards):
            baseline = self.Conn.center_overview()

        with_card = [c for c in cards
                     if c.get('kind', 'conversation') != 'acquisition']
        self.assertEqual(json.dumps(baseline, default=str, sort_keys=True),
                         json.dumps(with_card, default=str, sort_keys=True),
                         'installing this module must not change any '
                         'existing card by one byte')

    # ==================================================================
    # GA1-T02 — an honest card with no account, and no secret material
    # ==================================================================
    def test_ga1_t02_card_with_no_account_is_honest(self):
        # The fixtures create accounts in both companies, so ask the question
        # on a third, empty one — which is the state every new tenant is in.
        empty = self.env['res.company'].create({'name': 'GADS Empty Co'})
        card = self.env['google.ads.account'].with_company(
            empty)._center_card_payload()

        self.assertEqual(card['channel'], 'google_ads')
        self.assertEqual(card['state_chip'], 'Setup needed')
        self.assertEqual(card['primary_action'], 'connect')
        self.assertEqual(card['primary_label'], 'Set up Google Ads')
        self.assertFalse(card['sendable'], 'Google Ads never sends anything')
        self.assertEqual(card['checks_total'], 0)
        self.assertEqual(card['mode'], 'external_action')
        self.assertEqual(card['action_xmlid'],
                         'health_google_ads.action_google_ads_accounts')
        self.assertFalse(card['connection_id'],
                         'an acquisition card is never a channel connection')

        caps = {c['key']: c for c in card['capabilities']}
        self.assertEqual(caps['website']['status'], 'setup_needed')
        self.assertEqual(caps['reporting']['status'], 'not_connected')
        self.assertEqual(caps['native']['status'], 'unavailable')
        self.assertEqual(caps['native']['status_label'],
                         'Unavailable for healthcare ads')
        self.assertEqual(card['lines'][0], 'Last website lead: No leads received yet')
        self.assertEqual(card['lines'][1], 'Reporting updated: Not synced')

        # Rail R7 — nothing that is a secret anywhere may reach the browser.
        blob = json.dumps(card, default=str)
        for forbidden in ('token', 'secret', 'chs$1$', 'refresh',
                          'client_secret'):
            self.assertNotIn(forbidden, blob,
                             'no credential material may reach the browser')

    def test_ga1_t02b_card_never_says_sent_or_reply(self):
        blob = json.dumps(self.env['google.ads.account']
                          ._center_card_payload(), default=str)
        for forbidden in ('Sent', 'Reply', 'Compose'):
            self.assertNotIn(forbidden, blob)

    # ==================================================================
    # GA1-T03 — company scoping and the group gate
    # ==================================================================
    def test_ga1_t03_card_is_company_scoped(self):
        mine = self.env['google.ads.account'].with_company(
            self.company)._center_card_payload()
        theirs = self.env['google.ads.account'].with_company(
            self.company2)._center_card_payload()
        self.assertEqual(mine['resource_line'], '2 accounts',
                         'company 1 owns A1 and A2')
        self.assertIn('GADS B1', theirs['resource_line'],
                      'company 2 sees only B1')
        self.assertNotIn('GADS A1', theirs['resource_line'])
        self.assertNotIn('GADS A2', theirs['resource_line'])

    def test_ga1_t03b_plain_crm_user_still_gets_the_center_gate(self):
        with self.assertRaises(UserError):
            self.Conn.with_user(self.crm_user).center_overview()

    # ==================================================================
    # GA1-T18 — labels, actions
    # ==================================================================
    def test_ga1_t18_no_field_label_says_odoo(self):
        """White-label rule, on the fields THIS module declares.

        The mixin and magic fields are core's own text and are excluded
        deliberately — this phase neither owns nor may rewrite them.
        """
        inherited = set(self.env['mail.thread']._fields) \
            | set(self.env['mail.activity.mixin']._fields) \
            | {'id', 'display_name', 'create_uid', 'create_date',
               'write_uid', 'write_date', '__last_update'}
        checked = 0
        for model, prefix in (('crm.lead', 'google_ads_'),
                              ('health.lead.touchpoint', 'google_ads_'),
                              ('google.ads.account', ''),
                              ('google.ads.campaign', '')):
            described = self.env[model].sudo().fields_get()
            for name, spec in described.items():
                if prefix and not name.startswith(prefix):
                    continue
                if not prefix and name in inherited:
                    continue
                checked += 1
                for key in ('string', 'help'):
                    text = spec.get(key) or ''
                    self.assertNotIn(
                        'odoo', text.lower(),
                        '%s.%s %s must not name the platform' % (model, name, key))
                self.assertTrue(spec.get('string'),
                                '%s.%s needs a plain-English label' % (model, name))
        self.assertTrue(checked, 'no field was actually inspected')

    def test_ga1_t18b_view_leads_action_names_the_account(self):
        action = self.account_a1.action_view_leads()
        self.assertEqual(action['res_model'], 'crm.lead')
        self.assertIn(('google_ads_origin', '!=', False), action['domain'])
        self.assertIn(('google_ads_account_id', '=', self.account_a1.id),
                      action['domain'])
        self.assertEqual(action['context'].get('search_default_google_ads_first'), 1)

        touches = self.account_a1.action_view_touchpoints()
        self.assertEqual(touches['res_model'], 'health.lead.touchpoint')
        self.assertIn(('google_ads_account_id', '=', self.account_a1.id),
                      touches['domain'])

    def test_ga1_t18c_open_setup_opens_the_single_account(self):
        empty = self.env['res.company'].create({'name': 'GADS Setup Co'})
        Account = self.env['google.ads.account'].with_company(empty)
        listing = Account.action_open_setup()
        self.assertFalse(listing.get('res_id'),
                         'with no account the button opens the list')

        one = Account.create({'name': 'GADS Only', 'company_id': empty.id})
        form = Account.action_open_setup()
        self.assertEqual(form.get('res_id'), one.id,
                         'with exactly one account the button opens it')

        Account.create({'name': 'GADS Second', 'company_id': empty.id,
                        'customer_id': '4444444444'})
        again = Account.action_open_setup()
        self.assertFalse(again.get('res_id'),
                         'with two accounts the button opens the list again')

    # ==================================================================
    # GA1-T19 — the final URL suffix
    # ==================================================================
    def test_ga1_t19_final_url_suffix(self):
        self.assertEqual(
            self.account_a1.final_url_suffix,
            FINAL_URL_SUFFIX_BASE + '&h19_gads_customer_id=' + CUSTOMER_A1)

        draft = self.env['google.ads.account'].create({
            'name': 'GADS Draft suffix',
            'company_id': self.env['res.company'].create(
                {'name': 'GADS Suffix Co'}).id})
        self.assertEqual(draft.final_url_suffix, FINAL_URL_SUFFIX_BASE)

        for expected in ('utm_source=google', 'utm_medium=cpc',
                         '{campaignid}', '{adgroupid}', '{creative}'):
            self.assertIn(expected, self.account_a1.final_url_suffix)
        # `{campaignname}` is not a Google parameter and must never be invented.
        self.assertNotIn('{campaignname}', self.account_a1.final_url_suffix)
        # And it can never carry anything secret.
        self.assertNotIn('secret', self.account_a1.final_url_suffix.lower())
