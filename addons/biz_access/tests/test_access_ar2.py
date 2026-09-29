# -*- coding: utf-8 -*-
"""ACCESS REVAMP AR-2, the generic half — what a product's menu CAN do, said
by the menu, and the lens that listens.

Against the in-memory menu, which says the protocol's defaults: it CAN show an
entry locked (the teaser the protocol has always carried), and it CANNOT gate a
whole block. So this proves the defaults a product inherits, and that the lens
offers exactly what the menu says it can draw — the clinic's own half proves
the opposite answers on the real menu.

And the passport's folded parents: "x of y" counted off the same states the
sub-entries carry.
"""

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.models.access_common import (RailProvider,
                                                         groups_can_read)

from .fake_rail import FakeRailMixin


@tagged('post_install', '-at_install')
class TestAr2Generic(TransactionCase, FakeRailMixin):

    def setUp(self):
        super().setUp()
        self.rail = self.use_fake_rail()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        self.perm = self.env['res.groups'].create({'name': 'ZZ AR2 %s' % stamp})
        ability = self.env['biz.access.ability'].create({
            'technical_key': 'zz-ar2-%s' % stamp, 'name': 'ZZ AR2',
            'area': 'general', 'group_ids': [(6, 0, self.perm.ids)]})
        self.role = self.env['biz.access.role'].create({
            'name': 'ZZ AR2 role %s' % stamp, 'area': 'general',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, ability.ids)]})
        internal = self.env.ref('base.group_user')
        self.manager = Users.create({
            'name': 'ZZ AR2 manager', 'login': 'zz.ar2.mgr.%s' % stamp,
            'group_ids': [(6, 0, [internal.id, self.env.ref(
                'biz_access.group_access_manager').id])]})
        self.person = Users.create({
            'name': 'ZZ AR2 person', 'login': 'zz.ar2.p.%s' % stamp,
            'group_ids': [(6, 0, [internal.id, self.perm.id])]})
        self.section = self.rail.add_section('ZZ AR2 block')
        self.parent = self.rail.add_entry(self.section, 'ZZ AR2 parent', 1)
        self.kid_on = self.rail.add_entry(self.section, 'ZZ AR2 open kid', 1,
                                          parent=self.parent, roles=self.role)
        self.kid_off = self.rail.add_entry(self.section, 'ZZ AR2 closed kid', 2,
                                           parent=self.parent,
                                           groups=self.env['res.groups'].create(
                                               {'name': 'ZZ AR2 nobody'}))
        self.facade = self.env['biz.access'].with_user(self.manager)

    def test_the_protocol_defaults(self):
        base = RailProvider()
        self.assertFalse(base.supports_section_gates(self.env))
        self.assertTrue(base.supports_restricted(self.env))
        with self.assertRaises(NotImplementedError):
            base.set_section_roles(self.env, 1, [])

    def test_4_a_menu_that_can_tease_keeps_the_choice(self):
        board = self.facade.screens_board()
        self.assertTrue(board['can_restrict'])
        self.assertFalse(board['can_gate_blocks'])
        res = self.facade.set_screen_flags(self.kid_on['id'], restricted=True)
        self.assertTrue(res['ok'])

    def test_1_a_menu_without_block_gates_refuses_them_in_words(self):
        board = self.facade.screens_board()
        sec = next(s for s in board['sections'] if s['id'] == self.section['id'])
        self.assertFalse(sec['block']['editable'])
        with self.assertRaises(UserError) as caught:
            self.facade.set_section_roles(self.section['id'], self.role.ids)
        self.assertIn('entries inside it', str(caught.exception))

    def test_1_block_gates_are_the_access_teams(self):
        plain = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'ZZ AR2 plain', 'login': 'zz.ar2.plain.%s'
                % self.role.id,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['biz.access'].with_user(plain).set_section_roles(
                self.section['id'], [])

    def test_5_the_passport_counts_x_of_y_off_its_own_rows(self):
        passport = self.facade.passport(self.person.id)
        row = next(r for s in passport['rail'] for r in s['items']
                   if r['id'] == self.parent['id'])
        self.assertEqual(row['kids_total'], 2)
        self.assertEqual(row['kids_on'], 1)
        self.assertEqual(
            row['kids_on'],
            len([k for k in row['children'] if k['state'] == 'on']))

    def test_an_entry_without_an_effective_key_is_its_own_gate(self):
        """A product that says nothing about inheritance gets the old answer."""
        row = self.facade.screen_detail(self.kid_on['id'])
        self.assertEqual([g['id'] for g in row['gates']], self.role.ids)
        self.assertEqual(row['inherited'], [])
        self.assertEqual(row['via'], 'own')
        self.assertFalse(row['everyone'])

    def test_switch_on_is_only_for_what_the_product_says_is_waiting(self):
        self.rail.set_active(self.env, self.kid_off['id'], False)
        with self.assertRaises(UserError):
            self.facade.switch_on_for(self.kid_off['id'], self.role.id)

    def test_the_readable_question_is_asked_of_the_permissions_table(self):
        # A screen that opens no records refuses nobody.
        self.assertTrue(groups_can_read(self.env, self.perm, ''))
        self.assertTrue(groups_can_read(self.env, self.perm, 'no.such.model'))
        # A model only the access team reads: this permission cannot.
        acl = self.env['ir.model.access'].search(
            [('model_id.model', '=', 'biz.access.role'),
             ('perm_read', '=', True)])
        if acl and all(a.group_id for a in acl):
            self.assertFalse(groups_can_read(self.env, self.perm,
                                             'biz.access.role'))
