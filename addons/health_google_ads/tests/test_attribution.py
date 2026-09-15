# -*- coding: utf-8 -*-
"""GA1-T04 … GA1-T11, GA1-T16, GA1-T20 — what an ad click leaves behind.

The whole point of the phase is that an identifier a Google ad carried is
still readable on the enquiry afterwards, so these tests assert on the ROWS,
never on the return envelope alone.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.health_google_ads.services import attribution

from .common import (
    BIG_CAMPAIGN_ID,
    CUSTOMER_A1,
    CUSTOMER_B1,
    OTHER_CAMPAIGN_ID,
    GoogleAdsCase,
)


@tagged('post_install', '-at_install')
class TestGoogleAdsAttribution(GoogleAdsCase):

    # ==================================================================
    # GA1-T11 — the pure helpers (no ORM)
    # ==================================================================
    def test_ga1_t11_provider_ids_stay_strings(self):
        self.assertEqual(attribution.norm_customer_id('123-456-7890'),
                         '1234567890')
        self.assertFalse(attribution.norm_customer_id('123'))
        self.assertFalse(attribution.norm_customer_id(None))
        self.assertFalse(attribution.norm_customer_id(''))

        # Rail R3: byte equality on a 19-digit id, and no int() anywhere.
        self.assertEqual(attribution.norm_provider_id(BIG_CAMPAIGN_ID),
                         BIG_CAMPAIGN_ID)
        self.assertIsInstance(attribution.norm_provider_id(BIG_CAMPAIGN_ID),
                              str)
        # Over the 32-digit cap, non-digits, and the empties.
        self.assertFalse(attribution.norm_provider_id('12' * 40))
        self.assertFalse(attribution.norm_provider_id('abc'))
        self.assertFalse(attribution.norm_provider_id(None))
        # An int is accepted, and comes back as its digits.
        self.assertEqual(attribution.norm_provider_id(12345), '12345')

    def test_ga1_t11b_classification(self):
        # A click id alone is enough, with no UTM at all.
        for key in ('gclid', 'wbraid', 'gbraid'):
            is_ads, hint = attribution.classify({}, {key: 'X'})
            self.assertTrue(is_ads, '%s alone must classify as Google Ads' % key)
            self.assertEqual(hint, 'click_id')
        # Source + paid medium, with no click id.
        self.assertEqual(
            attribution.classify({'source': 'Google', 'medium': 'CPC'}, {}),
            (True, 'utm'))
        # Google source but an unpaid medium is NOT an ad click.
        self.assertEqual(
            attribution.classify({'source': 'google', 'medium': 'organic'}, {}),
            (False, ''))
        # A click id plus a contradicting declared source.
        self.assertEqual(
            attribution.classify({'source': 'facebook'}, {'gclid': 'X'}),
            (True, 'conflict'))
        # Garbage inputs must not raise.
        self.assertEqual(attribution.classify(None, None), (False, ''))

    def test_ga1_t11c_extract_ids(self):
        flat = attribution.extract_ids({
            'h19_gads_customer_id': '111-111-1111',
            'h19_gads_campaign_id': BIG_CAMPAIGN_ID})
        self.assertEqual(flat['customer_id'], CUSTOMER_A1)
        self.assertEqual(flat['campaign_id'], BIG_CAMPAIGN_ID)
        # The block wins over the flattened key when both are present.
        both = attribution.extract_ids({
            'google_ads': {'campaign_id': BIG_CAMPAIGN_ID},
            'h19_gads_campaign_id': OTHER_CAMPAIGN_ID})
        self.assertEqual(both['campaign_id'], BIG_CAMPAIGN_ID)

    # ==================================================================
    # GA1-T04 — a matched Google enquiry
    # ==================================================================
    def test_ga1_t04_matched_google_enquiry(self):
        payload = self._google_payload(
            0, google_ads={'customer_id': '111-111-1111',
                           'campaign_id': BIG_CAMPAIGN_ID,
                           'adgroup_id': '23456789012345678',
                           'creative_id': '34567890123456789'})
        result = self.Service.process_submission(payload)
        self.assertEqual(result['status'], 'created')

        lead = self._lead_of(result)
        self.assertEqual(lead.google_ads_origin, 'website')
        self.assertEqual(lead.google_ads_match_status, 'matched')
        self.assertEqual(lead.google_ads_account_id, self.account_a1)
        self.assertEqual(lead.google_ads_customer_id, CUSTOMER_A1)
        # Byte equality, not a numeric comparison (rail R3).
        self.assertEqual(lead.google_ads_campaign_id, BIG_CAMPAIGN_ID)
        self.assertEqual(lead.google_ads_adgroup_id, '23456789012345678')
        self.assertEqual(lead.google_ads_creative_id, '34567890123456789')
        self.assertEqual(lead.gclid, 'EAIaGA1test')

        touch = self._newest_touch(lead)
        self.assertEqual(touch.google_ads_origin, 'website')
        self.assertEqual(touch.google_ads_match_status, 'matched')
        self.assertEqual(touch.google_ads_account_id, self.account_a1)
        self.assertEqual(touch.google_ads_campaign_id, BIG_CAMPAIGN_ID)
        self.assertEqual(touch.google_ads_time_basis, 'website')
        self.assertEqual(touch.gclid, 'EAIaGA1test')

    # ==================================================================
    # GA1-T05 — braid-only clicks
    # ==================================================================
    def test_ga1_t05_braid_only_clicks(self):
        for index, key in ((1, 'wbraid'), (2, 'gbraid')):
            payload = self._payload(index)
            payload['click_ids'] = {key: 'BRAID-%s' % key}
            result = self.Service.process_submission(payload)
            self.assertEqual(result['status'], 'created',
                             'a braid-only click must still create an enquiry')
            lead = self._lead_of(result)
            touch = self._newest_touch(lead)

            self.assertEqual(lead[key], 'BRAID-%s' % key,
                             'the braid must persist on the enquiry')
            self.assertEqual(touch[key], 'BRAID-%s' % key,
                             'the braid must persist on the touch')
            self.assertFalse(lead.gclid, 'no gclid was sent, none may appear')
            self.assertFalse(touch.gclid)
            # Classified by the click id alone: the payload carries no utm.
            self.assertEqual(lead.google_ads_origin, 'website')
            self.assertEqual(touch.google_ads_origin, 'website')

    # ==================================================================
    # GA1-T06 — first touch is immutable
    # ==================================================================
    def test_ga1_t06_google_follow_up_never_rewrites_first_touch(self):
        organic = self._payload(3)
        first = self.Service.process_submission(organic)
        lead = self._lead_of(first)
        self.assertFalse(lead.google_ads_origin)
        source_before = lead.source_id

        second = self._payload(3, name=organic['name'],
                               utm={'source': 'google', 'medium': 'cpc'},
                               click_ids={'gclid': 'EAIalater'},
                               google_ads={'customer_id': CUSTOMER_A1})
        result = self.Service.process_submission(second)
        self.assertEqual(result['status'], 'merged')

        lead.invalidate_recordset()
        self.assertFalse(lead.google_ads_origin,
                         'a later ad click must not rewrite the first source')
        self.assertEqual(lead.source_id, source_before)

        touch = self._newest_touch(lead)
        self.assertEqual(touch.google_ads_origin, 'website')
        self.assertEqual(touch.google_ads_account_id, self.account_a1)

        # "influenced" finds it; "first source" does not.
        influenced = self.Lead.search([('id', '=', lead.id),
                                       ('google_ads_influenced', '=', True)])
        self.assertEqual(influenced, lead)
        first_source = self.Lead.search([('id', '=', lead.id),
                                         ('google_ads_origin', '!=', False)])
        self.assertFalse(first_source)
        self.assertTrue(lead.google_ads_influenced)

    def test_ga1_t06b_influenced_filter_survives_the_domain_optimizer(self):
        """Ledger §5.13, pinned.

        Odoo rewrites `('google_ads_influenced', '=', True)` into
        `('in', OrderedSet([True]))` before the search method ever sees it.
        A truthiness test that only understands a bare `True` reads that as
        FALSE and returns the exact complement — a filter that lists every
        enquiry EXCEPT the ones it is named for. Every spelling is asserted
        here, and the negative one is asserted to be the complement.
        """
        google = self._lead_of(self.Service.process_submission(
            self._google_payload(8)))
        organic = self._lead_of(self.Service.process_submission(
            self._payload(9)))

        for domain in ([('google_ads_influenced', '=', True)],
                       [('google_ads_influenced', '!=', False)],
                       [('google_ads_influenced', 'in', [True])]):
            found = self.Lead.search(domain + [('id', 'in',
                                                (google | organic).ids)])
            self.assertEqual(found, google, 'domain %s' % domain)

        for domain in ([('google_ads_influenced', '=', False)],
                       [('google_ads_influenced', '!=', True)],
                       [('google_ads_influenced', 'not in', [True])]):
            found = self.Lead.search(domain + [('id', 'in',
                                                (google | organic).ids)])
            self.assertEqual(found, organic, 'domain %s' % domain)

    # ==================================================================
    # GA1-T07 — replay
    # ==================================================================
    def test_ga1_t07_replay_is_a_duplicate(self):
        payload = self._google_payload(4)
        first = self.Service.process_submission(payload)
        self.assertEqual(first['status'], 'created')
        second = self.Service.process_submission(dict(payload))
        self.assertEqual(second['status'], 'duplicate')

        lead = self._lead_of(first)
        self.assertEqual(
            self.Touchpoint.search_count([('lead_id', '=', lead.id)]), 1,
            'one submission, one touch')
        self.assertEqual(self.Lead.search_count(
            [('external_submission_id', '=', payload['submission_id'])]), 1)

    # ==================================================================
    # GA1-T08 — another company's customer id (rail R1)
    # ==================================================================
    def test_ga1_t08_cross_company_customer_id_is_unmatched(self):
        payload = self._google_payload(
            5, google_ads={'customer_id': CUSTOMER_B1, 'campaign_id': ''})
        result = self.Service.process_submission(payload)
        lead = self._lead_of(result)
        touch = self._newest_touch(lead)

        self.assertEqual(lead.google_ads_origin, 'website')
        self.assertEqual(lead.google_ads_match_status, 'unmatched')
        self.assertFalse(lead.google_ads_account_id,
                         'a payload id may never reach across companies')
        self.assertFalse(touch.google_ads_account_id)
        # The hint is still recorded — it is evidence, just not a grant.
        self.assertEqual(lead.google_ads_customer_id, CUSTOMER_B1)
        self.assertNotEqual(lead.google_ads_account_id, self.account_b1)

    # ==================================================================
    # GA1-T09 — never the first of several (rail R4)
    # ==================================================================
    def test_ga1_t09_ambiguous_campaign_is_unmatched(self):
        self.Campaign.create({'account_id': self.account_a1.id,
                              'external_campaign_id': BIG_CAMPAIGN_ID,
                              'name': 'A1 mapping'})
        self.Campaign.create({'account_id': self.account_a2.id,
                              'external_campaign_id': BIG_CAMPAIGN_ID,
                              'name': 'A2 mapping'})

        ambiguous = self._google_payload(
            6, google_ads={'campaign_id': BIG_CAMPAIGN_ID})
        lead = self._lead_of(self.Service.process_submission(ambiguous))
        self.assertEqual(lead.google_ads_match_status, 'unmatched')
        self.assertFalse(lead.google_ads_account_id,
                         'two mappings must never be resolved by picking one')

        # Mapped on exactly one account → matched to that one.
        self.Campaign.create({'account_id': self.account_a2.id,
                              'external_campaign_id': OTHER_CAMPAIGN_ID,
                              'name': 'A2 only'})
        unique = self._google_payload(
            7, google_ads={'campaign_id': OTHER_CAMPAIGN_ID})
        lead2 = self._lead_of(self.Service.process_submission(unique))
        self.assertEqual(lead2.google_ads_match_status, 'matched')
        self.assertEqual(lead2.google_ads_account_id, self.account_a2)

    def test_ga1_t09b_unmapped_campaign_is_unmatched(self):
        payload = self._google_payload(
            0, google_ads={'campaign_id': '5555555555555555555'})
        lead = self._lead_of(self.Service.process_submission(payload))
        self.assertEqual(lead.google_ads_match_status, 'unmatched')
        self.assertFalse(lead.google_ads_account_id)
        self.assertEqual(lead.google_ads_campaign_id, '5555555555555555555')

    # ==================================================================
    # GA1-T10 — a conflicting declared source (rail R8)
    # ==================================================================
    def test_ga1_t10_conflicting_source_flags_review(self):
        payload = self._payload(1)
        payload['utm'] = {'source': 'facebook', 'medium': 'cpc'}
        payload['click_ids'] = {'gclid': 'EAIaconflict'}
        lead = self._lead_of(self.Service.process_submission(payload))
        touch = self._newest_touch(lead)

        self.assertEqual(lead.google_ads_origin, 'website')
        self.assertEqual(lead.google_ads_match_status, 'conflict')
        self.assertTrue(lead.web_needs_review)
        # The declared strings are recorded, never rewritten.
        self.assertEqual(touch.utm_source, 'facebook')
        self.assertEqual(touch.google_ads_match_status, 'conflict')

    def test_ga1_t10b_conflict_never_clears_an_existing_review_flag(self):
        """`web_needs_review` is ORed, not assigned: the base builder has
        already decided for its own reasons and a conflict can only add one."""
        payload = self._payload(2, location='', page_url='', form_id='nomap')
        payload['utm'] = {'source': 'facebook'}
        payload['click_ids'] = {'gclid': 'EAIaconflict2'}
        lead = self._lead_of(self.Service.process_submission(payload))
        self.assertTrue(lead.web_needs_review)
        self.assertEqual(lead.google_ads_match_status, 'conflict')

    def test_ga1_t10c_a_plain_enquiry_carries_no_google_fields(self):
        lead = self._lead_of(self.Service.process_submission(self._payload(3)))
        self.assertFalse(lead.google_ads_origin)
        self.assertFalse(lead.google_ads_match_status)
        self.assertFalse(lead.google_ads_account_id)
        self.assertFalse(self._newest_touch(lead).google_ads_origin)

    # ==================================================================
    # GA1-T16 — touchpoint company
    # ==================================================================
    def test_ga1_t16_touchpoint_company_follows_its_lead(self):
        lead = self._lead_of(self.Service.process_submission(
            self._google_payload(4)))
        touch = self._newest_touch(lead)
        self.assertEqual(touch.company_id, lead.company_id)
        self.assertTrue(touch.company_id,
                        'the touch must inherit a company from its lead')

    def test_ga1_t16b_foreign_account_on_a_touch_is_refused(self):
        lead = self._lead_of(self.Service.process_submission(self._payload(5)))
        touch = self._newest_touch(lead)
        self.assertEqual(touch.company_id, self.company)
        with self.assertRaises(ValidationError):
            touch.write({'google_ads_account_id': self.account_b1.id,
                         'google_ads_origin': 'website'})

    def test_ga1_t16c_lead_and_conversation_companies_must_agree(self):
        if 'care.conversation' not in self.env:
            self.skipTest('care.conversation is not installed')
        lead = self.Lead.sudo().create({
            'name': 'GADS company clash', 'type': 'opportunity',
            'company_id': self.company.id,
            'catchment_province_id': self.province.id})
        # `care.conversation` has no `channel` field: the model carries
        # `channel_primary` (traffic), `channel_declared` (what the lead said)
        # and the computed `channel_effective`. Verified against the model,
        # not assumed from the Center's vocabulary.
        conv = self.env['care.conversation'].sudo().create({
            'channel_declared': 'webchat', 'company_id': self.company2.id,
            'catchment_province_id': self.province.id})
        with self.assertRaises(ValidationError):
            self.Touchpoint.sudo().create({
                'lead_id': lead.id,
                'conversation_id': conv.id,
                'occurred_at': '2026-09-15 02:30:00',
                'touchpoint_type_id': self.env['health.lookup.value']
                ._default_for('touchpoint_type', 'form_submit'),
            })

    # ==================================================================
    # GA1-T20 — a conversation-born lead inherits the Google snapshot
    # ==================================================================
    def test_ga1_t20_conversation_lead_inherits_google_fields(self):
        if 'care.conversation' not in self.env:
            self.skipTest('care.conversation is not installed')
        Conversation = self.env['care.conversation'].sudo()
        conv = Conversation.create({
            'channel_declared': 'webchat',
            'company_id': self.company.id,
            'catchment_province_id': self.province.id,
            'phone_normalized': self.phones[6],
        })
        touch = self.Touchpoint.sudo().create({
            'conversation_id': conv.id,
            'occurred_at': '2026-09-15 02:30:00',
            'touchpoint_type_id': self.env['health.lookup.value']
            ._default_for('touchpoint_type', 'form_submit'),
            'gclid': 'EAIaconv',
            'google_ads_origin': 'website',
            'google_ads_match_status': 'matched',
            'google_ads_account_id': self.account_a1.id,
            'google_ads_customer_id': CUSTOMER_A1,
            'google_ads_campaign_id': BIG_CAMPAIGN_ID,
        })
        Conversation.action_create_lead(conv.id)
        conv.invalidate_recordset()
        lead = conv.lead_id
        self.assertTrue(lead, 'the conversation must have produced a lead')

        touch.invalidate_recordset()
        self.assertEqual(touch.lead_id, lead,
                         'the touch is re-pointed at the lead it produced')
        self.assertEqual(lead.gclid, 'EAIaconv')
        self.assertEqual(lead.google_ads_origin, 'website')
        self.assertEqual(lead.google_ads_account_id, self.account_a1)
        self.assertEqual(lead.google_ads_campaign_id, BIG_CAMPAIGN_ID)
