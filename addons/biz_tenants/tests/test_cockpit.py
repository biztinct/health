# -*- coding: utf-8 -*-
"""The parts of the cockpit that a database can reach: the guards, the
registries, and the two promises that cannot be proved any other way.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import tenants_common as common


@tagged('post_install', '-at_install')
class TestGuard(TransactionCase):
    """This is the platform owner's screen, and the gate is the one that owns
    the machine — a customer's own administrator deliberately does not hold it
    (the two-ring rule), and that is what makes it the right gate."""

    def setUp(self):
        super().setUp()
        self.plain = self.env['res.users'].sudo().create({
            'name': 'A colleague', 'login': 'bzt_plain_colleague',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_a_colleague_is_refused_every_door(self):
        service = self.env['biz.tenants'].with_user(self.plain)
        for method, args in (('get_fleet', []),
                             ('sync_report', []),
                             ('check_slug', ['x']),
                             ('release_list', [])):
            with self.assertRaises(AccessError, msg=method):
                getattr(service, method)(*args)

    def test_the_administrator_is_let_through(self):
        self.assertIsInstance(self.env['biz.tenants'].get_fleet(), dict)


@tagged('post_install', '-at_install')
class TestRegistries(TransactionCase):
    """Everything product-shaped arrives through a registration, and every
    reader takes `env` as an argument (ACCESS F4 / ledger H6) — one registry is
    loaded once per process and serves every database on this machine."""

    def setUp(self):
        super().setUp()
        self._never = dict(common.NEVER)
        self._prefixes = list(common.NEVER_PREFIXES)
        self._meters = list(common.METERS)
        self.addCleanup(self._restore)

    def _restore(self):
        common.NEVER.clear()
        common.NEVER.update(self._never)
        common.NEVER_PREFIXES[:] = self._prefixes
        common.METERS[:] = self._meters

    def test_the_cockpit_is_on_its_own_never_list_and_cannot_be_taken_off(self):
        self.assertTrue(common.is_never('biz_tenants'))
        self.assertIn('biz_tenants', common.never_list())

    def test_every_held_back_module_has_a_reason_written_for_the_owner(self):
        for name, reason in common.never_list().items():
            self.assertTrue(reason, '%s has no reason' % name)
            self.assertGreater(len(reason), 40,
                               '%s has a reason nobody could act on' % name)

    def test_a_setting_beats_the_registered_default(self):
        common.register_platform({'apex': 'nothing.example'})
        self.env['ir.config_parameter'].sudo().set_param(
            common.P_APEX, 'something.example')
        self.assertEqual(common.apex(self.env), 'something.example')

    def test_a_setting_that_is_empty_is_told_apart_from_one_that_is_absent(self):
        """Ledger F24, on the one setting where the difference is real."""
        Param = self.env['ir.config_parameter'].sudo()
        Param.search([('key', '=', common.P_HEALTH_IGNORE)]).unlink()
        self.assertIsNone(common.param_row(self.env, common.P_HEALTH_IGNORE))
        Param.create({'key': common.P_HEALTH_IGNORE, 'value': ''})
        self.assertEqual(common.param_row(self.env, common.P_HEALTH_IGNORE), '')

    def test_the_ignore_list_never_becomes_a_filter_that_filters_nothing(self):
        """A list parsed out of `get_param`'s False becomes `["False"]`, which
        is a filter that filters nothing and looks exactly like a working
        one."""
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', common.P_HEALTH_IGNORE)]).unlink()
        self.assertEqual(common.health_ignore(self.env), [])
        self.env['ir.config_parameter'].sudo().create(
            {'key': common.P_HEALTH_IGNORE, 'value': 'licence\n  \nNOISE'})
        self.assertEqual(common.health_ignore(self.env), ['licence', 'noise'])

    def test_a_meter_needs_a_key_and_a_query(self):
        with self.assertRaises(ValueError):
            common.register_meter({'label': 'no key'})

    def test_registering_the_same_meter_twice_keeps_the_first(self):
        common.register_meter({'key': 'zz', 'sql': 'SELECT 1', 'label': 'One'})
        common.register_meter({'key': 'zz', 'sql': 'SELECT 2', 'label': 'Two'})
        rows = [m for m in common.meters() if m['key'] == 'zz']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['label'], 'One')

    def test_a_customer_s_administrator_may_never_hold_the_keys(self):
        self.assertEqual(common.PLATFORM_GROUP_XMLIDS,
                         ('base.group_system', 'base.group_erp_manager'))


@tagged('post_install', '-at_install')
class TestCrossDatabaseWrite(TransactionCase):
    """⚠ THE ONE PROMISE THAT CANNOT BE PROVED ANY OTHER WAY (ledger F56).

    A commit on another database clears the cache of THIS process's copy of
    that registry and stops there. This machine runs two workers and a gevent
    process, so without `signal_changes()` the platform says a customer has
    been told something, their database agrees in SQL, and two-thirds of their
    people go on seeing yesterday's answer.
    """

    def test_the_environment_signals_after_it_commits(self):
        """⚠ AND THE PATCH IS ON THE INSTANCE, NOT THE CLASS (ledger F29).

        A test cursor REFUSES to commit — the framework raises rather than let
        a test leave anything behind. `patch.object(type(cr), 'commit', …)`
        does nothing at all to it; only patching the object itself gets a body
        that commits per customer under test.
        """
        service = self.env['biz.tenants']
        calls = []
        test_cursor = self.env.cr

        class FakeCursor:
            def __enter__(self_inner):
                return test_cursor

            def __exit__(self_inner, *a):
                return False

        class FakeRegistry:
            def cursor(self_inner):
                return FakeCursor()

            def signal_changes(self_inner):
                calls.append('signalled')

        with patch('odoo.addons.biz_tenants.models.service.Registry',
                   return_value=FakeRegistry()), \
             patch.object(test_cursor, 'commit',
                          lambda: calls.append('committed')):
            with service._tenant_env('anything'):
                pass
        self.assertEqual(calls, ['committed', 'signalled'],
                         'it must commit and then signal, in that order')


@tagged('post_install', '-at_install')
class TestSkippedCheck(TransactionCase):
    """Ledger F7 — an honest "could not tell" beats a green nought."""

    def test_it_answers_minus_one_when_there_is_nothing_to_compare_against(self):
        service = self.env['biz.tenants']

        class Empty:
            _init_modules = set()

        with patch.object(type(service), '_installed_on',
                          return_value={'a': '1.0'}), \
             patch('odoo.addons.biz_tenants.models.service.Registry',
                   return_value=Empty()):
            count, names = service._skipped_on('anything')
        self.assertEqual(count, -1)
        self.assertEqual(names, [])

    def test_it_answers_minus_one_when_the_attribute_is_missing_entirely(self):
        service = self.env['biz.tenants']

        class NoAttribute:
            pass

        with patch.object(type(service), '_installed_on',
                          return_value={'a': '1.0'}), \
             patch('odoo.addons.biz_tenants.models.service.Registry',
                   return_value=NoAttribute()):
            count, _names = service._skipped_on('anything')
        self.assertEqual(count, -1)

    def test_it_names_what_did_not_load_when_it_can_tell(self):
        service = self.env['biz.tenants']

        class Loaded:
            _init_modules = {'a'}

        with patch.object(type(service), '_installed_on',
                          return_value={'a': '1.0', 'b': '1.0'}), \
             patch('odoo.addons.biz_tenants.models.service.Registry',
                   return_value=Loaded()):
            count, names = service._skipped_on('anything')
        self.assertEqual((count, names), (1, ['b']))


@tagged('post_install', '-at_install')
class TestRefusals(TransactionCase):

    def test_the_three_targets_and_nothing_else(self):
        """Ledger F12. A practice copy is the only reason a bare name is
        accepted at all."""
        service = self.env['biz.tenants']
        tenant = self.env['biz.tenant'].sudo().create(
            {'name': 'Probe', 'slug': 'bztprobe'})
        db, _label, rec, is_template = service._resolve_target(tenant.id)
        self.assertEqual((db, rec.id, is_template),
                         ('bztprobe', tenant.id, False))
        db, _label, rec, is_template = service._resolve_target('bztprobe-staging')
        self.assertEqual((db, rec, is_template),
                         ('bztprobe-staging', None, False))
        for bad in ('somethingelse', 'bztother-staging', ''):
            with self.assertRaises(UserError, msg=bad):
                service._resolve_target(bad)

    def test_the_platform_s_own_system_is_refused_by_name(self):
        with self.assertRaises(UserError):
            self.env['biz.tenants']._resolve_target(self.env.cr.dbname)

    def test_a_message_is_never_sent_to_the_platform_itself(self):
        with self.assertRaises(UserError):
            self.env['biz.tenants'].push_settings(self.env.cr.dbname, {'a': 'b'})

    def test_the_never_list_is_re_asked_of_the_literal_list_to_be_written(self):
        """⚠ RAIL R2. Every earlier check is a check of something ELSE; this
        one asks about the exact names that are about to run. The assertion is
        on the SOURCE, because the guard's whole value is that it sits between
        the plan and the install call and no test can stand in that gap on a
        live machine."""
        import inspect

        from odoo.addons.biz_tenants.models import service as service_module
        src = inspect.getsource(service_module.BizTenants.sync_bring_in_step)
        guard = src.index('common.is_never(n)')
        install = src.index('button_immediate_install')
        self.assertLess(guard, install,
                        'the never-list must be re-asked BEFORE the install')
        self.assertIn('Refusing to put', src)

    def test_a_customer_that_has_been_closed_down_is_refused(self):
        service = self.env['biz.tenants']
        tenant = self.env['biz.tenant'].sudo().create(
            {'name': 'Closed', 'slug': 'bztclosed',
             'state': 'decommissioned'})
        with self.assertRaises(UserError):
            service.sync_bring_in_step(tenant.id, dry_run=True)

    def test_provisioning_a_short_name_already_in_use_is_refused(self):
        self.env['biz.tenant'].sudo().create(
            {'name': 'First', 'slug': 'bzttaken'})
        res = self.env['biz.tenants'].check_slug('bzttaken')
        self.assertFalse(res['ok'])
        with self.assertRaises(UserError):
            self.env['biz.tenants'].provision_start({
                'name': 'Second', 'slug': 'bzttaken',
                'contact_email': 'x@example.com'})

    def test_provisioning_with_no_room_on_the_machine_is_refused(self):
        """Patched at the reading, so the refusal itself is the thing under
        test rather than the machine's mood on the day.

        ⚠ THE QUESTION CHANGED IN H4b, AND SO DID THIS TEST. The first version
        asked "is there 400 MB free" — a fair question with no relationship at
        all to how much of it another customer would need. The guard now asks
        the question that matters: is there room for ONE MORE, given what one
        customer is allowed and what has to stay free for the rest of the
        machine.
        """
        service = self.env['biz.tenants']
        with patch.object(type(service), '_memory_reading',
                          return_value={'total_mb': 1910, 'available_mb': 410}):
            preview = service.provision_preview({
                'name': 'Too big', 'slug': 'bztmem',
                'contact_email': 'x@example.com'})
        self.assertFalse(preview['ok'])
        self.assertTrue(any('no room' in p.lower()
                            for p in preview['problems']),
                        preview['problems'])


@tagged('post_install', '-at_install')
class TestTenantRecord(TransactionCase):

    def test_the_log_is_appended_to_and_never_rewritten(self):
        tenant = self.env['biz.tenant'].sudo().create(
            {'name': 'Logger', 'slug': 'bztlog'})
        tenant.log('first thing')
        tenant.log('second thing', 'warn')
        lines = [l for l in tenant.provision_log.split('\n') if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn('first thing', lines[0])
        self.assertIn('NOTE', lines[1])

    def test_two_customers_cannot_share_a_short_name(self):
        """⚠ AND THE CONSTRAINT HAS TO REALLY EXIST IN THE DATABASE.

        On this framework the old `_sql_constraints` LIST form is accepted and
        never applied: `pg_constraint` simply has nothing in it, and two
        records could point at ONE system. The model uses `models.Constraint`,
        and this asserts the row in the catalogue as well as the refusal —
        because a refusal could also come from somewhere else and look right.
        """
        self.env.cr.execute(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conrelid = 'biz_tenant'::regclass AND contype = 'u'")
        self.assertGreaterEqual(
            self.env.cr.fetchone()[0], 1,
            'there is no unique constraint on the customer table at all')
        self.env['biz.tenant'].sudo().create({'name': 'One', 'slug': 'bztdup'})
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['biz.tenant'].sudo().create(
                    {'name': 'Two', 'slug': 'bztdup'})
                self.env.flush_all()

    def test_a_meter_reading_replaces_the_earlier_one_for_the_same_period(self):
        tenant = self.env['biz.tenant'].sudo().create(
            {'name': 'Metered', 'slug': 'bztmeter'})
        Meter = self.env['biz.tenant.meter'].sudo()
        Meter.record(tenant, {'key': 'visits', 'value': 3}, '2026-09-01',
                     '2026-09-30')
        Meter.record(tenant, {'key': 'visits', 'value': 5}, '2026-09-01',
                     '2026-09-30')
        rows = Meter.search([('tenant_id', '=', tenant.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.value, 5)


@tagged('post_install', '-at_install')
class TestContract(TransactionCase):
    """The platform and the link hold two copies of one set of setting names,
    deliberately — this module has to work on a system where the link is not
    installed. Two copies of a contract are only honest if something asserts
    they agree."""

    def test_both_sides_spell_the_settings_the_same_way(self):
        from odoo.addons.biz_tenancy.models import tenancy
        pairs = (
            (common.T_RELEASE, tenancy.P_RELEASE),
            (common.T_RELEASE_NOTES, tenancy.P_RELEASE_NOTES),
            (common.T_RELEASE_AT, tenancy.P_RELEASE_AT),
            (common.T_RELEASES, tenancy.P_RELEASES),
            (common.T_NOTICE, tenancy.P_NOTICE),
            (common.T_NOTICE_KIND, tenancy.P_NOTICE_KIND),
            (common.T_NOTICE_FROM, tenancy.P_NOTICE_FROM),
            (common.T_NOTICE_TO, tenancy.P_NOTICE_TO),
            (common.T_PUSHED_AT, tenancy.P_PUSHED_AT),
            (common.T_PLATFORM_URL, tenancy.P_PLATFORM_URL),
            (common.T_SUPPORT_EMAIL, tenancy.P_SUPPORT_EMAIL),
            (common.T_SLUG, tenancy.P_SLUG),
        )
        for ours, theirs in pairs:
            self.assertEqual(ours, theirs)


@tagged('post_install', '-at_install')
class TestReopen(TransactionCase):
    """A customer whose system had to be rebuilt is not a dead end (SAAS H4c).

    ⚠ THE HOLE THIS CLOSES. Closing a customer down leaves their record
    holding their short name, and the new-customer screen refuses a short name
    in use — so a customer could be closed and never created again, and the
    only move left was to edit the database by hand. That is exactly the state
    ledger H73 says this screen must not be able to reach.
    """

    def setUp(self):
        super().setUp()
        self.service = self.env['biz.tenants']
        self.tenant = self.env['biz.tenant'].create({
            'name': 'A closed customer', 'slug': 'reprobe',
            'state': 'decommissioned', 'provision_step': 'done',
            'health_state': 'down', 'http_status': 500,
        })

    def test_their_short_name_is_still_theirs_and_still_refused(self):
        """The refusal is right — this is why the way back has to exist."""
        with patch.object(type(self.service), '_all_databases',
                          lambda self: ['carejiox']):
            self.assertFalse(self.service.check_slug('reprobe')['ok'])

    def test_building_it_again_puts_them_back_at_the_start(self):
        with patch.object(type(self.service), '_db_exists',
                          lambda self, name: False):
            res = self.service.reopen(self.tenant.id, 'reprobe')
        self.assertTrue(res['ok'])
        self.assertEqual(self.tenant.state, 'draft')
        self.assertFalse(self.tenant.provision_step)
        self.assertEqual(self.tenant.health_state, 'unknown')
        self.assertEqual(self.tenant.http_status, 0)

    def test_the_same_record_keeps_their_copies_and_their_log(self):
        """A second record with the same short name would put a customer's
        history in two places and their address in one."""
        self.env['biz.tenant.backup'].create({
            'tenant_id': self.tenant.id, 'kind': 'final',
            'path': '/odoo/backups/tenants/reprobe/final.dump', 'state': 'done',
        })
        before = self.tenant.provision_log or ''
        with patch.object(type(self.service), '_db_exists',
                          lambda self, name: False):
            res = self.service.reopen(self.tenant.id, 'reprobe')
        self.assertEqual(len(self.tenant.backup_ids), 1)
        self.assertIn('final.dump', res['kept_backup'])
        self.assertGreater(len(self.tenant.provision_log or ''), len(before))
        self.assertIn('set up again', self.tenant.provision_log)

    def test_it_refuses_while_anything_of_that_name_is_still_on_the_machine(self):
        """That is the one state where "build it again" would mean
        "overwrite what is there"."""
        with patch.object(type(self.service), '_db_exists',
                          lambda self, name: True):
            try:
                self.service.reopen(self.tenant.id, 'reprobe')
            except UserError as e:
                self.assertIn('still called', str(e))
            else:
                self.fail('it agreed to build over a system that is there')
        self.assertEqual(self.tenant.state, 'decommissioned')

    def test_a_customer_who_is_live_is_refused_by_name(self):
        self.tenant.write({'state': 'live'})
        try:
            self.service.reopen(self.tenant.id, 'reprobe')
        except UserError as e:
            self.assertIn('has not been closed down', str(e))
        else:
            self.fail('a live customer was put back to the start')

    def test_the_short_name_has_to_be_typed(self):
        try:
            self.service.reopen(self.tenant.id, 'something else')
        except UserError as e:
            self.assertIn('reprobe', str(e))
        else:
            self.fail('it rebuilt without the name being typed')
        self.assertEqual(self.tenant.state, 'decommissioned')
