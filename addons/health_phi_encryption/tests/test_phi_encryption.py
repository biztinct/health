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


PARTNER_COLUMNS = (
    'allergies_enc', 'medical_history_enc', 'intake_diagnosis_enc',
    'intake_notes_enc', 'healthcare_notes_enc', 'emergency_contact_name_enc',
    'emergency_contact_phone_enc', 'emergency_contact_relation_enc',
    'emergency_contact_relationship_enc', 'national_id_enc',
    'national_id_bidx', 'cccd_number_enc', 'cccd_number_bidx')
NOTE_COLUMNS = (
    'clinical_notes_enc', 'diagnosis_enc', 'treatment_performed_enc',
    'medications_prescribed_enc', 'vital_signs_enc',
    'patient_condition_before_enc', 'patient_condition_after_enc')


@tagged('post_install', '-at_install')
class TestPhiColumnsNotExportMaterial(TransactionCase):

    def test_70_the_standard_encrypted_columns_are_not_export_material(self):
        """T70 (FS-H5) — the 13 client and 7 clinical-note storage columns
        say `exportable: False`, so the export dialog and the analytics
        catalogue leave them out; the fields people see stay exportable and
        still read and write for somebody who is not an administrator."""
        from odoo.tests import new_test_user
        Partner = self.env['res.partner']
        desc = Partner.fields_get(list(PARTNER_COLUMNS), ['exportable'])
        self.assertEqual(sorted(desc), sorted(PARTNER_COLUMNS))
        for name in PARTNER_COLUMNS:
            self.assertIs(desc[name]['exportable'], False, name)
        note = self.env['health.clinical.note'].fields_get(
            list(NOTE_COLUMNS), ['exportable'])
        self.assertEqual(sorted(note), sorted(NOTE_COLUMNS))
        for name in NOTE_COLUMNS:
            self.assertIs(note[name]['exportable'], False, name)
        # nothing else about the columns changed: no group, still copied
        for name in PARTNER_COLUMNS:
            field = Partner._fields[name]
            self.assertFalse(field.groups, name)
            self.assertTrue(field.store, name)
        visible = Partner.fields_get(
            ['allergies', 'national_id', 'cccd_number'], ['exportable'])
        for name, value in visible.items():
            self.assertIs(value['exportable'], True, name)
        # read and write as an Owner (not an administrator)
        province = (self.env['health.catchment.province'].search([], limit=1)
                    or self.env['health.catchment.province'].create({
                        'name': 'PHI70 Province', 'province_code': 'P70'}))
        user = new_test_user(
            self.env, login='phi70_owner',
            groups='base.group_user,health_base.group_healthcare_owner')
        self.assertFalse(user.has_group('base.group_system'))
        partner = Partner.create({
            'name': 'PHI70 Patient', 'is_patient': True,
            'catchment_province_id': province.id,
            'allergies': 'Latex', 'national_id': '079000000070'})
        self.env.invalidate_all()
        mine = partner.with_user(user)
        self.assertEqual(mine.read(['allergies', 'national_id'])[0][
            'allergies'], 'Latex')
        mine.write({'allergies': 'Latex, iodine'})
        self.env.invalidate_all()
        self.assertEqual(partner.allergies, 'Latex, iodine')
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT allergies_enc FROM res_partner WHERE id = %s",
            (partner.id,))
        self.assertTrue(self.env.cr.fetchone()[0].startswith(phi_crypto.PREFIX))
        # exporting the visible field still works
        data = partner.export_data(['name', 'allergies'])
        self.assertEqual(data['datas'], [['PHI70 Patient', 'Latex, iodine']])
