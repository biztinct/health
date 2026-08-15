# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.health_api_gateway.api_registry import API_REGISTRY, build_openapi


def _make_oauth_client(env, login_suffix, scope_codes, secret):
    user = new_test_user(env, login='gw_service_%s' % login_suffix,
                         groups='base.group_user')
    scopes = env['api.key.scope'].search([('code', 'in', list(scope_codes))])
    client = env['gateway.oauth.client'].create({
        'name': 'Test Client %s' % login_suffix,
        'user_id': user.id,
        'allowed_scope_ids': [(6, 0, scopes.ids)],
        'token_lifetime': 3600,
    })
    client._set_secret(secret)
    return client


def _get_fso_fixture(env):
    """FSO fixture: search existing records first, create fallback.
    Patients require catchment_province_id; FSO requires facility_id."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    patient = Partner.search([
        ('is_patient', '=', True),
        ('catchment_province_id', '!=', False),
    ], limit=1)
    facility = env['health.facility']
    if patient:
        facility = Facility.search([
            ('catchment_province_id', '=', patient.catchment_province_id.id),
            ('active', '=', True),
        ], limit=1)
    if not patient or not facility:
        province = env['health.catchment.province'].search([], limit=1)
        if not province:
            province = env['health.catchment.province'].create({
                'name': 'Test Gateway Province',
                'code': 'TGW',
            })
        facility = Facility.search([
            ('catchment_province_id', '=', province.id)], limit=1)
        if not facility:
            facility = Facility.create({
                'name': 'Test Gateway Facility',
                'code': 'TGWF',
                'street': '1 Test Street',
                'city': 'Test City',
                'catchment_province_id': province.id,
            })
        patient = Partner.create({
            'name': 'Gateway Test Patient',
            'is_patient': True,
            'catchment_province_id': province.id,
            'primary_facility_id': facility.id,
        })

    fso = env['health.fieldservice.order'].create({
        'patient_id': patient.id,
        'facility_id': facility.id,
        'scheduled_datetime': fields.Datetime.now() + timedelta(days=1),
        'scheduled_duration': 60,
    })
    return fso


@tagged('post_install', '-at_install')
class TestGatewayCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = _make_oauth_client(
            cls.env, 'core', ['booking.read', 'system/Patient.read'],
            'core-secret-123')

    # ------------------------------------------------------------------
    def test_token_issue_resolve_roundtrip_and_expiry(self):
        Token = self.env['gateway.token']
        raw = Token.issue(self.client, ['booking.read', 'system/Patient.read'])
        self.assertTrue(raw.startswith('hg_'))
        self.assertEqual(len(raw), 3 + 48)

        resolved = Token.sudo().resolve(raw)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved['user_id'], self.client.user_id.id)
        self.assertEqual(resolved['scope_names'],
                         {'booking.read', 'system/Patient.read'})
        self.assertEqual(resolved['client_id'], self.client.id)

        # Raw token is never stored — only its SHA-256.
        stored = Token.sudo().search([
            ('token_hash', '=', hashlib.sha256(raw.encode()).hexdigest())])
        self.assertEqual(len(stored), 1)
        self.assertNotIn(raw, stored.mapped('token_hash'))

        # Expiry: force the token into the past → resolve returns None.
        stored.write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        self.assertIsNone(Token.sudo().resolve(raw))

        # Purge cron removes it.
        Token._cron_purge_expired()
        self.assertFalse(stored.exists())

        # Garbage tokens resolve to None.
        self.assertIsNone(Token.sudo().resolve('hg_' + '0' * 48))
        self.assertIsNone(Token.sudo().resolve('not-a-gateway-token'))

    def test_openapi_contains_registered_routes(self):
        doc = build_openapi(self.env)
        self.assertEqual(doc['openapi'], '3.1.0')
        for expected in ('/api/v1/patients', '/api/v1/bookings',
                         '/api/v1/bookings/{order_id}/start',
                         '/api/v1/bookings/{order_id}/cancel',
                         '/api/v1/assignments/today',
                         '/api/v1/products/catalog',
                         '/api/v1/future-bookings'):
            self.assertIn(expected, doc['paths'],
                          'OpenAPI is missing route %s' % expected)
        # Every registry entry made it into the doc.
        self.assertGreaterEqual(
            sum(len(ops) for ops in doc['paths'].values()), len(API_REGISTRY))
        self.assertIn('oauth2ClientCredentials',
                      doc['components']['securitySchemes'])
        # Wrapped POST endpoints carry request bodies.
        cancel = doc['paths']['/api/v1/bookings/{order_id}/cancel']['post']
        self.assertIn('requestBody', cancel)

    def test_outbox_row_on_fso_cancellation(self):
        fso = _get_fso_fixture(self.env)
        reason = self.env['health.booking.cancellation.reason'].search(
            [], limit=1)
        if not reason:
            reason = self.env['health.booking.cancellation.reason'].create({
                'name': 'Gateway Test Reason',
                'reason_type_id': self.env['health.lookup.value']._default_for('cancellation_reason_type', 'patient'),
            })
        outbox_before = self.env['integration.outbox'].search_count(
            [('event_code', '=', 'booking.cancelled')])

        fso.cancel_with_reason(reason.id, 'gateway test cancellation')
        self.assertEqual(fso.state, 'cancelled')

        rows = self.env['integration.outbox'].search([
            ('event_code', '=', 'booking.cancelled'),
            ('res_model', '=', 'health.fieldservice.order'),
            ('res_id', '=', fso.id),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            self.env['integration.outbox'].search_count(
                [('event_code', '=', 'booking.cancelled')]),
            outbox_before + 1)
        payload = rows.payload
        self.assertEqual(payload['event'], 'booking.cancelled')
        self.assertEqual(payload['id'], fso.id)
        self.assertEqual(payload['data']['state'], 'cancelled')
        self.assertEqual(payload['data']['patient_id'], fso.patient_id.id)
        # PHI minimization: no phone numbers or clinical narrative.
        self.assertNotIn('phone', payload['data'])
        self.assertNotIn('clinical_notes', payload['data'])
        # Also emitted booking.created on the create() hook.
        self.assertTrue(self.env['integration.outbox'].search_count([
            ('event_code', '=', 'booking.created'),
            ('res_id', '=', fso.id),
        ]))

    def test_webhook_hmac_signature(self):
        subscription = self.env['webhook.subscription'].create({
            'name': 'Test Hook',
            'target_url': 'https://example.com/hook',
            'event_codes': 'booking.cancelled booking.completed',
            'secret': 'super-secret-hmac-key',
        })
        fso = _get_fso_fixture(self.env)
        outbox = self.env['integration.outbox'].emit(
            'booking.cancelled', fso, {'name': fso.name, 'state': 'cancelled'})
        delivery = self.env['webhook.delivery'].create({
            'subscription_id': subscription.id,
            'outbox_id': outbox.id,
        })
        body = delivery._body_bytes()
        signature = delivery._sign(body)
        expected = 'sha256=' + hmac.new(
            b'super-secret-hmac-key', body, hashlib.sha256).hexdigest()
        self.assertEqual(signature, expected)
        # Body is the exact outbox payload — a receiver verifying
        # hmac(secret, raw_body) gets the same digest.
        self.assertEqual(json.loads(body.decode('utf-8')), outbox.payload)
        # Subscription matching helper.
        self.assertTrue(subscription._matches_event('booking.cancelled'))
        self.assertFalse(subscription._matches_event('booking.created'))

    def test_dispatch_creates_deliveries_and_signs_requests(self):
        subscription = self.env['webhook.subscription'].create({
            'name': 'Match Hook',
            'target_url': 'https://example.com/hook2',
            'event_codes': 'gateway.test.event',
            'secret': 'dispatch-secret',
        })
        fso = _get_fso_fixture(self.env)
        outbox = self.env['integration.outbox'].emit(
            'gateway.test.event', fso, {'name': fso.name})

        with patch('odoo.addons.health_api_gateway.models.'
                   'webhook_delivery.requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = 'ok'
            self.env['integration.outbox']._cron_dispatch()

        self.assertEqual(outbox.state, 'dispatched')
        delivery = self.env['webhook.delivery'].search([
            ('subscription_id', '=', subscription.id),
            ('outbox_id', '=', outbox.id)])
        self.assertEqual(len(delivery), 1)
        self.assertEqual(delivery.state, 'sent')
        self.assertEqual(delivery.attempt, 1)
        self.assertEqual(subscription.failure_count, 0)

        # The HTTP POST carried a verifiable HMAC signature and event headers.
        matching = [c for c in mock_post.call_args_list
                    if c.args and c.args[0] == 'https://example.com/hook2']
        self.assertEqual(len(matching), 1)
        call = matching[0]
        body = call.kwargs['data']
        headers = call.kwargs['headers']
        expected_sig = 'sha256=' + hmac.new(
            b'dispatch-secret', body, hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Health19-Signature'], expected_sig)
        self.assertEqual(headers['X-Health19-Event'], 'gateway.test.event')
        self.assertEqual(headers['X-Health19-Delivery'], str(delivery.id))
        self.assertEqual(json.loads(body.decode('utf-8'))['event'],
                         'gateway.test.event')

    def test_delivery_failure_backoff(self):
        subscription = self.env['webhook.subscription'].create({
            'name': 'Failing Hook',
            'target_url': 'https://example.com/failing',
            'event_codes': 'gateway.test.fail',
            'secret': 'fail-secret',
        })
        fso = _get_fso_fixture(self.env)
        outbox = self.env['integration.outbox'].emit(
            'gateway.test.fail', fso, {'name': fso.name})
        delivery = self.env['webhook.delivery'].create({
            'subscription_id': subscription.id,
            'outbox_id': outbox.id,
        })
        with patch('odoo.addons.health_api_gateway.models.'
                   'webhook_delivery.requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = 'server error'
            for _attempt in range(6):
                delivery._attempt_delivery()
        self.assertEqual(delivery.state, 'dead')
        self.assertEqual(delivery.attempt, 6)
        self.assertEqual(subscription.failure_count, 6)

    def test_audit_log_append_only(self):
        row = self.env['api.audit.log'].sudo().log_access(
            user_id=self.env.user.id, client='test-client',
            route='/api/v1/test', method='GET',
            model='res.partner', record_ids=[1, 2], patient_ids=[3],
            status=200, latency_ms=12, ip='127.0.0.1', auth_kind='oauth')
        self.assertEqual(row.resource_ids, '1,2')
        self.assertEqual(row.patient_ids, '3')
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            row.write({'route': '/tampered'})
        with self.assertRaises(UserError):
            row.unlink()

    def test_oauth_client_secret_hashing(self):
        self.assertTrue(self.client._verify_secret('core-secret-123'))
        self.assertFalse(self.client._verify_secret('wrong'))
        self.assertFalse(self.client._verify_secret(''))
        # Plaintext is never stored.
        self.assertNotEqual(self.client.sudo().client_secret_hash,
                            'core-secret-123')


@tagged('post_install', '-at_install')
class TestGatewayHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.client = _make_oauth_client(
            self.env, 'http', ['booking.read'], 'http-secret-456')

    def _token(self, scope=None):
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client.client_id,
            'client_secret': 'http-secret-456',
        }
        if scope:
            data['scope'] = scope
        response = self.url_open('/oauth/token', data=data)
        return response

    def test_oauth_token_scope_intersection(self):
        # Requested scopes are intersected with the client's allowed scopes.
        response = self._token(scope='booking.read booking.write')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['access_token'].startswith('hg_'))
        self.assertEqual(body['token_type'], 'Bearer')
        self.assertEqual(body['scope'], 'booking.read')
        self.assertEqual(body['expires_in'], 3600)

    def test_oauth_token_invalid_client(self):
        response = self.url_open('/oauth/token', data={
            'grant_type': 'client_credentials',
            'client_id': self.client.client_id,
            'client_secret': 'wrong-secret',
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_client')

    def test_oauth_token_invalid_scope(self):
        response = self._token(scope='webhook.manage')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_scope')

    def test_oauth_token_bad_grant_type(self):
        response = self.url_open('/oauth/token', data={'grant_type': 'password'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'unsupported_grant_type')

    def test_wrapped_endpoint_rejects_without_token(self):
        response = self.url_open('/api/v1/bookings')
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertFalse(body['success'])
        self.assertIn('error', body)

    def test_wrapped_endpoint_rejects_missing_scope(self):
        token = self._token(scope='booking.read').json()['access_token']
        response = self.url_open(
            '/api/v1/patients',  # requires patient.read
            headers={'Authorization': 'Bearer %s' % token})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])

    def test_openapi_endpoint(self):
        response = self.url_open('/api/v1/openapi.json')
        self.assertEqual(response.status_code, 200)
        doc = response.json()
        self.assertEqual(doc['openapi'], '3.1.0')
        self.assertIn('/api/v1/bookings', doc['paths'])
        self.assertIn('/oauth/token', json.dumps(doc))

    def test_api_docs_self_contained(self):
        response = self.url_open('/api/docs')
        self.assertEqual(response.status_code, 200)
        html = response.text
        # Zero external network requests (debranding posture).
        self.assertNotIn('cdn.', html)
        self.assertNotIn('https://unpkg', html)
        self.assertIn('/api/v1/openapi.json', html)
