# -*- coding: utf-8 -*-
"""SH-1 §4 (F2) — Practitioner.qualification without an HR-privileged token.

`/fhir/r4/Practitioner` answered 403 for any service user without an HR group:
`PractitionerSerializer.to_fhir` reads `healthcare_skill_ids` to build
`Practitioner.qualification`, and `hr.employee._check_private_fields`
(`hr/models/hr_employee.py:1134-1137`) treats a field as public **iff a field
of that name exists on `hr.employee.public`** — there is no separate list.
SH-1 publishes the field on `hr.employee.public` in health_fieldservice (the
module that owns it; the GC-3 report said health_base, which is wrong on the
module).

§5.102 applies with full force: an admin-grouped fixture cannot see this class
of bug at all, so the user below holds exactly `base.group_user` plus one
healthcare group and nothing from HR.
"""
import uuid

from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_fhir_core.serializers import REGISTRY


@tagged('post_install', '-at_install')
class TestSh1PractitionerQualification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        tag = uuid.uuid4().hex[:5]
        cls.province = env['health.catchment.province'].search([], limit=1) or \
            env['health.catchment.province'].create({'name': 'SH1 FHIR P'})
        cls.facility = env['health.facility'].search(
            [('catchment_province_id', '=', cls.province.id)], limit=1)
        if not cls.facility:
            cls.facility = env['health.facility'].create({
                'name': 'SH1 FHIR Facility', 'code': 'SH1F%s' % tag[:3],
                'street': '1 St', 'city': 'Hà Nội',
                'catchment_province_id': cls.province.id})

        cls.skill = env['health.staff.skill'].create({
            'name': 'SH1 Wound Care %s' % tag, 'skill_category_id': cls.env['health.lookup.value']._default_for('staff_skill_category', 'nursing')})
        cls.employee = env['hr.employee'].create({
            'name': 'SH1 Practitioner %s' % tag,
            'healthcare_facility_id': cls.facility.id,
            'healthcare_skill_ids': [(6, 0, cls.skill.ids)],
        })

        # A minimally-scoped service user: one healthcare group, NOTHING from
        # HR. Cloned from the GC-1/GC-3 fixture shape (test_fhir_gc3.py:127).
        cls.service_user = new_test_user(
            env, login='sh1_fhir_service_%s' % tag,
            groups='base.group_user,health_base.group_healthcare_receptionist')
        cls.service_user.catchment_province_id = cls.province.id

    def test_41_minimal_user_can_fetch_healthcare_skill_ids(self):
        """The read that used to raise 'not available for employee public
        profiles'. Asserted as the minimal user — never as admin."""
        user = self.service_user
        self.assertFalse(
            user.has_group('hr.group_hr_user'),
            'fixture problem: the service user holds an HR group, so this '
            'test cannot see the bug at all (§5.102)')
        employee = self.env['hr.employee'].with_user(user).browse(self.employee.id)
        employee.fetch(['healthcare_skill_ids'])          # raised before SH-1
        self.assertEqual(employee.healthcare_skill_ids.ids, self.skill.ids)

    def test_41b_field_is_published_on_the_public_profile(self):
        """The mechanism, not the symptom: _check_private_fields consults
        hr.employee.public's field set."""
        public = self.env['hr.employee.public']
        self.assertIn('healthcare_skill_ids', public._fields)
        pub_field = public._fields['healthcare_skill_ids']
        priv_field = self.env['hr.employee']._fields['healthcare_skill_ids']
        self.assertEqual(pub_field.comodel_name, priv_field.comodel_name)
        self.assertEqual(pub_field.relation, priv_field.relation)
        self.assertEqual((pub_field.column1, pub_field.column2),
                         (priv_field.column1, priv_field.column2))

    def test_42_serializer_emits_qualification_for_the_minimal_user(self):
        """Assert on serializer OUTPUT, not on the field read."""
        env = self.env(user=self.service_user)
        serializer = REGISTRY['Practitioner']
        self.assertIn('healthcare_skill_ids', serializer.prefetch_fields)
        record = serializer.read_record(env, self.employee.id)
        self.assertTrue(record, 'record rules hid the employee from the '
                                'minimal-privilege user — fixture problem')
        resources = serializer.serialize_batch(record)
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertEqual(resource['resourceType'], 'Practitioner')
        self.assertIn(
            'qualification', resource,
            'Practitioner.qualification is still absent — the public-profile '
            'publish did not take effect for a non-HR user')
        self.assertEqual(
            [q['code']['text'] for q in resource['qualification']],
            [self.skill.name])
