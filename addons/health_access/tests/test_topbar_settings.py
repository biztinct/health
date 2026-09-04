# -*- coding: utf-8 -*-
"""⚠ THE TOP-BAR DECISION HAS TO REACH BOTH KINDS OF DATABASE (SAAS H4a §3.8).

THE FAULT THIS GUARDS, AND IT IS THE **A2 FAMILY**: a `post_init_hook` does not
fire on an upgrade, and a migration does not fire on an install. A decision
written in only one of them reaches only half the databases this product runs
on — and the half it misses is INVISIBLE, because both settings are read with a
default behind them and a missing row simply reads as `by_role`, which is the
opposite of what the owner decided. Every customer cloned from a blank system
in that state would show every nurse the whole application bar.

The data file writes both on a fresh install and is `noupdate="1"` on purpose,
so a clinic that changes its mind keeps its decision. The hook and the migration
are the other half.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_access.hooks import (
    TOPBAR_SETTINGS, ensure_topbar_settings,
)


@tagged('post_install', '-at_install')
class TestTopbarSettingsReachBothPaths(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Param = self.env['ir.config_parameter'].sudo()

    def _row(self, key):
        return self.Param.search([('key', '=', key)], limit=1)

    def test_this_database_carries_both_settings(self):
        """The install path, on whatever database the suite is running on."""
        for key, value in TOPBAR_SETTINGS.items():
            row = self._row(key)
            self.assertTrue(row, 'the setting %s is missing entirely' % key)
            if key == 'biz_access.topbar_mode':
                self.assertEqual(
                    row.value, value,
                    'the application bar is not restricted on this database')

    def test_a_database_with_neither_setting_gets_both(self):
        """The upgrade path, simulated by taking both rows away inside a
        transaction that is rolled back."""
        for key in TOPBAR_SETTINGS:
            self._row(key).unlink()
        written = ensure_topbar_settings(self.env)
        self.assertEqual(sorted(written), sorted(TOPBAR_SETTINGS))
        for key, value in TOPBAR_SETTINGS.items():
            self.assertEqual(self._row(key).value, value)

    def test_a_database_missing_only_one_gets_only_that_one(self):
        self._row('biz_access.topbar_mode').unlink()
        written = ensure_topbar_settings(self.env)
        self.assertEqual(written, ['biz_access.topbar_mode'])

    def test_a_decision_somebody_has_already_made_is_never_overwritten(self):
        """That is the whole reason the data file is `noupdate="1"`, and it
        would be undone by a repair that wrote unconditionally."""
        row = self._row('biz_access.topbar_mode')
        if not row:
            row = self.Param.create({'key': 'biz_access.topbar_mode',
                                     'value': 'by_role'})
        else:
            row.value = 'by_role'
        ensure_topbar_settings(self.env)
        self.assertEqual(self._row('biz_access.topbar_mode').value, 'by_role')

    def test_a_setting_somebody_deliberately_cleared_stays_cleared(self):
        """Ledger F24: clearing the home list is a real decision with its own
        defined behaviour, and filling it back in would undo it. `get_param`
        cannot tell that apart from "never set", which is why this reads the
        row."""
        row = self._row('biz_access.topbar_home_xmlids')
        if not row:
            row = self.Param.create(
                {'key': 'biz_access.topbar_home_xmlids', 'value': ''})
        else:
            row.value = ''
        ensure_topbar_settings(self.env)
        self.assertFalse(self._row('biz_access.topbar_home_xmlids').value,
                         'an empty value must be left exactly as it was')

    def test_running_it_twice_writes_nothing_the_second_time(self):
        ensure_topbar_settings(self.env)
        self.assertEqual(ensure_topbar_settings(self.env), [])

    def test_both_paths_reach_the_same_function(self):
        """The migration and the hook must not grow two copies of one rule."""
        import inspect

        from odoo.addons import health_access
        hooks = inspect.getsource(health_access.hooks.post_init_hook)
        self.assertIn('ensure_topbar_settings', hooks)
        import os
        path = os.path.join(
            os.path.dirname(inspect.getfile(health_access)),
            'migrations', '19.0.1.2.1', 'post-migrate.py')
        self.assertTrue(os.path.exists(path),
                        'the upgrade path has no migration')
        with open(path, encoding='utf-8') as fh:
            self.assertIn('ensure_topbar_settings', fh.read())
