# -*- coding: utf-8 -*-
"""Tests for health_ai_coding (handover §4).

The LLM is ALWAYS mocked at ``bi.ai.provider._complete`` — never a real HTTP
call. Live-data isolation (ledger §5.17): the sweep searches every clinical
note in the DB, so the fine-grained cases call ``_process_note`` /
``_build_user_prompt`` directly on a freshly-created note; only the gate and
batch-cap behaviours drive the full ``cron_ai_coding_sweep`` (with newest-first
ordering guaranteeing our just-created notes sort ahead of live ones)."""
import json
import uuid
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


def _fixture(env):
    Province = env['health.catchment.province']
    Facility = env['health.facility']
    Partner = env['res.partner']
    province = Province.search([], limit=1) or Province.create(
        {'name': 'AI Province', 'code': 'AIP'})
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'AI Facility', 'code': 'AIF',
            'timezone': 'Asia/Ho_Chi_Minh',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Nguyen Van Testpatient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
        'mobile': '0912345678',
        'email': 'testpatient@example.com',
        'street': '99 Secret Alley',
    })
    ollama = env['bi.ai.provider'].create({
        'name': 'AI Test Ollama', 'provider': 'ollama',
        'endpoint': 'http://localhost:11434/api/chat',
        'model_name': 'qwen2',
    })
    cloud = env['bi.ai.provider'].create({
        'name': 'AI Test Cloud', 'provider': 'openai',
        'endpoint': 'https://api.openai.com/v1/chat/completions',
        'model_name': 'gpt-4o-mini',
    })
    return province, facility, patient, ollama, cloud


@tagged('post_install', '-at_install')
class AiCodingBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.province, cls.facility, cls.patient,
         cls.ollama, cls.cloud) = _fixture(cls.env)
        cls.Sugg = cls.env['health.ai.code.suggestion']
        cls.Note = cls.env['health.clinical.note']
        cls.code_i10 = cls._ensure_icd10(cls.env, 'I10', 'Essential hypertension')
        cls.code_e11 = cls._ensure_icd10(cls.env, 'E11', 'Type 2 diabetes mellitus')
        cls._set_cfg(cls.env, enabled=True, provider_id=cls.ollama.id,
                     allow_cloud=False, batch_cap=25,
                     max_prompt_chars=4000, max_attempts=3)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _ensure_icd10(env, code, display):
        rec = env['medical.code'].get('icd10', code)
        if rec:
            return rec
        system = env['medical.coding.system'].search(
            [('code', '=', 'icd10')], limit=1)
        if not system:
            system = env['medical.coding.system'].create({
                'name': 'ICD-10', 'code': 'icd10',
                'uri': 'http://hl7.org/fhir/sid/icd-10'})
        return env['medical.code'].create({
            'system_id': system.id, 'code': code, 'display': display})

    @staticmethod
    def _set_cfg(env, **kw):
        icp = env['ir.config_parameter'].sudo()
        for key, val in kw.items():
            icp.set_param('health_ai_coding.%s' % key, str(val))

    def _make_fso(self):
        return self.env['health.fieldservice.order'].create({
            'patient_id': self.patient.id,
            'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60,
            'service_type': 'home_visit',
        })

    def _make_note(self, diagnosis='Tang huyet ap va dai thao duong',
                   clinical_notes=None):
        return self.Note.create({
            'order_id': self._make_fso().id,
            'diagnosis': diagnosis,
            'clinical_notes': clinical_notes or False,
        })

    def _grant_consent(self, patient=None):
        consent = self.env['health.consent'].create({
            'client_id': (patient or self.patient).id,
            'consent_type_id': self.env['health.lookup.value']._default_for('consent_type', 'data_sharing'),
            'method': 'verbal',
            'verbal_witness_id': self.env.uid,
            'effective_date': fields.Date.today(),
        })
        consent.action_grant()
        return consent

    @staticmethod
    def _codes_json(*items):
        return json.dumps({'codes': [
            {'code': c, 'confidence': conf, 'evidence': ev}
            for c, conf, ev in items]})

    def _make_user(self, group_xmlid):
        group = self.env.ref(group_xmlid)
        base_user = self.env.ref('base.group_user')
        return self.env['res.users'].create({
            'name': 'AI %s' % group_xmlid.split('_')[-1],
            'login': 'ai_%s' % uuid.uuid4().hex[:10],
            'email': 'ai_%s@example.com' % uuid.uuid4().hex[:6],
            'group_ids': [(6, 0, [base_user.id, group.id])],
            'catchment_province_id': self.province.id,
        })


# =====================================================================
# 1 — Gate matrix
# =====================================================================
@tagged('post_install', '-at_install')
class TestGates(AiCodingBase):

    def test_disabled_does_nothing(self):
        self._set_cfg(self.env, enabled=False)
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            self.Sugg.cron_ai_coding_sweep()
        self.assertFalse(mock.called)
        self.assertFalse(self.Sugg.search([('note_id', '=', note.id)]))
        self.assertEqual(note.ai_attempts, 0)

    def test_consent_false_skips_and_marks_attempt(self):
        note = self._make_note()  # no consent granted
        with patch.object(type(self.ollama), '_complete') as mock:
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertFalse(mock.called)
        self.assertEqual(created, 0)
        self.assertFalse(ok)
        self.assertEqual(note.ai_attempts, 1)
        self.assertFalse(self.Sugg.search([('note_id', '=', note.id)]))

    def test_cloud_provider_refused_when_cloud_off(self):
        self._set_cfg(self.env, provider_id=self.cloud.id, allow_cloud=False)
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.cloud), '_complete') as mock:
            self.Sugg.cron_ai_coding_sweep()
        self.assertFalse(mock.called, "a cloud model must not be called")
        self.assertFalse(self.Sugg.search([('note_id', '=', note.id)]))

    def test_cloud_provider_allowed_when_cloud_on(self):
        self._set_cfg(self.env, provider_id=self.cloud.id, allow_cloud=True)
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.cloud), '_complete') as mock:
            mock.return_value = self._codes_json(('I10', 0.9, 'tang huyet ap'))
            self.Sugg._process_note(note, self.cloud)
        self.assertTrue(mock.called)


# =====================================================================
# 2 — Redaction
# =====================================================================
@tagged('post_install', '-at_install')
class TestRedaction(AiCodingBase):

    def test_phi_absent_from_prompt_and_log(self):
        # Build the note text from the patient's ACTUAL field values so the
        # assertion holds regardless of any phone normalisation on create.
        p = self.patient
        note = self._make_note(
            diagnosis='Benh nhan %s, SDT %s, email %s, dia chi %s - chan '
                      'doan tang huyet ap.' % (p.name, p.mobile, p.email,
                                               p.street))
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = self._codes_json(('I10', 0.8, 'tang huyet ap'))
            self.Sugg._process_note(note, self.ollama)
        self.assertEqual(mock.call_count, 1)
        sent = mock.call_args.args[1]
        for phi in (p.name, 'Testpatient', p.mobile, p.email, p.street):
            self.assertNotIn(phi, sent, '%s leaked into the prompt' % phi)
        self.assertIn('[BN]', sent)
        log = self.env['health.ai.coding.log'].search(
            [('note_id', '=', note.id)], limit=1)
        self.assertTrue(log)
        logged = log.request_json['user']
        for phi in (p.name, p.mobile, p.email):
            self.assertNotIn(phi, logged)

    def test_html_stripped(self):
        note = self._make_note(
            diagnosis=False,
            clinical_notes='<p>Chan doan <b>dai thao duong</b> type 2</p>')
        prompt = self.Sugg._build_user_prompt(note)
        self.assertNotIn('<p>', prompt)
        self.assertNotIn('<b>', prompt)
        self.assertIn('dai thao duong', prompt)

    def test_truncation_at_max_prompt_chars(self):
        self._set_cfg(self.env, max_prompt_chars=50)
        note = self._make_note(diagnosis='x ' * 500)
        prompt = self.Sugg._build_user_prompt(note)
        self.assertLessEqual(len(prompt), 50)


# =====================================================================
# 3 — Happy path
# =====================================================================
@tagged('post_install', '-at_install')
class TestHappyPath(AiCodingBase):

    def test_two_valid_one_bogus(self):
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = self._codes_json(
                ('I10', 0.9, 'tang huyet ap'),
                ('E11', 0.7, 'dai thao duong'),
                ('ZZZ99', 0.5, 'bogus'))
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertTrue(ok)
        self.assertEqual(created, 2)
        rows = self.Sugg.search([('note_id', '=', note.id)])
        self.assertEqual(set(rows.mapped('code_id.code')), {'I10', 'E11'})
        self.assertEqual(rows.mapped('state'), ['suggested', 'suggested'])
        log = self.env['health.ai.coding.log'].search(
            [('note_id', '=', note.id)], limit=1)
        self.assertEqual(log.dropped_codes, 1)
        self.assertEqual(log.suggested_count, 2)
        # attempts untouched by a productive success (scope excludes it next run)
        self.assertEqual(note.ai_attempts, 0)

    def test_confidence_recorded(self):
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = self._codes_json(('I10', 0.9, 'x'))
            self.Sugg._process_note(note, self.ollama)
        row = self.Sugg.search([('note_id', '=', note.id)])
        self.assertAlmostEqual(row.confidence, 0.9, places=2)
        self.assertEqual(row.confidence_pct, 90)

    def test_empty_result_marks_attempt(self):
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = json.dumps({'codes': []})
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertEqual(created, 0)
        self.assertTrue(ok)
        self.assertEqual(note.ai_attempts, 1)


# =====================================================================
# 4 — Robustness
# =====================================================================
@tagged('post_install', '-at_install')
class TestRobustness(AiCodingBase):

    def test_malformed_json(self):
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = 'not json at all'
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertEqual(created, 0)
        self.assertFalse(ok)
        self.assertEqual(note.ai_attempts, 1)
        log = self.env['health.ai.coding.log'].search(
            [('note_id', '=', note.id)], limit=1)
        self.assertTrue(log.error)

    def test_provider_raises(self):
        note = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.side_effect = Exception('connection refused')
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertEqual(created, 0)
        self.assertFalse(ok)
        self.assertEqual(note.ai_attempts, 1)
        log = self.env['health.ai.coding.log'].search(
            [('note_id', '=', note.id)], limit=1)
        self.assertIn('connection refused', log.error or '')

    def test_savepoint_isolation(self):
        good1 = self._make_note()
        poison = self._make_note()
        good2 = self._make_note()
        self._grant_consent()  # patient shared across notes → one consent
        seen = []

        def fake(self2, note, provider):
            if note.id == poison.id:
                raise ValueError('boom')
            if note.id in (good1.id, good2.id):
                seen.append(note.id)
            return 0, True
        with patch.object(type(self.Sugg), '_process_note', fake):
            self.Sugg.cron_ai_coding_sweep()
        self.assertIn(good1.id, seen)
        self.assertIn(good2.id, seen)

    def test_attempts_exhausted_excluded(self):
        note = self._make_note()
        note.ai_attempts = 3
        fresh = self._make_note()
        eligible = self.Sugg._eligible_notes()
        self.assertNotIn(note, eligible)
        self.assertIn(fresh, eligible)


# =====================================================================
# 5 — Dedup
# =====================================================================
@tagged('post_install', '-at_install')
class TestDedup(AiCodingBase):

    def test_resweep_creates_nothing_new(self):
        note = self._make_note()
        self._grant_consent()
        payload = self._codes_json(('I10', 0.9, 'x'))
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = payload
            self.Sugg._process_note(note, self.ollama)
            self.Sugg._process_note(note, self.ollama)
        rows = self.Sugg.search([('note_id', '=', note.id)])
        self.assertEqual(len(rows), 1)

    def test_code_already_on_note_not_suggested(self):
        note = self._make_note()
        note.condition_code_ids = [(4, self.code_i10.id)]
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = self._codes_json(('I10', 0.9, 'x'))
            created, ok = self.Sugg._process_note(note, self.ollama)
        self.assertEqual(created, 0)
        self.assertFalse(self.Sugg.search([('note_id', '=', note.id)]))

    def test_excluded_when_prior_suggestion_exists(self):
        note = self._make_note()
        self.Sugg.sudo().create({'note_id': note.id, 'code_id': self.code_i10.id})
        self.assertNotIn(note, self.Sugg._eligible_notes())


# =====================================================================
# 6 — Approve
# =====================================================================
@tagged('post_install', '-at_install')
class TestApprove(AiCodingBase):

    def _suggestion(self, note=None, code=None):
        note = note or self._make_note()
        return self.Sugg.sudo().create({
            'note_id': note.id, 'code_id': (code or self.code_i10).id,
            'confidence': 0.9})

    def test_doctor_approve_lands_code(self):
        doctor = self._make_user('health_base.group_healthcare_doctor')
        sugg = self._suggestion()
        note = sugg.note_id
        self.assertNotIn(self.code_i10, note.condition_code_ids)
        sugg.with_user(doctor).action_approve()
        self.assertIn(self.code_i10, note.condition_code_ids)
        self.assertEqual(sugg.state, 'approved')
        self.assertEqual(sugg.reviewed_by, doctor)
        self.assertTrue(sugg.reviewed_at)

    def test_plain_nurse_blocked(self):
        nurse = self._make_user('health_base.group_healthcare_nurse')
        sugg = self._suggestion()
        with self.assertRaises(AccessError):
            sugg.with_user(nurse).action_approve()
        self.assertEqual(sugg.state, 'suggested')

    def test_batch_approve_one_failing_row(self):
        doctor = self._make_user('health_base.group_healthcare_doctor')
        good = self._suggestion(code=self.code_i10)
        bad = self._suggestion(note=self._make_note(), code=self.code_e11)
        batch = good | bad
        real = type(good.note_id).write

        def fake_write(self2, vals):
            if 'condition_code_ids' in vals and bad.note_id.id in self2.ids:
                raise ValueError('boom')
            return real(self2, vals)
        with patch.object(type(good.note_id), 'write', fake_write):
            batch.with_user(doctor).action_approve()
        self.assertEqual(good.state, 'approved')
        self.assertEqual(bad.state, 'suggested')


# =====================================================================
# 7 — Reject
# =====================================================================
@tagged('post_install', '-at_install')
class TestReject(AiCodingBase):

    def test_reject_leaves_sidecar_untouched(self):
        doctor = self._make_user('health_base.group_healthcare_doctor')
        note = self._make_note()
        sugg = self.Sugg.sudo().create({
            'note_id': note.id, 'code_id': self.code_i10.id, 'confidence': 0.5})
        sugg.with_user(doctor).action_reject()
        self.assertEqual(sugg.state, 'rejected')
        self.assertEqual(sugg.reviewed_by, doctor)
        self.assertNotIn(self.code_i10, note.condition_code_ids)


# =====================================================================
# 8 — Log immutability
# =====================================================================
@tagged('post_install', '-at_install')
class TestLogImmutability(AiCodingBase):

    def test_write_and_unlink_blocked_even_as_admin(self):
        note = self._make_note()
        log = self.env['health.ai.coding.log'].sudo().create({
            'note_id': note.id, 'provider_id': self.ollama.id,
            'request_json': {'user': 'x'}, 'suggested_count': 0})
        with self.assertRaises(UserError):
            log.write({'suggested_count': 5})
        with self.assertRaises(UserError):
            log.unlink()


# =====================================================================
# 9 — Batch cap
# =====================================================================
@tagged('post_install', '-at_install')
class TestBatchCap(AiCodingBase):

    def test_cap_respected(self):
        self._set_cfg(self.env, batch_cap=2)
        n1 = self._make_note()
        n2 = self._make_note()
        n3 = self._make_note()
        self._grant_consent()
        with patch.object(type(self.ollama), '_complete') as mock:
            mock.return_value = json.dumps({'codes': []})
            self.Sugg.cron_ai_coding_sweep()
        # newest-first (create_date desc, id desc): n3, n2 processed; n1 not.
        attempted = [n for n in (n1, n2, n3) if n.ai_attempts > 0]
        self.assertEqual(len(attempted), 2)
        self.assertEqual(n1.ai_attempts, 0)
