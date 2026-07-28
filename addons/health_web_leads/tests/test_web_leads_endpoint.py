# -*- coding: utf-8 -*-
"""T15–T16 — the HTTP surface: OAuth2 round-trip, scope gate, no-token gate.

These only run if the test command carries BOTH `--workers=0` and no
`--no-http` (conventions §2 / ledger §5.75, §5.83): with either wrong, every
HttpCase in the run dies in `setUpClass`, and the runner reports EXIT:1 with a
FAIL count of zero — which reads like unrelated breakage. Verify they ran:

    grep -ac "Starting .*Http\\|ERROR: setUpClass" <logfile>
"""
import json
import uuid

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP)


@tagged('post_install', '-at_install')
class TestWebLeadsEndpoint(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Scope = cls.env['api.key.scope']
        cls.write_scope = Scope.search([('code', '=', 'web_lead.write')],
                                       limit=1)
        cls.read_scope = Scope.search([('code', '=', 'web_lead.read')], limit=1)
        assert cls.write_scope, 'web_lead.write scope was not seeded'
        assert cls.read_scope, 'web_lead.read scope was not seeded'

        # The service user carries exactly what §10 tells ops to grant.
        cls.service_user = new_test_user(
            cls.env, login='svc_web_leads_test',
            password='svc_web_leads_test_pw',
            groups='base.group_user,health_web_leads.group_web_leads_service')

        cls.secret = 'w1-endpoint-secret-%s' % uuid.uuid4().hex[:8]
        cls.client = cls.env['gateway.oauth.client'].create({
            'name': 'W1 Endpoint Test Client',
            'user_id': cls.service_user.id,
            'allowed_scope_ids': [(6, 0, cls.write_scope.ids)],
            'token_lifetime': 3600,
        })
        cls.client._set_secret(cls.secret)

        # A client holding only the READ scope — the 403 arm of T16.
        cls.wrong_secret = 'w1-wrong-secret-%s' % uuid.uuid4().hex[:8]
        cls.wrong_client = cls.env['gateway.oauth.client'].create({
            'name': 'W1 Endpoint Test Client (read only)',
            'user_id': cls.service_user.id,
            'allowed_scope_ids': [(6, 0, cls.read_scope.ids)],
            'token_lifetime': 3600,
        })
        cls.wrong_client._set_secret(cls.wrong_secret)

        cls.env['ir.config_parameter'].sudo().set_param(
            PARAM_FORM_CITY_MAP, '{"15838": "HN", "15670": "HCM"}')

        # Live vietuat data would otherwise decide whether T15 reads "created"
        # or "merged" — claim numbers that match no lead and no client.
        cls.free_phones = cls._free_phones(8)

    @classmethod
    def _free_phones(cls, count):
        Lead = cls.env['crm.lead']
        Partner = cls.env['res.partner']
        found = []
        for offset in range(0, 2000):
            candidate = '09%08d' % (76000000 + offset)
            if Lead.search_count([('phone', '=', candidate)]):
                continue
            if Partner.with_context(active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            found.append(candidate)
            if len(found) == count:
                return found
        raise AssertionError('no free fixture phone numbers available')

    def setUp(self):
        super().setUp()
        # Ledger §5.32 — an HttpCase's writes are the classic way to poison a
        # later suite. Everything this class creates is named and removed,
        # pass or fail.
        self._submission_ids = []
        self.addCleanup(self._purge_created_leads)

    def _purge_created_leads(self):
        self.env.invalidate_all()
        leads = self.env['crm.lead'].sudo().with_context(
            active_test=False).search(
            [('external_submission_id', 'in', self._submission_ids)])
        if leads:
            leads.unlink()

    # ------------------------------------------------------------------
    def _token(self, client_id, secret, scope=None):
        body = {'grant_type': 'client_credentials',
                'client_id': client_id, 'client_secret': secret}
        if scope:
            body['scope'] = scope
        response = self.url_open(
            '/oauth/token', data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200,
                         'token endpoint said %s: %s'
                         % (response.status_code, response.text[:300]))
        return response.json()['access_token']

    def _post(self, payload, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        return self.url_open('/api/v1/web/leads',
                             data=json.dumps(payload).encode('utf-8'),
                             headers=headers)

    def _payload(self, **overrides):
        submission_id = uuid.uuid4().hex
        self._submission_ids.append(submission_id)
        index = len(self._submission_ids) - 1
        payload = {
            'submission_id': submission_id,
            'form_id': '15838',
            'submitted_at': '2026-07-28T09:30:00+07:00',
            'name': 'W1 HTTP Test %s' % index,
            'email': '%s@webleads.invalid' % uuid.uuid4().hex[:12],
            'phone': self.free_phones[index % len(self.free_phones)],
            'message': 'HttpCase round-trip.',
            'location': 'Hà Nội',
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        payload.update(overrides)
        return payload

    def _lead_for(self, submission_id):
        self.env.invalidate_all()
        return self.env['crm.lead'].sudo().search(
            [('external_submission_id', '=', submission_id)], limit=1)

    # ==================================================================
    # T15 — full round-trip
    # ==================================================================
    def test_15_full_round_trip(self):
        token = self._token(self.client.client_id, self.secret)
        payload = self._payload()
        response = self._post(payload, token)

        self.assertEqual(response.status_code, 200,
                         'endpoint said %s: %s'
                         % (response.status_code, response.text[:500]))
        envelope = response.json()
        self.assertTrue(envelope['success'], envelope)
        self.assertIn(
            'data', envelope,
            'no `data` key — a WRITE endpoint built on the gateway decorator '
            'swallows the readonly-cursor retry and 500s here (ledger §5.38)')
        self.assertEqual(envelope['data']['status'], 'created')
        self.assertEqual(envelope['data']['submission_id'],
                         payload['submission_id'])
        self.assertTrue(envelope['data']['lead_ref'])

        lead = self._lead_for(payload['submission_id'])
        self.assertTrue(lead, 'the endpoint returned created but no lead '
                              'exists')
        self.assertEqual(lead.unique_contact_code, envelope['data']['lead_ref'])
        self.assertEqual(lead.create_uid, self.service_user,
                         'the lead must be written as the service user, so '
                         'record rules and the audit trail mean something')
        self.assertEqual(len(lead.web_touchpoint_ids), 1)
        self.assertTrue(lead.catchment_province_id)

        # A replay over HTTP is a no-op.
        replay = self._post(payload, token)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()['data']['status'], 'duplicate')
        self.assertEqual(replay.json()['data']['lead_ref'],
                         envelope['data']['lead_ref'])

        # The spam gate answers 200 and leaves nothing behind (rail R3).
        spam_payload = self._payload(
            anti_spam={'honeypot_filled': True, 'token_ok': True})
        spam = self._post(spam_payload, token)
        self.assertEqual(spam.status_code, 200)
        self.assertEqual(spam.json()['data']['status'], 'rejected_spam')
        self.assertFalse(self._lead_for(spam_payload['submission_id']))

    # ==================================================================
    # T16 — the auth gates
    # ==================================================================
    def test_16_scope_and_auth_gates(self):
        # A token whose client may only READ cannot write.
        wrong_token = self._token(self.wrong_client.client_id,
                                  self.wrong_secret)
        denied = self._post(self._payload(), wrong_token)
        self.assertEqual(denied.status_code, 403, denied.text[:300])
        self.assertFalse(denied.json()['success'])

        # No credentials at all.
        anonymous = self._post(self._payload())
        self.assertEqual(anonymous.status_code, 401, anonymous.text[:300])
        self.assertFalse(anonymous.json()['success'])

        # A garbage bearer token is 401, not 500.
        garbage = self._post(self._payload(), 'hg_' + '0' * 48)
        self.assertEqual(garbage.status_code, 401)

        # Authenticated but incomplete: the required-field gate is 422.
        token = self._token(self.client.client_id, self.secret)
        incomplete = self._post({'form_id': '15838'}, token)
        self.assertEqual(incomplete.status_code, 422, incomplete.text[:300])

        # Nothing above may have created a lead.
        self.env.invalidate_all()
        self.assertFalse(self.env['crm.lead'].sudo().search_count(
            [('external_submission_id', 'in', self._submission_ids)]))

    # ==================================================================
    # T21 (extra, not in the handover) — every call leaves an audit row
    # ==================================================================
    def test_21_calls_are_audited(self):
        token = self._token(self.client.client_id, self.secret)
        payload = self._payload()
        before = self.env['api.audit.log'].sudo().search_count(
            [('route', '=', '/api/v1/web/leads')])
        self._post(payload, token)
        self._post(self._payload(), 'hg_' + '0' * 48)   # a 401 is audited too
        self.env.invalidate_all()
        after = self.env['api.audit.log'].sudo().search_count(
            [('route', '=', '/api/v1/web/leads')])
        self.assertGreaterEqual(
            after - before, 2,
            'the capture endpoint did not write an api.audit.log row per call')
