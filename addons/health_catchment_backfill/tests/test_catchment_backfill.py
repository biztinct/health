from odoo.tests import TransactionCase, new_test_user, tagged

from ..hooks import backfill_doctor_catchment


@tagged('post_install', '-at_install')
class TestCatchmentBackfill(TransactionCase):
    """T-012 — the doctor catchment backfill, tested in isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facility = cls.env['health.facility'].search(
            [('catchment_province_id', '!=', False)], limit=1)
        cls.province = cls.facility.catchment_province_id
        cls.other_province = cls.env['health.catchment.province'].search(
            [('id', '!=', cls.province.id)], limit=1)
        cls.doctor_role = cls.env['access.role'].search(
            [('name', 'ilike', 'doctor')], limit=1)
        cls.nurse_role = cls.env['access.role'].search(
            [('name', 'ilike', 'nurse')], limit=1)

    def _make_user(self, login, role, facility=True, catchment=False):
        user = new_test_user(self.env, login=login, groups='base.group_user')
        if role:
            user.access_role_id = role.id
        user.catchment_province_id = catchment and catchment.id or False
        if facility:
            self.env['hr.employee'].create({
                'name': login, 'user_id': user.id,
                'healthcare_facility_id': self.facility.id,
            })
        return user

    def test_doctor_with_null_catchment_is_backfilled_from_facility(self):
        if not self.facility or not self.doctor_role:
            self.skipTest("missing facility or Doctor role on this database")
        user = self._make_user('t012_doc_null', self.doctor_role)
        self.assertFalse(user.catchment_province_id)
        backfill_doctor_catchment(self.env)
        self.assertEqual(
            user.catchment_province_id, self.province,
            "doctor should inherit the catchment province of their facility")

    def test_backfill_never_overwrites_an_existing_catchment(self):
        if not self.facility or not self.doctor_role or not self.other_province:
            self.skipTest("need a second province to prove non-overwrite")
        user = self._make_user('t012_doc_set', self.doctor_role,
                               catchment=self.other_province)
        backfill_doctor_catchment(self.env)
        self.assertEqual(
            user.catchment_province_id, self.other_province,
            "a doctor who already has a catchment must not be re-pointed")

    def test_nurse_role_is_left_untouched(self):
        if not self.facility or not self.nurse_role:
            self.skipTest("no Nurse role on this database")
        user = self._make_user('t012_nurse_null', self.nurse_role)
        backfill_doctor_catchment(self.env)
        self.assertFalse(
            user.catchment_province_id,
            "nurses are out of scope for T-012 and must stay NULL")

    def test_backfill_is_idempotent(self):
        if not self.facility or not self.doctor_role:
            self.skipTest("missing facility or Doctor role on this database")
        user = self._make_user('t012_doc_idem', self.doctor_role)
        backfill_doctor_catchment(self.env)
        first = user.catchment_province_id
        backfill_doctor_catchment(self.env)
        self.assertEqual(user.catchment_province_id, first,
                         "a second run must be a no-op")
