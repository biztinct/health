# -*- coding: utf-8 -*-
"""The paused door, the trial bar's answer, and the seat limit.

Numbered test cases 8 and 9 of SAAS H4d.

⚠ THE ONE THAT MATTERS MOST IS `test_the_door_decides_correctly_when_env_user
_is_an_empty_recordset`, and it is written to CONSTRUCT the case rather than to
agree with the design (ledger F53). A route declared `auth='none'` runs with an
environment whose uid is None even when somebody is signed in, so
`request.env.user` is an EMPTY RECORDSET and `has_group()` on it raises
"Expected singleton" — which the original fail-open handler caught, letting
every request through, silently, on every page. And `/odoo` on this build is
exactly such a route.
"""
import logging
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import werkzeug.exceptions
import werkzeug.wrappers

from odoo import fields
from odoo.exceptions import AccessDenied, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenancy.models import standing as st


# =============================================================================
#  THE PURE HALF
# =============================================================================
@tagged('post_install', '-at_install')
class TestStandingRules(TransactionCase):

    def test_the_countdown_agrees_with_the_platform_s_own_copy(self):
        """⚠ TWO COPIES OF ONE JUDGEMENT, AND THIS IS WHAT KEEPS THEM HONEST.

        A customer's system may not import the platform's billing code — the
        never-list is the whole point of the cockpit — so twenty lines are
        written out twice. That is a better trade than the dependency, and it
        is only safe with an assertion that the two agree.
        """
        try:
            from odoo.addons.biz_tenants.models import billing_rules as br
        except ImportError:
            self.skipTest("the cockpit is not on this system, which is the "
                          "normal case for a customer")
        today = date(2026, 9, 5)
        for ends in (date(2026, 10, 30), date(2026, 9, 12), date(2026, 9, 1),
                     False):
            self.assertEqual(st.trial_phase(ends, today),
                             br.trial_phase(ends, today),
                             'the two copies of the trial rule disagree')
        for limit, count in ((0, 5), (10, 5), (10, 9), (10, 10), (10, 12)):
            self.assertEqual(st.seat_verdict(limit, count)['verdict'],
                             br.seat_verdict(limit, count)['verdict'],
                             'the two copies of the seat rule disagree')

    def test_damaged_usage_figures_show_nothing_rather_than_wrong_numbers(self):
        self.assertEqual(st.read_usage('not json')['rows'], [])
        self.assertEqual(st.read_usage('')['rows'], [])
        self.assertEqual(st.read_usage('[]')['rows'], [])
        good = st.read_usage('{"month": "2026-08-01", "month_label": '
                             '"August 2026", "rows": [{"key": "a", '
                             '"label": "A", "value": 3, "charged": true}]}')
        self.assertEqual(good['rows'][0]['value'], 3)
        self.assertTrue(good['rows'][0]['charged'])

    def test_the_signature_moves_only_when_the_answer_moves(self):
        seat = {'verdict': 'ok', 'count': 3}
        first = st.standing_signature('open', 'none', seat, 'Growth')
        self.assertEqual(first, st.standing_signature('open', 'none',
                                                      dict(seat), 'Growth'))
        self.assertNotEqual(first, st.standing_signature('paused', 'none',
                                                         seat, 'Growth'))


# =============================================================================
#  THE SETTINGS THIS SYSTEM READS
# =============================================================================
@tagged('post_install', '-at_install')
class TestStandingReads(TransactionCase):

    def setUp(self):
        super().setUp()
        self.tenancy = self.env['biz.tenancy']
        self.icp = self.env['ir.config_parameter'].sudo()

    def _set(self, key, value):
        self.icp.set_param(key, value)

    def test_a_system_nobody_has_told_anything_is_open(self):
        """FAIL OPEN, ALWAYS. The alternative is a working system locked out of
        its own records because a settings row was empty."""
        self.icp.search([('key', '=', st.P_ACCESS)]).unlink()
        self.assertEqual(self.tenancy.access_state()['access'], 'open')
        self.assertFalse(self.tenancy.is_paused())

    def test_a_pause_with_no_words_still_says_something_actionable(self):
        self._set(st.P_ACCESS, 'paused')
        self._set(st.P_ACCESS_TEXT, '')
        state = self.tenancy.access_state()
        self.assertEqual(state['access'], 'paused')
        self.assertTrue(state['access_text'])

    def test_absent_and_nought_both_mean_no_limit_and_are_told_apart(self):
        """⚠ LEDGER F24. `get_param` answers `False` for both, and the
        difference is what somebody debugging a refusal that is not happening
        needs to see."""
        self.icp.search([('key', '=', st.P_SEAT_LIMIT)]).unlink()
        self.assertEqual(self.tenancy.seat_limit(), 0)
        self._set(st.P_SEAT_LIMIT, '0')
        self.assertEqual(self.tenancy.seat_limit(), 0)
        self._set(st.P_SEAT_LIMIT, '25')
        self.assertEqual(self.tenancy.seat_limit(), 25)
        self._set(st.P_SEAT_LIMIT, 'nonsense')
        self.assertEqual(self.tenancy.seat_limit(), 0)

    def test_the_chrome_answer_carries_the_standing_in_one_read(self):
        self._set(st.P_PLAN_NAME, 'Growth')
        self._set(st.P_TRIAL_ENDS,
                  (date.today() + timedelta(days=4)).isoformat())
        state = self.tenancy.state()
        for key in ('access', 'access_text', 'plan_name', 'trial', 'seat',
                    'standing_sig'):
            self.assertIn(key, state)
        self.assertEqual(state['plan_name'], 'Growth')
        self.assertEqual(state['trial']['phase'], 'ending')

    def test_the_plan_card_reads_the_platform_s_numbers_not_its_own(self):
        self._set(st.P_PLAN_NAME, 'Growth')
        self._set(st.P_USAGE, '{"month": "2026-08-01", "month_label": '
                              '"August 2026", "rows": [{"key": "patients", '
                              '"label": "People in care", "value": 236, '
                              '"charged": true}]}')
        card = self.tenancy.plan_usage()
        self.assertEqual(card['plan_name'], 'Growth')
        self.assertEqual(card['usage']['rows'][0]['value'], 236)


# =============================================================================
#  8. THE PAUSED DOOR
# =============================================================================
@tagged('post_install', '-at_install')
class TestPausedDoor(TransactionCase):
    """Every branch of the door, constructed rather than restated."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.icp.set_param(st.P_ACCESS, 'paused')
        self.icp.set_param(st.P_ACCESS_TEXT, 'The account is unsettled.')
        self.icp.set_param(st.P_RECOVERY, 'bzt_recovery_probe')
        self.ordinary = self.env['res.users'].sudo().create({
            'name': 'An ordinary colleague', 'login': 'bzt_door_ordinary',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.recovery = self.env['res.users'].sudo().create({
            'name': 'The way back in', 'login': 'bzt_recovery_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.IrHttp = type(self.env['ir.http'])

    def _rule(self, kind='http'):
        rule = MagicMock()
        rule.endpoint.routing = {'type': kind}
        return rule

    def _decide(self, uid, env_uid, path='/bizapp', kind='http'):
        """Run the door with a request built to order, and report what it did.

        ⚠ `env_uid` IS SEPARATE FROM `uid` ON PURPOSE, and that separation is
        the whole test. On a route declared `auth='none'` the ENVIRONMENT's uid
        is None while the SESSION still knows perfectly well who is signed in.
        The framework's own `Environment` cannot be handed a uid of None, so
        the seam is stood in for by an object that answers `uid` however this
        case needs and passes everything else through to a real environment.
        """
        real = self.env

        class _Env:
            def __init__(self, uid):
                self.uid = uid

            def __getitem__(self, name):
                return real[name]

            def __contains__(self, name):
                return name in real

        req = MagicMock()
        req.session.uid = uid
        req.httprequest.path = path
        req.env = _Env(env_uid)
        # ⚠ A REAL RESPONSE, NOT AN EXCEPTION. The framework's own `abort()`
        # raises `LookupError: no exception for <...>` for anything that is not
        # one — and the first version of this test handed it an exception
        # instance, which the fail-open handler then swallowed and reported as
        # "let through". That is the F53 shape reproduced by accident, and it
        # is why the assertion below is on WHERE somebody was sent rather than
        # on "it did not raise".
        req.redirect = lambda url: werkzeug.wrappers.Response(
            status=303, headers={'Location': url})
        with patch('odoo.addons.biz_tenancy.models.ir_http.request', req):
            try:
                self.IrHttp._biz_paused_door(self._rule(kind))
            except werkzeug.exceptions.HTTPException as exc:
                where = ''
                if getattr(exc, 'response', None) is not None:
                    where = exc.response.headers.get('Location', '')
                return 'redirected:%s' % (where or exc.description or '')
            except AccessDenied as exc:
                return 'refused:%s' % exc
        return 'through'

    def test_an_ordinary_person_is_stopped_and_sent_somewhere_that_explains(self):
        out = self._decide(self.ordinary.id, self.ordinary.id)
        self.assertTrue(out.startswith('redirected:'), out)
        self.assertIn('/biz_tenancy/paused', out)

    def test_the_door_decides_correctly_when_env_user_is_empty(self):
        """⚠ THE F53 CASE, CONSTRUCTED.

        `request.env.uid` is None — which is exactly what a route declared
        `auth='none'` gives — while the session still knows who is signed in.
        The original code read `env.user`, got an EMPTY recordset, and
        `has_group()` raised "Expected singleton"; the fail-open handler caught
        it and let every request through, silently, on every page. `/odoo` on
        this build is such a route, so the door was open on the first hop of
        every navigation.
        """
        out = self._decide(self.ordinary.id, None)
        self.assertTrue(out.startswith('redirected:'),
                        'the door was OPEN for a signed-in person on an '
                        "auth='none' route — this is exactly ledger F53")

    def test_the_odoo_prefix_is_covered(self):
        """`/odoo` is the redirect this build serves at `auth='none'`, so it is
        the first hop of every navigation and the one that must be shut."""
        for path in ('/odoo', '/odoo/action-123', '/bizapp', '/bizapp/x'):
            out = self._decide(self.ordinary.id, None, path=path)
            self.assertTrue(out.startswith('redirected:'),
                            '%s was let through' % path)

    def test_the_recovery_account_still_gets_in(self):
        self.assertEqual(self._decide(self.recovery.id, self.recovery.id),
                         'through')

    def test_an_active_support_session_still_gets_in(self):
        session = self.env['biz.support.session'].sudo().create({
            'user_id': self.ordinary.id, 'reason': 'fixing the pause',
            'minutes': 30, 'state': 'active',
            'opened_at': fields.Datetime.now(),
            'expires_at': fields.Datetime.now()
            + timedelta(minutes=30),
        })
        self.assertTrue(session)
        self.assertEqual(self._decide(self.ordinary.id, self.ordinary.id),
                         'through')

    def test_the_page_the_door_draws_itself_from_is_never_behind_it(self):
        """A door served without its own stylesheet is a wall of unstyled text,
        and a door that redirects its own page loops for ever."""
        for path in ('/biz_tenancy/paused', '/web/login', '/web/assets/x.css',
                     '/web/static/img/a.png', '/biz_tenancy/state',
                     '/web/session/logout', '/favicon.ico'):
            self.assertEqual(self._decide(self.ordinary.id, None, path=path),
                             'through', '%s was shut' % path)

    def test_a_call_from_a_page_already_open_is_refused_by_name(self):
        out = self._decide(self.ordinary.id, None, kind='jsonrpc')
        self.assertTrue(out.startswith('refused:'), out)
        self.assertIn('unsettled', out)

    def test_nobody_signed_in_meets_the_sign_in_page_rather_than_the_door(self):
        self.assertEqual(self._decide(None, None), 'through')

    def test_an_open_system_lets_everybody_through(self):
        self.icp.set_param(st.P_ACCESS, 'open')
        self.assertEqual(self._decide(self.ordinary.id, None), 'through')

    def test_the_fail_open_path_puts_its_reason_in_the_log_line(self):
        """⚠ NOT ONLY IN A TRACEBACK (ledger F53). The line is the only thing
        anybody greps on a live box, and here a silent failure means an OPEN
        DOOR. Asserted on the log RECORD, not on "it did not raise"."""
        req = MagicMock()
        req.session.uid = self.ordinary.id
        req.httprequest.path = '/bizapp'

        def _boom(rule):
            raise RuntimeError('the settings table is on fire')

        with patch('odoo.addons.biz_tenancy.models.ir_http.request', req), \
                patch.object(self.IrHttp, '_biz_paused_decide',
                             classmethod(lambda cls, rule: _boom(rule))), \
                self.assertLogs('odoo.addons.biz_tenancy.models.ir_http',
                                level=logging.WARNING) as caught:
            self.IrHttp._biz_paused_door(self._rule())
        joined = '\n'.join(caught.output)
        self.assertIn('the settings table is on fire', joined,
                      'the fail-open path did not put its reason in the line')
        self.assertIn('LET THROUGH', joined)


# =============================================================================
#  9. THE SEAT LIMIT
# =============================================================================
@tagged('post_install', '-at_install')
class TestSeatLimit(TransactionCase):

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.tenancy = self.env['biz.tenancy']
        self.icp.set_param(st.P_SEAT_MODEL, 'res.users')
        self.icp.set_param(st.P_PLAN_NAME, 'Growth')
        self.icp.set_param(st.P_RECOVERY, '')
        st._SEAT_CACHE.clear()
        self.addCleanup(st._SEAT_CACHE.clear)

    def _count(self):
        return self.tenancy.seat_count(fresh=True)

    def _overlay_installed(self):
        """Is the product's own `create` override on this system?

        Named rather than assumed: this file ships to the generic module, and
        a skip that says why is honest where a silent pass is not.
        """
        return bool(self.env['ir.module.module'].sudo().search_count(
            [('name', '=', 'health_tenancy'), ('state', '=', 'installed')]))

    def test_an_absent_limit_means_no_limit(self):
        self.icp.search([('key', '=', st.P_SEAT_LIMIT)]).unlink()
        self.assertEqual(self.tenancy.seat_gate(1), '')

    def test_a_limit_of_nought_means_no_limit(self):
        self.icp.set_param(st.P_SEAT_LIMIT, '0')
        self.assertEqual(self.tenancy.seat_gate(1), '')

    def test_past_the_limit_is_refused_with_the_plain_sentence(self):
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count()))
        refusal = self.tenancy.seat_gate(1)
        self.assertTrue(refusal)
        self.assertIn('Growth', refusal)
        self.assertIn('larger plan', refusal)

    def test_under_the_limit_is_let_through(self):
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count() + 5))
        self.assertEqual(self.tenancy.seat_gate(1), '')

    def test_adding_several_at_once_is_asked_once(self):
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count() + 2))
        self.assertEqual(self.tenancy.seat_gate(2), '')
        self.assertTrue(self.tenancy.seat_gate(3))

    def test_the_limit_is_read_from_the_pushed_parameter(self):
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count() + 1))
        self.assertEqual(self.tenancy.seat_gate(1), '')
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count()))
        self.assertTrue(self.tenancy.seat_gate(1))

    def test_the_recovery_account_is_never_refused(self):
        """The way back in must not be behind the problem."""
        recovery = self.env['res.users'].sudo().create({
            'name': 'Way back', 'login': 'bzt_seat_recovery',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.icp.set_param(st.P_RECOVERY, 'bzt_seat_recovery')
        self.icp.set_param(st.P_SEAT_LIMIT, '1')
        self.assertTrue(self.tenancy.seat_gate(1))
        self.assertEqual(
            self.tenancy.with_user(recovery).seat_gate(1), '',
            'the recovery account was refused by the limit')

    def test_a_support_session_is_never_refused(self):
        ordinary = self.env['res.users'].sudo().create({
            'name': 'Operator', 'login': 'bzt_seat_operator',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.icp.set_param(st.P_SEAT_LIMIT, '1')
        self.assertTrue(self.tenancy.with_user(ordinary).seat_gate(1))
        self.env['biz.support.session'].sudo().create({
            'user_id': ordinary.id, 'reason': 'adding a colleague they need',
            'minutes': 30, 'state': 'active',
            'opened_at': fields.Datetime.now(),
            'expires_at': fields.Datetime.now()
            + timedelta(minutes=30),
        })
        self.assertEqual(self.tenancy.with_user(ordinary).seat_gate(1), '',
                         'somebody fixing the problem was stopped by it')

    def test_the_product_s_own_override_refuses_a_new_account(self):
        """The one line of glue in the overlay. Skipped where the overlay is
        not on this system, which is honest rather than a false pass."""
        if not self._overlay_installed():
            self.skipTest('the product overlay is not installed here')
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count()))
        with self.assertRaises(UserError) as caught:
            self.env['res.users'].sudo().create({
                'name': 'One too many', 'login': 'bzt_seat_over',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            })
        self.assertIn('Growth', str(caught.exception))

    def test_a_portal_account_is_not_a_person_with_a_login(self):
        if not self._overlay_installed():
            self.skipTest('the product overlay is not installed here')
        self.icp.set_param(st.P_SEAT_LIMIT, str(self._count()))
        portal = self.env['res.users'].sudo().create({
            'name': 'A family member', 'login': 'bzt_seat_portal',
            'share': True,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.assertTrue(portal)
