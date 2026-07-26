# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
import re

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestBizDeroute(HttpCase):

    # FORCED EDIT (Phase GB): every authenticating test here used the literal
    # credentials admin/admin. That holds on a fresh demo database and nowhere
    # else — on vietuat it raised "Login failed for login:admin" (4 errors),
    # and the login-redirect test POSTed those same dead credentials, got the
    # login page re-rendered at 200, and read as a routing regression
    # (200 != 303) when routing was never reached. These suites had never
    # executed, so nobody saw it. Own the user instead of borrowing the
    # deployment's, which is what every other HttpCase in this repo does.
    PASSWORD = 'deroute-test-pw'

    def setUp(self):
        super().setUp()
        self.test_user = new_test_user(
            self.env, login='deroute_user', groups='base.group_user',
            password=self.PASSWORD)

    def _login(self):
        self.authenticate(self.test_user.login, self.PASSWORD)

    def _location(self, response):
        return response.headers.get('Location', '')

    def test_legacy_odoo_301(self):
        res = self.url_open('/odoo', allow_redirects=False)
        self.assertEqual(res.status_code, 301)
        self.assertTrue(self._location(res).endswith('/bizapp'))

    def test_legacy_odoo_subpath_query_301(self):
        res = self.url_open('/odoo/action-1/5?cids=1&x=a%20b', allow_redirects=False)
        self.assertEqual(res.status_code, 301)
        self.assertTrue(
            self._location(res).endswith('/bizapp/action-1/5?cids=1&x=a%20b'),
            self._location(res),
        )

    def test_root_redirects_to_brand(self):
        res = self.url_open('/', allow_redirects=False)
        if res.status_code in (301, 302, 303):
            # Without website installed, / redirects into the backend and
            # must never expose /odoo.
            self.assertNotIn('/odoo', self._location(res))

    def test_bizapp_anonymous_redirects_to_login(self):
        res = self.url_open('/bizapp/action-1', allow_redirects=False)
        self.assertEqual(res.status_code, 303)
        location = self._location(res)
        self.assertIn('/web/login', location)
        self.assertIn('bizapp', location)
        self.assertNotIn('odoo', location.replace('odoo.com', ''))

    def test_bizapp_serves_webclient(self):
        self._login()
        res = self.url_open('/bizapp')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'session_info', res.content)

    def test_bizapp_subpath_serves_webclient(self):
        self._login()
        res = self.url_open('/bizapp/settings')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'session_info', res.content)

    def test_login_redirect_default_is_branded(self):
        # GET the login page to obtain the CSRF token, then POST credentials.
        res = self.url_open('/web/login')
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.text)
        self.assertTrue(match, 'csrf_token input not found on login page')
        token = match.group(1)
        res = self.url_open(
            '/web/login',
            data={'login': self.test_user.login, 'password': self.PASSWORD,
                  'csrf_token': token},
            allow_redirects=False,
        )
        self.assertEqual(res.status_code, 303)
        self.assertTrue(self._location(res).endswith('/bizapp'), self._location(res))

    def test_logout_redirects_to_brand(self):
        self._login()
        res = self.url_open('/web/session/logout', allow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertTrue(self._location(res).endswith('/bizapp'), self._location(res))

    def test_web_still_serves(self):
        # /web stays alive: the client-side retrocompat shim converts legacy
        # hash URLs and replaces the visible URL with the branded one.
        self._login()
        res = self.url_open('/web', allow_redirects=False)
        self.assertEqual(res.status_code, 200)
