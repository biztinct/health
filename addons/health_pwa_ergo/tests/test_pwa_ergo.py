# -*- coding: utf-8 -*-
import os

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestPwaErgo(HttpCase):
    """Front-end phase — the Python surface is the shell render + a CSS pin."""

    # FORCED EDIT (Phase GB): these two pins still named 1.9.0 while the shell
    # has been on 1.19.0 for ten bumps. The assets ARE injected — the run that
    # caught this shows ergo.css?v=1.19.0 and ergo.js?v=1.19.0 in the body — so
    # the product never drifted; the pins did. They survived because
    # health_pwa_ergo is absent from the conventions §3 pin-test list AND
    # because no HttpCase in this repo had ever executed. Both are fixed in
    # this phase; the pin stays a hard literal on purpose (that is the
    # tripwire that forces the 5-place bump to be noticed).
    PWA_VERSION = '1.19.0'

    def test_01_shell_injects_ergo_assets(self):
        """The PWA shell serves ergo.css/ergo.js at the pinned version."""
        user = new_test_user(
            self.env, login='ergo_shell_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('ergo.css?v=%s' % self.PWA_VERSION, body)
        self.assertIn('ergo.js?v=%s' % self.PWA_VERSION, body)
        # No-FOUC boot script reads localStorage.vu_ergo_modes in <head>.
        self.assertIn('vu_ergo_modes', body)

    def test_02_shell_version_is_pinned(self):
        """Guards the 5-place version bump (shared PWA asset version)."""
        user = new_test_user(
            self.env, login='ergo_ver_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.PWA_VERSION, res.text)

    def test_03_glove_touch_target_pinned(self):
        """Static sanity: glove mode sets --touch-target: 64px."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'static', 'src', 'css', 'ergo.css'),
                  encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('html.vu-glove', css)
        self.assertIn('--touch-target: 64px', css)
