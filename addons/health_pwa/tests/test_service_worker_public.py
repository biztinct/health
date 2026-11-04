# -*- coding: utf-8 -*-
"""UAT 2026-11-04, round 3 item 9: "Failed to update a ServiceWorker …
service-worker.js?v=1.21.3: The script resource is behind a redirect".

The browser's own update check for the nurse app's service worker must get
the script itself (200, JavaScript), never a redirect to the sign-in page —
with or without a session. Nothing else of the app opens without a sign-in."""
import re

from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestServiceWorkerPublic(HttpCase):

    def _get(self, path):
        return self.url_open(path, allow_redirects=False)

    def _version(self):
        tpl = self.env['ir.ui.view']._render_template('health_pwa.service_worker_js')
        return re.search(r"CACHE_VERSION = '([\d.]+)'", str(tpl)).group(1)

    def test_1_update_check_without_a_session_gets_the_script(self):
        version = self._version()
        resp = self._get('/health_pwa/service-worker.js?v=%s' % version)
        self.assertEqual(resp.status_code, 200, resp.headers.get('Location'))
        self.assertIn('javascript', resp.headers.get('Content-Type', ''))
        self.assertIn("CACHE_VERSION = '%s'" % version, resp.text)
        self.assertEqual(resp.headers.get('Service-Worker-Allowed'), '/health_pwa/')

    def test_2_signed_in_gets_the_same_script(self):
        new_test_user(self.env, login='sw_nurse', password='swnursepw',
                      groups='base.group_user,health_base.group_healthcare_nurse')
        anonymous = self._get('/health_pwa/service-worker.js').text
        self.authenticate('sw_nurse', 'swnursepw')
        resp = self._get('/health_pwa/service-worker.js')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, anonymous, 'one script for everybody: no user data in it')

    def test_3_the_app_and_its_data_still_need_a_sign_in(self):
        for path in ('/health_pwa', '/health_pwa/api/user/profile', '/health_pwa/api/fso'):
            resp = self._get(path)
            self.assertNotEqual(resp.status_code, 200, path)
