# -*- coding: utf-8 -*-
"""Section-level role gating flows down to the items underneath.

Client spec under test:
  * Assign roles at the ROOT (section) level and every item in that section
    is gated by them — including items that carry no roles of their own.
  * An item WITH its own roles is visible to those roles IN ADDITION to the
    inherited ones (union, never an override).
  * Parent items pass their gate down to their children the same way.
  * A section with no roles changes nothing: role-less items stay open.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSidebarRoleInheritance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Role = cls.env['access.role']
        cls.role_admin = Role.create({'name': 'RI Probe Admin'})
        cls.role_nurse = Role.create({'name': 'RI Probe Nurse'})
        cls.role_other = Role.create({'name': 'RI Probe Other'})

        cls.section = cls.env['cms.sidebar.section'].create({
            'name': 'RI Probe Section',
            'technical_key': 'ri_probe',
            'sequence': 900,
        })
        Item = cls.env['cms.sidebar.item']
        cls.bare = Item.create({
            'name': 'RI Bare Leaf', 'section_id': cls.section.id,
            'action_xmlid': 'health_landing.action_admin_facilities',
        })
        cls.owned = Item.create({
            'name': 'RI Owned Leaf', 'section_id': cls.section.id,
            'role_ids': [(6, 0, [cls.role_nurse.id])],
            'action_xmlid': 'health_landing.action_admin_catchments',
        })
        cls.parent = Item.create({
            'name': 'RI Parent', 'section_id': cls.section.id,
            'role_ids': [(6, 0, [cls.role_other.id])],
        })
        cls.child = Item.create({
            'name': 'RI Child', 'section_id': cls.section.id,
            'parent_id': cls.parent.id,
            'action_xmlid': 'health_landing.action_admin_districts',
        })

    def test_01_no_section_roles_leaves_everything_open(self):
        self.assertFalse(self.bare.effective_role_ids)
        self.assertEqual(self.owned.effective_role_ids, self.role_nurse)

    def test_02_section_roles_gate_a_role_less_leaf(self):
        self.section.role_ids = [(6, 0, [self.role_admin.id])]
        self.assertEqual(self.bare.effective_role_ids, self.role_admin)

    def test_03_leaf_roles_are_added_to_the_section_roles(self):
        self.section.role_ids = [(6, 0, [self.role_admin.id])]
        self.assertEqual(
            self.owned.effective_role_ids,
            self.role_admin | self.role_nurse,
            'a leaf must keep its own role AND gain the section role')

    def test_04_child_inherits_through_its_parent(self):
        self.section.role_ids = [(6, 0, [self.role_admin.id])]
        self.assertEqual(
            self.child.effective_role_ids,
            self.role_admin | self.role_other,
            'child inherits the section AND the parent item')

    def test_05_sidebar_payload_hides_the_leaf_from_a_foreign_role(self):
        self.section.role_ids = [(6, 0, [self.role_admin.id])]
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'RI Probe User', 'login': 'ri_probe_user',
        })
        user.access_role_id = self.role_other
        names = self._section_item_names(user)
        self.assertNotIn('RI Bare Leaf', names,
                         'a role-less leaf must be hidden once its section is gated')
        self.assertNotIn('RI Owned Leaf', names)
        self.assertIn('RI Parent', names, 'the parent carries RI Probe Other')

    def test_06_sidebar_payload_shows_the_leaf_to_the_section_role(self):
        self.section.role_ids = [(6, 0, [self.role_admin.id])]
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'RI Probe Admin User', 'login': 'ri_probe_admin_user',
        })
        user.access_role_id = self.role_admin
        names = self._section_item_names(user)
        self.assertIn('RI Bare Leaf', names)
        self.assertIn('RI Owned Leaf', names,
                      'union semantics: the section role sees it too')

    def _section_item_names(self, user):
        data = self.env['cms.sidebar.item'].with_user(user).get_sidebar_data()
        names = []
        for section in data:
            if section['key'] != 'ri_probe':
                continue
            for item in section['items']:
                names.append(item['name'])
                names.extend(c['name'] for c in item.get('children', []))
        return names
