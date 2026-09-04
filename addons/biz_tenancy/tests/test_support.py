# -*- coding: utf-8 -*-
"""Somebody from the platform, in this system. SAAS H4c §5.8.

The record is on the CUSTOMER's own database, which is this one in a test, so
almost all of it is real here: minting, redeeming, the single use, the time
box, the trail and the customer's own refusal.

The two things a database cannot prove are asserted against the SOURCE, and
both are ledger entries that cost a test cycle each on the platform this was
ported from (F62): a route that signs somebody in must say `readonly=False`,
and `authenticate` must not be inside a bare `except Exception`.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.biz_tenancy.models.support import (
    MAX_MINUTES, is_screen_path, token_hash,
)
from odoo.addons.biz_tenancy.models.tenancy import P_SUPPORT_ALLOWED


def _src(*parts):
    with open(os.path.join(get_module_path('biz_tenancy'), *parts),
              encoding='utf-8') as fh:
        return fh.read()


# =========================================================================
#  THE PURE HALF
# =========================================================================
@tagged('post_install', '-at_install')
class TestScreenPaths(TransactionCase):
    """⚠ Ledger F66. A page load is thirty requests, and a trail of
    `/web/image` lines is a record of nothing."""

    def test_a_backend_address_is_a_screen(self):
        for path in ('/bizapp', '/odoo/action-123', '/bizapp/settings'):
            self.assertTrue(is_screen_path(path), path)

    def test_plumbing_is_not_a_screen(self):
        for path in ('/web/image/1', '/web/assets/x/web.assets_backend.js',
                     '/mail/data', '/bus/websocket', '/websocket',
                     '/biz_tenancy/state', '/favicon.ico', '/report/pdf/x'):
            self.assertFalse(is_screen_path(path), path)

    def test_an_asset_with_no_prefix_is_still_not_a_screen(self):
        self.assertFalse(is_screen_path('/something/style.css'))

    def test_rubbish_is_not_a_screen(self):
        for path in ('', None, 'bizapp', 'http://elsewhere/x'):
            self.assertFalse(is_screen_path(path))

    def test_the_token_is_only_ever_kept_as_a_hash(self):
        self.assertEqual(len(token_hash('abc')), 64)
        self.assertNotEqual(token_hash('abc'), 'abc')
        self.assertEqual(token_hash('abc'), token_hash('abc'))


# =========================================================================
#  THE RECORD
# =========================================================================
@tagged('post_install', '-at_install')
class TestSupportSession(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Session = self.env['biz.support.session']
        self.user = self.env['res.users'].sudo().create({
            'name': 'Recovery', 'login': 'bztn_recovery_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.token = 'a-token-nobody-else-has'

    def _mint(self, minutes=30, reason='check the invoice numbering'):
        return self.Session.browse(self.Session.mint({
            'reason': reason, 'minutes': minutes,
            'token_sha': token_hash(self.token),
            'operator_name': 'An operator', 'platform_name': 'The platform',
            'user_id': self.user.id,
        }))

    def test_a_link_without_a_reason_is_refused(self):
        with self.assertRaises(ValueError):
            self.Session.mint({'reason': '  ', 'minutes': 30,
                               'user_id': self.user.id})

    def test_a_time_box_is_capped_whatever_anybody_asks_for(self):
        row = self._mint(minutes=100000)
        self.assertEqual(row.minutes, MAX_MINUTES)

    def test_the_link_works_once_and_only_once(self):
        row = self._mint()
        found, refusal = self.Session.redeem(self.token)
        self.assertEqual(found, row)
        self.assertFalse(refusal)
        found.open_now()
        self.assertEqual(found.state, 'active')
        self.assertFalse(found.token_sha,
                         'the hash is cleared in the same write that opens the '
                         'door, so two people cannot both arrive holding it')
        again, refusal = self.Session.redeem(self.token)
        self.assertFalse(again)
        self.assertIn('already been used', refusal)

    def test_a_link_nobody_ever_made_is_refused_with_a_sentence(self):
        found, refusal = self.Session.redeem('not-a-real-token')
        self.assertFalse(found)
        self.assertTrue(refusal)
        self.assertNotIn('Traceback', refusal)

    def test_a_link_that_ran_out_before_it_was_used_says_so(self):
        from odoo import fields
        row = self._mint()
        row.sudo().write({'link_expires_at':
                          fields.Datetime.subtract(fields.Datetime.now(),
                                                   minutes=5)})
        found, refusal = self.Session.redeem(self.token)
        self.assertFalse(found)
        self.assertIn('ran out', refusal)
        self.assertEqual(row.state, 'expired')

    def test_the_session_ends_at_the_time_box(self):
        from odoo import fields
        row = self._mint(minutes=15)
        row.open_now()
        self.assertEqual(
            round((row.expires_at - row.opened_at).total_seconds() / 60), 15)
        row.sudo().write({'expires_at':
                          fields.Datetime.subtract(fields.Datetime.now(),
                                                   minutes=1)})
        self.assertEqual(self.Session.sweep(), 1)
        self.assertEqual(row.state, 'expired')
        self.assertIn('time ran out', row.end_reason)

    def test_a_link_issued_but_not_used_counts_as_pending(self):
        """⚠ Ledger F68. Reading the record the instant the button is pressed
        finds a link issued and not yet used; treating that as "nothing is
        running" closes the alert about a session that has not begun."""
        self._mint()
        self.assertEqual(self.Session.pending_count(), 1)

    def test_ending_it_is_recorded_with_a_reason_a_person_can_read(self):
        row = self._mint()
        row.open_now()
        row.finish('operator')
        self.assertEqual(row.state, 'ended')
        self.assertTrue(row.ended_at)
        self.assertIn('finished', row.end_reason.lower())

    # ------------------------------------------------------------ the trail
    def test_only_a_backend_address_is_written_down(self):
        row = self._mint()
        row.open_now()
        row.note_screen('/web/image/42')
        row.note_screen('/bizapp/action-9')
        self.assertEqual(row.screen_ids.mapped('path'), ['/bizapp/action-9'])

    def test_a_repeat_fills_the_name_in_rather_than_being_deduplicated_away(self):
        """⚠ Ledger F66's second half. The request seam sees the address
        BEFORE the page has a name, so the first line is nameless; the browser
        reports the title afterwards and that report has to complete it."""
        row = self._mint()
        row.open_now()
        row.note_screen('/bizapp/action-9')
        screen = row.screen_ids
        self.assertFalse(screen.name)
        row.note_screen('/bizapp/action-9', 'Invoices')
        self.assertEqual(len(row.screen_ids), 1)
        self.assertEqual(row.screen_ids.name, 'Invoices')
        self.assertEqual(row.screen_ids.count, 2)

    def test_a_query_string_is_not_a_different_screen(self):
        row = self._mint()
        row.open_now()
        row.note_screen('/bizapp/action-9?x=1')
        row.note_screen('/bizapp/action-9?x=2')
        self.assertEqual(len(row.screen_ids), 1)

    def test_the_trail_is_readable_by_the_customer(self):
        row = self._mint()
        row.open_now()
        row.note_screen('/bizapp/action-9', 'Invoices')
        trail = self.Session.trail()
        self.assertTrue(trail)
        first = trail[0]
        self.assertEqual(first['reason'], 'check the invoice numbering')
        self.assertEqual(first['screens'][0]['name'], 'Invoices')
        self.assertTrue(first['state_label'])

    def test_a_refused_attempt_leaves_its_mark(self):
        """⚠ Ledger F64's point, on this side of the wire: the whole reason to
        write a refusal down is that it LEAVES SOMETHING BEHIND."""
        rid = self.Session.refuse({
            'reason': 'wanted a look', 'minutes': 30,
            'operator_name': 'An operator',
            'refusal': 'This system does not allow support access.'})
        row = self.Session.browse(rid)
        self.assertEqual(row.state, 'refused')
        self.assertTrue(row.ended_at)
        self.assertIn(row.id, [r['id'] for r in self.Session.trail()])


# =========================================================================
#  THE CUSTOMER'S OWN SWITCH
# =========================================================================
@tagged('post_install', '-at_install')
class TestSupportAllowed(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Tenancy = self.env['biz.tenancy']
        self.Param = self.env['ir.config_parameter'].sudo()
        self.Param.search([('key', '=', P_SUPPORT_ALLOWED)]).unlink()

    def test_a_customer_nobody_has_asked_allows_it(self):
        """A real default rather than an oversight: somebody who rings up about
        a problem expects the people who sold them the product to be able to
        look at it."""
        self.assertTrue(self.Tenancy.support_allowed())

    def test_switching_it_off_is_remembered(self):
        self.Tenancy.set_support_allowed(False)
        self.assertFalse(self.Tenancy.support_allowed())
        self.Tenancy.set_support_allowed(True)
        self.assertTrue(self.Tenancy.support_allowed())

    def test_every_spelling_of_off_is_read_as_off(self):
        for value in ('0', 'false', 'False', 'no', 'off'):
            self.Param.set_param(P_SUPPORT_ALLOWED, value)
            self.assertFalse(self.Tenancy.support_allowed(), value)

    def test_who_may_change_it_is_a_seam_and_not_the_platform_s_own_gate(self):
        """⚠ FOUND ON A LIVE CUSTOMER'S SCREEN. The framework's administrator
        permission is exactly what the two-ring rule withholds from a
        customer's administrator, so gating this on it refused the one setting
        a customer owns to the only person who should be able to change it."""
        self.assertTrue(self.Tenancy.may_change_support(),
                        'the platform administrator can always change it')
        plain = self.env['res.users'].sudo().create({
            'name': 'A colleague', 'login': 'bztn_plain_support_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.assertFalse(
            self.env['biz.tenancy'].with_user(plain).may_change_support(),
            'somebody who does not run this system can change its settings')

    def test_it_is_carried_on_every_page(self):
        self.Tenancy.set_support_allowed(False)
        self.assertFalse(self.Tenancy.state()['support_allowed'])


# =========================================================================
#  THE TWO THINGS ONLY THE SOURCE CAN PROVE
# =========================================================================
@tagged('post_install', '-at_install')
class TestSupportRouteSource(TransactionCase):

    def setUp(self):
        super().setUp()
        self.src = _src('controllers', 'main.py')

    def test_the_door_is_declared_read_write(self):
        """⚠ Ledger F62. A route declared `auth='none'` is READ-ONLY BY
        DEFAULT on this framework. Signing somebody in writes, so without
        `readonly=False` the door answers "cannot execute INSERT in a
        read-only transaction"."""
        block = self.src.split("def support_open")[0].split(
            "/biz_tenancy/support/link/")[-1]
        self.assertIn('readonly=False', block)
        self.assertIn("auth='none'", block)

    def test_the_sign_in_is_not_inside_a_bare_except(self):
        """⚠ Ledger F62's other half. The framework recovers from a read-only
        transaction by re-running the whole request; a blanket catch turns that
        recovery into "your link has expired" and hides the real fault."""
        body = self.src.split("def support_open")[1].split("@http.route")[0]
        self.assertIn('finalize', body,
                      'the door no longer signs anybody in through the '
                      "framework's own path")
        self.assertNotIn('except Exception', body)

    def test_the_link_does_not_land_on_a_public_website(self):
        """⚠ FOUND BY FOLLOWING THE LINK. `/` on a system that also serves a
        public site is the MARKETING PAGE: the operator was signed in
        correctly and arrived on a home page with a "Sign in" button on it,
        which reads exactly like a link that did not work."""
        from odoo.addons.biz_tenancy.controllers.main import BACKEND_ROOT
        self.assertNotEqual(BACKEND_ROOT, '/')
        self.assertTrue(BACKEND_ROOT.startswith('/'))
        self.assertIn('BACKEND_ROOT', self.src.split('def support_open')[1])

    def test_only_a_real_page_load_is_recorded_as_a_screen(self):
        """⚠ Ledger F66, one more turn of it, found on a live customer's
        system. A path filter alone put `/website/translations` on their own
        record as a screen somebody opened — it is a fetch the page makes for
        itself. The browser already says which is which, and a rule about the
        KIND of request cannot go stale the way a list of names does."""
        src = _src('models', 'ir_http.py')
        self.assertIn('Sec-Fetch-Dest', src)
        self.assertIn("== 'document'", src)

    def test_the_request_seam_re_raises_the_read_only_error(self):
        """The end of a support session must never be silently lost."""
        src = _src('models', 'ir_http.py')
        # Docstrings first: this one NAMES the trap it exists for, and a scan
        # that reads the explanation instead of the code is a scan that agrees
        # with the comment rather than with the file.
        code = re.sub(r'"""(?:.|\n)*?"""', '', src)
        self.assertIn('ReadOnlySqlTransaction', code)
        for block in code.split("ReadOnlySqlTransaction")[1:]:
            self.assertIn('raise', block[:80],
                          'the read-only error is caught and not re-raised')


@tagged('post_install', '-at_install')
class TestSupportRoutes(HttpCase):
    """The door itself. An HttpCase here needs `--workers=0` and a
    `--db-filter` naming this database (ledger H32/H55)."""

    def test_a_link_nobody_made_gets_a_page_and_never_a_traceback(self):
        res = self.url_open('/biz_tenancy/support/link/not-a-real-token')
        self.assertEqual(res.status_code, 200)
        self.assertIn('cannot be used', res.text)
        self.assertNotIn('Traceback', res.text)
        self.assertNotIn('odoo', res.text.lower().split('<body')[-1][:400],
                         'the refusal page names the framework')
