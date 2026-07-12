# -*- coding: utf-8 -*-
"""Tests for health_scribe (handover §4).

The STT backend is ALWAYS mocked at
``odoo.addons.health_scribe.models.scribe_job.requests.post`` — never a real
HTTP call. Scribe jobs are a brand-new model, so the sweep has no live rows to
pollute the assertions; sweep cases run the cron / call ``_process_job``
directly on freshly created jobs.
"""
import base64
import hashlib
import uuid
from unittest.mock import patch, MagicMock

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user

_STT_PATH = 'odoo.addons.health_scribe.models.scribe_job.requests.post'
_AUDIO = b'RIFFxxxxWEBMxxxx-fake-opus-bytes-for-testing-0123456789'


def _fixture(env):
    Province = env['health.catchment.province']
    Facility = env['health.facility']
    Partner = env['res.partner']
    province = Province.search([], limit=1) or Province.create(
        {'name': 'Scribe Province', 'code': 'SCP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Scribe Facility', 'code': 'SCF',
            'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Scribe Patient', 'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id, 'mobile': '0912000111',
    })
    return province, facility, patient


class ScribeCommon:

    @classmethod
    def _setup(cls):
        cls.province, cls.facility, cls.patient = _fixture(cls.env)
        cls.Job = cls.env['health.scribe.job']
        cls._set_cfg(cls.env, enabled=True, stt_endpoint='',
                     allow_cloud=False, language='vi', max_bytes=15728640,
                     max_attempts=3, batch_cap=10, stt_timeout_s=120)

    @staticmethod
    def _set_cfg(env, **kw):
        icp = env['ir.config_parameter'].sudo()
        for key, val in kw.items():
            icp.set_param('health_scribe.%s' % key, str(val))

    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60, 'service_type': 'home_visit',
        })

    def _make_note(self, clinical_notes='<p>ban đầu</p>'):
        return self.env['health.clinical.note'].create({
            'order_id': self._make_fso().id, 'clinical_notes': clinical_notes})

    def _make_job(self, note=None, audio=_AUDIO, mimetype='audio/webm'):
        note = note or self._make_note()
        return self.Job.register_upload(
            note.order_id, note, audio, mimetype, filename='rec.webm',
            duration_s=3.0)

    def _grant_consent(self, ctype='data_sharing', patient=None):
        consent = self.env['health.consent'].create({
            'client_id': (patient or self.patient).id, 'consent_type': ctype,
            'method': 'verbal', 'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today()})
        consent.action_grant()
        return consent

    def _mock_stt(self, text='bệnh nhân ổn định', raises=None):
        m = MagicMock()
        if raises is not None:
            m.side_effect = raises
        else:
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {'text': text}
            m.return_value = resp
        return m


@tagged('post_install', '-at_install')
class TestUpload(HttpCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls.nurse = new_test_user(
            cls.env, login='scribe_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        cls.nurse.catchment_province_id = cls.province.id
        cls.nurse_emp = cls.env['hr.employee'].create(
            {'name': 'Scribe Nurse', 'user_id': cls.nurse.id})

    def _assigned_note(self):
        """A note whose FSO the nurse is assigned to — the production case (a
        nurse uploads audio for HER visit; the FSO record rule requires
        catchment + assignment)."""
        note = self._make_note()
        note.order_id.action_assign_staff_to_fso(
            self.nurse_emp.id, assignment_role='lead')
        return note

    def _upload(self, note, ctype='audio/webm', payload=_AUDIO):
        return self.url_open(
            '/health_pwa/api/fso/%s/upload_audio' % note.order_id.id,
            files={'audio': ('rec.webm', payload, ctype)},
            data={'note_id': str(note.id), 'duration_s': '3.0'})

    def test_happy_upload(self):
        note = self._assigned_note()
        self.authenticate(self.nurse.login, self.nurse.login)
        res = self._upload(note)
        self.assertEqual(res.status_code, 200)
        job = self.Job.sudo().search([('note_id', '=', note.id)])
        self.assertEqual(len(job), 1)
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.audio_sha256, hashlib.sha256(_AUDIO).hexdigest())
        self.assertIn(job.attachment_id, note.audio_ids)
        # photography consent check-log row written (log-only).
        log = self.env['health.consent.check.log'].sudo().search([
            ('client_id', '=', self.patient.id),
            ('consent_type', '=', 'photography')], limit=1)
        self.assertTrue(log)

    def test_non_audio_rejected(self):
        note = self._assigned_note()
        self.authenticate(self.nurse.login, self.nurse.login)
        res = self._upload(note, ctype='text/plain', payload=b'hello')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(self.Job.sudo().search([('note_id', '=', note.id)]))

    def test_oversize_rejected(self):
        self._set_cfg(self.env, max_bytes=10)
        note = self._assigned_note()
        self.authenticate(self.nurse.login, self.nurse.login)
        res = self._upload(note, payload=b'x' * 50)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(self.Job.sudo().search([('note_id', '=', note.id)]))
        self._set_cfg(self.env, max_bytes=15728640)

    def test_replay_same_sha_one_job(self):
        note = self._assigned_note()
        self.authenticate(self.nurse.login, self.nurse.login)
        r1 = self._upload(note)
        r2 = self._upload(note)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()['data']['job_id'],
                         r2.json()['data']['job_id'])
        self.assertEqual(
            len(self.Job.sudo().search([('note_id', '=', note.id)])), 1)


@tagged('post_install', '-at_install')
class TestSweepGates(TransactionCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()

    def test_disabled_does_nothing(self):
        self._set_cfg(self.env, enabled=False,
                      stt_endpoint='http://127.0.0.1:8123/v1/audio/transcriptions')
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt()) as m:
            self.Job.cron_scribe_transcribe()
        self.assertFalse(m.called)
        self.assertEqual(job.state, 'pending')

    def test_empty_endpoint_keeps_pending(self):
        self._set_cfg(self.env, stt_endpoint='')
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt()) as m:
            self.Job.cron_scribe_transcribe()
        self.assertFalse(m.called)
        self.assertEqual(job.state, 'pending')

    def test_public_endpoint_refused(self):
        self._set_cfg(self.env, allow_cloud=False,
                      stt_endpoint='http://8.8.8.8:9000/v1/audio/transcriptions')
        self._grant_consent()
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt()) as m:
            self.Job.cron_scribe_transcribe()
        self.assertFalse(m.called, 'audio must not go to a public host')
        self.assertEqual(job.state, 'pending')

    def test_private_endpoints_pass(self):
        self._grant_consent()
        for endpoint in ('http://10.0.0.5:9000/v1/audio/transcriptions',
                         'http://127.0.0.1:8123/v1/audio/transcriptions',
                         'http://localhost:8123/v1/audio/transcriptions'):
            self.assertTrue(self.Job._endpoint_is_private(endpoint), endpoint)

    def test_allow_cloud_lets_public_through(self):
        self._set_cfg(self.env, allow_cloud=True,
                      stt_endpoint='http://8.8.8.8:9000/v1/audio/transcriptions')
        self._grant_consent()
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt()) as m:
            self.Job.cron_scribe_transcribe()
        self.assertTrue(m.called)
        self.assertEqual(job.state, 'done')


@tagged('post_install', '-at_install')
class TestTranscription(TransactionCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls._set_cfg(cls.env,
                     stt_endpoint='http://127.0.0.1:8123/v1/audio/transcriptions')

    def test_happy_transcription_appends_marker_block(self):
        self._grant_consent()
        note = self._make_note()
        job = self._make_job(note=note)
        with patch(_STT_PATH, self._mock_stt(text='bệnh nhân ổn định')) as m:
            self.Job.cron_scribe_transcribe()
        self.assertTrue(m.called)
        self.assertEqual(job.state, 'done')
        self.assertEqual(job.transcript, 'bệnh nhân ổn định')
        body = str(note.clinical_notes or '')
        self.assertIn('vui lòng kiểm tra', body)
        self.assertIn('bệnh nhân ổn định', body)
        # The block must be REAL html, not escaped into literal text.
        self.assertIn('<em>[Bản ghi', body)
        self.assertNotIn('&lt;em&gt;', body)
        # The prior note content survives the append.
        self.assertIn('ban đầu', body)
        # §5.19: prove the append went through the encrypted ORM path.
        if 'clinical_notes_enc' in note._fields:
            self.assertTrue(note.clinical_notes_enc)
        else:
            self.skipTest('health_phi_encryption not installed')


@tagged('post_install', '-at_install')
class TestRobustness(TransactionCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls._set_cfg(cls.env,
                     stt_endpoint='http://127.0.0.1:8123/v1/audio/transcriptions')

    def test_stt_raises_marks_attempt_pending(self):
        self._grant_consent()
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt(raises=Exception('down'))):
            self.Job.cron_scribe_transcribe()
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempts, 1)
        self.assertIn('down', job.error or '')

    def test_attempts_exhausted_fails(self):
        self._set_cfg(self.env, max_attempts=2)
        self._grant_consent()
        job = self._make_job()
        with patch(_STT_PATH, self._mock_stt(raises=Exception('down'))):
            self.Job.cron_scribe_transcribe()
            self.assertEqual(job.state, 'pending')
            self.Job.cron_scribe_transcribe()
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.attempts, 2)
        self._set_cfg(self.env, max_attempts=3)

    def test_blank_transcript_no_append(self):
        self._grant_consent()
        note = self._make_note(clinical_notes='<p>only this</p>')
        job = self._make_job(note=note)
        with patch(_STT_PATH, self._mock_stt(text='   ')):
            self.Job.cron_scribe_transcribe()
        self.assertEqual(job.state, 'pending')
        self.assertEqual(job.attempts, 1)
        self.assertNotIn('vui lòng kiểm tra', note.clinical_notes or '')

    def test_savepoint_isolation(self):
        self._grant_consent()
        good1 = self._make_job()
        bad = self._make_job()
        good2 = self._make_job()
        real = type(self.Job)._process_job

        def flaky(self2, endpoint, language, timeout):
            if self2.id == bad.id:
                raise ValueError('boom')
            return real(self2, endpoint, language, timeout)
        with patch(_STT_PATH, self._mock_stt()), \
                patch.object(type(self.Job), '_process_job', flaky):
            self.Job.cron_scribe_transcribe()
        self.assertEqual(good1.state, 'done')
        self.assertEqual(good2.state, 'done')

    def test_consent_false_fails_zero_calls(self):
        job = self._make_job()   # no data_sharing consent
        # Scope to this job via _run_jobs (not the global cron): the cron scans
        # ALL pending jobs, which on a live DB includes rows whose patient DOES
        # have consent — that would call the mock and defeat the assertion
        # (ledger §5.17 live-data isolation).
        with patch(_STT_PATH, self._mock_stt()) as m:
            self.Job._run_jobs(job)
        self.assertFalse(m.called)
        self.assertEqual(job.state, 'failed')
        self.assertEqual(job.error, 'consent')


@tagged('post_install', '-at_install')
class TestIdempotency(TransactionCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()
        cls._set_cfg(cls.env,
                     stt_endpoint='http://127.0.0.1:8123/v1/audio/transcriptions')

    def test_resweep_no_double_append(self):
        self._grant_consent()
        note = self._make_note()
        self._make_job(note=note)
        with patch(_STT_PATH, self._mock_stt(text='ghi chú thoại')):
            self.Job.cron_scribe_transcribe()
            self.Job.cron_scribe_transcribe()
        self.assertEqual((note.clinical_notes or '').count('vui lòng kiểm tra'), 1)

    def test_transcribe_now_on_done_is_noop(self):
        self._grant_consent()
        note = self._make_note()
        job = self._make_job(note=note)
        with patch(_STT_PATH, self._mock_stt(text='xong')):
            self.Job.cron_scribe_transcribe()
        self.assertEqual(job.state, 'done')
        manager = new_test_user(
            self.env, login='scribe_mgr_%s' % uuid.uuid4().hex[:8],
            groups='base.group_user,health_base.group_healthcare_manager')
        manager.catchment_province_id = self.province.id
        with patch(_STT_PATH, self._mock_stt()) as m:
            job.with_user(manager).action_transcribe_now()
        self.assertFalse(m.called)
        self.assertEqual((note.clinical_notes or '').count('vui lòng kiểm tra'), 1)


@tagged('post_install', '-at_install')
class TestAcl(TransactionCase, ScribeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup()

    def _user(self, group_xmlid):
        return new_test_user(
            self.env, login='scribe_%s' % uuid.uuid4().hex[:8],
            groups='base.group_user,%s' % group_xmlid)

    def test_plain_nurse_cannot_read_job(self):
        job = self._make_job()
        nurse = self._user('health_base.group_healthcare_nurse')
        with self.assertRaises(AccessError):
            job.with_user(nurse).read(['state'])

    def test_manager_can_read_job(self):
        job = self._make_job()
        manager = self._user('health_base.group_healthcare_manager')
        manager.catchment_province_id = self.province.id
        self.assertEqual(job.with_user(manager).read(['state'])[0]['state'],
                         'pending')


@tagged('post_install', '-at_install')
class TestShellAssets(HttpCase):

    def test_shell_serves_scribe_assets_at_1_9_0(self):
        user = new_test_user(
            self.env, login='scribe_shell_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('scribe.css?v=1.15.0', body)
        self.assertIn('scribe.js?v=1.15.0', body)
        self.assertIn('1.15.0', body)
        # Co-resident shell modules pinned to the same bumped version.
        self.assertIn('daystrip.js?v=1.15.0', body)
        self.assertIn('telehealth.js?v=1.15.0', body)
        self.assertIn('ergo.css?v=1.15.0', body)
