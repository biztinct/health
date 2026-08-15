# -*- coding: utf-8 -*-
"""T1–T14 — the capture algorithm, exercised through the service model.

TransactionCase throughout: the business rules live in `web.lead.service`
precisely so they can be proven without HTTP. The endpoint's own auth/scope
round-trip is T15/T16 in test_web_leads_endpoint.py.
"""
import uuid
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_api_gateway.controllers.gateway import ApiError
from odoo.addons.health_web_leads.models.web_lead_service import (
    CITY_HCM, CITY_HN, PARAM_FORM_CITY_MAP, PARAM_URL_CITY_MAP)


@tagged('post_install', '-at_install')
class TestWebLeadService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Service = cls.env['web.lead.service']
        cls.Lead = cls.env['crm.lead']
        cls.Touchpoint = cls.env['health.lead.touchpoint']

        # Resolve the live catchment rows the resolver will find — on vietuat
        # these carry codes 01/02, on a fresh database HN/HCM (design §2.3).
        # Never assert on the code; assert on the RECORD (ledger §5.50).
        cls.hn = cls.Service._resolve_catchment(CITY_HN)
        cls.hcm = cls.Service._resolve_catchment(CITY_HCM)
        if not cls.hn:
            cls.hn = cls.env['health.catchment.province'].create(
                {'name': 'Test Hanoi', 'code': 'HN'})
        if not cls.hcm:
            cls.hcm = cls.env['health.catchment.province'].create(
                {'name': 'Test HCMC', 'code': 'HCM'})

        # vietuat carries 476 live leads and a full client book. A fixture
        # phone that happens to belong to one of them would silently turn T1's
        # "created" into a "merged", or raise its review flag through the
        # possible-existing-client note — so claim identities that provably
        # match NOTHING, in leads or in the patient book (ledger §5.17's
        # live-data-isolation lesson, applied to identity rather than slots).
        cls.phone, cls.phone_alt, cls.phone_alt2 = cls._free_phones(3)
        cls.email = '%s@webleads.invalid' % uuid.uuid4().hex[:12]

        # The maps the service reads. Pinned here rather than trusted from the
        # data file so a live edit on the server cannot silently retune a test.
        Param = cls.env['ir.config_parameter'].sudo()
        Param.set_param(PARAM_FORM_CITY_MAP,
                        '{"15838": "HN", "15670": "HCM"}')
        Param.set_param(
            PARAM_URL_CITY_MAP,
            '{"/lien-he-hanoi/": "HN", "/dich-vu-tai-hn/": "HN", '
            '"/doi-ngu-tai-ha-noi/": "HN", "/lien-he-tphcm/": "HCM", '
            '"/dich-vu-tai-tphcm/": "HCM", "/doi-ngu-tai-tphcm/": "HCM"}')

    @classmethod
    def _free_phones(cls, count):
        """`count` valid VN mobile numbers that match no lead and no partner."""
        Lead = cls.env['crm.lead']
        Partner = cls.env['res.partner']
        found = []
        for offset in range(0, 2000):
            candidate = '09%08d' % (77000000 + offset)
            if Lead.search_count([('phone', '=', candidate)]):
                continue
            if Partner.with_context(active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            found.append(candidate)
            if len(found) == count:
                return found
        raise AssertionError('no free fixture phone numbers available')

    @staticmethod
    def _international(phone):
        """'0912345678' -> '+84 912 345 678' — the same number, as a visitor
        types it. Proves normalization is what the dedup matches on."""
        national = phone[1:]
        return '+84 %s %s %s' % (national[:3], national[3:6], national[6:])

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _payload(self, **overrides):
        payload = {
            'submission_id': uuid.uuid4().hex,
            'form_id': '15838',
            'submitted_at': '2026-07-28T09:30:00+07:00',
            'name': 'Nguyễn Thị A',
            'email': self.email,
            'phone': self.phone,
            'message': 'Cần tư vấn chăm sóc tại nhà.',
            'location': 'Hà Nội',
            'page_url': 'https://pkgdvietuc.com/lien-he-hanoi/',
            'landing_url': 'https://pkgdvietuc.com/dich-vu-tai-hn/',
            'referrer_url': 'https://www.google.com/',
            'utm': {'source': 'google', 'medium': 'cpc',
                    'campaign': 'hn_homecare_leads_202607',
                    'content': 'ad-variant-b', 'term': 'cham soc tai nha'},
            'click_ids': {'gclid': 'EAIaIQtest', 'fbclid': None,
                          'fbc': None, 'fbp': None},
            'ga_client_id': '1660915166.1753672800',
            'consent': {'marketing': True, 'text_version': 'v1'},
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        payload.update(overrides)
        return payload

    def _lead_of(self, result):
        self.assertTrue(result.get('lead_ref'), 'result carries no lead_ref')
        lead = self.Lead.search(
            [('unique_contact_code', '=', result['lead_ref'])], limit=1)
        self.assertTrue(lead, 'lead_ref %s resolves to no lead'
                        % result['lead_ref'])
        return lead

    def _existing_lead(self, **vals):
        base = {
            'name': 'Existing enquiry',
            'type': 'opportunity',
            'contact_status': 'lead',
            'contact_name': 'Nguyễn Thị A',
            'phone': self.phone,
            'catchment_province_id': self.hn.id,
        }
        base.update(vals)
        return self.Lead.create(base)

    # ==================================================================
    # T1 — the happy path
    # ==================================================================
    def test_01_created_hanoi_from_form_location(self):
        payload = self._payload()
        result = self.Service.process_submission(payload)

        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['submission_id'], payload['submission_id'])
        lead = self._lead_of(result)

        self.assertEqual(lead.catchment_province_id, self.hn)
        self.assertEqual(lead.city_source, 'form_location')
        self.assertFalse(lead.web_needs_review)
        self.assertEqual(lead.phone, self.phone)
        self.assertEqual(lead.email_from, self.email)
        self.assertEqual(lead.mode_of_contact, 'website')
        self.assertEqual(lead.contact_source, 'website_form')
        self.assertEqual(lead.healthcare_lead_source, 'website_form')
        self.assertEqual(lead.vietnamese_channel, 'website')
        self.assertEqual(lead.contact_status, 'active')
        self.assertFalse(lead.is_spam_caller)
        self.assertTrue(lead.web_consent_marketing)
        self.assertEqual(lead.web_consent_text_version, 'v1')
        self.assertEqual(lead.gclid, 'EAIaIQtest')
        self.assertEqual(lead.web_form_id, '15838')

        # The contact code is city-prefixed, which only works because the
        # catchment was resolved BEFORE create (handover fact #5 / rail R2).
        self.assertTrue(
            lead.unique_contact_code.startswith(self.hn.code[:2]),
            'contact code %r does not carry the HN prefix %r'
            % (lead.unique_contact_code, self.hn.code[:2]))

        touchpoints = lead.web_touchpoint_ids
        self.assertEqual(len(touchpoints), 1)
        self.assertEqual(touchpoints.touchpoint_type_code, 'form_submit')
        self.assertEqual(touchpoints.source_system, 'wordpress')
        self.assertEqual(touchpoints.external_event_id,
                         payload['submission_id'])
        self.assertEqual(touchpoints.catchment_province_id, self.hn)
        self.assertEqual(touchpoints.utm_campaign, 'hn_homecare_leads_202607')
        # occurred_at is the VISITOR's time (09:30 +07:00) in naive UTC — not
        # the moment we received it (rail R7).
        self.assertEqual(touchpoints.occurred_at,
                         datetime(2026, 7, 28, 2, 30, 0))
        self.assertTrue(touchpoints.received_at)
        self.assertIn(payload['submission_id'], touchpoints.raw_payload)

    # ==================================================================
    # T2 — city from the form id when the visitor left the field empty
    # ==================================================================
    def test_02_city_from_form_id(self):
        result = self.Service.process_submission(self._payload(
            location='', form_id='15670',
            page_url='https://pkgdvietuc.com/', landing_url='',
            utm={'source': 'direct'}))
        lead = self._lead_of(result)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(lead.city_source, 'form_id')
        self.assertEqual(lead.catchment_province_id, self.hcm)

    # ==================================================================
    # T3 — the shared form with no other signal is honestly unknown
    # ==================================================================
    def test_03_shared_form_unknown_city(self):
        result = self.Service.process_submission(self._payload(
            location='', form_id='15615',
            page_url='https://pkgdvietuc.com/gioi-thieu/',
            landing_url='https://pkgdvietuc.com/gioi-thieu/',
            utm={}))
        lead = self._lead_of(result)
        self.assertEqual(result['status'], 'created')
        self.assertFalse(lead.catchment_province_id)
        self.assertEqual(lead.city_source, 'unknown')
        self.assertTrue(lead.web_needs_review)
        self.assertEqual(lead.web_touchpoint_ids.city_source, 'unknown')

    # ==================================================================
    # T4 — an exact replay changes nothing
    # ==================================================================
    def test_04_replay_is_a_noop(self):
        payload = self._payload()
        first = self.Service.process_submission(payload)
        self.assertEqual(first['status'], 'created')

        leads_before = self.Lead.search_count([])
        touches_before = self.Touchpoint.search_count([])

        second = self.Service.process_submission(dict(payload))
        self.assertEqual(second['status'], 'duplicate')
        self.assertEqual(second['lead_ref'], first['lead_ref'])
        self.assertEqual(self.Lead.search_count([]), leads_before)
        self.assertEqual(self.Touchpoint.search_count([]), touches_before)

    # ==================================================================
    # T5 — the re-search branch: the lead already carries the id
    # ==================================================================
    def test_05_preexisting_submission_id_is_a_duplicate(self):
        payload = self._payload()
        planted = self._existing_lead(
            name='Planted', external_submission_id=payload['submission_id'])
        leads_before = self.Lead.search_count([])

        result = self.Service.process_submission(payload)
        self.assertEqual(result['status'], 'duplicate')
        self.assertEqual(result['lead_ref'], planted.unique_contact_code)
        self.assertEqual(self.Lead.search_count([]), leads_before)
        self.assertFalse(planted.web_touchpoint_ids)

    # ==================================================================
    # T6 — a repeat enquiry from the same person merges
    # ==================================================================
    def test_06_repeat_enquiry_merges(self):
        existing = self._existing_lead()
        conversation = None
        if 'care.conversation' in self.env:
            conversation = self.env['care.conversation'].sudo().search(
                [('lead_id', '=', existing.id)], limit=1)
            if conversation:
                # Park it out of the way so "needs_reply" afterwards proves the
                # merge path re-raised it (rail R5), not that it never moved.
                conversation.write({'status': 'closed'})

        leads_before = self.Lead.search_count([])
        result = self.Service.process_submission(self._payload(
            phone=self._international(self.phone), name='Nguyễn Thị A'))

        self.assertEqual(result['status'], 'merged')
        self.assertEqual(result['lead_ref'], existing.unique_contact_code)
        self.assertEqual(self.Lead.search_count([]), leads_before,
                         'a merge must not create a second lead')
        self.assertEqual(len(existing.web_touchpoint_ids), 1)
        self.assertEqual(existing.web_touchpoint_ids.touchpoint_type_code,
                         'form_submit')

        if conversation:
            conversation.invalidate_recordset()
            self.assertEqual(conversation.status, 'needs_reply')

    # ==================================================================
    # T7 — a shared family phone under another name stays separate
    # ==================================================================
    def test_07_shared_phone_different_name_creates(self):
        existing = self._existing_lead(contact_name='Nguyễn Văn B',
                                       name='Nguyễn Văn B')
        result = self.Service.process_submission(self._payload(
            name='Trần Thị C', email=False))
        self.assertEqual(result['status'], 'created')
        new_lead = self._lead_of(result)
        self.assertNotEqual(new_lead, existing)
        self.assertTrue(new_lead.web_needs_review)

        new_bodies = ' '.join(new_lead.message_ids.mapped('body'))
        old_bodies = ' '.join(existing.message_ids.mapped('body'))
        self.assertIn(existing.unique_contact_code, new_bodies)
        self.assertIn(new_lead.unique_contact_code, old_bodies)

    # ==================================================================
    # T8 — a merge whose city disagrees flags, never overwrites
    # ==================================================================
    def test_08_merge_city_conflict(self):
        existing = self._existing_lead(catchment_province_id=self.hn.id)
        result = self.Service.process_submission(self._payload(
            location='TP. Hồ Chí Minh', form_id='15670',
            page_url='https://pkgdvietuc.com/lien-he-tphcm/'))

        self.assertEqual(result['status'], 'merged')
        existing.invalidate_recordset()
        self.assertEqual(existing.catchment_province_id, self.hn,
                         'the stored city must never be auto-changed')
        self.assertTrue(existing.city_conflict)
        self.assertTrue(existing.web_needs_review)
        self.assertEqual(existing.web_touchpoint_ids.catchment_province_id,
                         self.hcm)

    # ==================================================================
    # T9 — an unusable phone is preserved as text, never as a phone
    # ==================================================================
    def test_09_invalid_phone_is_quarantined(self):
        result = self.Service.process_submission(self._payload(
            phone='123', email='invalid-phone-%s' % self.email))
        lead = self._lead_of(result)
        self.assertEqual(result['status'], 'created')
        self.assertFalse(lead.phone, 'invalid input must never reach the '
                                     'phone field (ledger §5.15 / rail R1)')
        self.assertIn('123', lead.description or '')
        self.assertTrue(lead.web_needs_review)

    # ==================================================================
    # T10 — no way to reach the person is a 422
    # ==================================================================
    def test_10_no_identity_is_422(self):
        with self.assertRaises(ApiError) as caught:
            self.Service.process_submission(self._payload(
                phone=None, email=None))
        self.assertEqual(caught.exception.status_code, 422)

    # ==================================================================
    # T11 — the honeypot leaves no trace
    # ==================================================================
    def test_11_honeypot_creates_nothing(self):
        leads_before = self.Lead.search_count([])
        touches_before = self.Touchpoint.search_count([])
        result = self.Service.process_submission(self._payload(
            anti_spam={'honeypot_filled': True, 'token_ok': True}))

        self.assertEqual(result['status'], 'rejected_spam')
        self.assertNotIn('lead_ref', result)
        self.assertEqual(self.Lead.search_count([]), leads_before)
        self.assertEqual(self.Touchpoint.search_count([]), touches_before)

        # …and the same for a failed anti-spam token.
        result = self.Service.process_submission(self._payload(
            anti_spam={'honeypot_filled': False, 'token_ok': False}))
        self.assertEqual(result['status'], 'rejected_spam')
        self.assertEqual(self.Lead.search_count([]), leads_before)

    # ==================================================================
    # T12 — a known spam number still lands, marked
    # ==================================================================
    def test_12_spam_listed_phone_is_created_as_spam(self):
        self._existing_lead(name='Known spam', contact_status='spam',
                            contact_name='Spam Caller')
        result = self.Service.process_submission(self._payload(
            name='Trần Thị D', email=False))
        lead = self._lead_of(result)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(lead.contact_status, 'spam')
        self.assertTrue(lead.is_spam_caller)

    # ==================================================================
    # T13 — UTM governance: source/medium materialise, campaigns do not
    # ==================================================================
    def test_13_utm_record_policy(self):
        result = self.Service.process_submission(self._payload(
            utm={'source': 'google', 'medium': 'cpc',
                 'campaign': 'zzz_unknown_junk', 'content': 'c', 'term': 't'}))
        lead = self._lead_of(result)
        self.assertFalse(lead.campaign_id,
                         'campaign values are attacker-controllable — '
                         'find-only, never auto-created')
        self.assertEqual(lead.web_touchpoint_ids.utm_campaign,
                         'zzz_unknown_junk')
        self.assertTrue(lead.source_id)
        self.assertEqual(lead.source_id.name.lower(), 'google')
        self.assertTrue(lead.medium_id)

        # A second submission REUSES the utm.source rather than duplicating it.
        source_count = self.env['utm.source'].sudo().search_count(
            [('name', '=ilike', 'google')])
        self.Service.process_submission(self._payload(
            phone=self.phone_alt, email='alt-%s' % self.email,
            name='Lê Văn E', utm={'source': 'google', 'medium': 'cpc'}))
        self.assertEqual(
            self.env['utm.source'].sudo().search_count(
                [('name', '=ilike', 'google')]),
            source_count)

        # A URL-shaped source is stored raw but never materialised.
        result = self.Service.process_submission(self._payload(
            phone=self.phone_alt2, email='alt2-%s' % self.email,
            name='Phạm Thị F',
            utm={'source': 'http://evil.example.com/x', 'medium': 'cpc'}))
        lead = self._lead_of(result)
        self.assertFalse(lead.source_id)
        self.assertEqual(lead.web_touchpoint_ids.utm_source,
                         'http://evil.example.com/x')

    # ==================================================================
    # T14 — a closed lead is not revived by a new enquiry
    # ==================================================================
    def test_14_lost_booking_is_not_merged_onto(self):
        existing = self._existing_lead(contact_status='lost_booking')
        result = self.Service.process_submission(self._payload())
        lead = self._lead_of(result)
        self.assertEqual(result['status'], 'created')
        self.assertNotEqual(lead, existing)
        self.assertFalse(existing.web_touchpoint_ids)

    # ==================================================================
    # T17 (extra, not in the handover) — the merge window closes at 60 days
    # ==================================================================
    def _backdate(self, lead, days):
        """write_date is ORM-managed — move it in SQL (ledger §5.9)."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE crm_lead SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=days), lead.id))
        self.env.invalidate_all()

    def test_17_stale_open_lead_is_not_merged_onto(self):
        existing = self._existing_lead()
        self._backdate(existing, 90)

        result = self.Service.process_submission(self._payload())
        self.assertEqual(result['status'], 'created')
        fresh = self._lead_of(result)
        self.assertNotEqual(fresh, existing)

        # …but a lead already at `booking` has no time window at all. Close the
        # lead the first half just created, or it — not `existing` — is the
        # newest open lead on this number and the candidate search is right to
        # pick it (which is exactly how this test first went red).
        fresh.write({'contact_status': 'lost_booking'})
        existing.write({'contact_status': 'booking'})
        self._backdate(existing, 90)

        result = self.Service.process_submission(self._payload())
        self.assertEqual(result['status'], 'merged')
        self.assertEqual(result['lead_ref'], existing.unique_contact_code)

    # ==================================================================
    # T18 (extra, not in the handover) — city precedence, signal by signal
    # ==================================================================
    def test_18_city_precedence(self):
        cases = [
            # (payload overrides, expected city record, expected source)
            ({'location': 'Hà Nội', 'form_id': '15670'}, self.hn,
             'form_location'),
            ({'location': 'Sài Gòn', 'form_id': '15838'}, self.hcm,
             'form_location'),
            ({'location': '', 'form_id': '15838'}, self.hn, 'form_id'),
            ({'location': '', 'form_id': '15615',
              'page_url': 'https://pkgdvietuc.com/doi-ngu-tai-tphcm/'},
             self.hcm, 'page_url'),
            ({'location': '', 'form_id': '15615', 'page_url': '',
              'landing_url': 'https://pkgdvietuc.com/doi-ngu-tai-ha-noi/'},
             self.hn, 'page_url'),
            ({'location': '', 'form_id': '15615', 'page_url': '',
              'landing_url': '', 'utm': {'campaign': 'hcm_physio_202609'}},
             self.hcm, 'campaign_prefix'),
        ]
        for overrides, expected_city, expected_source in cases:
            with self.subTest(source=expected_source, city=expected_city.name):
                payload = self._payload(**overrides)
                city_key, source = self.Service._derive_city(payload)
                self.assertEqual(source, expected_source)
                self.assertEqual(self.Service._resolve_catchment(city_key),
                                 expected_city)

    # ==================================================================
    # T19 (extra, not in the handover) — the catalogue points at real xmlids
    # ==================================================================
    def test_19_vi_po_occurrences_resolve(self):
        """A `#: model:…` occurrence naming an xmlid that does not exist is
        read by nothing and translates nothing (ledger §5.67/§5.85) — and no
        repo-wide shape test can catch it, because the shape is perfect."""
        import os
        import re
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'i18n', 'vi.po')
        self.assertTrue(os.path.exists(path), 'health_web_leads ships no vi.po')
        with open(path, encoding='utf-8') as handle:
            body = handle.read()

        missing = []
        pattern = re.compile(
            r'^#: model(?:_terms)?:[\w.]+,[\w]+:(health_web_leads\.[\w.]+)$',
            re.M)
        found = pattern.findall(body)
        self.assertTrue(found, 'no model occurrences to verify')
        for xmlid in sorted(set(found)):
            if not self.env.ref(xmlid, raise_if_not_found=False):
                missing.append(xmlid)
        self.assertFalse(
            missing,
            'vi.po occurrences pointing at xmlids that do not exist:\n%s'
            % '\n'.join(missing))

    # ==================================================================
    # T20 (extra, not in the handover) — the catalogue actually TRANSLATES
    # ==================================================================
    def test_20_vi_catalogue_loads_and_reaches_the_screen(self):
        """Shape is necessary and not sufficient (§5.58 / §5.67 / §5.85).

        The repo-wide guard for this lives in health_base, and running it
        means upgrading health_base — which cascades an upgrade onto every
        module above it. So our own module carries the same two proofs for
        its own catalogue: the code half loads, and the label half reaches
        the database in Vietnamese.
        """
        from odoo.tools.translate import code_translations

        loaded = code_translations.get_python_translations(
            'health_web_leads', 'vi_VN')
        self.assertTrue(loaded, 'health_web_leads python translations: 0 '
                                'loaded — the catalogue is inert')
        self.assertEqual(loaded.get('Rate limit exceeded'),
                         'Đã vượt quá giới hạn số lần gọi')

        field = self.env.ref(
            'health_web_leads.field_health_lead_touchpoint__touchpoint_type')
        self.assertNotEqual(
            field.with_context(lang='vi_VN').field_description,
            'Touchpoint Type',
            'the field label never reached the database in Vietnamese')
