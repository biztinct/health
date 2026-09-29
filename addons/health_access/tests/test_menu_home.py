# -*- coding: utf-8 -*-
"""MENU M1 — Home is each role's own dashboard, and the menu's gates did not
move when the menu changed shape.

  * T2  `home_action()` for a front-desk (CRM) person, an Owner, an
        Accountant, a Nurse; Care Command switched off; nobody's role at all.
  * T7  a Nurse's rail draws exactly the blocks and entries `visibility_for`
        says she opens — Home always among them.
  * the Training heading moves from ADMIN to Learn keeping every role that
        opened it there, and a second run changes nothing.
"""

import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_access import hooks

CARE_COMMAND = 'health_care_command.action_care_command'
CRM_DASHBOARD = 'health_crm.action_crm_dashboard'
OPERATIONS = 'health_fieldservice.action_ops_command_center'
FINANCE = 'health_invoicing.action_fin_dashboard'
OBSERVATIONS = 'health_vitals.action_health_observation'
BOOKINGS = 'health_fieldservice.action_ops_booking_list_native'


@tagged('post_install', '-at_install')
class TestMenuHome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Item = cls.env['cms.sidebar.item']
        cls.Param = cls.env['ir.config_parameter'].sudo()
        cls.base = cls.env.ref('base.group_user')

    def _person(self, login, *role_xmlids):
        groups = self.base
        for xmlid in role_xmlids:
            role = self.env.ref(xmlid, raise_if_not_found=False)
            if not role:
                self.skipTest('%s is not on this database' % xmlid)
            groups |= role.group_ids
        return self.env['res.users'].create({
            'name': login, 'login': '%s@m1.example.test' % login,
            'group_ids': [(6, 0, groups.ids)]})

    def _home(self, user):
        return self.Item.with_user(user).home_action()

    def _set_features(self, value):
        self.Param.set_param('biz_tenancy.features', value)
        self.env.registry.clear_cache()

    # ------------------------------------------------------------------ T2
    def test_01_front_desk_lands_on_care_command(self):
        crm = self._person('m1crm', 'health_access.role_crm')
        self.assertEqual(self.Item.sudo()._home_area(crm), 'front_desk')
        expected = CARE_COMMAND if self.env.ref(
            CARE_COMMAND, raise_if_not_found=False) else CRM_DASHBOARD
        self.assertEqual(self._home(crm), expected)

    def test_02_an_owner_lands_on_operations(self):
        owner = self._person('m1owner', 'health_access.role_owner')
        self.assertEqual(self.Item.sudo()._home_area(owner), 'admin')
        self.assertEqual(self._home(owner), OPERATIONS)

    def test_03_an_accountant_lands_on_finance(self):
        accountant = self._person('m1acct', 'health_access.role_accountant')
        self.assertEqual(self.Item.sudo()._home_area(accountant), 'finance')
        self.assertEqual(self._home(accountant), FINANCE)

    def test_04_a_nurse_lands_on_bookings(self):
        """MENU M2 ruling: a nurse lands on the visits she is going out to."""
        nurse = self._person('m1nurse', 'health_access.role_nurse')
        self.assertEqual(self.Item.sudo()._home_area(nurse), 'clinical')
        self.assertEqual(self._home(nurse), BOOKINGS)

    def test_04b_a_doctor_lands_on_observations(self):
        doctor = self._person('m2doctor', 'health_access.role_doctor')
        self.assertEqual(self.Item.sudo()._home_area(doctor), 'clinical')
        self.assertEqual(self._home(doctor), OBSERVATIONS)

    def test_04c_home_never_lands_off_the_persons_menu(self):
        """The guard (MENU M2): whatever Home answers is a screen this
        person's own menu draws — for every one of the nine roles."""
        for xmlid in ('health_access.role_owner', 'health_access.role_admin',
                      'health_access.role_nurse', 'health_access.role_doctor',
                      'health_access.role_accountant', 'health_access.role_crm',
                      'health_access.role_operations_manager',
                      'health_access.role_branch_manager'):
            if not self.env.ref(xmlid, raise_if_not_found=False):
                continue
            person = self._person('m2g_%s' % xmlid.split('_', 2)[-1], xmlid)
            drawn = self.Item.with_user(person)._home_drawn_actions()
            if drawn:
                self.assertIn(self._home(person), drawn, xmlid)

    def test_05_care_command_switched_off_sends_the_desk_to_the_crm_dashboard(self):
        if 'biz.tenancy' not in self.env:
            self.skipTest('no product switches on this database')
        if not self.env.ref(CARE_COMMAND, raise_if_not_found=False):
            self.skipTest('Care Command is not installed here')
        key = self.env['biz.tenancy'].sudo().feature_of_action(CARE_COMMAND)
        if not key:
            # feature_of_action is only asked while something is off.
            self._set_features(json.dumps({'care_command': {'on': False, 'name': 'Care Command'}}))
            key = self.env['biz.tenancy'].sudo().feature_of_action(CARE_COMMAND)
        self.assertEqual(key, 'care_command')
        crm = self._person('m1crm2', 'health_access.role_crm')
        self._set_features(json.dumps({'care_command': {'on': False, 'name': 'Care Command'}}))
        try:
            self.assertEqual(self._home(crm), CRM_DASHBOARD)
        finally:
            self._set_features('')
        self.assertEqual(self._home(crm), CARE_COMMAND)

    def test_06_nobody_with_a_role_lands_on_the_first_screen_they_have(self):
        """No role: the Operations dashboard where their menu draws it, and
        otherwise the first screen it does draw (MENU M2 guard)."""
        loner = self._person('m1loner')
        self.assertEqual(self.Item.sudo()._home_area(loner), '')
        drawn = self.Item.with_user(loner)._home_drawn_actions()
        expected = OPERATIONS if (OPERATIONS in drawn or not drawn) else drawn[0]
        self.assertEqual(self._home(loner), expected)

    def test_07_two_roles_the_higher_area_wins(self):
        both = self._person('m1both', 'health_access.role_nurse',
                            'health_access.role_accountant')
        self.assertEqual(self._home(both), FINANCE,
                         'finance comes before clinical')

    def test_08_home_keeps_its_model_marker(self):
        method = type(self.Item).home_action
        self.assertTrue(getattr(method, '_api_model', False)
                        or getattr(method, '_api', None) == 'model')

    # ------------------------------------------------------------------ T7
    def test_09_a_nurses_rail_is_what_her_roles_open(self):
        nurse = self._person('m1nurse2', 'health_access.role_nurse')
        data = self.Item.with_user(nurse).sudo().get_sidebar_data()
        items, sections = self.Item._biz_visible_map(nurse)
        drawn_sections = {s['id'] for s in data}
        self.assertEqual(
            drawn_sections, {sid for sid, st in sections.items() if st == 'on'},
            'the rail draws a block her roles do not open, or misses one')
        drawn_items = set()
        for section in data:
            for item in section['items']:
                drawn_items.add(item['id'])
                drawn_items.update(k['id'] for k in item['children'])
        self.assertEqual(drawn_items,
                         {iid for iid, st in items.items() if st == 'on'})
        keys = [s['key'] for s in data]
        self.assertEqual(keys[0], 'home', 'Home is on everybody\'s rail')

    # ------------------------------------------------------------ re-home
    def test_10_training_moves_to_learn_keeping_its_gate(self):
        admin = self.env.ref('health_cms_sidebar.section_admin')
        learn = self.env.ref('health_cms_sidebar.section_learn')
        heading = self.env.ref(hooks.TRAINING_HEADING_XMLID).with_context(
            active_test=False)
        kids = self.Item.with_context(active_test=False).search(
            [('parent_id', '=', heading.id)])
        owner = self.env.ref('health_access.role_owner')
        ops = self.env.ref('health_access.role_operations_manager')
        # Put everything back where the seed used to have it, under a gated
        # ADMIN block, and remember who could open the heading there.
        (heading | kids).write({'section_id': admin.id})
        heading.write({'sequence': hooks.TRAINING_OLD_SEQUENCE,
                       'biz_role_ids': [(6, 0, owner.ids)]})
        admin.write({'biz_role_ids': [(6, 0, (owner | ops).ids)]})
        self.Item.invalidate_model(['effective_biz_role_ids'])
        before = set(heading.effective_biz_role_ids.ids)
        self.assertIn(ops.id, before)

        moved = hooks.rehome_training(self.env)
        self.assertEqual(moved, 1 + len(kids))
        self.assertEqual(heading.section_id, learn)
        self.assertEqual(set(kids.mapped('section_id')), {learn})
        self.assertEqual(heading.sequence, hooks.TRAINING_NEW_SEQUENCE)
        self.Item.invalidate_model(['effective_biz_role_ids'])
        self.assertEqual(set(heading.effective_biz_role_ids.ids), before,
                         'leaving the gated block took a role off the heading')
        self.assertEqual(hooks.rehome_training(self.env), 0,
                         'a second run must change nothing')

    def test_11_a_heading_moved_by_hand_stays_where_it_was_put(self):
        ops_section = self.env.ref('health_cms_sidebar.section_ops')
        heading = self.env.ref(hooks.TRAINING_HEADING_XMLID).with_context(
            active_test=False)
        heading.write({'section_id': ops_section.id})
        self.assertEqual(hooks.rehome_training(self.env), 0)
        self.assertEqual(heading.section_id, ops_section)
