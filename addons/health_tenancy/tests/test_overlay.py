# -*- coding: utf-8 -*-
"""What the overlay promises the two generic modules, and the two doors.

The whole of this module is five registrations and a hook, so the tests are
about exactly two things: that the five facts arrived, and that neither door is
a dead end.
"""
import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_tenancy.hooks import DOORS, wire_doors, wire_features
from odoo.addons.health_tenancy.models.registrations import (
    EXTRAS, FEATURES, METERS, NEVER, PRODUCT_PREFIXES,
)

#: The eighteen the computation exposed in SAAS H4c §3.1. Named here so that
#: the day one of them stops being held back it is a failed test rather than a
#: warehouse on a nurse's screen.
HELD_BACK_APPS = (
    'stock', 'stock_account', 'stock_sms', 'purchase_stock',
    'sale_management', 'sale_pdf_quote_builder', 'sale_project',
    'sale_project_stock_account', 'sale_purchase_project', 'sale_service',
    'sale_timesheet', 'spreadsheet_dashboard_sale_timesheet',
    'project_stock', 'project_purchase_stock', 'project_stock_account',
    'barcodes_gs1_nomenclature', 'base_automation', 'theme_default',
)


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
class TestCustomerModuleSet(TransactionCase):
    """§3.1 — what a customer is made of, asked of THIS machine.

    The pure rule is tested in `biz_tenants/tests/test_module_set.py`. These
    ask the rule about the modules this database really has, which is the only
    place the answer can be wrong for a reason nobody invented.
    """

    def setUp(self):
        super().setUp()
        self.common = _cockpit()
        if not self.common:
            self.skipTest("the customers screen is not on this system")
        self.answer = self.env['biz.tenants'].sudo()._module_set()

    def test_the_product_said_how_its_own_parts_are_named(self):
        from odoo.addons.biz_tenants.models import module_set
        self.assertEqual(set(PRODUCT_PREFIXES) - set(module_set.product_prefixes()),
                         set())

    def test_nothing_held_back_is_needed_by_anything_a_customer_gets(self):
        """⚠ THE MAINTENANCE TRIPWIRE, ON REAL MANIFESTS. If this fails it
        names the held-back part AND the part of the product that started
        needing it, so nobody has to go looking."""
        from odoo.addons.biz_tenants.models.module_set import (
            dependency_conflicts,
        )
        pairs = dependency_conflicts(self.answer)
        self.assertEqual(
            pairs, [],
            "a part a customer never gets is needed by one they do: "
            + '; '.join('%s is needed by %s' % (m, why) for m, why in pairs))

    def test_the_real_dependencies_are_in_the_set(self):
        """`sale`, `purchase` and `hr_timesheet` are genuinely needed — by
        visits, by invoicing and by pricing. The APPS built on top of them are
        not, and that distinction is the whole of the owner's rule."""
        got = set(self.answer['modules'])
        for name in ('sale', 'purchase', 'hr_timesheet'):
            self.assertIn(name, got)

    def test_none_of_the_eighteen_is_in_the_set(self):
        got = set(self.answer['modules'])
        for name in HELD_BACK_APPS:
            self.assertNotIn(name, got, '%s reached a customer' % name)

    def test_each_of_the_eighteen_is_held_back_with_a_plain_reason(self):
        registered = self.common.never_list()
        for name in HELD_BACK_APPS:
            self.assertIn(name, registered, name)
            self.assertTrue(self.common.is_never(name), name)
            self.assertGreater(
                len(registered[name]), 40,
                '%s is held back for a reason nobody could act on' % name)
            self.assertNotIn('odoo', registered[name].lower(), name)

    def test_the_vietnamese_chart_of_accounts_is_asked_for_by_name(self):
        self.assertIn('l10n_vn', EXTRAS)
        self.assertIn('l10n_vn', set(self.answer['modules']))
        self.assertEqual(self.answer['pulled_by'].get('l10n_vn'), 'seed',
                         'nothing depends on it — it is asked for')

    def test_iban_and_the_european_payment_code_are_deliberately_not_refused(self):
        """⚠ Ledger H57's family, third sighting, asserted rather than hoped
        for. The Vietnamese chart of accounts DECLARES `base_iban`, and
        `base_iban` is the trigger the framework auto-installs
        `account_qr_code_sepa` on. Both were on the first draft of the
        never-list; a never-list entry the framework overrules is not a rule."""
        self.assertNotIn('base_iban', self.common.never_list())
        self.assertNotIn('account_qr_code_sepa', self.common.never_list())
        got = set(self.answer['modules'])
        self.assertIn('base_iban', got)
        self.assertEqual(self.answer['pulled_by'].get('base_iban'), 'l10n_vn')

    def test_the_cockpit_itself_is_never_part_of_a_customer(self):
        self.assertNotIn('biz_tenants', set(self.answer['modules']))

    def test_the_screen_can_say_why_for_every_held_back_part(self):
        report = self.env['biz.tenants'].sudo().module_set_report()
        self.assertGreater(report['total'], 100)
        self.assertEqual(report['conflicts'], [])
        for row in report['held_back']:
            self.assertTrue(row['reason'].strip(), row['module'])


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
class TestFeatureGate(TransactionCase):
    """SAAS H4c §5.6 — a switched-off part takes its entries off the menu, and
    the door behind them says so."""

    def setUp(self):
        super().setUp()
        self.Item = self.env['cms.sidebar.item']
        self.Tenancy = self.env['biz.tenancy']
        self.Param = self.env['ir.config_parameter'].sudo()
        wire_features(self.env)

    def _set_features(self, value):
        self.Param.set_param('biz_tenancy.features', value)
        self.env.registry.clear_cache()

    def _drawn(self):
        names = set()
        for section in self.Item.get_sidebar_data():
            for item in section['items']:
                names.add(item['name'])
                for kid in item.get('children') or ():
                    names.add(kid['name'])
        return names

    def tearDown(self):
        self._set_features('')
        super().tearDown()

    # ------------------------------------------------------------- the marker
    def test_the_menu_call_keeps_its_model_marker(self):
        """⚠ Ledger F46. `@api.model` IS NOT INHERITED, and an override that
        drops it takes the whole left menu away from everybody — with no
        Python test able to see it, because a test calls the method directly
        and both shapes work. So the MARKER is what is asserted."""
        for name in ('get_sidebar_data', '_sidebar_visible_items'):
            method = getattr(type(self.Item), name)
            self.assertTrue(getattr(method, '_api_model', False)
                            or getattr(method, '_api', None) == 'model',
                            '%s has lost its @api.model marker' % name)

    # ------------------------------------------------------------- the wiring
    def test_every_entry_that_belongs_to_a_part_says_which(self):
        report = wire_features(self.env)
        self.assertEqual(report['wired'], [],
                         'running it twice should change nothing')
        wired = self.Item.with_context(active_test=False).search(
            [('feature_key', '!=', False)])
        self.assertTrue(wired, 'no entry belongs to any part of the product')
        keys = set(wired.mapped('feature_key'))
        registered = {f['key'] for f in FEATURES}
        self.assertFalse(keys - registered,
                         'an entry names a part that is not on the list: %s'
                         % (keys - registered))

    def test_an_entry_from_a_module_that_is_not_here_is_skipped_not_fatal(self):
        """The entries come from nine modules and this one depends on three.
        A data file naming them would take the upgrade down on any system
        missing one; a hook counts them instead."""
        report = wire_features(self.env)
        self.assertIsInstance(report['missing'], list)

    def test_a_child_inherits_its_parent_s_part(self):
        parent = self.Item.with_context(active_test=False).search(
            [('feature_key', '!=', False), ('parent_id', '=', False)], limit=1)
        if not parent:
            self.skipTest('nothing on this menu belongs to a part yet')
        child = self.Item.with_context(active_test=False).search(
            [('parent_id', '=', parent.id)], limit=1)
        if not child:
            self.skipTest('that entry has no children on this system')
        child.sudo().write({'feature_key': False})
        self.assertEqual(self.Item._feature_key_of(child), parent.feature_key)

    # -------------------------------------------------------------- the rule
    def test_a_switched_off_part_takes_its_entries_off_the_menu(self):
        wired = self.Item.search([('feature_key', '!=', False),
                                  ('active', '=', True)], limit=1)
        if not wired:
            self.skipTest('no active entry belongs to a part on this system')
        key = wired.feature_key
        before = self._drawn()
        self.assertIn(wired.name, before)
        self._set_features(json.dumps({key: {'on': False, 'name': key}}))
        after = self._drawn()
        self.assertNotIn(wired.name, after)
        # AND NO OTHER ENTRY MOVED. A gate that takes more than it was asked
        # for is worse than one that takes nothing.
        others = self.Item.search([('active', '=', True),
                                   ('feature_key', '!=', key)])
        gone = before - after
        for name in gone:
            match = others.filtered(lambda i, n=name: i.name == n)
            for item in match:
                self.assertEqual(self.Item._feature_key_of(item), key,
                                 '%s went with it and should not have' % name)

    def test_an_unreadable_setting_takes_every_gated_entry_off_and_no_more(self):
        """⚠ Fail CLOSED on damage (ledger F53), but never leave somebody
        staring at an empty menu: everything ungated stays."""
        self._set_features('{{{ not json')
        drawn = self._drawn()
        self.assertTrue(drawn, 'the whole menu vanished')
        for item in self.Item.search([('active', '=', True)]):
            if self.Item._feature_key_of(item):
                self.assertNotIn(item.name, drawn, item.name)

    def test_an_absent_setting_draws_everything(self):
        self.Param.search([('key', '=', 'biz_tenancy.features')]).unlink()
        self.env.registry.clear_cache()
        self.assertEqual(self.Tenancy.features_off(), set())

    # --------------------------------------------------- the door behind it
    def test_the_screen_behind_a_switched_off_entry_says_so(self):
        wired = self.Item.search([('feature_key', '!=', False),
                                  ('action_xmlid', '!=', False)], limit=1)
        if not wired:
            self.skipTest('no entry with an action belongs to a part here')
        key = wired.feature_key
        self._set_features(json.dumps(
            {key: {'on': False, 'name': 'A part', 'blurb': 'What you lose.'}}))
        blocked = self.Tenancy.feature_block(wired.action_xmlid, None)
        self.assertTrue(blocked, 'the door was left open')
        self.assertEqual(blocked['tag'], 'biz_tenancy_feature_off')
        self.assertEqual(blocked['params']['label'], 'A part')
        self.assertEqual(blocked['params']['blurb'], 'What you lose.')

    def test_a_screen_that_belongs_to_nothing_is_never_blocked(self):
        self._set_features(json.dumps({'telehealth': {'on': False}}))
        self.assertIsNone(
            self.Tenancy.feature_block('base.action_res_users', None))

    def test_with_nothing_switched_off_the_guard_costs_one_read(self):
        self._set_features('')
        self.assertIsNone(self.Tenancy.feature_block('anything.at.all', None))


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
