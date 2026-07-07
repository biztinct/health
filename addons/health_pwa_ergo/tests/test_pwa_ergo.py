# -*- coding: utf-8 -*-
import os

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestPwaErgo(HttpCase):
    """Front-end phase — the Python surface is the shell render + a CSS pin."""

    def test_01_shell_injects_ergo_assets(self):
        """The PWA shell serves ergo.css/ergo.js at 1.6.0 + the boot marker."""
        user = new_test_user(
            self.env, login='ergo_shell_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('ergo.css?v=1.6.0', body)
        self.assertIn('ergo.js?v=1.6.0', body)
        # No-FOUC boot script reads localStorage.vu_ergo_modes in <head>.
        self.assertIn('vu_ergo_modes', body)

    def test_02_shell_version_is_1_6_0(self):
        """Guards the 5-place version bump."""
        user = new_test_user(
            self.env, login='ergo_ver_user', groups='base.group_user')
        self.authenticate(user.login, user.login)
        res = self.url_open('/health_pwa')
        self.assertEqual(res.status_code, 200)
        self.assertIn('1.6.0', res.text)

    def test_03_glove_touch_target_pinned(self):
        """Static sanity: glove mode sets --touch-target: 64px."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'static', 'src', 'css', 'ergo.css'),
                  encoding='utf-8') as fh:
            css = fh.read()
        self.assertIn('html.vu-glove', css)
        self.assertIn('--touch-target: 64px', css)
