# -*- coding: utf-8 -*-
"""Adding a colleague, and the four refusals that make it safe.

CREATING A USER IS THE MOST DANGEROUS WRITE IN ANY SYSTEM: whoever can do it
can, in principle, create one with the keys to the box. This form is used by
people who deliberately do NOT have those keys, so what is pinned here is not
that it works — it is that it cannot be made to do the one thing it must never
do.

  * somebody outside the access team is refused, on the server, whichever way
    they reached the form;
  * a role that carries — or merely IMPLIES, over the whole closure — the
    administrator permission is refused, because the one route that has ever got
    past a direct check is an ordinary-looking wrapper group;
  * a login that already exists is refused, in words that name who has it;
  * the qualifiers are offered by ABILITY, never by the name of the role, so a
    role called "Doctor's assistant" does not put somebody on the duty roster.

And then that it works: one press, and there is a login, a staff record and a
role, all three or none.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_access import hooks


@tagged('post_install', '-at_install')
class NewPersonCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['health.access.new.person']
        cls.internal = cls.env.ref('base.group_user')
        # SOMEBODY WHO ADDS COLLEAGUES AND DOES NOT OWN THE BOX. That is the
        # whole point of the form, so it is the account every test uses.
        cls.keeper = cls.env['res.users'].create({
            'name': 'NP keeper', 'login': 'np.keeper@example.test',
            'group_ids': [
                (4, cls.internal.id),
                (4, cls.env.ref('biz_access.group_access_manager').id)]})
        cls.outsider = cls.env['res.users'].create({
            'name': 'NP outsider', 'login': 'np.outsider@example.test',
            'group_ids': [(4, cls.internal.id)]})
        cls.nurse = hooks.role_by_name(cls.env, 'Nurse')

    def wizard(self, user=None, **vals):
        base = {'name': 'NP newcomer', 'login': 'np.newcomer@example.test'}
        base.update(vals)
        return self.Wizard.with_user(user or self.keeper).create(base)


@tagged('post_install', '-at_install')
class TestTheRefusals(NewPersonCase):

    def test_somebody_outside_the_access_team_cannot_add_anybody(self):
        """On the server. A form that is merely not linked to is a form
        somebody can call around."""
        wiz = self.wizard(user=self.outsider)
        with self.assertRaises(UserError):
            wiz.action_create()

    def test_a_login_that_already_exists_is_refused_by_name(self):
        wiz = self.wizard(login=self.outsider.login)
        with self.assertRaises(ValidationError) as caught:
            wiz.action_create()
        self.assertIn(self.outsider.name, str(caught.exception))

    def test_a_role_that_reaches_the_keys_to_the_building_is_refused(self):
        """It cannot normally exist — the model refuses it — so the check is
        made against a role forced past that, which is the only way it could
        ever arrive."""
        wrapper = self.env['res.groups'].create({
            'name': 'NP wrapper',
            'implied_ids': [(4, self.env.ref('base.group_system').id)]})
        role = self.env['biz.access.role'].create({'name': 'NP forced role'})
        self.env.cr.execute(
            'INSERT INTO biz_access_role_group_rel (profile_id, group_id) '
            'VALUES (%s, %s)', (role.id, wrapper.id))
        role.invalidate_recordset(['group_ids'])
        wiz = self.wizard(role_id=role.id)
        with self.assertRaises(UserError) as caught:
            wiz.action_create()
        self.assertIn('administrator permission', str(caught.exception))

    def test_a_role_that_hands_out_nothing_is_refused(self):
        empty = self.env['biz.access.role'].create({'name': 'NP empty role'})
        wiz = self.wizard(role_id=empty.id)
        with self.assertRaises(UserError):
            wiz.action_create()

    def test_the_picker_never_offers_a_role_that_has_been_put_away(self):
        field = self.Wizard._fields['role_id']
        self.assertIn("('active', '=', True)", str(field.domain))


@tagged('post_install', '-at_install')
class TestTheQualifiers(NewPersonCase):

    def test_they_are_offered_by_ability_and_not_by_the_word_in_the_name(self):
        if not self.nurse:
            self.skipTest('this database has no Nurse role')
        wiz = self.wizard(role_id=self.nurse.id)
        self.assertTrue(wiz.show_head_nurse)
        self.assertFalse(wiz.show_duty_doctor)

        # A role with "doctor" in its NAME and nothing of the job in it.
        decoy_ability = self.env['biz.access.ability'].create({
            'technical_key': 'np-decoy', 'name': 'NP decoy',
            'group_ids': [(6, 0, self.internal.ids)]})
        decoy = self.env['biz.access.role'].create({
            'name': "NP doctor's assistant",
            'ability_ids': [(6, 0, decoy_ability.ids)]})
        wiz = self.wizard(role_id=decoy.id)
        self.assertFalse(wiz.show_duty_doctor,
                         'a role was read by its name rather than its job')

    def test_a_qualifier_that_no_longer_applies_is_cleared(self):
        """Hidden and still set is how somebody ends up on the duty roster
        because of a role they held for ten seconds."""
        if not self.nurse:
            self.skipTest('this database has no Nurse role')
        wiz = self.wizard(role_id=self.nurse.id, is_head_nurse=True)
        wiz.role_id = self.env['biz.access.role'].create({
            'name': 'NP nothing role'})
        wiz._onchange_role_id()
        self.assertFalse(wiz.is_head_nurse)


@tagged('post_install', '-at_install')
class TestItActuallyAddsThem(NewPersonCase):

    def test_one_press_makes_a_login_a_staff_record_and_a_role(self):
        if not self.nurse:
            self.skipTest('this database has no Nurse role')
        wiz = self.wizard(role_id=self.nurse.id, is_head_nurse=True)
        wiz.action_create()

        user = self.env['res.users'].sudo().search(
            [('login', '=', 'np.newcomer@example.test')], limit=1)
        self.assertTrue(user, 'nobody was added')
        self.assertTrue(user.active)
        self.assertTrue(user.is_healthcare_staff)
        self.assertTrue(user.is_head_nurse)

        self.assertTrue(
            set(self.nurse.group_ids.ids) <= set(user.all_group_ids.ids),
            'they do not hold the role they were given')

        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1)
        self.assertTrue(employee, 'no staff record was made')
        self.assertTrue(employee.is_healthcare_staff)
        self.assertTrue(employee.is_head_nurse)

    def test_the_history_says_who_added_them_and_why(self):
        if not self.nurse:
            self.skipTest('this database has no Nurse role')
        self.wizard(login='np.second@example.test',
                    role_id=self.nurse.id).action_create()
        user = self.env['res.users'].sudo().search(
            [('login', '=', 'np.second@example.test')], limit=1)
        rows = self.env['biz.access.delegation'].sudo().search(
            [('delegate_user_id', '=', user.id)])
        self.assertTrue(rows, 'the role was given with no record of it')
        self.assertIn('added', rows[0].reason)

    def test_the_older_access_app_is_told_too_while_it_is_still_here(self):
        """Somebody added today has to look exactly like somebody added last
        week to every screen that has not moved across yet."""
        if 'access.role' not in self.env:
            self.skipTest('the previous access application is not installed')
        if not self.nurse:
            self.skipTest('this database has no Nurse role')
        self.wizard(login='np.third@example.test',
                    role_id=self.nurse.id).action_create()
        user = self.env['res.users'].sudo().search(
            [('login', '=', 'np.third@example.test')], limit=1)
        self.assertEqual(user.access_role_id.name, 'Nurse')
