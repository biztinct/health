# -*- coding: utf-8 -*-
"""Developer mode belongs to the person who owns the box.

`?debug=1` is a switch anybody can flick from the address bar. It grants no
permission, and that is exactly why it is easy to dismiss: what it does is put
the machinery in front of somebody who was given a product — raw field names,
technical menus, the unminified world — and on a white-labelled product that is
not a small thing.

It is closed at ONE seam, and this file is about that seam having been chosen
correctly. `web` reads the query string into the SESSION during `_pre_dispatch`;
everything downstream reads it back off the session. Standing immediately after
that closes the web client AND the sign-in page's "Log in as superuser" button
in the same three lines, which is the whole argument for standing there.

THE SIGN-IN PAGE IS THE PROBE, and not for convenience. It renders that button
if — and only if — `request.session.debug` is truthy at the moment it is drawn,
which makes it a signal with exactly one cause. The off-switch test proves the
probe works by turning the block off and watching the button come back.
"""

from odoo.tests import HttpCase, tagged

SUPERUSER_BUTTON = '/web/become'
PARAM = 'biz_access.debug_block'


@tagged('post_install', '-at_install')
class TestDeveloperModeIsTheAdministrators(HttpCase):

    def setUp(self):
        super().setUp()
        self.plain = self.env['res.users'].create({
            'name': 'DB plain person',
            'login': 'db.plain@example.test',
            'password': 'db-plain-2026',
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.icp = self.env['ir.config_parameter'].sudo()
        self.env.cr.flush()

    def test_nobody_signed_in_is_not_a_system_administrator(self):
        """The sign-in page, asked for developer mode, does not offer the
        superuser button — because there is nobody there to be allowed it."""
        page = self.url_open('/web/login?debug=1')
        self.assertNotIn(SUPERUSER_BUTTON, page.text)

    def test_switching_the_rail_off_brings_it_back(self):
        """The probe, proved.

        If the button were absent for some OTHER reason, the test above would
        pass whatever this rule did. Turning the block off has to bring it back,
        and that is the only thing that makes the other test mean anything.
        """
        self.icp.set_param(PARAM, 'off')
        self.addCleanup(self.icp.set_param, PARAM, 'on')
        self.env.cr.flush()
        page = self.url_open('/web/login?debug=1')
        self.assertIn(SUPERUSER_BUTTON, page.text)

    def test_a_typo_in_the_setting_leaves_the_rail_on(self):
        """Anything but the word `off` means on. A rail that could be taken
        down by a misspelling is a rail that will be."""
        self.icp.set_param(PARAM, 'offf')
        self.addCleanup(self.icp.set_param, PARAM, 'on')
        self.env.cr.flush()
        page = self.url_open('/web/login?debug=1')
        self.assertNotIn(SUPERUSER_BUTTON, page.text)

    def test_an_ordinary_person_asking_for_it_does_not_get_it(self):
        self.authenticate('db.plain@example.test', 'db-plain-2026')
        self.url_open('/odoo?debug=1')
        self.assertNotIn('"debug"', self._session_json())

    def test_the_system_administrator_keeps_it(self):
        """And this is what proves the check above is a check and not an
        accident of how the page happens to be rendered."""
        admin = self.env.ref('base.user_admin')
        admin.write({'password': 'db-admin-2026'})
        self.env.cr.flush()
        self.authenticate(admin.login, 'db-admin-2026')
        self.url_open('/odoo?debug=1')
        self.assertIn('"debug"', self._session_json())

    def _session_json(self):
        """What the server currently believes about this session.

        Asked of the route that answers it directly rather than scraped out of
        a rendered page, so the assertion does not depend on which address the
        backend happens to live at on this build.
        """
        res = self.opener.post(
            self.base_url() + '/web/session/get_session_info',
            json={'jsonrpc': '2.0', 'method': 'call', 'params': {}})
        return res.text
