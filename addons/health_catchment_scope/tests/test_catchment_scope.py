# -*- coding: utf-8 -*-
"""health_catchment_scope acceptance tests.

Two things are asserted separately and must never be conflated:

* the FACET — what the search view offers the user, which is a signal;
* the BOUNDARY — what the record rules allow, which is the security.

A test that only checked the facet would pass on a build where removing the
facet leaked another area's records.
"""
from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCatchmentScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Province = cls.env['health.catchment.province']
        cls.area_a = Province.create({'name': 'Scope Test Area A', 'code': 'STA'})
        cls.area_b = Province.create({'name': 'Scope Test Area B', 'code': 'STB'})

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.g_nurse = cls.env.ref('health_base.group_healthcare_nurse')
        cls.g_owner = cls.env.ref('health_base.group_healthcare_owner')

        cls.nurse = Users.create({
            'name': 'Scope Nurse A', 'login': 'scope_nurse_a',
            'group_ids': [(6, 0, cls.g_nurse.ids)],
            'catchment_province_id': cls.area_a.id,
        })
        cls.nurse_no_area = Users.create({
            'name': 'Scope Nurse None', 'login': 'scope_nurse_none',
            'group_ids': [(6, 0, cls.g_nurse.ids)],
            'catchment_province_id': False,
        })
        cls.owner = Users.create({
            'name': 'Scope Owner A', 'login': 'scope_owner_a',
            'group_ids': [(6, 0, cls.g_owner.ids)],
            'catchment_province_id': cls.area_a.id,
        })
        cls.owner_no_area = Users.create({
            'name': 'Scope Owner None', 'login': 'scope_owner_none',
            'group_ids': [(6, 0, cls.g_owner.ids)],
            'catchment_province_id': False,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _search_arch(self, user, model='res.partner'):
        arch = self.env[model].with_user(user).get_view(view_type='search')['arch']
        return etree.fromstring(arch)

    def _filter_names(self, tree):
        return {n.get('name') for n in tree.xpath('//filter') if n.get('name')}

    def _domain_of(self, tree, name):
        nodes = tree.xpath('//filter[@name="%s"]' % name)
        return nodes[0].get('domain') if nodes else None

    # ------------------------------------------------------------------
    # the facet
    # ------------------------------------------------------------------
    def test_scoped_user_gets_no_catchment_search_ui_at_all(self):
        """Test 1 + 2: no other area is reachable anywhere in a scoped user's
        search UI — and neither is their own, because the scope is a domain the
        sidebar ANDs in rather than a facet they could clear."""
        tree = self._search_arch(self.nurse)
        names = self._filter_names(tree)

        self.assertNotIn('catchment_mine', names,
                         'a removable facet is not the enforcement seam')
        self.assertNotIn('catchment_p%s' % self.area_b.id, names)
        self.assertNotIn('Scope Test Area B', etree.tostring(tree, encoding='unicode'))
        # No searchable field either — it would autocomplete over every area.
        self.assertFalse(
            tree.xpath('//field[@name="catchment_province_id"]'),
            'a scoped user must not get the catchment search field')

    def test_owner_gets_every_area(self):
        """Test 4: the owner keeps a 'mine' filter to default onto, plus one
        filter per other area to switch to, plus the searchable field."""
        tree = self._search_arch(self.owner)
        names = self._filter_names(tree)

        self.assertIn('catchment_mine', names)
        self.assertIn('catchment_p%s' % self.area_b.id, names)
        self.assertTrue(tree.xpath('//field[@name="catchment_province_id"]'))
        # Their own area is offered once, as "mine" — not twice.
        self.assertNotIn('catchment_p%s' % self.area_a.id, names)

    def test_scoped_user_without_an_area_gets_no_search_ui_either(self):
        """Test 6: fail-closed is carried by the sidebar domain ([(0,'=',1)])
        and by the record rules — never by something the user can clear."""
        tree = self._search_arch(self.nurse_no_area)
        self.assertNotIn('catchment_mine', self._filter_names(tree))
        self.assertFalse(tree.xpath('//field[@name="catchment_province_id"]'))

    def test_owner_without_an_area_is_not_pinned(self):
        """An owner with no area set must see everything, not nothing — so no
        'mine' filter exists for the sidebar default to land on."""
        tree = self._search_arch(self.owner_no_area)
        names = self._filter_names(tree)
        self.assertNotIn('catchment_mine', names)
        self.assertIn('catchment_p%s' % self.area_a.id, names)

    def test_model_without_a_catchment_field_is_untouched(self):
        """Test 10: reference data gets no facet at all."""
        tree = self._search_arch(self.nurse, model='res.currency')
        self.assertNotIn('catchment_mine', self._filter_names(tree))

    def test_non_search_views_are_untouched(self):
        arch = self.env['res.partner'].with_user(self.nurse).get_view(
            view_type='form')['arch']
        self.assertNotIn('catchment_mine', arch)

    def test_injection_is_idempotent(self):
        """Two consecutive fetches must not stack two copies of the filter."""
        tree = self._search_arch(self.owner)
        self.assertEqual(
            len(tree.xpath('//filter[@name="catchment_mine"]')), 1)

    def test_sidebar_reports_the_field_to_scope_by(self):
        """The sidebar builds its domain from the field name the server gives
        it, which is not always `catchment_province_id` — hr.employee stores
        its area as staff_catchment_province_id."""
        if 'cms.sidebar.item' not in self.env:
            self.skipTest('health_cms_sidebar not installed')
        Item = self.env['cms.sidebar.item']
        self.assertEqual(
            Item._catchment_scoped_action('health_fieldservice.action_ops_booking_list_native'),
            'catchment_province_id')
        self.assertEqual(
            Item._catchment_scoped_action('health_landing.action_admin_staff'),
            'staff_catchment_province_id')
        # Reference data has no area and must come back False, so the sidebar
        # adds no domain at all.
        self.assertFalse(
            Item._catchment_scoped_action('health_fhir_terminology.action_medical_code'))

    # ------------------------------------------------------------------
    # the boundary
    # ------------------------------------------------------------------
    def test_removing_the_facet_does_not_widen_access(self):
        """Test 3 — THE security assertion. The facet is a signal; the record
        rule is the boundary. Querying with no domain at all must still not
        return another area's patients."""
        Partner = self.env['res.partner']
        p_a = Partner.create({
            'name': 'Scope Patient A', 'is_patient': True,
            'catchment_province_id': self.area_a.id})
        p_b = Partner.create({
            'name': 'Scope Patient B', 'is_patient': True,
            'catchment_province_id': self.area_b.id})

        visible = Partner.with_user(self.nurse).search(
            [('id', 'in', (p_a + p_b).ids)])
        self.assertIn(p_a, visible)
        self.assertNotIn(p_b, visible, 'record rule leaked another area')

    def test_a_permissive_group_rule_cannot_or_away_the_catchment(self):
        """THE hardening assertion.

        Odoo ORs every group rule matching any group the user holds. Before the
        global rules, a scoped user who also held the stock Sales group
        "User: All Documents" — whose rule is [(1,'=',1)] — saw every lead in
        the company; measured on this database, 17 models leaked that way and a
        Hà Nội doctor could read 150 Ho Chi Minh City patients.

        A global rule is AND-ed in and cannot be OR-ed away. This test gives a
        nurse exactly that kind of blanket rule and proves it no longer helps.
        """
        Partner = self.env['res.partner']
        mine = Partner.create({
            'name': 'Hardening Mine', 'is_patient': True,
            'catchment_province_id': self.area_a.id})
        theirs = Partner.create({
            'name': 'Hardening Theirs', 'is_patient': True,
            'catchment_province_id': self.area_b.id})
        # NOT a patient: health_base refuses to create one without an area
        # ("Catchment Province is required for patients"), so the realistic
        # area-less partner is an ordinary contact — a supplier, a company, a
        # user's own partner. Those are the bulk of the 256 area-less rows here
        # and they must stay visible to everyone.
        unassigned = Partner.create({'name': 'Hardening Unassigned'})

        blanket = self.env['res.groups'].create({'name': 'Blanket Read All'})
        self.env['ir.rule'].create({
            'name': 'Blanket: every partner',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'domain_force': "[(1, '=', 1)]",
            'groups': [(6, 0, blanket.ids)],
            'perm_read': True,
        })
        self.nurse.write({'group_ids': [(4, blanket.id)]})
        self.nurse.env.invalidate_all()

        visible = Partner.with_user(self.nurse).search(
            [('id', 'in', (mine + theirs + unassigned).ids)])
        self.assertIn(mine, visible)
        self.assertIn(unassigned, visible,
                      'records with no area belong to nobody and stay visible')
        self.assertNotIn(theirs, visible,
                         'a blanket [(1,=,1)] rule must not reach another area')

    def test_owner_and_non_staff_are_untouched_by_the_global_rule(self):
        """The global rule keys off `catchment_enforced`, so it has to leave
        owners and everyone outside healthcare completely alone."""
        self.assertTrue(self.nurse.catchment_enforced)
        self.assertFalse(self.owner.catchment_enforced)

        outsider = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Scope Outsider', 'login': 'scope_outsider',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.assertFalse(outsider.catchment_enforced,
                         'a non-healthcare internal user must not be scoped')

        Partner = self.env['res.partner']
        theirs = Partner.create({
            'name': 'Hardening Owner Sees', 'is_patient': True,
            'catchment_province_id': self.area_b.id})
        self.assertIn(theirs,
                      Partner.with_user(self.owner).search([('id', '=', theirs.id)]))

    def test_province_dropdown_is_scoped(self):
        """Test 11: a scoped user cannot pick another area on a form."""
        Province = self.env['health.catchment.province']
        visible = Province.with_user(self.nurse).search(
            [('id', 'in', (self.area_a + self.area_b).ids)])
        self.assertEqual(visible, self.area_a)

        with self.assertRaises(AccessError):
            Province.with_user(self.nurse).browse(self.area_b.id).name

    def test_owner_and_admin_are_not_pinned_by_the_province_rule(self):
        """The bypass rules matter: owner implies admin implies manager, and
        manager is in the scoped list, so without them an owner would be
        pinned to one province by their own inherited groups."""
        Province = self.env['health.catchment.province']
        both = (self.area_a + self.area_b)
        self.assertEqual(
            Province.with_user(self.owner).search([('id', 'in', both.ids)]),
            both)

        admin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Scope Admin', 'login': 'scope_admin',
            'group_ids': [(6, 0, self.env.ref(
                'health_base.group_healthcare_admin').ids)],
            'catchment_province_id': self.area_a.id,
        })
        self.assertEqual(
            Province.with_user(admin).search([('id', 'in', both.ids)]), both)

    def test_user_without_an_area_can_still_read_provinces(self):
        """60 of 70 live accounts have no area. Blocking province reads for
        them would raise AccessError on every list that renders somebody
        else's province, while hiding nothing they can already reach."""
        Province = self.env['health.catchment.province']
        both = (self.area_a + self.area_b)
        self.assertEqual(
            Province.with_user(self.nurse_no_area).search(
                [('id', 'in', both.ids)]),
            both)

    # ------------------------------------------------------------------
    # the sidebar payload
    # ------------------------------------------------------------------
    def test_scope_info_hides_other_areas_from_scoped_users(self):
        info = self.env['res.users'].with_user(self.nurse)._catchment_scope_info()
        self.assertFalse(info['can_switch'])
        self.assertEqual(info['options'], [],
                         'the sidebar must not be handed another area to draw')
        self.assertEqual(info['current_id'], self.area_a.id)

        info = self.env['res.users'].with_user(self.owner)._catchment_scope_info()
        self.assertTrue(info['can_switch'])
        option_ids = [o['id'] for o in info['options']]
        self.assertIn(self.area_b.id, option_ids)
        # Their own area is the picker's first entry ("My area (X)"), so it must
        # not also appear in the list below it.
        self.assertNotIn(self.area_a.id, option_ids)
