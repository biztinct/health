# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

from ..models import phi_crypto


@tagged('post_install', '-at_install')
class TestPhiEncryption(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province = (cls.env['health.catchment.province'].search([], limit=1)
                        or cls.env['health.catchment.province'].create({
                            'name': 'PHI Test Province',
                            'province_code': 'PHI',
                        }))
        cls.partner = cls.env['res.partner'].create({
            'name': 'PHI Test Patient',
            'is_patient': True,
            'catchment_province_id': cls.province.id,
            'medical_history': 'Type 2 diabetes since 2019',
            'allergies': 'Penicillin',
            'national_id': '079123456789',
            'emergency_contact_phone': '0938038028',
        })

    def test_round_trip(self):
        """Reading through the ORM returns the original plaintext."""
        self.assertEqual(self.partner.medical_history, 'Type 2 diabetes since 2019')
        self.assertEqual(self.partner.allergies, 'Penicillin')
        self.assertEqual(self.partner.national_id, '079123456789')

    def test_ciphertext_at_rest(self):
        """The database column holds an enc$1$ token, never plaintext."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT medical_history_enc, national_id_enc FROM res_partner WHERE id = %s",
            (self.partner.id,))
        med_enc, nid_enc = self.env.cr.fetchone()
        self.assertTrue(med_enc.startswith(phi_crypto.PREFIX))
        self.assertTrue(nid_enc.startswith(phi_crypto.PREFIX))
        self.assertNotIn('diabetes', med_enc)
        self.assertNotIn('079123456789', nid_enc)

    def test_blind_index_search(self):
        """Exact-match search works on encrypted identifiers, for '=' and the
        legacy ilike path used by health_base controllers."""
        Partner = self.env['res.partner']
        self.assertIn(self.partner, Partner.search([('national_id', '=', '079123456789')]))
        self.assertIn(self.partner, Partner.search([('national_id', 'ilike', '079123456789')]))
        # normalization: separators/case do not matter
        self.assertIn(self.partner, Partner.search([('national_id', '=', '079 1234 56789')]))
        self.assertNotIn(self.partner, Partner.search([('national_id', '=', '000000000000')]))
        # emptiness search
        blank = Partner.create({'name': 'No ID', 'is_patient': True,
                                'catchment_province_id': self.province.id})
        self.assertIn(blank, Partner.search([('national_id', '=', False), ('is_patient', '=', True)]))

    def test_update_and_clear(self):
        self.partner.medical_history = 'Updated history'
        self.assertEqual(self.partner.medical_history, 'Updated history')
        self.partner.medical_history = False
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT medical_history_enc FROM res_partner WHERE id = %s", (self.partner.id,))
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_clinical_note_fields(self):
        fso_model = self.env['health.fieldservice.order']
        facility = (self.env['health.facility'].search([], limit=1)
                    or self.env['health.facility'].create({
                        'name': 'PHI Test Facility',
                        'code': 'PHIF',
                        'catchment_province_id': self.province.id,
                    }))
        # Clinical notes require an order; build the minimal valid one.
        order = fso_model.create({
            'patient_id': self.partner.id,
            'facility_id': facility.id,
            'scheduled_datetime': '2026-07-10 03:00:00',
        })
        note = self.env['health.clinical.note'].create({
            'order_id': order.id,
            'clinical_notes': '<p>Wound dressing changed</p>',
            'diagnosis': 'Stage 2 pressure injury',
            'vital_signs': 'BP 130/85, HR 78',
        })
        self.assertIn('Wound dressing changed', str(note.clinical_notes))
        self.assertEqual(note.diagnosis, 'Stage 2 pressure injury')
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT clinical_notes_enc, diagnosis_enc FROM health_clinical_note WHERE id = %s",
            (note.id,))
        cn_enc, dx_enc = self.env.cr.fetchone()
        self.assertTrue(cn_enc.startswith(phi_crypto.PREFIX))
        self.assertTrue(dx_enc.startswith(phi_crypto.PREFIX))
        self.assertNotIn('pressure injury', dx_enc)

    def test_decrypt_passthrough_and_tamper(self):
        """Plain (unmigrated) values pass through; corrupted tokens degrade to
        a visible marker instead of raising."""
        self.assertEqual(phi_crypto.decrypt(self.env, 'legacy plaintext'), 'legacy plaintext')
        broken = phi_crypto.PREFIX + 'AAAA'
        self.assertEqual(phi_crypto.decrypt(self.env, broken), phi_crypto.DECRYPT_ERROR_MARKER)
