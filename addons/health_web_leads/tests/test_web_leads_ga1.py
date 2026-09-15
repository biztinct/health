# -*- coding: utf-8 -*-
"""GA1 — braid persistence, the two extension seams, and touchpoint company.

These are the base module's own guarantees: they must hold whether or not
`health_google_ads` is installed, which is exactly why the seams default to
``{}`` rather than to anything Google-shaped.
"""
import uuid
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP, PARAM_URL_CITY_MAP, WebLeadService)


@tagged('post_install', '-at_install')
class TestWebLeadsGA1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Service = cls.env['web.lead.service']
        cls.Lead = cls.env['crm.lead']
        cls.Touchpoint = cls.env['health.lead.touchpoint']
        cls.province = cls.env['health.catchment.province'].search([], limit=1) \
            or cls.env['health.catchment.province'].create(
                {'name': 'GA1 Prov'})
        cls.phones = cls._free_phones(4)
        Param = cls.env['ir.config_parameter'].sudo()
        Param.set_param(PARAM_FORM_CITY_MAP, '{"15838": "HN"}')
        Param.set_param(PARAM_URL_CITY_MAP, '{"/lien-he-hanoi/": "HN"}')

    @classmethod
    def _free_phones(cls, count):
        """Identities that provably match no live lead and no live patient —
        the master database carries a real book (ledger §5.17's live-data
        isolation lesson, applied to identity)."""
        Lead = cls.env['crm.lead']
        Partner = cls.env['res.partner']
        found = []
        for offset in range(0, 4000):
            candidate = '09%08d' % (78500000 + offset)
            if Lead.with_context(active_test=False).search_count(
                    [('phone', '=', candidate)]):
                continue
            if Partner.with_context(active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            found.append(candidate)
            if len(found) == count:
                return found
        raise AssertionError('no free fixture phone numbers available')

    def _payload(self, index, **overrides):
        payload = {
            'submission_id': uuid.uuid4().hex,
            'form_id': '15838',
            'name': 'GA1 Tester %s' % index,
            'phone': self.phones[index],
            'page_url': 'https://pkgdvietuc.com/lien-he-hanoi/',
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        payload.update(overrides)
        return payload

    def _lead(self, result):
        return self.Lead.browse(result['_lead_id'])

    def _touch(self, lead):
        return self.Touchpoint.search(
            [('lead_id', '=', lead.id)],
            order='occurred_at desc, id desc', limit=1)

    # ==================================================================
    # Braid persistence — the columns existed since W1 and nothing wrote them
    # ==================================================================
    def test_ga1_wl_01_braids_persist_on_create(self):
        payload = self._payload(0, click_ids={
            'gclid': 'G-1', 'wbraid': 'W-1', 'gbraid': 'B-1'})
        lead = self._lead(self.Service.process_submission(payload))
        touch = self._touch(lead)
        for field, value in (('gclid', 'G-1'), ('wbraid', 'W-1'),
                             ('gbraid', 'B-1')):
            self.assertEqual(lead[field], value,
                             'crm.lead.%s must persist' % field)
            self.assertEqual(touch[field], value,
                             'touchpoint.%s must persist' % field)

    def test_ga1_wl_02_braids_persist_on_merge(self):
        first = self.Service.process_submission(self._payload(1))
        lead = self._lead(first)
        second = self._payload(1, name='GA1 Tester 1',
                               click_ids={'wbraid': 'W-merge'})
        result = self.Service.process_submission(second)
        self.assertEqual(result['status'], 'merged')
        touch = self._touch(lead)
        self.assertEqual(touch.wbraid, 'W-merge',
                         'a repeat touch keeps its own braid')
        lead.invalidate_recordset()
        self.assertFalse(lead.wbraid,
                         'the first touch stays frozen — a later braid never '
                         'back-fills the enquiry')

    def test_ga1_wl_03_absent_braids_stay_empty(self):
        lead = self._lead(self.Service.process_submission(self._payload(2)))
        touch = self._touch(lead)
        for field in ('gclid', 'wbraid', 'gbraid'):
            self.assertFalse(lead[field])
            self.assertFalse(touch[field])

    # ==================================================================
    # The extension seams
    # ==================================================================
    def test_ga1_wl_04_seams_default_to_empty(self):
        """With nothing overriding them the base behaviour is unchanged."""
        service = self.Service
        self.assertEqual(
            WebLeadService._lead_extra_vals(service, {}, None, 'unknown'), {})
        self.assertEqual(
            WebLeadService._touchpoint_extra_vals(
                service, None, {}, None, 'unknown'), {})

    def test_ga1_wl_05_seams_are_called_with_the_documented_signature(self):
        """Patched with PLAIN FUNCTIONS, never `autospec` (ledger §5.76)."""
        seen = {}

        def _lead_extra(self, payload, catchment, city_source):
            seen['lead'] = (payload, catchment, city_source)
            return {'utm_term': 'from-the-seam'}

        def _touch_extra(self, lead, payload, catchment, city_source):
            seen['touch'] = (lead, payload, catchment, city_source)
            return {'utm_term': 'touch-seam'}

        Service = type(self.Service)
        with patch.object(Service, '_lead_extra_vals', _lead_extra), \
                patch.object(Service, '_touchpoint_extra_vals', _touch_extra):
            payload = self._payload(3)
            lead = self._lead(self.Service.process_submission(payload))

        self.assertIn('lead', seen, '_lead_extra_vals must be called once')
        self.assertIn('touch', seen, '_touchpoint_extra_vals must be called')
        self.assertEqual(seen['lead'][0]['submission_id'],
                         payload['submission_id'])
        self.assertEqual(seen['lead'][2], seen['touch'][3],
                         'both seams see the same city verdict')
        self.assertEqual(seen['touch'][0], lead,
                         'the touchpoint seam is handed the lead')
        self.assertEqual(lead.utm_term, 'from-the-seam',
                         'the seam value reaches the enquiry')
        self.assertEqual(self._touch(lead).utm_term, 'touch-seam')

    def test_ga1_wl_06_the_lead_seam_never_runs_on_a_merge(self):
        """First-touch immutability is a property of WHERE the seam is
        called, not of what any extension chooses to return."""
        calls = []

        def _lead_extra(self, payload, catchment, city_source):
            calls.append(payload.get('submission_id'))
            return {}

        first = self.Service.process_submission(self._payload(0))
        lead = self._lead(first)

        Service = type(self.Service)
        with patch.object(Service, '_lead_extra_vals', _lead_extra):
            repeat = self._payload(0, name='GA1 Tester 0')
            result = self.Service.process_submission(repeat)

        self.assertEqual(result['status'], 'merged')
        self.assertEqual(calls, [],
                         'a merge must never reach the first-touch seam')
        self.assertTrue(self._touch(lead))

    # ==================================================================
    # Touchpoint company
    # ==================================================================
    def test_ga1_wl_07_touchpoint_company_follows_its_lead(self):
        lead = self._lead(self.Service.process_submission(self._payload(1)))
        touch = self._touch(lead)
        self.assertEqual(touch.company_id, lead.company_id)

    def test_ga1_wl_08_touchpoint_company_recomputes_when_the_lead_moves(self):
        other = self.env['res.company'].create({'name': 'GA1 Other Co'})
        lead = self._lead(self.Service.process_submission(self._payload(2)))
        touch = self._touch(lead)
        self.assertEqual(touch.company_id, lead.company_id)

        # `team_id` is company-checked, so moving the lead alone trips
        # `_check_company` on the sales team it was routed to. Clear the team
        # in the same write — the point of the test is the touchpoint's
        # computed company, not CRM routing.
        lead.sudo().write({'team_id': False, 'company_id': other.id})
        touch.invalidate_recordset()
        self.assertEqual(touch.company_id, other,
                         'the stored compute must follow its anchor')

    def test_ga1_wl_09_an_anchorless_touchpoint_has_no_company(self):
        """The record rule's `company_id = False` branch is not decorative —
        a conversation-only touch on a conversation with no company reaches
        it, and it must stay visible rather than vanish."""
        lead = self._lead(self.Service.process_submission(self._payload(3)))
        touch = self._touch(lead)
        # The compute, read directly, with no lead: the rule's other branch.
        empty = self.Touchpoint.new({'lead_id': False,
                                     'conversation_id': False})
        empty._compute_company_id()
        self.assertFalse(empty.company_id)
        self.assertTrue(touch.company_id)
