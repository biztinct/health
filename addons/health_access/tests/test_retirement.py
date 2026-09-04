# -*- coding: utf-8 -*-
"""What the retirement had to leave true, checked against the real database.

Three fabricated users prove a rule; seventy real colleagues prove a clinic.
Everything here is asked of whatever is actually on the database it runs on, and
skips honestly where the thing it asks about is not installed — because a test
that quietly passes on an empty set is a test that will pass on the day it
matters most.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_access import hooks
from odoo.addons.health_access.models.access_role import kind_from_name


@tagged('post_install', '-at_install')
class RetirementCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Role = cls.env['biz.access.role'].with_context(active_test=False)


@tagged('post_install', '-at_install')
class TestWhatEachRoleCountsAs(RetirementCase):

    def test_the_nine_say_what_they_are(self):
        expected = {
            'health_access.role_doctor': 'doctor',
            'health_access.role_nurse': 'nurse',
            'health_access.role_operations_manager': 'operations_manager',
            'health_access.role_owner': 'other',
            'health_access.role_admin': 'other',
            'health_access.role_crm': 'other',
            'health_access.role_accountant': 'other',
            'health_access.role_branch_manager': 'other',
            'health_access.role_banker': 'other',
        }
        for xmlid, kind in expected.items():
            role = self.env.ref(xmlid, raise_if_not_found=False)
            if not role:
                continue
            with self.subTest(role=role.name):
                self.assertEqual(role.clinical_kind, kind)

    def test_it_is_exactly_the_rule_the_product_used_to_apply(self):
        """The old rule read the role's NAME. It was applied once, so that
        nothing changed on the day this shipped, and then never again."""
        for role in self.Role.search([]):
            if role.clinical_kind == 'other':
                continue
            with self.subTest(role=role.name):
                self.assertEqual(role.clinical_kind, kind_from_name(role.name))

    def test_a_second_run_does_not_overrule_a_deliberate_answer(self):
        """A NAME IS READ ONCE. Every role starts on the same default, so the
        field cannot tell "nobody has looked at this" from "somebody looked and
        said no" — which is why the step records which names it has read."""
        role = self.Role.create({'name': 'RT doctor of philosophy'})
        self.assertEqual(role.clinical_kind, 'other')
        hooks._set_clinical_kinds(self.env)
        role.invalidate_recordset()
        self.assertEqual(role.clinical_kind, 'doctor')     # first read
        role.write({'clinical_kind': 'other'})             # somebody says no
        hooks._set_clinical_kinds(self.env)
        role.invalidate_recordset()
        self.assertEqual(
            role.clinical_kind, 'other',
            'the re-run overruled somebody who had already answered')

    def test_the_nine_are_on_the_read_list(self):
        """The list is what makes "once" mean once, so it has to be there."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            hooks.KINDS_READ_PARAM) or ''
        read = {int(x) for x in raw.split(',') if x.strip().isdigit()}
        for xmlid in hooks.ROLE_XMLIDS.values():
            role = self.env.ref('health_access.%s' % xmlid,
                                raise_if_not_found=False)
            if role:
                self.assertIn(role.id, read, '%s was never read' % role.name)


@tagged('post_install', '-at_install')
class TestEverybodyHasTheirJob(RetirementCase):

    def test_everybody_who_was_given_a_role_has_a_job(self):
        """ASSIGNED, NOT HELD, AND THE TWO ARE DIFFERENT NUMBERS.

        The previous application gave each person exactly one role, and that
        assignment is what became their job. HOLDING a role is a different
        fact: the platform administrator holds all nine, and the six service
        and demo accounts hold whatever their permissions add up to. None of
        them was ever given a job and none of them gets one here.

        Skipped once that application is gone, because the question it asks no
        longer has a source of truth — by then the parity is the before/after
        snapshot's job, not a test's.
        """
        Users = self.env['res.users'].sudo()
        if 'access_role_id' not in Users._fields:
            self.skipTest('the previous access application is not installed')
        users = Users.search([('active', '=', True), ('share', '=', False),
                              ('access_role_id', '!=', False)])
        without = [u.login for u in users if not u.job_role_id]
        self.assertFalse(
            without,
            '%s colleague(s) were given a role and have no job: %s'
            % (len(without), ', '.join(sorted(without)[:10])))

    def test_every_job_written_down_is_a_real_role(self):
        """True whether or not the previous application is still here."""
        users = self.env['res.users'].sudo().with_context(
            active_test=False).search([('job_role_id', '!=', False)])
        self.assertTrue(users, 'nobody on this database has a job')
        for user in users:
            with self.subTest(login=user.login):
                self.assertTrue(user.job_role_id.exists())
                self.assertTrue(user.job_role_id.name)

    def test_the_job_and_the_staff_record_never_disagree(self):
        staff = self.env['hr.employee'].sudo().with_context(
            active_test=False).search([('user_id', '!=', False)])
        for emp in staff:
            with self.subTest(who=emp.name):
                self.assertEqual(emp.job_role_id, emp.user_id.job_role_id)

    def test_the_flags_say_what_the_job_says(self):
        staff = self.env['hr.employee'].sudo().with_context(
            active_test=False).search([])
        for emp in staff:
            kind = emp.job_role_id.clinical_kind if emp.job_role_id else False
            with self.subTest(who=emp.name):
                self.assertEqual(emp.is_doctor_role, kind == 'doctor')
                self.assertEqual(emp.is_nurse_role, kind == 'nurse')
                self.assertEqual(emp.is_om_role, kind == 'operations_manager')
                self.assertEqual(emp.access_role_display,
                                 emp.job_role_id.name or '')


@tagged('post_install', '-at_install')
class TestTheGatesThatMovedWithIt(RetirementCase):

    def test_the_left_menu_gates_are_written_on_the_role_bundles(self):
        """Seventy-nine entries were gated under the previous application. They
        are gated on the bundles now, and a gate that came across empty would be
        an entry silently opened to the whole clinic."""
        gated = self.env['cms.sidebar.item'].sudo().search(
            [('biz_role_ids', '!=', False)])
        self.assertTrue(gated, 'not one left-menu entry carries a gate')

    def test_the_analytics_roles_may_build_reports(self):
        ability = self.env['biz.access.ability'].with_context(
            active_test=False).search(
                [('technical_key', '=', hooks.ANALYTICS_ABILITY)], limit=1)
        if not ability:
            self.skipTest('the reporting module is not on this database')
        for name in hooks.ANALYTICS_ROLES:
            role = hooks.role_by_name(self.env, name)
            if not role:
                continue
            with self.subTest(role=name):
                self.assertIn(ability, role.ability_ids)

    def test_nobody_stopped_holding_a_role_because_it_grew(self):
        """THE DEFECT THIS GUARDS, WHICH A REAL DOCTOR FOUND.

        Adding "build reports" to four bundles made those bundles BIGGER, and
        holding a role means holding all of it — so anybody without the
        reporting permission silently stopped holding the role and lost every
        left-menu entry it opened. The step now works out who to give the
        permission to from the role WITHOUT it. This is that promise: on this
        database, everybody who holds all of an Analytics role EXCEPT the
        reporting permission has the reporting permission.
        """
        ability = self.env['biz.access.ability'].with_context(
            active_test=False).search(
                [('technical_key', '=', hooks.ANALYTICS_ABILITY)], limit=1)
        if not ability:
            self.skipTest('the reporting module is not on this database')
        reporting = ability.group_ids
        users = self.env['res.users'].sudo().search(
            [('active', '=', True), ('share', '=', False)])
        for name in hooks.ANALYTICS_ROLES:
            role = hooks.role_by_name(self.env, name)
            if not role or not role.group_ids:
                continue
            needed = set((role.group_ids - reporting).ids)
            if not needed:
                continue
            for user in users:
                held = set(user.all_group_ids.ids)
                if not needed <= held:
                    continue
                with self.subTest(role=name, login=user.login):
                    self.assertTrue(
                        set(reporting.ids) <= held,
                        '%s holds everything in "%s" except the reporting '
                        'permission, so they no longer hold the role at all'
                        % (user.login, name))

    def test_every_new_entry_either_opens_something_or_is_switched_off(self):
        """ZERO DEAD ENDS. An entry naming a screen this database does not have
        is switched off rather than left to answer "that does not exist"."""
        rows = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'health_access'),
            ('model', '=', 'cms.sidebar.item')])
        items = self.env['cms.sidebar.item'].sudo().with_context(
            active_test=False).browse([r.res_id for r in rows]).exists()
        for item in items:
            if not item.active or not item.action_xmlid:
                continue
            with self.subTest(entry=item.name):
                self.assertTrue(
                    self.env.ref(item.action_xmlid, raise_if_not_found=False),
                    '"%s" is drawn and opens nothing (%s)'
                    % (item.name, item.action_xmlid))

    def test_a_heading_with_nothing_under_it_is_switched_off(self):
        rows = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'health_access'),
            ('model', '=', 'cms.sidebar.item')])
        Item = self.env['cms.sidebar.item'].sudo().with_context(
            active_test=False)
        for item in Item.browse([r.res_id for r in rows]).exists():
            if item.action_xmlid or item.action_tag:
                continue
            children = Item.search_count(
                [('parent_id', '=', item.id), ('active', '=', True)])
            with self.subTest(heading=item.name):
                self.assertEqual(bool(item.active), bool(children))


@tagged('post_install', '-at_install')
class TestTheFieldNamesTheProductReads(RetirementCase):

    def test_the_four_flags_are_still_called_what_they_were_called(self):
        """SIXTY-ODD READERS ACROSS A DOZEN MODULES read these by name — the
        offline app among them. What they MEAN changed; what they are CALLED
        did not, and this is the guard on that promise."""
        employee = self.env['hr.employee']
        for name in ('is_doctor_role', 'is_nurse_role', 'is_om_role',
                     'access_role_display', 'job_role_id'):
            self.assertIn(name, employee._fields,
                          'hr.employee lost %s' % name)
        users = self.env['res.users']
        for name in ('is_doctor_role', 'is_nurse_role', 'job_role_id'):
            self.assertIn(name, users._fields, 'res.users lost %s' % name)
        public = self.env['hr.employee.public']
        for name in ('is_doctor_role', 'is_nurse_role', 'access_role_display'):
            self.assertIn(name, public._fields,
                          'hr.employee.public lost %s' % name)


@tagged('post_install', '-at_install')
class TestSealedNotesStillVerify(RetirementCase):

    def test_three_finalised_notes_still_pass_their_integrity_check(self):
        """The author's ROLE NAME is part of a sealed hash. The job stopped
        being a pointer at the previous application's row and became a role
        bundle of the same name, so the string resolves to the same words —
        and that is why every note sealed before this change still verifies."""
        if 'health.clinical.note' not in self.env:
            self.skipTest('clinical notes are not on this database')
        Note = self.env['health.clinical.note'].sudo()
        if not hasattr(Note, 'verify_integrity'):
            self.skipTest('this clinical note has no integrity seal')
        notes = Note.search(
            [('emr_state', '=', 'final'), ('content_hash', '!=', False)],
            limit=3)
        if not notes:
            self.skipTest('this database has no sealed clinical note')
        for note in notes:
            with self.subTest(note=note.id):
                self.assertTrue(
                    note.verify_integrity(),
                    'note %s no longer verifies against its seal' % note.id)
