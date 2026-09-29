# -*- coding: utf-8 -*-
"""ACCESS REVAMP AR-2, the clinic's half — the Screens lens on the real menu.

The numbered tests of the handover, each named after its number:

  1. a block's roles are a row on the lens, and a clinic administrator edits
     them; somebody who does not manage access cannot;
  2. an entry gated only through its block is gated — never "everyone with a
     login" — and is opened by exactly as many people as the block;
  3. the last role off a block leaves each entry to its own gate;
  4. this menu cannot show an entry locked, so the lens does not offer it;
  5. a passport parent says "3 of 5", matching what the menu draws;
  6. five abilities for the dark screens, each wrapping a permission, none
     reaching the keys to the box, none carried by any role;
  7. the dark screens sit under "Switched off", and "Switch on for …" works;
  8. the gate hook does not switch that entry off again;
  9. the re-read door is the platform administrator's alone, and counts;
 10. "Access & roles" on the Settings strip comes from the registry;
 11. what a role counts as, written on the role, reaches its people's flags;
 13. only a holder of a guarded role may take it away (owner decision, item I).

Tests 6, 7 and 8 are about THIS clinic's menu and catalogue — the fifteen
entries that are dark on it and the abilities written for them — so they read
the real rows rather than inventing some.
"""

import os
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import forbidden_in_closure
from odoo.addons.health_access import hooks

#: The fifteen entries that are dark on the live clinic (handover §2).
DARK_XMLIDS = (
    'health_access.item_crm_zalo',
    'health_access.item_crm_zalo_conversations',
    'health_access.item_crm_zalo_messages',
    'health_access.item_crm_zalo_settings',
    'health_access.item_ops_voice',
    'health_access.item_ops_voice_calls',
    'health_access.item_ops_voice_missed',
    'health_access.item_ops_voice_recordings',
    'health_access.item_ops_voice_extensions',
    'health_access.item_ops_voice_sync',
    'health_access.item_ops_voice_config',
    'biz_bi_cms.item_analytics_import',
    'biz_bi_cms.item_analytics_settings',
    'biz_bi_cms.item_analytics_access_rules',
    'biz_bi_cms.item_analytics_ai',
)


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts),
              encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class Ar2Case(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.internal = internal
        cls.clinic_admin = Users.create({
            'name': 'AR2 Clinic Admin', 'login': 'ar2.admin@example.test',
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_access.group_clinic_admin').id])]})
        cls.plain = Users.create({
            'name': 'AR2 Plain', 'login': 'ar2.plain@example.test',
            'group_ids': [(6, 0, [internal.id])]})
        cls.system = Users.create({
            'name': 'AR2 Platform', 'login': 'ar2.system@example.test',
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'base.group_system').id])]})
        cls.Section = cls.env['cms.sidebar.section']
        cls.Item = cls.env['cms.sidebar.item'].with_context(active_test=False)

    # ------------------------------------------------------------ fixtures
    def _group(self, name):
        return self.env['res.groups'].create({'name': name})

    def _role(self, name, groups, guarded=False):
        ability = self.env['biz.access.ability'].create({
            'technical_key': 'ar2-%s' % re.sub(r'\W+', '-', name.lower()),
            'name': name, 'area': 'admin',
            'group_ids': [(6, 0, groups.ids)]})
        return self.env['biz.access.role'].create({
            'name': name, 'area': 'admin', 'guarded': guarded,
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, ability.ids)]})

    def _user(self, login, groups=None):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': '%s@example.test' % login,
            'group_ids': [(6, 0, [self.internal.id])]})
        if groups:
            user.write({'group_ids': [(4, g.id) for g in groups]})
        return user

    def facade(self, user):
        return self.env['biz.access'].with_user(user)

    def board_section(self, board, section_id):
        return next(s for s in board['sections'] if s['id'] == section_id)

    def all_rows(self, board):
        for sec in board['sections']:
            for row in sec['items'] + sec['switched_off']:
                yield row
                for kid in row['children']:
                    yield kid


@tagged('post_install', '-at_install')
class TestAr2Blocks(Ar2Case):

    def test_1_the_admin_block_is_a_row_with_the_owner_chip(self):
        admin = self.Section.search([('technical_key', '=', 'admin')], limit=1)
        if not admin:
            self.skipTest('no ADMIN block on this database')
        owner = self.env.ref('health_access.role_owner')
        if owner not in admin.biz_role_ids:
            admin.write({'biz_role_ids': [(4, owner.id)]})
        board = self.facade(self.clinic_admin).screens_board()
        block = self.board_section(board, admin.id)['block']
        self.assertEqual(block['kind'], 'block')
        self.assertIn(owner.id, [g['id'] for g in block['gates']])
        self.assertFalse(block['everyone'])
        self.assertTrue(block['editable'])
        self.assertTrue(board['can_gate_blocks'])
        self.assertGreater(block['flows_to'], 0)

    def test_1_a_clinic_admin_writes_the_block_and_a_colleague_cannot(self):
        section = self.Section.create({'name': 'AR2 block',
                                       'technical_key': 'ar2_block',
                                       'sequence': 995})
        role = self._role('AR2 block role', self._group('AR2 block perm'))
        res = self.facade(self.clinic_admin).set_section_roles(
            section.id, role.ids)
        self.assertTrue(res['ok'])
        self.assertEqual(res['reload_event'], 'CMS_SIDEBAR:RELOAD')
        section.invalidate_recordset()
        self.assertEqual(section.biz_role_ids, role)
        with self.assertRaises(AccessError):
            self.facade(self.plain).set_section_roles(section.id, [])
        section.invalidate_recordset()
        self.assertEqual(section.biz_role_ids, role)

    def test_2_an_entry_gated_only_by_its_block_is_gated(self):
        section = self.Section.create({'name': 'AR2 gated block',
                                       'technical_key': 'ar2_gated',
                                       'sequence': 996})
        perm = self._group('AR2 gated perm')
        role = self._role('AR2 gated role', perm)
        holder = self._user('ar2.holder', perm)
        section.write({'biz_role_ids': [(6, 0, role.ids)]})
        entry = self.Item.create({'name': 'AR2 inherits',
                                  'section_id': section.id})
        board = self.facade(self.clinic_admin).screens_board()
        sec = self.board_section(board, section.id)
        row = next(r for r in sec['items'] if r['id'] == entry.id)
        self.assertFalse(row['everyone'])
        self.assertTrue(row['gated'])
        self.assertEqual(row['via'], 'section')
        self.assertEqual(row['via_label'], 'AR2 gated block')
        self.assertEqual(row['gates'], [])
        self.assertEqual([g['id'] for g in row['inherited']], role.ids)
        # Opened by exactly the block's people — administrators plus holders.
        self.assertEqual(row['seen_by'], sec['block']['seen_by'])
        admins = self.env.ref('base.group_system').all_user_ids.filtered(
            'active')
        self.assertEqual(row['seen_by'], len(set(admins.ids) | {holder.id}))
        detail = self.facade(self.clinic_admin).screen_detail(entry.id)
        self.assertFalse(detail['who']['everyone'])
        self.assertIn(holder.id, [w['id'] for w in detail['who']['rows']])

    def test_3_the_last_role_off_a_block_leaves_each_entry_its_own_gate(self):
        section = self.Section.create({'name': 'AR2 opening block',
                                       'technical_key': 'ar2_open',
                                       'sequence': 997})
        nurse_perm = self._group('AR2 nurse perm')
        other_perm = self._group('AR2 other perm')
        boss_perm = self._group('AR2 boss perm')
        nurse_role = self._role('AR2 nurse role', nurse_perm)
        other_role = self._role('AR2 other role', other_perm)
        boss_role = self._role('AR2 boss role', boss_perm)
        nurse = self._user('ar2.nurse', nurse_perm)
        section.write({'biz_role_ids': [(6, 0, boss_role.ids)]})
        open_one = self.Item.create({'name': 'AR2 no own gate',
                                     'section_id': section.id})
        nurses = self.Item.create({
            'name': 'AR2 nurses only', 'section_id': section.id,
            'biz_role_ids': [(6, 0, nurse_role.ids)]})
        others = self.Item.create({
            'name': 'AR2 others only', 'section_id': section.id,
            'biz_role_ids': [(6, 0, other_role.ids)]})
        rail = self.env['biz.access.rail']
        seen = rail.visibility_for(nurse)['items']
        self.assertEqual(seen[open_one.id], 'hidden')      # the block gates it
        self.assertEqual(seen[nurses.id], 'on')
        self.assertEqual(seen[others.id], 'hidden')

        res = self.facade(self.clinic_admin).set_section_roles(section.id, [])
        self.assertIn('own gate', res['message'])
        seen = rail.visibility_for(nurse)['items']
        self.assertEqual(seen[open_one.id], 'on')          # no gate at all now
        self.assertEqual(seen[nurses.id], 'on')
        self.assertEqual(seen[others.id], 'hidden')        # still its own

    def test_4_this_menu_has_no_locked_preview_and_the_lens_knows(self):
        board = self.facade(self.clinic_admin).screens_board()
        self.assertFalse(board['can_restrict'])
        entry = self.Item.create({'name': 'AR2 plain row', 'section_id':
                                  self.Section.search([], limit=1).id})
        with self.assertRaises(UserError) as caught:
            self.facade(self.clinic_admin).set_screen_flags(
                entry.id, restricted=True)
        self.assertIn('shown or hidden', str(caught.exception))
        xml = _src('biz_access', 'static', 'src', 'xml', 'access_board.xml')
        self.assertRegex(
            xml, r't-if="dt\.can_manage and !dt\.everyone and canRestrict"',
            'the "Everybody else" choice is no longer behind can_restrict')


@tagged('post_install', '-at_install')
class TestAr2Passport(Ar2Case):

    def test_5_a_nurse_passport_says_x_of_y_as_the_menu_draws_it(self):
        nurse_role = self.env.ref('health_access.role_nurse',
                                  raise_if_not_found=False)
        if not nurse_role or not nurse_role.group_ids:
            self.skipTest('no Nurse role on this database')
        nurse = self._user('ar2.passport.nurse', nurse_role.group_ids)
        passport = self.facade(self.clinic_admin).passport(nurse.id)
        seen = self.env['biz.access.rail'].visibility_for(nurse)['items']
        parents = [r for s in passport['rail'] for r in s['items']
                   if r['children']]
        self.assertTrue(parents, 'no entry with sub-entries on the menu')
        for row in parents:
            self.assertIn('kids_on', row)
            self.assertEqual(row['kids_total'], len(row['children']))
            on = len([k for k in row['children']
                      if seen.get(k['id']) == 'on'])
            self.assertEqual(row['kids_on'], on, row['label'])


@tagged('post_install', '-at_install')
class TestAr2DarkScreens(Ar2Case):

    def dark(self):
        out = self.Item.browse()
        for xmlid in DARK_XMLIDS:
            item = self.env.ref(xmlid, raise_if_not_found=False)
            if item and not item.active:
                out |= item
        return out

    def test_6_five_abilities_written_down_and_given_to_nobody(self):
        Ability = self.env['biz.access.ability'].with_context(
            active_test=False)
        present = [key for key, _a, _s, _n, _d, xmlids in hooks.ABILITIES
                   if key in hooks.DARK_SCREEN_ABILITIES
                   and all(self.env.ref(x, raise_if_not_found=False)
                           for x in xmlids)]
        if len(present) < 5:
            self.skipTest('the Zalo, phone or reporting modules are not all '
                          'installed here')
        found = Ability.search(
            [('technical_key', 'in', list(hooks.DARK_SCREEN_ABILITIES))])
        self.assertEqual(sorted(found.mapped('technical_key')),
                         sorted(hooks.DARK_SCREEN_ABILITIES))
        for ability in found:
            self.assertTrue(ability.group_ids, ability.technical_key)
            self.assertFalse(forbidden_in_closure(ability.group_ids, self.env),
                             ability.technical_key)
            # One ability per permission still holds.
            others = Ability.search([('id', '!=', ability.id),
                                     ('group_ids', 'in', ability.group_ids.ids)])
            self.assertFalse(others, ability.technical_key)
        # MENU M2 (owner ruling): the two PHONE abilities are written onto
        # the roles that work the phone and set it up. Every other one is
        # still given to nobody.
        ruled = {}
        try:
            from odoo.addons.health_cms_ia.hooks import PHONE_ABILITIES
            for key, role_xmlids in PHONE_ABILITIES.items():
                ruled[key] = {self.env.ref(x).id for x in role_xmlids
                              if self.env.ref(x, raise_if_not_found=False)}
        except ImportError:
            pass
        for ability in found:
            carriers = self.env['biz.access.role'].with_context(
                active_test=False).search([('ability_ids', 'in', ability.ids)])
            self.assertLessEqual(
                set(carriers.ids), ruled.get(ability.technical_key, set()),
                'a role was given "%s": %s' % (
                    ability.technical_key, ', '.join(carriers.mapped('name'))))

    def test_7_the_dark_screens_sit_under_switched_off(self):
        dark = self.dark()
        if len(dark) < len(DARK_XMLIDS):
            self.skipTest('not all fifteen are dark on this database')
        board = self.facade(self.clinic_admin).screens_board()
        listed = {}
        for sec in board['sections']:
            for row in sec['switched_off']:
                listed[row['id']] = row
                for kid in row['children']:
                    listed.setdefault(kid['id'], kid)
        for item in dark:
            self.assertIn(item.id, listed, item.name)
            self.assertTrue(listed[item.id]['awaiting'], item.name)
            if (item.feature_key == 'voice'
                    or (item.action_xmlid or '').startswith('health_voip24h.')):
                # Since MENU M2 the roles that handle calls can open these —
                # the same screens are on the menu as CRM › Phone — so "could
                # be opened by" is honestly no longer empty.
                continue
            self.assertEqual(listed[item.id]['could_be_opened_by'], [],
                             '%s: somebody can already open it' % item.name)
        self.assertGreaterEqual(board['counts']['switched_off'], 15)
        # Nothing switched off ON PURPOSE is offered to be switched on.
        staff = self.env.ref('health_cms_sidebar.item_ops_staff',
                             raise_if_not_found=False)
        if staff and not staff.active:
            self.assertNotIn(staff.id, listed)

    def test_7_switch_on_for_a_role_that_can_open_the_calls(self):
        voice = self.env.ref('health_access.item_ops_voice',
                             raise_if_not_found=False)
        calls = self.env.ref('health_access.item_ops_voice_calls',
                             raise_if_not_found=False)
        sync = self.env.ref('health_access.item_ops_voice_sync',
                            raise_if_not_found=False)
        handle = self.env['biz.access.ability'].search(
            [('technical_key', '=', 'calls-handle')], limit=1)
        if not (voice and calls and sync and handle) or voice.active:
            self.skipTest('the voice screens are not dark here')
        role = self.env['biz.access.role'].create({
            'name': 'AR2 call handler', 'area': 'operations',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, handle.ids)]})
        admin = self.facade(self.clinic_admin)
        row = admin.screen_detail(voice.id)
        self.assertTrue(row['awaiting'])
        self.assertIn(role.id, [g['id'] for g in row['could_be_opened_by']])
        kid = admin.screen_detail(calls.id)
        self.assertIn(role.id, [g['id'] for g in kid['could_be_opened_by']])

        with self.assertRaises(AccessError):
            self.facade(self.plain).switch_on_for(voice.id, role.id)
        res = admin.switch_on_for(voice.id, role.id)
        self.assertTrue(res['ok'])
        self.Item.invalidate_model()
        self.assertTrue(voice.active)
        self.assertEqual(voice.biz_role_ids, role)
        self.assertTrue(calls.active)
        self.assertIn(role, calls.effective_biz_role_ids)
        self.assertFalse(calls.biz_role_ids, 'the child should inherit')
        self.assertFalse(sync.active,
                         'the sync screen needs more than handling calls')

        # 8 — the gate hook does not undo it.
        hooks._gate_new_items(self.env)
        self.Item.invalidate_model()
        self.assertTrue(voice.active)
        self.assertEqual(voice.biz_role_ids, role)
        self.assertTrue(calls.active)

    def test_7_a_role_that_cannot_open_it_is_refused(self):
        voice = self.env.ref('health_access.item_ops_voice',
                             raise_if_not_found=False)
        if not voice or voice.active:
            self.skipTest('the voice screens are not dark here')
        role = self._role('AR2 unrelated', self._group('AR2 unrelated perm'))
        with self.assertRaises(UserError) as caught:
            self.facade(self.clinic_admin).switch_on_for(voice.id, role.id)
        self.assertIn('could open the screen', str(caught.exception))

    def test_7_an_entry_switched_off_on_purpose_is_not_this_doors(self):
        section = self.Section.search([], limit=1)
        role = self._role('AR2 door role', self._group('AR2 door perm'))
        entry = self.Item.create({'name': 'AR2 off on purpose',
                                  'section_id': section.id, 'active': False})
        with self.assertRaises(UserError) as caught:
            self.facade(self.clinic_admin).switch_on_for(entry.id, role.id)
        self.assertIn('on purpose', str(caught.exception))

    def test_8_the_hook_decides_a_new_entry_once_and_then_leaves_it(self):
        handled = hooks._gate_handled(self.env)
        for xmlid in hooks.NEW_ITEM_ROLES:
            item = self.env.ref(xmlid, raise_if_not_found=False)
            if item:
                self.assertIn(item.id, handled, xmlid)
        voice = self.env.ref('health_access.item_ops_voice',
                             raise_if_not_found=False)
        if not voice:
            self.skipTest('no voice entry')
        voice.write({'active': True, 'biz_role_ids': [(5, 0, 0)]})
        hooks._gate_new_items(self.env)
        voice.invalidate_recordset()
        self.assertTrue(voice.active, 'a handled entry was re-decided')


@tagged('post_install', '-at_install')
class TestAr2DoorsAndForms(Ar2Case):

    def test_9_the_re_read_door_is_the_platform_administrators(self):
        with self.assertRaises(AccessError):
            self.facade(self.clinic_admin).reseed_catalogue()
        self.assertFalse(self.facade(self.clinic_admin).get_board()[
            'can_reseed'])
        self.assertTrue(self.facade(self.system).get_board()['can_reseed'])
        res = self.facade(self.system).reseed_catalogue()
        self.assertTrue(res['ok'])
        for key in ('roles', 'abilities'):
            self.assertIn(key, res['before'])
            self.assertIn(key, res['after'])
            self.assertGreaterEqual(res['after'][key], res['before'][key])
        self.assertTrue(res['message'])

    def test_9_the_tooling_names_the_button_that_exists(self):
        service = _src('biz_tenants', 'models', 'service.py')
        self.assertIn('\\"Re-read the role ', service)
        xml = _src('biz_access', 'static', 'src', 'xml', 'access_board.xml')
        self.assertIn('Re-read the role catalogue', xml)

    def test_10_access_and_roles_comes_from_the_registry(self):
        nav = _src('health_landing', 'static', 'src', 'js',
                   'admin_model_navigator.js')
        self.assertNotIn('action: "biz_access.action_biz_access_home"', nav,
                         'the hard-coded tab is still in the strip')
        self.assertIn('ACCESS_TAB_IDS = new Set(["access"])', nav)
        tabs = _src('health_access', 'static', 'src', 'js', 'admin_tabs.js')
        self.assertIn('registry.category("health_landing.admin_tabs")'
                      '.add("access"', tabs)
        self.assertIn('group: "people"', tabs)
        self.assertIn('action: "biz_access.action_biz_access_home"', tabs)
        manifest = _src('health_access', '__manifest__.py')
        self.assertIn('health_access/static/src/js/admin_tabs.js', manifest)

    def test_11_what_a_role_counts_as_reaches_its_peoples_flags(self):
        role = self._role('AR2 job role', self._group('AR2 job perm'))
        self.assertEqual(role.clinical_kind, 'other')
        person = self._user('ar2.job')
        person.write({'job_role_id': role.id})
        self.assertFalse(person.is_nurse_role)
        role.write({'clinical_kind': 'nurse'})
        person.invalidate_recordset(['is_nurse_role'])
        self.assertTrue(person.is_nurse_role)
        role.write({'clinical_kind': 'doctor'})
        person.invalidate_recordset(['is_nurse_role', 'is_doctor_role'])
        self.assertFalse(person.is_nurse_role)
        self.assertTrue(person.is_doctor_role)
        form = self.env.ref(
            'health_access.view_biz_access_role_form_clinical_kind')
        self.assertIn('clinical_kind', form.arch_db)


@tagged('post_install', '-at_install')
class TestAr2TakingAGuardedRoleAway(Ar2Case):
    """13 — only somebody who holds a guarded role may take it away.

    The real Owner role for the refusal (the sentence has to name it) and for
    the removals that succeed (an Owner, the platform administrator); a
    throwaway guarded role as well, so the rule is proven on the flag and not
    on one role's name. Ending a hand-over is NOT this rule and stays the
    lender's. Both ways of changing somebody's job ask first too.
    """

    def setUp(self):
        super().setUp()
        self.owner = self.env.ref('health_access.role_owner')
        self.holder = self._user('ar2.owner.holder')
        self.env['biz.access'].grant(self.owner.id, self.holder.id)
        perm = self._group('AR2 keys perm')
        self.keys = self._role('AR2 keys', perm, guarded=True)
        self.keyholder = self._user('ar2.keyholder', perm | self.env.ref(
            'biz_access.group_access_manager'))
        self.target = self._user('ar2.keys.target')
        self.env['biz.access'].grant(self.keys.id, self.target.id)

    def test_13_a_clinic_admin_cannot_take_owner_away(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.clinic_admin).remove(self.owner.id,
                                                  self.holder.id)
        self.assertIn('Only somebody who holds "%s" can take it away'
                      % self.owner.name, str(caught.exception))

    def test_13_a_clinic_admin_cannot_take_any_guarded_role_away(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.clinic_admin).remove(self.keys.id,
                                                  self.target.id)
        self.assertIn('AR2 keys', str(caught.exception))
        self.assertTrue(set(self.keys.group_ids.ids)
                        <= set(self.target.all_group_ids.ids))

    def test_13_a_holder_can(self):
        res = self.facade(self.keyholder).remove(self.keys.id, self.target.id)
        self.assertTrue(res['ok'])
        self.target.invalidate_recordset()
        self.assertFalse(set(self.keys.group_ids.ids)
                         <= set(self.target.all_group_ids.ids))

    def _holds_owner(self, user):
        user.invalidate_recordset()
        return set(self.owner.group_ids.ids) <= set(user.all_group_ids.ids)

    def test_13_an_owner_can_take_owner_away(self):
        owner_actor = self._user('ar2.owner.actor', self.owner.group_ids)
        self.assertTrue(self._holds_owner(self.holder))
        res = self.facade(owner_actor).remove(self.owner.id, self.holder.id)
        self.assertTrue(res['ok'])
        self.assertFalse(self._holds_owner(self.holder))

    def test_13_the_platform_administrator_can_take_owner_away(self):
        res = self.facade(self.system).remove(self.owner.id, self.holder.id)
        self.assertTrue(res['ok'])
        self.assertFalse(self._holds_owner(self.holder))

    def test_13_the_platform_administrator_can(self):
        res = self.facade(self.system).remove(self.keys.id, self.target.id)
        self.assertTrue(res['ok'])

    def test_13_the_change_job_dialog_refuses_a_non_holder_too(self):
        """The dialog writes as the system, so it must ask first itself."""
        self.holder.write({'job_role_id': self.owner.id})
        other = self._role('AR2 dialog job', self._group('AR2 dialog perm'))
        wizard = self.env['health.access.set.job'].with_user(
            self.clinic_admin).create({'user_id': self.holder.id,
                                       'job_role_id': other.id})
        with self.assertRaises(UserError) as caught:
            wizard.action_apply()
        self.assertIn('Only somebody who holds "%s" can take it away'
                      % self.owner.name, str(caught.exception))
        self.holder.invalidate_recordset()
        self.assertEqual(self.holder.job_role_id, self.owner)
        self.assertTrue(self._holds_owner(self.holder))

    def test_13_operations_manager_stays_unguarded(self):
        ops = self.env.ref('health_access.role_operations_manager',
                           raise_if_not_found=False)
        if not ops:
            self.skipTest('no Operations Manager role here')
        self.assertFalse(ops.guarded)

    def test_13_ending_a_loan_of_a_guarded_role_is_still_the_lenders(self):
        borrower = self._user('ar2.keys.borrower')
        lent = self.facade(self.keyholder).delegate({
            'delegate_user_id': borrower.id,
            'profile_ids': [self.keys.id], 'kind': 'temporary',
            'date_end': fields.Date.today() + timedelta(days=5)})
        res = self.facade(self.keyholder).revoke(lent['id'])
        self.assertTrue(res['ok'])
        self.assertEqual(
            self.env['biz.access.delegation'].browse(lent['id']).state,
            'revoked')

    def test_13_the_passport_does_not_offer_what_it_would_refuse(self):
        rows = self.facade(self.clinic_admin).passport(self.holder.id)['roles']
        owner_row = next(r for r in rows if r['profile_id'] == self.owner.id)
        self.assertFalse(owner_row['can_take_back'])

    def test_13_changing_an_owners_job_is_refused_for_a_non_holder(self):
        self.holder.write({'job_role_id': self.owner.id})
        other = self._role('AR2 new job', self._group('AR2 new job perm'))
        with self.assertRaises(UserError) as caught:
            self.holder.with_user(self.clinic_admin).write(
                {'job_role_id': other.id})
        self.assertIn('can take it away', str(caught.exception))
        self.assertEqual(self.holder.job_role_id, self.owner)
