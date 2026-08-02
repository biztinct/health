# -*- coding: utf-8 -*-
"""health_consent acceptance tests (clinical spec §6.11)."""
import base64
import uuid
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

# 1x1 transparent PNG.
PNG_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNg'
    'YGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC')


def _get_fixture(env):
    """Patient partners REQUIRE catchment_province_id. Search existing
    province/facility first, create fallback (health_vitals test
    pattern)."""
    Partner = env['res.partner']
    Facility = env['health.facility']

    province = env['health.catchment.province'].search([], limit=1)
    if not province:
        province = env['health.catchment.province'].create({
            'name': 'Test Consent Province',
            'code': 'TCN',
        })
    facility = Facility.search(
        [('catchment_province_id', '=', province.id)], limit=1)
    if not facility:
        facility = Facility.create({
            'name': 'Test Consent Facility',
            'code': 'TCF',
            'street': '1 Consent Street',
            'city': 'Test City',
            'catchment_province_id': province.id,
        })
    patient = Partner.create({
        'name': 'Consent Test Patient',
        'is_patient': True,
        'catchment_province_id': province.id,
        'primary_facility_id': facility.id,
    })
    return province, facility, patient


@tagged('post_install', '-at_install')
class TestHealthConsent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province, cls.facility, cls.patient = _get_fixture(cls.env)
        cls.Consent = cls.env['health.consent']
        cls.CheckLog = cls.env['health.consent.check.log']
        cls.representative = cls.env['res.partner'].create({
            'name': 'Consent Test Daughter',
            'is_representative': True,
        })
        cls.relation_guardian = cls.env['health.client.relation'].create({
            'client_id': cls.patient.id,
            'representative_id': cls.representative.id,
            'role': 'legal_guardian',
            'relationship_type': 'child',
            'can_make_medical_decisions': True,
            'can_receive_medical_info': True,
        })
        cls.plain_rep = cls.env['res.partner'].create({
            'name': 'Consent Test Neighbor',
            'is_representative': True,
        })
        cls.relation_plain = cls.env['health.client.relation'].create({
            'client_id': cls.patient.id,
            'representative_id': cls.plain_rep.id,
            'role': 'client_representative',
            'relationship_type': 'neighbor',
            'can_make_medical_decisions': False,
            'can_receive_medical_info': False,
        })

    def setUp(self):
        super().setUp()
        # Log-only default for every test unless explicitly enabled.
        self.env['ir.config_parameter'].sudo().set_param(
            'health_consent.enforce', 'False')

    def _make_consent(self, consent_type='service', method='verbal',
                      grant=False, **vals):
        consent = self.Consent.create(dict({
            'client_id': self.patient.id,
            'consent_type': consent_type,
            'method': method,
        }, **vals))
        if grant:
            consent.action_grant()
        return consent

    # ------------------------------------------------------------------
    # Acceptance #1 — digital signature evidence guard
    # ------------------------------------------------------------------
    def test_01_digital_requires_signature(self):
        consent = self._make_consent(method='digital_signature')
        with self.assertRaises(UserError):
            consent.action_grant()
        consent.signature = PNG_B64
        consent.action_grant()
        self.assertEqual(consent.state, 'active')
        self.assertEqual(consent.name[:3], 'CNS')

    def test_01b_written_requires_attachment(self):
        consent = self._make_consent(method='written')
        with self.assertRaises(UserError):
            consent.action_grant()
        attachment = self.env['ir.attachment'].create({
            'name': 'scan.png',
            'datas': PNG_B64,
        })
        consent.evidence_attachment_ids = [(4, attachment.id)]
        consent.action_grant()
        self.assertEqual(consent.state, 'active')

    # ------------------------------------------------------------------
    # Acceptance #2 — supersede on grant
    # ------------------------------------------------------------------
    def test_02_supersede(self):
        first = self._make_consent('photography', grant=True)
        second = self._make_consent('photography', grant=True)
        self.assertEqual(second.state, 'active')
        self.assertEqual(first.state, 'withdrawn')
        self.assertEqual(first.withdrawal_reason, 'Superseded')
        self.assertTrue(any(
            'Superseded by' in (message.body or '')
            for message in first.message_ids))
        self.assertTrue(any(
            'Supersedes' in (message.body or '')
            for message in second.message_ids))

    # ------------------------------------------------------------------
    # Acceptance #3 — check_consent windows + check log evidence
    # ------------------------------------------------------------------
    def test_03_check_consent(self):
        Consent = self.Consent
        logs_before = self.CheckLog.search_count([
            ('client_id', '=', self.patient.id)])
        # No record.
        self.assertFalse(
            Consent.check_consent(self.patient, 'marketing'))
        consent = self._make_consent('marketing', grant=True)
        self.assertTrue(
            Consent.check_consent(self.patient.id, 'marketing'))
        # Outside the date window.
        self.assertFalse(Consent.check_consent(
            self.patient, 'marketing',
            at_date=consent.effective_date - timedelta(days=1)))
        # Withdrawn.
        consent.with_context(
            withdrawal_reason='Client changed mind').action_withdraw()
        self.assertFalse(
            Consent.check_consent(self.patient, 'marketing'))
        # Expired.
        expired = self._make_consent(
            'marketing',
            effective_date=fields.Date.today() - timedelta(days=30),
            expiry_date=fields.Date.today() - timedelta(days=1))
        expired.action_grant()
        expired.flush_recordset()
        self.Consent._cron_expire_consents()
        self.assertEqual(expired.state, 'expired')
        self.assertFalse(
            Consent.check_consent(self.patient, 'marketing'))
        # Every check wrote an append-only evidence row.
        logs_after = self.CheckLog.search_count([
            ('client_id', '=', self.patient.id)])
        self.assertGreaterEqual(logs_after - logs_before, 5)
        last_log = self.CheckLog.search([
            ('client_id', '=', self.patient.id)], limit=1)
        with self.assertRaises(UserError):
            last_log.write({'result': True})
        with self.assertRaises(UserError):
            last_log.unlink()

    def test_03b_check_consents_batch(self):
        self._make_consent('service', grant=True)
        result = self.Consent.check_consents(
            self.patient, ['service', 'marketing'])
        self.assertEqual(result,
                         {'service': True, 'marketing': False})

    def test_03c_scope_matching(self):
        self._make_consent(
            'photography', grant=True,
            scope_note='Photos for clinical record only')
        self.assertTrue(self.Consent.check_consent(
            self.patient, 'photography'))
        self.assertTrue(self.Consent.check_consent(
            self.patient, 'photography', scope='clinical record'))
        self.assertFalse(self.Consent.check_consent(
            self.patient, 'photography', scope='social media'))

    # ------------------------------------------------------------------
    # Log-only vs enforce (DESIGN §7.1 / health_consent.enforce)
    # ------------------------------------------------------------------
    def test_03d_require_consent_enforce_modes(self):
        # Default (falsy param): never raises, just logs.
        self.assertFalse(self.Consent.require_consent(
            self.patient, 'data_sharing'))
        # Enforce mode: missing consent raises AccessError.
        self.env['ir.config_parameter'].sudo().set_param(
            'health_consent.enforce', 'True')
        with self.assertRaises(AccessError):
            self.Consent.require_consent(self.patient, 'data_sharing')
        # A granted consent passes in enforce mode too.
        self._make_consent('data_sharing', grant=True)
        self.assertTrue(self.Consent.require_consent(
            self.patient, 'data_sharing'))

    # ------------------------------------------------------------------
    # Acceptance #4 — cron expiry + renewal activity
    # ------------------------------------------------------------------
    def test_04_cron_expiry_and_renewal(self):
        past = self._make_consent(
            'service',
            effective_date=fields.Date.today() - timedelta(days=60),
            expiry_date=fields.Date.today() - timedelta(days=1))
        past.action_grant()
        expiring = self._make_consent(
            'marketing',
            expiry_date=fields.Date.today() + timedelta(days=14),
            grant=True)
        manager_user = self.env['res.users'].create({
            'name': 'Consent Facility Manager',
            'login': 'consent_fm_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        employee = self.env['hr.employee'].create({
            'name': 'Consent Facility Manager',
            'user_id': manager_user.id,
        })
        self.facility.facility_manager_id = employee
        self.Consent._cron_expire_consents()
        self.assertEqual(past.state, 'expired')
        self.assertEqual(expiring.state, 'active')
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'health.consent'),
            ('res_id', '=', expiring.id),
        ])
        self.assertTrue(activity)
        self.assertIn('Consent expiring', activity[0].summary)

    # ------------------------------------------------------------------
    # Acceptance #5 — kinship grantor validation
    # ------------------------------------------------------------------
    def test_05_grantor_validation(self):
        # Non-self grant without a relation is blocked (create-time).
        with self.assertRaises(ValidationError):
            self._make_consent('marketing', self_granted=False)
        # Any active relation may grant marketing/photography.
        consent = self._make_consent(
            'marketing', self_granted=False,
            granted_by_relation_id=self.relation_plain.id, grant=True)
        self.assertEqual(consent.state, 'active')
        self.assertEqual(consent.granted_by_partner_id, self.plain_rep)
        self.assertEqual(consent.granted_by_role,
                         'client_representative')
        # Medical types need can_make_medical_decisions.
        with self.assertRaises(ValidationError):
            self._make_consent(
                'service', self_granted=False,
                granted_by_relation_id=self.relation_plain.id)
        service = self._make_consent(
            'service', self_granted=False,
            granted_by_relation_id=self.relation_guardian.id,
            grant=True)
        self.assertEqual(service.state, 'active')
        # A relation of another client is rejected.
        other = self.env['res.partner'].create({
            'name': 'Other Consent Patient',
            'is_patient': True,
            'catchment_province_id': self.province.id,
        })
        with self.assertRaises(ValidationError):
            self.Consent.create({
                'client_id': other.id,
                'consent_type': 'marketing',
                'method': 'verbal',
                'self_granted': False,
                'granted_by_relation_id': self.relation_plain.id,
            })

    def test_05b_data_sharing_grantor(self):
        # data_sharing: medical info — receive-info permission counts.
        info_rep = self.env['res.partner'].create({
            'name': 'Consent Test Info Rep',
            'is_representative': True,
        })
        relation = self.env['health.client.relation'].create({
            'client_id': self.patient.id,
            'representative_id': info_rep.id,
            'role': 'emergency_contact',
            'can_receive_medical_info': True,
        })
        consent = self._make_consent(
            'data_sharing', self_granted=False,
            granted_by_relation_id=relation.id, grant=True)
        self.assertEqual(consent.state, 'active')
        with self.assertRaises(ValidationError):
            self._make_consent(
                'data_sharing', self_granted=False,
                granted_by_relation_id=self.relation_plain.id)

    # ------------------------------------------------------------------
    # Acceptance #6 (model level) — signature payload + idempotency key
    # ------------------------------------------------------------------
    def test_06_signature_and_mutation_idempotency(self):
        key = uuid.uuid4().hex
        consent = self._make_consent(
            'photography', method='digital_signature',
            signature=PNG_B64, client_mutation_id=key, grant=True)
        self.assertEqual(consent.state, 'active')
        self.assertEqual(
            base64.b64decode(consent.with_context(
                bin_size=False).signature)[:8],
            base64.b64decode(PNG_B64)[:8])
        with self.assertRaises(ValidationError):
            self._make_consent(
                'marketing', client_mutation_id=key)

    # ------------------------------------------------------------------
    # Acceptance #7 — withdraw reason + evidence lock
    # ------------------------------------------------------------------
    def test_07_withdraw_and_evidence_lock(self):
        consent = self._make_consent('service', grant=True)
        with self.assertRaises(UserError):
            consent.action_withdraw()
        consent.withdrawal_reason = 'Client moved away'
        consent.action_withdraw()
        self.assertEqual(consent.state, 'withdrawn')
        self.assertEqual(consent.withdrawn_by_id, self.env.user)
        self.assertTrue(consent.withdrawal_date)
        with self.assertRaises(UserError):
            consent.write({'signature': PNG_B64})
        with self.assertRaises(UserError):
            consent.write({'consent_type': 'marketing'})

    # ------------------------------------------------------------------
    # Acceptance #8 — immutable audit records (unlink)
    # ------------------------------------------------------------------
    def test_08_unlink_guard(self):
        draft = self._make_consent('service')
        draft.unlink()
        self.assertFalse(draft.exists())
        active = self._make_consent('service', grant=True)
        with self.assertRaises(UserError):
            active.unlink()
        nurse = self._make_nurse_user()
        with self.assertRaises(Exception):
            active.with_user(nurse).unlink()

    # ------------------------------------------------------------------
    # Acceptance #9 — catchment rules
    # ------------------------------------------------------------------
    def _make_nurse_user(self, province=None):
        nurse_group = self.env.ref('health_base.group_healthcare_nurse')
        return self.env['res.users'].create({
            'name': 'Consent Test Nurse',
            'login': 'consent_test_nurse_%s' % uuid.uuid4().hex[:8],
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id, nurse_group.id])],
            'catchment_province_id': (province or self.province).id,
        })

    def test_09_catchment_rules(self):
        consent = self._make_consent('service', grant=True)
        self.assertEqual(consent.catchment_province_id, self.province)
        nurse = self._make_nurse_user()
        visible = self.Consent.with_user(nurse).search([
            ('id', '=', consent.id)])
        self.assertEqual(visible, consent)
        other_province = self.env['health.catchment.province'].create({
            'name': 'Test Consent Far Province',
            'code': 'TCF2',
        })
        far_nurse = self._make_nurse_user(province=other_province)
        hidden = self.Consent.with_user(far_nurse).search([
            ('id', '=', consent.id)])
        self.assertFalse(hidden)

    # ------------------------------------------------------------------
    # Acceptance #10 — res.partner.can_send_marketing()
    # ------------------------------------------------------------------
    def test_10_can_send_marketing(self):
        self.assertFalse(self.patient.can_send_marketing())
        consent = self._make_consent('marketing', grant=True)
        self.assertTrue(self.patient.can_send_marketing())
        consent.with_context(
            withdrawal_reason='Opt-out call').action_withdraw()
        self.assertFalse(self.patient.can_send_marketing())

    # ------------------------------------------------------------------
    # Extras — summary + one-active constraint
    # ------------------------------------------------------------------
    def test_11_consent_summary(self):
        self._make_consent('service', grant=True)
        summary = self.patient.consent_summary
        self.assertIn('service ✓', summary)
        self.assertIn('marketing ✗', summary)

    def test_12_one_active_constraint(self):
        self._make_consent('service', grant=True)
        with self.assertRaises(ValidationError):
            # Bypassing action_grant (direct create as active) trips
            # the one-active-per-(client, type) constraint.
            self._make_consent('service', state='active')

    # ------------------------------------------------------------------
    # GC-3 R1 — the check log is evidence, so it must outlive its subject
    # (gotcha ledger §5.99: an ondelete='cascade' FK into an append-only
    # audit model deletes the evidence at the SQL layer, where the Python
    # guard above never runs — it took the GC-2 probe's deny rows).
    # ------------------------------------------------------------------
    def test_13_check_log_survives_patient_deletion(self):
        probe = self.env['res.partner'].create({
            'name': 'Nguyễn Văn Xoá GC3',
            'is_patient': True,
            'catchment_province_id': self.province.id,
            'patient_code': 'PGC3DEL',
        })
        # Two deny rows written by the service API itself (not hand-created),
        # so the test covers the real evidence path. The probe deliberately
        # has NO granted consent: `health.consent.client_id` is
        # ondelete='restrict', so a patient who has ever been consented
        # cannot be hard-deleted at all — the rows at risk are precisely the
        # DENY rows of a patient nobody consented, which is what GC-2 lost.
        self.assertFalse(self.Consent.check_consent(probe, 'service'))
        self.assertFalse(self.Consent.check_consent(probe, 'data_sharing'))
        rows = self.CheckLog.search([('client_id', '=', probe.id)])
        self.assertEqual(len(rows), 2, 'the evidence rows were not written')
        self.assertEqual(
            set(rows.mapped('client_ref')), {'Nguyễn Văn Xoá GC3 [PGC3DEL]'},
            'the subject label was not frozen at create time')

        probe.unlink()
        self.assertFalse(probe.exists())
        # flush + invalidate: the SET NULL happened in the database, and the
        # ORM cache still holds the pre-delete client_id.
        self.env.invalidate_all()

        survivors = self.CheckLog.browse(rows.ids).exists()
        self.assertEqual(
            len(survivors), 2,
            'deleting the patient destroyed the consent-check evidence — '
            "the FK is back to ondelete='cascade'")
        self.assertFalse(any(survivors.mapped('client_id')),
                         'client_id should be empty after SET NULL')
        self.assertEqual(set(survivors.mapped('client_ref')),
                         {'Nguyễn Văn Xoá GC3 [PGC3DEL]'},
                         'an orphaned row no longer names its subject')
        self.assertEqual(set(survivors.mapped('consent_type')),
                         {'service', 'data_sharing'})
        self.assertEqual(sorted(survivors.mapped('result')), [False, False])

    def test_13b_orphaned_rows_are_still_append_only(self):
        """The guard is unchanged — an orphan is still un-writable and
        un-deletable through the ORM."""
        probe = self.env['res.partner'].create({
            'name': 'GC3 Append Only Probe',
            'is_patient': True,
            'catchment_province_id': self.province.id,
        })
        self.Consent.check_consent(probe, 'data_sharing')
        row = self.CheckLog.search([('client_id', '=', probe.id)], limit=1)
        self.assertTrue(row)
        # patient_code is auto-assigned on create for patients, so the label
        # is "Name [code]" here; the bare-name branch is covered below with a
        # partner that has no code.
        self.assertEqual(
            row.client_ref,
            'GC3 Append Only Probe [%s]' % probe.patient_code)
        probe.unlink()
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            row.write({'result': True})
        with self.assertRaises(UserError):
            row.unlink()

    def test_13c_client_label_without_a_patient_code(self):
        """A partner with no `patient_code` (a representative, say) still gets
        a label — the bare name — never a bracketed empty code."""
        plain = self.env['res.partner'].create(
            {'name': 'GC3 Label Probe', 'is_representative': True})
        self.assertFalse(plain.patient_code)
        self.assertEqual(self.CheckLog._client_label(plain),
                         'GC3 Label Probe')
        self.assertFalse(
            self.CheckLog._client_label(self.env['res.partner']),
            'an empty recordset must not produce a label')
