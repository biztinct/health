# -*- coding: utf-8 -*-
"""What somebody is employed as, and what writing it does.

THE POINT OF THE FIELD, IN ONE SENTENCE: classification is not permission. An
owner holds the Doctor role because an owner can do everything a doctor can;
that does not make the owner a doctor, and the roster must not put them on a
ward round. So there are two facts about a person now — what they HOLD and what
they ARE — and everything here checks that the second is the one the product
reads when it asks "is this a nurse".

And one deliberate crossing between them: writing the JOB grants that role,
because that is what everybody who has ever used this clinic's staff form
expects. The arrow points one way only — being granted a role on the Access
home does not change anybody's job.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class JobFieldCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = cls.env.ref('base.group_user')
        cls.Role = cls.env['biz.access.role']

        def role(name, kind, group_name, key):
            group = cls.env['res.groups'].create({'name': group_name})
            ability = cls.env['biz.access.ability'].create({
                'technical_key': key, 'name': group_name,
                'group_ids': [(6, 0, group.ids)]})
            bundle = cls.Role.create({
                'name': name, 'clinical_kind': kind,
                'ability_ids': [(6, 0, ability.ids)]})
            return bundle, group

        cls.nurse_job, cls.nurse_group = role(
            'JF nurse', 'nurse', 'JF nursing', 'jf-nursing')
        cls.doctor_job, cls.doctor_group = role(
            'JF doctor', 'doctor', 'JF doctoring', 'jf-doctoring')
        cls.om_job, cls.om_group = role(
            'JF operations', 'operations_manager', 'JF ops', 'jf-ops')
        cls.plain_job, cls.plain_group = role(
            'JF something else', 'other', 'JF other', 'jf-other')

        cls.person = cls.env['res.users'].create({
            'name': 'JF person', 'login': 'jf.person@example.test',
            'group_ids': [(4, cls.internal.id)]})
        cls.staff = cls.env['hr.employee'].create({
            'name': 'JF person', 'user_id': cls.person.id})


@tagged('post_install', '-at_install')
class TestTheFlagsComeFromTheJob(JobFieldCase):

    def test_the_four_flags_follow_the_job(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.staff.invalidate_recordset()
        self.assertTrue(self.staff.is_nurse_role)
        self.assertFalse(self.staff.is_doctor_role)
        self.assertFalse(self.staff.is_om_role)
        self.assertEqual(self.staff.access_role_display, 'JF nurse')
        self.assertTrue(self.person.is_nurse_role)
        self.assertFalse(self.person.is_doctor_role)

        self.person.sudo().job_role_id = self.om_job
        self.staff.invalidate_recordset()
        self.assertTrue(self.staff.is_om_role)
        self.assertFalse(self.staff.is_nurse_role)
        self.assertEqual(self.staff.access_role_display, 'JF operations')

    def test_holding_a_role_does_not_make_it_your_job(self):
        """THE WHOLE REASON THE FIELD EXISTS. Someone granted the Doctor role
        is not thereby a doctor to the roster."""
        self.env['biz.access'].sudo().grant(
            self.doctor_job.id, self.person.id, reason='a test')
        self.person.invalidate_recordset()
        self.staff.invalidate_recordset()
        self.assertFalse(self.person.job_role_id)
        self.assertFalse(self.staff.is_doctor_role)

    def test_a_name_with_the_word_doctor_in_it_is_not_a_doctor(self):
        """The old rule read the role's NAME. "Doctor's assistant" matched it
        and was not a doctor; the field says so instead."""
        assistant = self.Role.create({
            'name': "JF doctor's assistant", 'clinical_kind': 'other'})
        self.person.sudo().job_role_id = assistant
        self.staff.invalidate_recordset()
        self.assertFalse(self.staff.is_doctor_role)
        self.assertEqual(self.staff.access_role_display,
                         "JF doctor's assistant")

    def test_the_staff_record_and_the_login_mirror_each_other(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.staff.invalidate_recordset()
        self.assertEqual(self.staff.job_role_id, self.nurse_job)
        # ... and the other way, through the inverse on the staff form.
        self.staff.sudo().job_role_id = self.doctor_job
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_role_id, self.doctor_job)

    def test_the_public_profile_says_the_same_thing(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.staff.invalidate_recordset()
        public = self.env['hr.employee.public'].sudo().browse(self.staff.id)
        public.invalidate_recordset()
        self.assertTrue(public.is_nurse_role)
        self.assertEqual(public.access_role_display, 'JF nurse')


@tagged('post_install', '-at_install')
class TestWritingTheJobGivesTheRole(JobFieldCase):

    def test_setting_a_job_grants_it(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.person.invalidate_recordset()
        self.assertIn(self.nurse_group.id, self.person.all_group_ids.ids)

    def test_changing_the_job_takes_the_old_one_back(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.person.sudo().job_role_id = self.doctor_job
        self.person.invalidate_recordset()
        self.assertIn(self.doctor_group.id, self.person.all_group_ids.ids)
        self.assertNotIn(self.nurse_group.id, self.person.all_group_ids.ids)

    def test_it_keeps_what_another_role_they_hold_still_needs(self):
        """THE REMOVAL IS THE SAFE ONE. Somebody who also holds a second role
        that needs a permission the old job carried keeps that permission."""
        shared = self.Role.create({
            'name': 'JF shared', 'ability_ids': [
                (6, 0, self.nurse_job.ability_ids.ids)]})
        # The second role FIRST, so granting it is a real grant rather than
        # "they already have that" — after which setting the nursing job is
        # quietly a no-op, which is itself the behaviour under test two cases
        # down.
        self.env['biz.access'].sudo().grant(
            shared.id, self.person.id, reason='a second role')
        self.person.sudo().job_role_id = self.nurse_job
        self.person.sudo().job_role_id = self.doctor_job
        self.person.invalidate_recordset()
        self.assertIn(self.nurse_group.id, self.person.all_group_ids.ids,
                      'a permission a second role still needs was taken away')

    def test_clearing_the_job_takes_the_role_back(self):
        self.person.sudo().job_role_id = self.nurse_job
        self.person.sudo().job_role_id = False
        self.person.invalidate_recordset()
        self.assertNotIn(self.nurse_group.id, self.person.all_group_ids.ids)

    def test_setting_the_same_job_twice_is_quiet(self):
        """"They already have that" is an answer to a question nobody asked
        here; the job simply is what it is."""
        self.person.sudo().job_role_id = self.nurse_job
        self.person.sudo().job_role_id = self.nurse_job     # must not raise
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_role_id, self.nurse_job)

    def test_somebody_who_may_not_manage_access_cannot_write_it(self):
        """Server-side, in plain words: the field also hands out permissions,
        so hiding it on a form would leave the write open to anything that is
        not the form."""
        outsider = self.env['res.users'].create({
            'name': 'JF outsider', 'login': 'jf.outsider@example.test',
            'group_ids': [(4, self.internal.id)]})
        with self.assertRaises(AccessError):
            self.person.with_user(outsider).write(
                {'job_role_id': self.nurse_job.id})
