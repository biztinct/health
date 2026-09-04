# -*- coding: utf-8 -*-
"""The support door, from the platform's side. SAAS H4c §5.8 and §5.9.

The refusals are the interesting half, so they are a pure function with tests
of their own; the acts against a customer's database are stood in for by
patches, and the ONE thing that must not be patched away is the mark a refusal
leaves on the customer's own record.

⚠ AND NOT ONE REFUSAL HERE IS WRAPPED IN `assertRaises` (ledger F64).
`assertRaises` takes a savepoint and rolls it back on the way out, which is
right for the usual case and wrong whenever the whole point of the refusal is
that it LEAVES SOMETHING BEHIND. Every one of them catches the exception by
hand.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models.support_service import (
    TIME_BOXES, check_support_request, support_link,
)


@tagged('post_install', '-at_install')
class TestSupportRules(TransactionCase):
    """The refusals, pure. §5.8's first two."""

    def test_no_reason_is_refused_and_the_message_says_why_it_matters(self):
        msg = check_support_request('', 30)
        self.assertTrue(msg)
        self.assertIn('read', msg,
                      'the refusal has to say that the customer reads it')

    def test_a_reason_nobody_could_act_on_is_refused(self):
        self.assertTrue(check_support_request('look', 30))
        self.assertFalse(check_support_request(
            'check why invoice numbering restarted', 30))

    def test_an_enormous_reason_is_refused(self):
        self.assertTrue(check_support_request('x' * 400, 30))

    def test_only_the_three_time_boxes_are_accepted(self):
        for minutes in TIME_BOXES:
            self.assertFalse(check_support_request('a good enough reason',
                                                   minutes))
        for bad in (0, 5, 480, 'soon', None):
            self.assertTrue(check_support_request('a good enough reason', bad),
                            bad)

    def test_the_link_is_built_from_the_customer_s_own_address(self):
        self.assertEqual(support_link('https://x.example/', 'tok'),
                         'https://x.example/biz_tenancy/support/link/tok')


@tagged('post_install', '-at_install')
class TestSupportDoor(TransactionCase):

    def setUp(self):
        super().setUp()
        self.tenant = self.env['biz.tenant'].create({
            'name': 'A customer', 'slug': 'supprobe', 'state': 'live'})
        self.service = self.env['biz.tenants']
        self.minted = []
        self.refused = []

        class FakeSession:
            def __init__(self, outer):
                self.outer = outer

            def mint(self, vals):
                self.outer.minted.append(dict(vals))
                return 7

            def refuse(self, vals):
                self.outer.refused.append(dict(vals))
                return 8

        class FakeEnv(dict):
            pass

        outer = self

        class _Ctx:
            def __enter__(self):
                env = FakeEnv()
                env['biz.support.session'] = FakeSession(outer)
                return env

            def __exit__(self, *a):
                return False

        # ⚠ A TEST CURSOR REFUSES TO COMMIT, AND THE REFUSAL IS BOLTED TO THE
        # INSTANCE (ledger F29/H69). `patch.object(self.env.cr, ...)` — the
        # OBJECT — is what works; patching the class raises "Cannot commit or
        # rollback a cursor from inside a test".
        self.committed = False

        def note_commit():
            self.committed = True

        self._patchers = [
            patch.object(self.env.cr, 'commit', side_effect=note_commit),
            patch.object(type(self.service), '_tenant_env',
                         lambda self, db: _Ctx()),
            patch.object(type(self.service), '_db_exists',
                         lambda self, name: True),
            patch.object(type(self.service), '_support_recovery_uid',
                         lambda self, db: (9, 'platform.recovery@example')),
            patch.object(type(self.service), '_support_rows',
                         lambda self, db, limit=10: []),
            patch.object(type(self.service), '_send_alert_mail',
                         lambda self, s, b, recipients=None:
                         ('dark', 'no outgoing mail account')),
        ]
        for p in self._patchers:
            p.start()
            self.addCleanup(p.stop)

    def _allow(self, allowed, why=''):
        return patch.object(type(self.service), '_support_allowed_on',
                            lambda self, db: (allowed, why))

    # ------------------------------------------------------------- the door
    def test_a_link_is_made_and_it_is_one_use(self):
        with self._allow(True):
            res = self.service.support_start(
                self.tenant.id, 'check why invoice numbering restarted', 30)
        self.assertTrue(res['ok'])
        self.assertIn('/biz_tenancy/support/link/', res['link'])
        self.assertEqual(len(self.minted), 1)
        self.assertEqual(len(self.minted[0]['token_sha']), 64,
                         'the customer is sent a HASH, never the link')
        self.assertNotIn(self.minted[0]['token_sha'], res['link'])

    def test_the_reason_reaches_the_customer_s_own_record(self):
        with self._allow(True):
            self.service.support_start(self.tenant.id,
                                       'check the invoice numbering', 30)
        self.assertEqual(self.minted[0]['reason'],
                         'check the invoice numbering')

    def test_it_is_written_on_our_own_log_too(self):
        with self._allow(True):
            self.service.support_start(self.tenant.id,
                                       'check the invoice numbering', 15)
        self.assertIn('support link', self.tenant.provision_log)
        self.assertIn('15 minutes', self.tenant.provision_log)

    def test_no_reason_is_refused_by_name(self):
        with self._allow(True):
            try:
                self.service.support_start(self.tenant.id, '', 30)
            except UserError as e:
                self.assertIn('why', str(e))
            else:
                self.fail('a link was made with no reason')
        self.assertFalse(self.minted)

    def test_a_customer_who_is_not_live_is_refused_by_name(self):
        self.tenant.write({'state': 'draft'})
        with self._allow(True):
            try:
                self.service.support_start(self.tenant.id, 'a good reason', 30)
            except UserError as e:
                self.assertIn('A customer', str(e))
            else:
                self.fail('a link was made into a system that is not live')

    # ------------------------------------------- the customer's own refusal
    def test_a_customer_who_has_switched_it_off_is_refused_BY_NAME(self):
        """⚠ CAUGHT BY HAND, NEVER `assertRaises` (ledger F64). The whole
        point of this refusal is the mark it leaves on the customer's own
        record, and `assertRaises` takes a savepoint and rolls that back."""
        with self._allow(False):
            try:
                self.service.support_start(self.tenant.id,
                                           'check the invoice numbering', 30)
            except UserError as e:
                message = str(e)
            else:
                self.fail('a link was made into a system that refuses them')
        self.assertIn('A customer', message)
        self.assertIn('switched support access off', message)
        self.assertIn('About screen', message,
                      'the refusal has to say where they can switch it on')
        # AND THE SIDE EFFECT SURVIVED, which is the assertion this test is for.
        self.assertFalse(self.minted, 'nothing was minted')
        self.assertEqual(len(self.refused), 1,
                         'the attempt was not written on their own record')
        self.assertIn('refuse', self.refused[0]['refusal'].lower())
        self.assertIn('REFUSED', self.tenant.provision_log)
        self.assertTrue(self.committed,
                        'the refusal rolls back its own record of itself: a '
                        'raise undoes everything written on OUR side, and only '
                        "the mark on the customer's own record survives")

    # --------------------------------------------------------- the alert
    def test_the_alert_fires_on_the_press_and_is_dark(self):
        """⚠ Ledger F67. A session is an ACT, not a fault: a thirty-minute
        session ended after two is over before the fifteen-minute sweep ever
        looks at it."""
        with self._allow(True):
            self.service.support_start(self.tenant.id,
                                       'check the invoice numbering', 30)
        alert = self.env['biz.alert'].search([
            ('key', '=', 'support_session:supprobe')], limit=1)
        self.assertTrue(alert, 'nothing was raised when the button was pressed')
        self.assertEqual(alert.kind, 'support_session')
        self.assertEqual(alert.severity, 'info',
                         'a deliberate act is not "something needs your '
                         'attention" (ledger F68)')
        self.assertEqual(alert.channel_state, 'dark')
        self.assertFalse(alert.spoken_at,
                         'nothing was sent, so nothing says it was (F40)')
        self.assertIn('check the invoice numbering', alert.body_text)

    def test_a_refusal_raises_its_own_alert_and_it_is_a_warning(self):
        with self._allow(False):
            try:
                self.service.support_start(self.tenant.id, 'a good reason here',
                                           30)
            except UserError:
                pass
        alert = self.env['biz.alert'].search([
            ('key', '=', 'support_refused:supprobe')], limit=1)
        self.assertTrue(alert)
        self.assertEqual(alert.severity, 'warning')

    def test_the_sweep_never_resolves_a_support_alert_on_its_own(self):
        """⚠ These two kinds are ACTS and nothing measures them, so a sweep
        that resolved anything it could not see would close a thirty-minute
        session fifteen minutes in."""
        from odoo.addons.biz_tenants.models.alert_rules import (
            SELF_MANAGED_KINDS, reconcile,
        )
        self.assertIn('support_session', SELF_MANAGED_KINDS)
        with self._allow(True):
            self.service.support_start(self.tenant.id, 'a good reason here', 30)
        alert = self.env['biz.alert'].search([
            ('key', '=', 'support_session:supprobe')], limit=1)
        _create, _bump, to_resolve = reconcile(alert.as_dict(), [], 'now')
        self.assertNotIn(alert.id, to_resolve)

    def test_ending_it_closes_the_alert(self):
        with self._allow(True):
            self.service.support_start(self.tenant.id, 'a good reason here', 30)
        alert = self.env['biz.alert'].search([
            ('key', '=', 'support_session:supprobe')], limit=1)
        self.assertEqual(alert.state, 'open')

        class _EndCtx:
            def __enter__(self):
                class Rows:
                    def exists(self):
                        return self

                    def finish(self, reason):
                        return self

                    def __len__(self):
                        return 1

                    def sudo(self):
                        return self

                    def browse(self, *a):
                        return self

                    def search(self, *a, **k):
                        return self
                return {'biz.support.session': Rows()}

            def __exit__(self, *a):
                return False

        with patch.object(type(self.service), '_tenant_env',
                          lambda self, db: _EndCtx()):
            self.service.support_end(self.tenant.id)
        self.assertEqual(alert.state, 'resolved')
        self.assertIn('ended', (alert.resolution or '').lower())

    def test_the_screen_reads_the_record_off_the_customer_s_own_system(self):
        with self._allow(True):
            data = self.service.support_data(self.tenant.id)
        self.assertTrue(data['allowed'])
        self.assertEqual(data['time_boxes'], list(TIME_BOXES))
        self.assertIn("own system", data['note'])
        self.assertIn('not here', data['note'])
