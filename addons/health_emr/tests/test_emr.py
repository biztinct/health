# -*- coding: utf-8 -*-
"""EMR record-spine tests (Circular 13/2025 phase 1).

The load-bearing property is immutability with NO superuser escape: an EMR
whose signed records can be silently altered is worse than none. Every guard
is tested for the su path too.
"""
import uuid

from odoo import SUPERUSER_ID, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class EmrBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'EMR P %s' % uuid.uuid4().hex[:5],
            'code': 'EP%s' % uuid.uuid4().hex[:3]})
        cls.facility = cls.env['health.facility'].create({
            'name': 'EMR Facility', 'code': 'EF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'EMR Patient', 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        cls.order = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60, 'service_type': 'home_visit'})

    def _make_patient(self, name):
        return self.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': self.province.id,
            'primary_facility_id': self.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})

    def _make_order(self, patient):
        return self.env['health.fieldservice.order'].create({
            'patient_id': patient.id, 'facility_id': self.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60, 'service_type': 'home_visit'})

    def _note(self, order=None, **kw):
        vals = {'order_id': (order or self.order).id,
                'clinical_notes': '<p>BP stable, patient comfortable</p>',
                'diagnosis': 'Routine review'}
        vals.update(kw)
        return self.env['health.clinical.note'].create(vals)


@tagged('post_install', '-at_install')
class TestFinalize(EmrBase):

    def test_finalize_sets_state_signer_seal(self):
        note = self._note()
        self.assertEqual(note.emr_state, 'draft')
        note.action_finalize()
        self.assertEqual(note.emr_state, 'final')
        self.assertEqual(note.signed_by_id, self.env.user)
        self.assertTrue(note.signed_role)
        self.assertTrue(note.signed_datetime)
        self.assertEqual(len(note.content_hash or ''), 64)
        self.assertEqual(note.hash_version, 'v1')
        self.assertTrue(note.verify_integrity())

    def test_finalize_empty_note_raises(self):
        note = self._note(clinical_notes=False, diagnosis=False)
        with self.assertRaises(UserError):
            note.action_finalize()

    def test_double_finalize_raises(self):
        note = self._note()
        note.action_finalize()
        with self.assertRaises(UserError):
            note.action_finalize()

    def test_finalize_permission_denied(self):
        # A nurse who is neither the author nor a head nurse cannot finalize.
        note = self._note()  # authored by admin (uid 1)
        nurse = new_test_user(
            self.env, login='emr_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse')
        with self.assertRaises(UserError):
            note.with_user(nurse).action_finalize()
        note.invalidate_recordset()
        self.assertEqual(note.emr_state, 'draft')


@tagged('post_install', '-at_install')
class TestImmutability(EmrBase):

    def test_locked_write_raises_after_finalize(self):
        note = self._note()
        note.action_finalize()
        with self.assertRaises(UserError):
            note.write({'diagnosis': 'tampered'})

    def test_no_superuser_escape(self):
        note = self._note()
        note.action_finalize()
        with self.assertRaises(UserError):
            note.with_user(SUPERUSER_ID).write({'clinical_notes': '<p>x</p>'})

    def test_enc_column_write_also_blocked(self):
        # Direct-to-ciphertext write must not bypass the lock.
        note = self._note()
        note.action_finalize()
        if 'diagnosis_enc' in note._fields:
            with self.assertRaises(UserError):
                note.with_user(SUPERUSER_ID).write({'diagnosis_enc': 'ZZZ'})

    def test_signature_ref_stays_writable(self):
        # The Phase-3 CA-signature seam attaches to a finalized record.
        note = self._note()
        note.action_finalize()
        note.write({'signature_ref': 'ca-sig-123'})
        self.assertEqual(note.signature_ref, 'ca-sig-123')

    def test_draft_writes_freely(self):
        note = self._note()
        note.write({'diagnosis': 'edited freely'})
        self.assertEqual(note.diagnosis, 'edited freely')

    def test_unlink_guard(self):
        final = self._note()
        final.action_finalize()
        with self.assertRaises(UserError):
            final.unlink()
        draft = self._note()
        draft_id = draft.id
        draft.unlink()
        self.assertFalse(
            self.env['health.clinical.note'].browse(draft_id).exists())

    def test_unlink_guard_no_superuser_escape(self):
        final = self._note()
        final.action_finalize()
        with self.assertRaises(UserError):
            final.with_user(SUPERUSER_ID).unlink()


@tagged('post_install', '-at_install')
class TestIntegritySeal(EmrBase):

    def test_hash_covers_narrative(self):
        note = self._note(diagnosis='Alpha')
        h1 = note._compute_content_hash()
        note.write({'diagnosis': 'Beta'})  # draft, allowed
        note.invalidate_recordset()
        h2 = note._compute_content_hash()
        self.assertNotEqual(h1, h2)

    def test_distinct_notes_distinct_seals(self):
        n1 = self._note()
        n2 = self._note()
        n1.action_finalize()
        n2.action_finalize()
        self.assertNotEqual(n1.content_hash, n2.content_hash)

    def test_recompute_reproduces_seal(self):
        note = self._note()
        note.action_finalize()
        self.assertEqual(note._compute_content_hash(), note.content_hash)

    def test_seal_detects_tamper(self):
        note = self._note(injection_count=2)
        note.action_finalize()
        self.assertTrue(note.verify_integrity())
        # Alter a sealed plain column directly in the DB.
        self.env.cr.execute(
            "UPDATE health_clinical_note SET injection_count = 99 WHERE id = %s",
            (note.id,))
        note.invalidate_recordset()
        self.assertFalse(note.verify_integrity())


@tagged('post_install', '-at_install')
class TestAddendum(EmrBase):

    def test_addendum_to_finalized_ok(self):
        original = self._note()
        original.action_finalize()
        addendum = self._note(diagnosis='Correction: allergy noted',
                              amends_note_id=original.id)
        self.assertTrue(addendum.is_amendment)
        self.assertIn(addendum, original.amendment_ids)
        # Original untouched.
        self.assertEqual(original.emr_state, 'final')
        self.assertTrue(original.verify_integrity())

    def test_addendum_to_draft_raises(self):
        draft = self._note()
        with self.assertRaises(ValidationError):
            self._note(amends_note_id=draft.id)

    def test_addendum_cross_patient_raises(self):
        original = self._note()
        original.action_finalize()
        other_patient = self._make_patient('Other Patient')
        other_order = self._make_order(other_patient)
        with self.assertRaises(ValidationError):
            self._note(order=other_order, amends_note_id=original.id)

    def test_addendum_can_be_finalized_and_locks(self):
        original = self._note()
        original.action_finalize()
        addendum = self._note(amends_note_id=original.id)
        addendum.action_finalize()
        self.assertEqual(addendum.emr_state, 'final')
        with self.assertRaises(UserError):
            addendum.write({'diagnosis': 'edit after sign'})


@tagged('post_install', '-at_install')
class TestFhirReflection(EmrBase):
    """The FHIR DocumentReference reflects EMR status — verified from here so
    the coupling lives with health_emr (health_fhir_core stays independent).
    Skips cleanly when health_fhir_core is not installed."""

    def _serializer(self):
        installed = self.env['ir.module.module'].search([
            ('name', '=', 'health_fhir_core'), ('state', '=', 'installed')])
        if not installed:
            self.skipTest('health_fhir_core not installed')
        from odoo.addons.health_fhir_core.serializers import REGISTRY
        return REGISTRY['DocumentReference']

    def test_docstatus_reflects_finalization(self):
        serializer = self._serializer()
        note = self._note()
        self.assertEqual(serializer.to_fhir(note)['docStatus'], 'preliminary')
        note.action_finalize()
        note.invalidate_recordset()
        res = serializer.to_fhir(note)
        self.assertEqual(res['docStatus'], 'final')

    def test_addendum_relatesto(self):
        serializer = self._serializer()
        original = self._note()
        original.action_finalize()
        addendum = self._note(amends_note_id=original.id)
        res = serializer.to_fhir(addendum)
        self.assertEqual(res['relatesTo'][0]['code'], 'appends')
        self.assertEqual(
            res['relatesTo'][0]['target']['reference'],
            'DocumentReference/%s' % original.id)
