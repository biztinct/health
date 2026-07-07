# -*- coding: utf-8 -*-
"""Guard tests for fhir.submission.log (append-only audit evidence)."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubmissionLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        province = cls.env['health.catchment.province'].search([], limit=1)
        if not province:
            province = cls.env['health.catchment.province'].create(
                {'name': 'Adapter Base Province'})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Adapter Base Patient', 'is_patient': True,
            'catchment_province_id': province.id})

    def _make_log(self, state='draft'):
        log = self.env['fhir.submission.log'].create({
            'adapter_code': 'vn', 'patient_id': self.patient.id,
            'bundle_sha256': 'abc', 'entry_count': 3})
        if state != 'draft':
            log.write({'state': state})
        return log

    def test_sequence_assigned(self):
        log = self._make_log()
        self.assertTrue(log.name.startswith('SUB'))
        self.assertEqual(log.catchment_province_id,
                         self.patient.catchment_province_id)

    def test_unlink_non_draft_raises_even_for_su(self):
        log = self._make_log(state='exported')
        # env.su is True in tests (uid 1) — the guard must still fire.
        self.assertTrue(self.env.su)
        with self.assertRaises(UserError):
            log.unlink()
        # draft rows may be deleted
        draft = self._make_log()
        draft.unlink()
        self.assertFalse(draft.exists())

    def test_locked_field_write_post_draft_raises(self):
        log = self._make_log(state='exported')
        with self.assertRaises(UserError):
            log.write({'bundle_sha256': 'tampered'})

    def test_state_and_receipt_writable_post_draft(self):
        log = self._make_log(state='exported')
        log.write({'state': 'acked', 'receipt_ref': 'RCPT-1',
                   'error_text': 'none'})
        self.assertEqual(log.state, 'acked')
        self.assertEqual(log.receipt_ref, 'RCPT-1')
