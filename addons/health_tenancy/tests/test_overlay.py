# -*- coding: utf-8 -*-
"""What the overlay promises the two generic modules, and the two doors.

The whole of this module is five registrations and a hook, so the tests are
about exactly two things: that the five facts arrived, and that neither door is
a dead end.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_tenancy.hooks import DOORS, wire_doors
from odoo.addons.health_tenancy.models.registrations import METERS, NEVER


def _cockpit():
    """The registries, or None on a system that has no cockpit."""
    try:
        from odoo.addons.biz_tenants.models import tenants_common as common
    except ImportError:
        return None
    return common


@tagged('post_install', '-at_install')
class TestRegistrations(TransactionCase):

    def setUp(self):
        super().setUp()
        self.common = _cockpit()
        if not self.common:
            self.skipTest("the customers screen is not on this system")

    def test_the_product_named_itself(self):
        got = self.common.platform_defaults()
        self.assertEqual(got['brand'], 'Viet Uc Care')
        self.assertEqual(got['apex'], 'carejiox.com')
        self.assertEqual(got['backend_prefix'], '/bizapp')
        self.assertEqual(got['template_db'], 'carejiox_template')

    def test_every_address_is_a_setting_and_the_registration_is_the_default(self):
        """The platform's own address has already changed once in the middle of
        this programme and took seventeen written-down copies of itself with
        it."""
        self.env['ir.config_parameter'].sudo().set_param(
            self.common.P_APEX, 'moved.example')
        self.assertEqual(self.common.apex(self.env), 'moved.example')

    def test_the_never_list_arrived_with_a_reason_on_every_entry(self):
        registered = self.common.never_list()
        for name in NEVER:
            self.assertIn(name, registered)
            self.assertTrue(self.common.is_never(name))
            self.assertGreater(len(registered[name]), 40,
                               '%s has a reason nobody could act on' % name)

    def test_the_prefix_rail_refuses_a_platform_module_nobody_has_listed(self):
        self.assertTrue(self.common.is_never('biz_platform_anything'))

    def test_the_web_lead_funnel_is_honestly_NOT_on_the_never_list(self):
        """⚠ Ledger H57, asserted rather than hoped for. `health_learn` and
        `health_cms_coverage` both DECLARE `health_web_leads` as a dependency,
        so the framework pulls it in whatever a list says. Every new customer
        gets the web-lead screens, inert until somebody connects a website.
        This test exists so that the day somebody breaks those dependencies,
        it fails and reminds them to put it on the list."""
        self.assertNotIn('health_web_leads', self.common.never_list())
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'health_web_leads')], limit=1)
        if module:
            dependants = self.env['ir.module.module.dependency'].sudo().search(
                [('name', '=', 'health_web_leads')]).mapped('module_id.name')
            self.assertTrue(
                set(dependants) & {'health_learn', 'health_cms_coverage'},
                'nothing depends on the lead funnel any more — it can now go '
                'on the never-list, and this test is the reminder')

    def test_all_four_numbers_are_registered(self):
        keys = {m['key'] for m in self.common.meters()}
        for spec in METERS:
            self.assertIn(spec['key'], keys)

    def test_every_number_guards_on_its_own_table_and_column(self):
        """A customer who has not been brought in step does not have every
        table, and one number that raises must not take the other three with
        it."""
        for spec in METERS:
            self.assertTrue(spec['table_guard'], spec['key'])
            self.assertTrue(spec['column_guard'], spec['key'])
            self.assertIn('.', spec['column_guard'], spec['key'])

    def test_every_number_has_a_label_a_person_recognises(self):
        for spec in METERS:
            self.assertTrue(spec['label'])
            self.assertNotEqual(spec['label'], spec['key'])

    def test_the_visits_number_is_counted_on_the_day_it_was_FOR(self):
        """The evidence is in the module's own comment, and it is this: of 975
        completed visits on the platform's own system, `booking_date` is filled
        on all of them and answers the WRONG question (the day it was booked),
        `actual_end_datetime` on 870, and `scheduled_date` — the day the visit
        was for — on 971."""
        spec = next(m for m in METERS if m['key'] == 'visits')
        self.assertIn('scheduled_date', spec['sql'])
        self.assertNotIn('booking_date', spec['sql'])
        self.assertIn('%(start)s', spec['sql'])
        self.assertIn('%(end)s', spec['sql'])

    def test_the_customer_administrator_is_named_by_id_never_by_name(self):
        spec = self.common.tenant_admin()
        self.assertEqual(spec['role_xmlid'], 'health_access.role_owner')
        self.assertIn('health_access.group_clinic_admin', spec['group_xmlids'])

    def test_the_role_the_administrator_holds_carries_none_of_the_keys(self):
        """⚠ THE TWO-RING RULE. Provisioning refuses to finish rather than hand
        over an account that still holds the system administrator permission,
        so a role that carried it would make every customer un-creatable — and
        the moment to find that out is here."""
        role = self.env.ref('health_access.role_owner',
                            raise_if_not_found=False)
        self.assertTrue(role, 'the Owner role is not on this system')
        forbidden = set()
        for xmlid in self.common.PLATFORM_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                forbidden.add(group.id)
        reach = set()
        for group in role.group_ids:
            reach |= set(group.all_implied_ids.ids) | {group.id}
        self.assertFalse(forbidden & reach,
                         'the Owner role reaches the keys to this machine')

    def test_the_administrator_lands_somewhere_that_exists(self):
        xmlid = self.common.home_action()
        self.assertEqual(xmlid, 'health_landing.action_admin_dashboard')
        self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                        'the home screen a new administrator opens on is not '
                        'on this system')


@tagged('post_install', '-at_install')
class TestDoors(TransactionCase):
    """Neither door may be a dead end: an entry that opens nothing is worse
    than an absence, because somebody clicks it and gets an error."""

    def test_every_door_points_at_an_action_or_is_switched_off(self):
        wire_doors(self.env)
        for door in DOORS:
            item = self.env.ref(door['xmlid'], raise_if_not_found=False)
            self.assertTrue(item, door['xmlid'])
            resolves = bool(self.env.ref(door['action'],
                                         raise_if_not_found=False))
            self.assertEqual(
                item.active, resolves,
                '%s is %s and its action %s'
                % (door['xmlid'], 'on' if item.active else 'off',
                   'resolves' if resolves else 'does not resolve'))

    def test_the_about_door_is_open_to_the_people_who_run_the_place(self):
        wire_doors(self.env)
        item = self.env.ref('health_tenancy.item_admin_about')
        names = set(item.biz_role_ids.mapped('name'))
        self.assertIn('Owner', names)
        self.assertIn('Admin', names)

    def test_the_customers_door_is_open_to_the_owner_alone(self):
        wire_doors(self.env)
        item = self.env.ref('health_tenancy.item_admin_customers')
        names = set(item.biz_role_ids.mapped('name'))
        self.assertEqual(names, {'Owner'})

    def test_wiring_the_doors_twice_changes_nothing_the_second_time(self):
        wire_doors(self.env)
        second = wire_doors(self.env)
        self.assertEqual(second['gated'], [])
        self.assertEqual(second['switched_on'], [])
        self.assertEqual(second['switched_off'], [])

    def test_both_doors_sit_under_the_administration_section(self):
        section = self.env.ref('health_cms_sidebar.section_admin')
        for door in DOORS:
            item = self.env.ref(door['xmlid'], raise_if_not_found=False)
            if item:
                self.assertEqual(item.section_id, section, door['xmlid'])


@tagged('post_install', '-at_install')
class TestLoadsWithoutTheCockpit(TransactionCase):
    """This module ships to EVERY customer's system, and the cockpit ships to
    none of them. So the registrations have to be skippable rather than
    fatal."""

    def test_the_registration_says_whether_it_found_the_cockpit(self):
        from odoo.addons.health_tenancy.models import registrations
        self.assertIn(registrations.REGISTERED, (True, False))

    def test_the_about_screen_is_reachable_on_any_system(self):
        self.assertTrue(
            self.env.ref('biz_tenancy.action_biz_tenancy_about',
                         raise_if_not_found=False),
            'the About screen has to exist wherever this module is installed')
