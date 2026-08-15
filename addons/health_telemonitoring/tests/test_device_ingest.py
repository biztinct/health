# -*- coding: utf-8 -*-
"""Phase 2 — device registry + ingestion endpoint tests.

TransactionCase covers the registry/receipt models (unique index, retire
guard, catchment, immutability, GC). HttpCase drives the real
``POST /api/v1/telemonitoring/readings`` through the gateway (auth ladder,
happy path, idempotency, BP pairing, partials, caps, engine interplay,
rate-limit path) — token issuance clones health_api_gateway's own test setup.
"""
import json
import os
from datetime import timedelta
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.health_telemonitoring.models import tm_config


def _get_fixture(env, suffix=''):
    """Province + facility + patient (conventions §6)."""
    Partner = env['res.partner']
    Facility = env['health.facility']
    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'TM Dev Province', 'code': 'TMD'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'TM Dev Facility', 'code': 'TMDF',
            'street': '1 Dev Street', 'city': 'Test City',
            'catchment_province_id': province.id})
    patient = Partner.create({
        'name': 'TM Device Patient%s' % suffix,
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id})
    return province, facility, patient


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# =====================================================================
# Registry + receipt models (TransactionCase)
# =====================================================================
@tagged('post_install', '-at_install')
class TestDeviceRegistry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Device = cls.env['health.monitor.device']
        cls.Receipt = cls.env['health.device.receipt']
        cls.nurse = new_test_user(
            cls.env, login='tm_dev_nurse', password='tm_dev_nurse',
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province

    def _device(self, external_id='DEV-A', **kw):
        vals = dict(name='Omron X5', client_id=self.patient.id,
                    device_type='bp_monitor', external_id=external_id)
        vals.update(kw)
        return self.Device.create(vals)

    # -- 1a: external_id unique index --------------------------------
    def test_01a_external_id_unique(self):
        self._device(external_id='DEV-UNIQ')
        with self.assertRaises(IntegrityError):
            with mute_logger('odoo.sql_db'), self.env.cr.savepoint():
                self._device(external_id='DEV-UNIQ')
                self.env.flush_all()

    # -- 1b: retire/unlink guard (ACL) -------------------------------
    def test_01b_unlink_acl(self):
        device = self._device(external_id='DEV-DEL')
        with self.assertRaises(AccessError):
            device.with_user(self.nurse).unlink()
        # admin (su test env) may delete.
        device.unlink()
        self.assertFalse(device.exists())

    # -- 1c: catchment computed --------------------------------------
    def test_01c_catchment(self):
        device = self._device(external_id='DEV-CATCH')
        self.assertEqual(device.catchment_province_id, self.province)

    # -- 13a: receipt immutable --------------------------------------
    def test_13a_receipt_immutable(self):
        device = self._device(external_id='DEV-RCPT')
        receipt = self.Receipt.create({
            'device_id': device.id, 'client_batch_uuid': 'batch-1',
            'state': 'applied', 'result_json': '{}'})
        with self.assertRaises(UserError):
            receipt.write({'state': 'rejected'})

    # -- 13b: receipt unique index -----------------------------------
    def test_13b_receipt_unique(self):
        device = self._device(external_id='DEV-RCPT2')
        self.Receipt.create({
            'device_id': device.id, 'client_batch_uuid': 'dup-batch',
            'state': 'applied', 'result_json': '{}'})
        with self.assertRaises(IntegrityError):
            with mute_logger('odoo.sql_db'), self.env.cr.savepoint():
                self.Receipt.create({
                    'device_id': device.id, 'client_batch_uuid': 'dup-batch',
                    'state': 'applied', 'result_json': '{}'})
                self.env.flush_all()

    # -- 13c: GC cron removes >retention rows ------------------------
    def test_13c_receipt_gc(self):
        device = self._device(external_id='DEV-GC')
        old = self.Receipt.create({
            'device_id': device.id, 'client_batch_uuid': 'old-batch',
            'state': 'applied', 'result_json': '{}'})
        fresh = self.Receipt.create({
            'device_id': device.id, 'client_batch_uuid': 'fresh-batch',
            'state': 'applied', 'result_json': '{}'})
        # Backdate the old one past the 90-day horizon (create_date is
        # ORM-managed → raw SQL, flush/invalidate around it, §5.9).
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_device_receipt SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=120), old.id))
        self.env.invalidate_all()
        self.Receipt.cron_gc_receipts()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    # -- 15: rider present (static guard; UI browser-QA'd at review) --
    def test_15_rider_static_guard(self):
        here = os.path.dirname(__file__)
        path = os.path.normpath(os.path.join(
            here, '..', '..', 'health_vitals',
            'static', 'src', 'js', 'vitals-components.js'))
        with open(path, encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn('__vitalsFabFetchWrapped', js)
        self.assertIn('booking-detail-modal-content', js)
        self.assertIn("modalFsoState === 'in_progress'", js)


# =====================================================================
# Ingestion endpoint (HttpCase — real gateway round-trips)
# =====================================================================
@tagged('post_install', '-at_install')
class TestDeviceIngest(HttpCase):

    def setUp(self):
        super().setUp()
        self.province, self.facility, self.patient = _get_fixture(
            self.env, suffix=' HTTP')
        self.Device = self.env['health.monitor.device']
        self.Obs = self.env['health.observation']
        self.Receipt = self.env['health.device.receipt']
        self.device = self.Device.create({
            'name': 'Omron HTTP', 'client_id': self.patient.id,
            'device_type_id': self.env['health.lookup.value']._default_for('monitor_device_type', 'bp_monitor'), 'external_id': 'OMRON-HTTP-1',
            'state': 'active'})
        # §5.32 discipline: pin off side-effects we do not assert on.
        ICP = self.env['ir.config_parameter'].sudo()
        self._saved = {
            'act': ICP.get_param('health_telemonitoring.activity_on_critical'),
        }
        ICP.set_param('health_telemonitoring.activity_on_critical', 'False')
        # OAuth client with the ingest scope.
        scopes = self.env['api.key.scope'].search(
            [('code', 'in', ['telemonitoring.ingest'])])
        self.assertTrue(scopes, 'telemonitoring.ingest scope must be seeded')
        user = new_test_user(self.env, login='tm_ingest_svc',
                             groups='base.group_user')
        self.client = self.env['gateway.oauth.client'].create({
            'name': 'TM Ingest Client', 'user_id': user.id,
            'allowed_scope_ids': [(6, 0, scopes.ids)], 'token_lifetime': 3600})
        self.secret = 'tm-ingest-secret-1'
        self.client._set_secret(self.secret)
        self.env.flush_all()

    def tearDown(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.activity_on_critical',
            self._saved['act'] or 'True')
        super().tearDown()

    # -- helpers -------------------------------------------------------
    def _token(self, scope='telemonitoring.ingest'):
        resp = self.url_open('/oauth/token', data={
            'grant_type': 'client_credentials',
            'client_id': self.client.client_id,
            'client_secret': self.secret,
            'scope': scope})
        return resp.json().get('access_token')

    def _post(self, payload, token='__default__'):
        if token == '__default__':
            token = self._token()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        return self.url_open(
            '/api/v1/telemonitoring/readings',
            data=json.dumps(payload), headers=headers)

    def _batch(self, readings, uuid='batch-http-1', external_id='OMRON-HTTP-1'):
        return {'device_external_id': external_id,
                'client_batch_uuid': uuid, 'readings': readings}

    # -- 2: auth ladder ----------------------------------------------
    def test_02_auth_ladder(self):
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        body = self._batch([{'code': 'hr', 'value': 72, 'taken_at': when}])
        # No token → 401.
        r = self._post(body, token=None)
        self.assertEqual(r.status_code, 401)
        # Token lacking the scope → 403. Give the client booking.read too.
        bad = self.env['gateway.oauth.client'].create({
            'name': 'TM Bad', 'user_id': self.client.user_id.id,
            'allowed_scope_ids': [(6, 0, self.env['api.key.scope'].search(
                [('code', '=', 'booking.read')]).ids)]})
        bad._set_secret('bad-secret')
        self.env.flush_all()
        bad_tok = self.url_open('/oauth/token', data={
            'grant_type': 'client_credentials', 'client_id': bad.client_id,
            'client_secret': 'bad-secret', 'scope': 'booking.read'}
        ).json()['access_token']
        r = self._post(body, token=bad_tok)
        self.assertEqual(r.status_code, 403)
        # Proper scope → 200.
        r = self._post(body)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

    # -- 3: unknown device 404 neutral; suspended 422 ----------------
    def test_03_device_states(self):
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        r = self._post(self._batch(
            [{'code': 'hr', 'value': 72, 'taken_at': when}],
            external_id='NOPE-XYZ'))
        self.assertEqual(r.status_code, 404)
        self.device.state = 'suspended'
        self.env.flush_all()
        r = self._post(self._batch(
            [{'code': 'hr', 'value': 72, 'taken_at': when}]))
        self.assertEqual(r.status_code, 422)

    # -- 4: happy path -----------------------------------------------
    def test_04_happy_path(self):
        taken = fields.Datetime.now() - timedelta(minutes=5)
        when = _iso(taken)
        body = self._batch([
            {'code': 'hr', 'value': 72, 'taken_at': when},
            {'code': 'spo2_po', 'value': 97, 'taken_at': when},
            {'code': 'temp', 'value': 36.8, 'taken_at': when}],
            uuid='happy-1')
        r = self._post(body)
        self.assertEqual(r.status_code, 200)
        data = r.json()['data']
        self.assertEqual(data['accepted'], 3)
        self.assertEqual(data['rejected'], [])
        obs = self.Obs.search([('client_id', '=', self.patient.id)])
        self.assertEqual(len(obs), 3)
        marker = 'Omron HTTP (OMRON-HTTP-1)'
        self.assertTrue(all(o.device == marker for o in obs))
        hr = obs.filtered(lambda o: o.vitals_type_id.code == 'hr')
        self.assertEqual(hr.value_quantity, 72)
        self.assertEqual(fields.Datetime.to_string(hr.effective_datetime),
                         fields.Datetime.to_string(taken))
        self.device.invalidate_recordset()
        self.assertTrue(self.device.last_reading_at)
        receipt = self.Receipt.search([('device_id', '=', self.device.id),
                                       ('client_batch_uuid', '=', 'happy-1')])
        self.assertEqual(receipt.state, 'applied')

    # -- 5: idempotent replay ----------------------------------------
    def test_05_idempotent(self):
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        body = self._batch([{'code': 'hr', 'value': 80, 'taken_at': when}],
                           uuid='idem-1')
        r1 = self._post(body)
        r2 = self._post(body)
        self.assertEqual(r1.json()['data'], r2.json()['data'])
        self.assertEqual(
            self.Obs.search_count([('client_id', '=', self.patient.id)]), 1)
        self.assertEqual(
            self.Receipt.search_count([('device_id', '=', self.device.id),
                                       ('client_batch_uuid', '=', 'idem-1')]), 1)

    # -- 6: BP pairing -----------------------------------------------
    def test_06_bp_pairing(self):
        t1 = _iso(fields.Datetime.now() - timedelta(minutes=5))
        t2 = _iso(fields.Datetime.now() - timedelta(minutes=3))
        body = self._batch([
            {'code': 'bp_sys', 'value': 132, 'taken_at': t1},
            {'code': 'bp_dia', 'value': 84, 'taken_at': t1},
            {'code': 'bp_sys', 'value': 128, 'taken_at': t2}],  # unpaired
            uuid='bp-1')
        r = self._post(body)
        self.assertEqual(r.json()['data']['accepted'], 3)
        panels = self.Obs.search([('client_id', '=', self.patient.id),
                                  ('vitals_type_id.code', '=', 'bp_panel')])
        self.assertEqual(len(panels), 1)
        self.assertEqual(len(panels.child_ids), 2)
        standalone = self.Obs.search([
            ('client_id', '=', self.patient.id),
            ('vitals_type_id.code', '=', 'bp_sys'),
            ('parent_id', '=', False)])
        self.assertEqual(len(standalone), 1)
        self.assertEqual(standalone.value_quantity, 128)

    # -- 7: partial batch --------------------------------------------
    def test_07_partial(self):
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        body = self._batch([
            {'code': 'hr', 'value': 500, 'taken_at': when},   # implausible
            {'code': 'hr', 'value': 75, 'taken_at': when}],   # good
            uuid='partial-1')
        r = self._post(body)
        data = r.json()['data']
        self.assertEqual(data['accepted'], 1)
        self.assertEqual(len(data['rejected']), 1)
        self.assertEqual(data['rejected'][0]['index'], 0)
        self.assertEqual(data['rejected'][0]['reason'], 'implausible')
        receipt = self.Receipt.search([('client_batch_uuid', '=', 'partial-1')])
        self.assertEqual(receipt.state, 'partial')
        self.assertEqual(
            self.Obs.search_count([('client_id', '=', self.patient.id),
                                   ('value_quantity', '=', 75)]), 1)

    # -- 8: reason coverage ------------------------------------------
    def test_08_reasons(self):
        now = fields.Datetime.now()
        body = self._batch([
            {'code': 'bogus', 'value': 5, 'taken_at': _iso(now)},
            {'code': 'hr', 'value': 70},                       # missing taken_at
            {'code': 'hr', 'value': 70, 'taken_at': _iso(now + timedelta(minutes=30))},
            {'code': 'hr', 'value': 70, 'taken_at': _iso(now - timedelta(days=10))}],
            uuid='reasons-1')
        r = self._post(body)
        data = r.json()['data']
        self.assertEqual(data['accepted'], 0)
        reasons = {row['index']: row['reason'] for row in data['rejected']}
        self.assertEqual(reasons[0], 'unknown_code')
        self.assertEqual(reasons[1], 'missing_taken_at')
        self.assertEqual(reasons[2], 'future_reading')
        self.assertEqual(reasons[3], 'stale_reading')
        receipt = self.Receipt.search([('client_batch_uuid', '=', 'reasons-1')])
        self.assertEqual(receipt.state, 'rejected')

    # -- 9: oversized batch → 422, no receipt ------------------------
    def test_09_oversize(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.ingest_max_batch', '2')
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        body = self._batch(
            [{'code': 'hr', 'value': 70, 'taken_at': when}] * 3, uuid='big-1')
        r = self._post(body)
        self.assertEqual(r.status_code, 422)
        self.assertFalse(self.Receipt.search_count(
            [('client_batch_uuid', '=', 'big-1')]))

    # -- 10: daily flood cap -----------------------------------------
    def test_10_flood_cap(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'health_telemonitoring.ingest_daily_cap_per_device', '2')
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        first = self._batch([
            {'code': 'hr', 'value': 70, 'taken_at': when},
            {'code': 'spo2_po', 'value': 96, 'taken_at': when}], uuid='cap-1')
        self.assertEqual(self._post(first).status_code, 200)
        # Now 2 observations exist today → next batch trips the cap.
        second = self._batch(
            [{'code': 'hr', 'value': 71, 'taken_at': when}], uuid='cap-2')
        r = self._post(second)
        self.assertEqual(r.status_code, 429)
        self.assertFalse(self.Receipt.search_count(
            [('client_batch_uuid', '=', 'cap-2')]))

    # -- 11: threshold interplay -------------------------------------
    def test_11_threshold_mirror(self):
        hr_type = self.env.ref('health_vitals.vitals_type_heart_rate')
        self.env['health.vitals.threshold'].create({
            'client_id': self.patient.id, 'vitals_type_id': hr_type.id,
            'severity': 'critical', 'max_value': 100,
            'escalation_action': 'none'})
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        self._post(self._batch(
            [{'code': 'hr', 'value': 140, 'taken_at': when}], uuid='thr-1'))
        alert = self.env['health.monitor.alert'].search([
            ('client_id', '=', self.patient.id), ('rule', '=', 'threshold')])
        self.assertTrue(alert)
        self.assertEqual(alert.vitals_type_id, hr_type)

    # -- 12: NEWS2 interplay -----------------------------------------
    def test_12_news2_chain(self):
        taken = fields.Datetime.now() - timedelta(minutes=5)
        when = _iso(taken)
        body = self._batch([
            {'code': 'rr', 'value': 16, 'taken_at': when},
            {'code': 'spo2_po', 'value': 98, 'taken_at': when},
            {'code': 'hr', 'value': 70, 'taken_at': when},
            {'code': 'temp', 'value': 36.6, 'taken_at': when},
            {'code': 'bp_sys', 'value': 120, 'taken_at': when},
            {'code': 'bp_dia', 'value': 80, 'taken_at': when}],
            uuid='news2-1')
        r = self._post(body)
        self.assertEqual(r.json()['data']['accepted'], 6)
        score = self.env['health.ews.score'].search([
            ('client_id', '=', self.patient.id), ('superseded', '=', False)])
        self.assertEqual(len(score), 1)
        self.assertEqual(score.total, 0)

    # -- 14: rate-limit path -----------------------------------------
    def test_14_rate_limit(self):
        when = _iso(fields.Datetime.now() - timedelta(minutes=5))
        body = self._batch(
            [{'code': 'hr', 'value': 70, 'taken_at': when}], uuid='rate-1')
        Counter = type(self.env['gateway.rate.counter'])
        with patch.object(Counter, 'hit', lambda self, key: (False, 30)):
            r = self._post(body)
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.headers.get('Retry-After'), '30')
