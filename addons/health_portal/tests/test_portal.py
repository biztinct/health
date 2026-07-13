# -*- coding: utf-8 -*-
"""Patient My Care portal — Phase 4A (foundation + My Visits).

The load-bearing properties: a token resolves to exactly ONE patient (no
cross-patient leak), invalid/revoked/expired tokens are indistinguishable
(neutral page, no oracle, no PHI), and the access log is append-only.
"""
import uuid
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged


class PortalFixtures:

    @classmethod
    def _setup(cls):
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'PP Prov %s' % uuid.uuid4().hex[:5],
            'code': 'PP%s' % uuid.uuid4().hex[:3]})
        cls.facility = cls.env['health.facility'].create({
            'name': 'PP Facility', 'code': 'PPF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City', 'phone': '02499999999',
            'catchment_province_id': cls.province.id})

    @classmethod
    def _patient(cls, name):
        return cls.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})

    @classmethod
    def _order(cls, patient, when, state):
        o = cls.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': when, 'scheduled_duration': 60,
            'service_type': 'home_visit'})
        o.state = state
        return o


@tagged('post_install', '-at_install')
class TestPortalModel(TransactionCase, PortalFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP Patient A')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})

    def test_token_generated_and_url(self):
        self.assertTrue(self.access.token)
        self.assertGreaterEqual(len(self.access.token), 32)
        self.assertIn('/my/care/%s' % self.access.token, self.access.portal_url)

    def test_one_access_per_patient(self):
        again = self.env['health.portal.access'].get_or_create_for(self.patient)
        self.assertEqual(again, self.access)

    def test_rotate_changes_token(self):
        old = self.access.token
        self.access.action_rotate_token()
        self.assertNotEqual(self.access.token, old)

    def test_get_or_create_reactivates(self):
        self.access.action_revoke()
        again = self.env['health.portal.access'].get_or_create_for(self.patient)
        self.assertEqual(again, self.access)
        self.assertEqual(again.state, 'active')

    def test_expiry(self):
        self.assertFalse(self.access._is_expired())
        self.access.expires_at = fields.Datetime.now() - timedelta(hours=1)
        self.assertTrue(self.access._is_expired())

    def test_visits_scoped_and_no_phi(self):
        now = fields.Datetime.now()
        self._order(self.patient, now + timedelta(days=1), 'assigned')
        self._order(self.patient, now - timedelta(days=3), 'closed')
        # Another patient's visit must never appear.
        other = self._patient('PP Patient B')
        self._order(other, now + timedelta(days=1), 'assigned')
        ctx = self.access._hub_context()
        self.assertEqual(len(ctx['upcoming']), 1)
        self.assertEqual(len(ctx['history']), 1)
        # No clinical PHI keys on a visit row.
        row = ctx['upcoming'][0]
        for k in row:
            self.assertNotIn(k, ('diagnosis', 'clinical_notes', 'notes'))

    def test_visit_row_no_facility_phone(self):
        # A facility without a phone must not crash the hub (the fixture
        # facility has one, which masked an AttributeError in QA).
        nophone = self.env['health.facility'].create({
            'name': 'PP NoPhone', 'code': 'PPN%s' % uuid.uuid4().hex[:3],
            'street': '2 St', 'city': 'City',
            'catchment_province_id': self.province.id})
        order = self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': nophone.id,
            'scheduled_datetime': fields.Datetime.now() + timedelta(days=2),
            'scheduled_duration': 60, 'service_type': 'home_visit'})
        order.state = 'assigned'
        ctx = self.access._hub_context()  # must not raise
        row = [r for r in ctx['upcoming'] if r['ref'] == order.name][0]
        self.assertEqual(row['facility_phone'], '')

    def test_hub_has_balance_and_rebook(self):
        # 4D: hub carries package balance + rebook keys; empty/graceful with none.
        ctx = self.access._hub_context()
        self.assertEqual(ctx['packages'], [])  # patient has no package
        self.assertIn('invite_token', ctx['rebook'])
        self.assertEqual(ctx['rebook']['invite_token'], '')  # no sent invite
        self.assertEqual(ctx['rebook']['facility_phone'], '02499999999')  # fixture

    def test_log_append_only(self):
        self.access._record_access('hub', '1.2.3.4')
        log = self.env['health.portal.access.log'].search(
            [('access_id', '=', self.access.id)], limit=1)
        self.assertTrue(log)
        with self.assertRaises(UserError):
            log.write({'section': 'x'})
        with self.assertRaises(UserError):
            log.unlink()


@tagged('post_install', '-at_install')
class TestPortalPublic(HttpCase, PortalFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP Http Patient')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})
        cls._order(cls.patient, fields.Datetime.now() + timedelta(days=1),
                   'assigned')

    def _get(self, token):
        return self.url_open('/my/care/%s' % token)

    def test_valid_token_shows_visits(self):
        r = self._get(self.access.token)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Chăm sóc', r.text)  # hub rendered
        self.assertIn('sắp tới', r.text)   # upcoming section

    def test_unknown_token_neutral(self):
        r = self._get('deadbeef_not_a_real_token')
        self.assertEqual(r.status_code, 200)
        self.assertIn('không khả dụng', r.text)  # neutral page
        self.assertNotIn('PP Http Patient', r.text)  # no patient name leak

    def test_revoked_token_neutral(self):
        self.access.action_revoke()
        r = self._get(self.access.token)
        self.assertIn('không khả dụng', r.text)
        self.access.action_reactivate()

    def test_expired_token_neutral(self):
        self.access.expires_at = fields.Datetime.now() - timedelta(hours=1)
        r = self._get(self.access.token)
        self.assertIn('không khả dụng', r.text)
        self.access.expires_at = False


@tagged('post_install', '-at_install')
class TestPortalRecordsHttp(HttpCase, PortalFixtures):
    """Phase 4B — records routes over real HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP RecHttp Patient')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})
        cls.order = cls._order(
            cls.patient, fields.Datetime.now() - timedelta(days=1), 'completed')
        cls.note = cls.env['health.clinical.note'].create({
            'order_id': cls.order.id, 'clinical_notes': '<p>BP stable</p>',
            'diagnosis': 'Routine review'})
        cls.note.action_finalize()

    def test_records_list_and_detail_and_download(self):
        base = '/my/care/%s' % self.access.token
        lst = self.url_open(base + '/records')
        self.assertEqual(lst.status_code, 200)
        self.assertIn('Hồ sơ', lst.text)
        det = self.url_open('%s/records/%s' % (base, self.note.id))
        self.assertEqual(det.status_code, 200)
        self.assertIn('Routine review', det.text)  # patient sees their record
        dl = self.url_open('%s/records/%s/download' % (base, self.note.id))
        self.assertEqual(dl.status_code, 200)
        self.assertIn('text/plain', dl.headers.get('Content-Type', ''))
        self.assertIn('Routine review', dl.text)

    def test_record_bad_id_neutral(self):
        r = self.url_open('/my/care/%s/records/999999999' % self.access.token)
        self.assertEqual(r.status_code, 200)
        self.assertIn('không khả dụng', r.text)  # neutral, not the note


@tagged('post_install', '-at_install')
class TestPortalRecords(TransactionCase, PortalFixtures):
    """Phase 4B — My Records: finalized-only, patient-scoped."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP Rec Patient')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})
        cls.order = cls._order(
            cls.patient, fields.Datetime.now() - timedelta(days=1), 'completed')

    def _note(self, order, **kw):
        vals = {'order_id': order.id, 'clinical_notes': '<p>BP stable</p>',
                'diagnosis': 'Routine review'}
        vals.update(kw)
        return self.env['health.clinical.note'].create(vals)

    def test_only_finalized_notes_listed(self):
        draft = self._note(self.order)
        final = self._note(self.order)
        final.action_finalize()
        ids = [r['id'] for r in self.access._records_ctx()['records']]
        self.assertIn(final.id, ids)
        self.assertNotIn(draft.id, ids)

    def test_note_scope_and_content(self):
        final = self._note(self.order)
        final.action_finalize()
        note = self.access._note_or_false(final.id)
        self.assertEqual(note, final)
        ctx = self.access._note_ctx(note)
        labels = [s[0] for s in ctx['sections']]
        values = [s[1] for s in ctx['sections']]
        self.assertIn('Chẩn đoán', labels)
        self.assertIn('Routine review', values)
        self.assertIn('Routine review', self.access._note_text(note))

    def test_cannot_view_other_patients_note(self):
        other_p = self._patient('PP Rec Other')
        other_o = self._order(other_p, fields.Datetime.now(), 'completed')
        other_note = self._note(other_o)
        other_note.action_finalize()
        # This patient's token must not resolve another patient's note.
        self.assertFalse(self.access._note_or_false(other_note.id))

    def test_cannot_view_draft_note(self):
        draft = self._note(self.order)
        self.assertFalse(self.access._note_or_false(draft.id))


# A valid 1x1 transparent PNG (signature evidence; the field image-validates).
_SIG_B64 = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
            'z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestPortalConsents(TransactionCase, PortalFixtures):
    """Phase 4C — view + withdraw + grant-with-signature."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP Consent Patient')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})
        cls.Consent = cls.env['health.consent']

    def _active(self, ctype):
        return self.Consent.check_consent(self.patient, ctype)

    def test_grant_then_withdraw(self):
        self.assertFalse(self._active('data_sharing'))
        self.assertTrue(self.access._portal_grant('data_sharing', _SIG_B64))
        self.assertTrue(self._active('data_sharing'))
        self.access._portal_withdraw('data_sharing')
        self.assertFalse(self._active('data_sharing'))

    def test_grant_requires_signature(self):
        self.assertFalse(self.access._portal_grant('marketing', ''))
        self.assertFalse(self._active('marketing'))

    def test_grant_rejects_unmanaged_type(self):
        # 'service' is a care-delivery consent — not patient-toggleable.
        self.assertFalse(self.access._portal_grant('service', _SIG_B64))
        self.assertFalse(self.access._portal_withdraw('service'))

    def test_consents_ctx_status(self):
        self.access._portal_grant('photography', _SIG_B64)
        rows = {r['type']: r['active'] for r in self.access._consents_ctx()['consents']}
        self.assertTrue(rows['photography'])
        self.assertFalse(rows['data_sharing'])
        self.assertIn('marketing', rows)


@tagged('post_install', '-at_install')
class TestPortalConsentsHttp(HttpCase, PortalFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.patient = cls._patient('PP Consent Http')
        cls.access = cls.env['health.portal.access'].create(
            {'patient_id': cls.patient.id})

    def test_consent_flow_over_http(self):
        base = '/my/care/%s' % self.access.token
        page = self.url_open(base + '/consents')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Chưa đồng ý', page.text)
        # grant form renders
        gf = self.url_open(base + '/consents/data_sharing/grant')
        self.assertEqual(gf.status_code, 200)
        self.assertIn('pad', gf.text)  # signature canvas
        # grant POST with a signature -> active
        self.url_open(base + '/consents/data_sharing/grant',
                      data={'signature': 'data:image/png;base64,' + _SIG_B64})
        self.assertTrue(
            self.env['health.consent'].check_consent(self.patient, 'data_sharing'))
        # withdraw POST -> inactive (non-empty data so url_open sends POST)
        self.url_open(base + '/consents/data_sharing/withdraw', data={'ok': '1'})
        self.assertFalse(
            self.env['health.consent'].check_consent(self.patient, 'data_sharing'))
