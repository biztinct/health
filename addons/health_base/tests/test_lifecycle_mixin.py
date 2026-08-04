# -*- coding: utf-8 -*-
"""Record lifecycle (soft delete / custodian archive / owner purge).

Client spec under test:
  * Delete is a USER function: mandatory reason, record stays visible in
    tables (deleted_test=False) but is excluded from every count.
  * Archive is a CUSTODIAN function: hidden from views, still counted where
    active_test=False is used (BI contract).
  * Physical delete is an OWNER function, and only after a Delete request.
  * Every action lands in the append-only health.archive.log.
"""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLifecycleMixin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_nurse = Users.create({
            'name': 'Lifecycle Nurse',
            'login': 'lifecycle_nurse',
            'group_ids': [(4, cls.env.ref('health_base.group_healthcare_nurse').id)],
        })
        cls.user_custodian = Users.create({
            'name': 'Lifecycle Custodian',
            'login': 'lifecycle_custodian',
            'group_ids': [
                (4, cls.env.ref('health_base.group_healthcare_nurse').id),
                (4, cls.env.ref('health_base.group_healthcare_custodian').id),
            ],
        })
        cls.user_owner = Users.create({
            'name': 'Lifecycle Owner',
            'login': 'lifecycle_owner',
            'group_ids': [(4, cls.env.ref('health_base.group_healthcare_owner').id)],
        })
        cls.reason = cls.env.ref('health_base.deletion_reason_duplicate')
        cls.reason_note = cls.env.ref('health_base.deletion_reason_other')
        # The healthcare-staff partner rule scopes patients by catchment —
        # nurse/custodian need a matching one to write on the test patient.
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'Lifecycle Test Province'})
        (cls.user_nurse | cls.user_custodian).write({
            'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Lifecycle Test Patient',
            'is_patient': True,
            'catchment_province_id': cls.province.id,
        })

    def _patient_as(self, user):
        return self.patient.with_user(user)

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    def test_soft_delete_requires_reason(self):
        with self.assertRaises(UserError):
            self._patient_as(self.user_nurse).action_soft_delete(False, '')

    def test_soft_delete_other_requires_note(self):
        with self.assertRaises(UserError):
            self._patient_as(self.user_nurse).action_soft_delete(
                self.reason_note.id, '')

    def test_soft_delete_sets_flags_and_logs(self):
        self._patient_as(self.user_nurse).action_soft_delete(
            self.reason.id, 'entered twice')
        self.assertTrue(self.patient.deleted)
        self.assertEqual(self.patient.deleted_by_id, self.user_nurse)
        self.assertEqual(self.patient.deleted_reason_id, self.reason)
        log = self.env['health.archive.log'].search([
            ('model_technical', '=', 'res.partner'),
            ('res_id', '=', self.patient.id),
            ('action', '=', 'delete'),
        ])
        self.assertEqual(len(log), 1)
        self.assertIn(self.reason.name, log.reason)
        self.assertEqual(log.record_state, 'deleted')

    def test_deleted_excluded_from_counts_but_visible_in_tables(self):
        Partner = self.env['res.partner']
        domain = [('id', '=', self.patient.id)]
        self.assertEqual(Partner.search_count(domain), 1)
        self.patient.action_soft_delete(self.reason.id, '')
        # counts / search exclude it by default…
        self.assertEqual(Partner.search_count(domain), 0)
        self.assertFalse(Partner.search(domain))
        self.assertFalse(Partner._read_group(domain, [], ['__count'])[0][0])
        self.assertFalse(Partner.name_search(self.patient.name))
        # …record tables (deleted_test=False) still show it
        ctx = Partner.with_context(deleted_test=False)
        self.assertEqual(ctx.search_count(domain), 1)
        # …and an explicit `deleted` reference in-domain wins over the default
        self.assertEqual(Partner.search_count(
            [('id', '=', self.patient.id), ('deleted', '=', True)]), 1)

    def test_archived_still_counted_with_active_test_false(self):
        # the BI/reporting contract: archived stays countable, deleted never
        Partner = self.env['res.partner']
        domain = [('id', '=', self.patient.id)]
        self.patient.action_archive()
        self.assertEqual(
            Partner.with_context(active_test=False).search_count(domain), 1)
        self.patient.action_unarchive()
        self.patient.action_soft_delete(self.reason.id, '')
        self.assertEqual(
            Partner.with_context(active_test=False).search_count(domain), 0)

    def test_copy_does_not_carry_lifecycle(self):
        self.patient.action_soft_delete(self.reason.id, '')
        clone = self.patient.with_context(deleted_test=False).copy(
            {'name': 'Lifecycle Clone'})
        self.assertFalse(clone.deleted)
        self.assertFalse(clone.deleted_reason_id)

    def test_raw_write_is_logged(self):
        self.patient.write({'deleted': True})
        log = self.env['health.archive.log'].search([
            ('model_technical', '=', 'res.partner'),
            ('res_id', '=', self.patient.id),
            ('action', '=', 'delete'),
        ])
        self.assertEqual(len(log), 1)

    def test_partner_guards(self):
        # partners linked to users / staff records are not client records
        with self.assertRaises(UserError):
            self.user_nurse.partner_id.action_soft_delete(self.reason.id, '')
        staff = self.env['res.partner'].create({
            'name': 'Lifecycle Staff', 'is_healthcare_staff': True})
        with self.assertRaises(UserError):
            staff.action_soft_delete(self.reason.id, '')

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def test_restore_is_custodian_only(self):
        self.patient.action_soft_delete(self.reason.id, '')
        with self.assertRaises(UserError):
            self._patient_as(self.user_nurse).action_restore()
        self._patient_as(self.user_custodian).action_restore()
        self.assertFalse(self.patient.deleted)
        self.assertFalse(self.patient.deleted_reason_id)
        log = self.env['health.archive.log'].search([
            ('res_id', '=', self.patient.id),
            ('model_technical', '=', 'res.partner'),
            ('action', '=', 'restore'),
        ])
        self.assertEqual(len(log), 1)

    # ------------------------------------------------------------------
    # Archive (custodian function)
    # ------------------------------------------------------------------

    def test_ui_archive_needs_custodian_and_reason(self):
        as_nurse = self._patient_as(self.user_nurse).with_context(
            archive_from_ui=True, archive_reason='cleanup')
        with self.assertRaises(AccessError):
            as_nurse.action_archive()
        as_custodian = self._patient_as(self.user_custodian).with_context(
            archive_from_ui=True)
        with self.assertRaises(UserError):
            as_custodian.action_archive()
        as_custodian.with_context(archive_reason='cleanup').action_archive()
        self.assertFalse(self.patient.active)

    def test_programmatic_archive_not_blocked(self):
        # internal code paths (no archive_from_ui) must keep working
        self._patient_as(self.user_nurse).action_archive()
        self.assertFalse(self.patient.active)

    # ------------------------------------------------------------------
    # Purge (owner physical delete)
    # ------------------------------------------------------------------

    def test_purge_matrix(self):
        # non-owner: never
        with self.assertRaises(AccessError):
            self._patient_as(self.user_nurse).unlink()
        # owner, no delete request yet: refused
        with self.assertRaises(UserError):
            self._patient_as(self.user_owner).unlink()
        # owner after a verified Delete request: allowed + logged
        self.patient.action_soft_delete(self.reason.id, '')
        patient_id = self.patient.id
        self._patient_as(self.user_owner).unlink()
        log = self.env['health.archive.log'].search([
            ('model_technical', '=', 'res.partner'),
            ('res_id', '=', patient_id),
            ('action', '=', 'purge'),
        ])
        self.assertEqual(len(log), 1)
        self.assertIn(self.reason.name, log.reason)
        self.assertEqual(log.record_state, 'purged')

    def test_owner_implies_custodian(self):
        self.assertTrue(self.user_owner.has_group(
            'health_base.group_healthcare_custodian'))

    # ------------------------------------------------------------------
    # Wizard
    # ------------------------------------------------------------------

    def test_wizard_delete_mode(self):
        wiz = self.env['health.archive.reason.wizard'].with_user(
            self.user_nurse,
        ).with_context(
            active_model='res.partner', active_ids=[self.patient.id],
        ).create({'mode': 'delete', 'reason_id': self.reason.id})
        wiz.action_confirm()
        self.assertTrue(self.patient.deleted)

    def test_wizard_delete_mode_requires_reason(self):
        with self.assertRaises(ValidationError):
            self.env['health.archive.reason.wizard'].with_context(
                active_model='res.partner', active_ids=[self.patient.id],
            ).create({'mode': 'delete'})

    def test_wizard_archive_mode_min_reason(self):
        with self.assertRaises(ValidationError):
            self.env['health.archive.reason.wizard'].with_context(
                active_model='res.partner', active_ids=[self.patient.id],
            ).create({'mode': 'archive', 'reason': 'x'})

    # ------------------------------------------------------------------
    # Log append-only
    # ------------------------------------------------------------------

    def test_log_append_only(self):
        self.patient.action_soft_delete(self.reason.id, '')
        log = self.env['health.archive.log'].search([
            ('res_id', '=', self.patient.id),
            ('model_technical', '=', 'res.partner'),
        ], limit=1)
        with self.assertRaises(UserError):
            log.write({'reason': 'tampered'})
        with self.assertRaises(UserError):
            log.unlink()
