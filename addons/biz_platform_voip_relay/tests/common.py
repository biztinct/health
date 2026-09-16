# -*- coding: utf-8 -*-
"""Shared fixtures for the phone relay suites (R01–R24, H01–H04).

Built on ``health_voip24h``'s own ``VoipCommon`` rather than beside it: that
class already mints a ``voip.config`` with a real receiver address, and the
relay's routing decision starts by asking whether an address is one of THIS
system's own. A second, parallel copy of that setup would drift.

Three things are neutralised here, inside the transaction so they roll back
with the class:

* relay customers are ARCHIVED (never deleted) — a live platform holds a row
  per clinic, and ``_find`` / ``_sync_customers`` must see an empty world;
* pending hand-offs are marked given-up, so ``_cron_retry`` works on this
  suite's rows and nobody else's;
* the platform's real customer list is set to "not started", so a reconcile
  started by a test can never walk a real clinic's database.

**A second database cannot be reached from inside a test transaction** (ledger
§5.63), so ``_pg_cursor`` and ``_tenant_env`` are stood in for. That is not a
convenience: a test that really opened ``hhh`` would commit outside its own
transaction and leave rows behind on a live customer's system.
"""
from contextlib import contextmanager

from odoo.addons.health_voip24h.tests.test_voip24h import VoipCommon

# Short names that can never be a real clinic's web address, so a fixture can
# never collide with the row the relay itself wrote for a live customer. `hhh`
# is a REAL customer on this platform and `voip.relay.tenant.slug` carries an
# unconditional unique index, so creating it here would collide in
# `setUpClass` — which errors every test in the class rather than failing one
# (ledger §5.175).
SLUG_A = 'vrelaya'
SLUG_B = 'vrelayb'

# A hotline and an address that belong to nobody.
HOTLINE_A = '02873007777'
HOTLINE_B = '02873008888'
HOTLINE_NOBODY = '02873009999'
RECEIVER_NOBODY = 'NoSuchReceiverAtAll1'


class FakeResponse:
    def __init__(self, status_code=200, text='{"status":"accepted"}'):
        self.status_code = status_code
        self.text = text


class FakeCursor:
    """What ``biz.tenants._pg_cursor`` hands back, without another database.

    ``rows`` is a list of receiver ids; ``None`` means the customer's system
    has no phone settings table yet.
    """

    def __init__(self, rows):
        self.rows = rows
        self._wants_regclass = False

    def execute(self, sql, params=None):
        self._wants_regclass = 'to_regclass' in sql

    def fetchone(self):
        if self._wants_regclass:
            return ('voip_config',) if self.rows is not None else (None,)
        return None

    def fetchall(self):
        return [(r,) for r in (self.rows or [])]


class VoipRelayCase(VoipCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Relay = env['voip.relay.tenant']
        cls.Route = env['voip.relay.route']
        cls.Delivery = env['voip.relay.delivery']
        cls.Router = env['voip.relay.router']
        cls.Service = env['biz.tenants']

        # A live platform carries these; this suite must not see them.
        cls.Relay.sudo().with_context(active_test=False).search([]).write(
            {'active': False})
        cls.Delivery.sudo().search([('state', '=', 'pending')]).write(
            {'state': 'dead'})
        if 'biz.tenant' in env:
            env['biz.tenant'].sudo().search([]).write({'state': 'draft'})

        # The address this system's own clinic answers to, from VoipCommon.
        cls.local_receiver = cls.config.receiver_id

    # -- helpers -------------------------------------------------------
    def _relay_tenant(self, slug, name=None, state='live', with_biz=False):
        """A relay customer, and optionally the platform row behind it."""
        if with_biz and 'biz.tenant' in self.env:
            Biz = self.env['biz.tenant'].sudo()
            row = Biz.search([('slug', '=', slug)], limit=1)
            if row:
                row.write({'state': state, 'name': name or slug.upper()})
            else:
                Biz.create({'slug': slug, 'name': name or slug.upper(),
                            'state': state})
        existing = self.Relay.sudo().with_context(active_test=False).search(
            [('slug', '=', slug)], limit=1)
        if existing:
            existing.write({'active': True, 'name': name or slug})
            return existing
        return self.Relay.sudo().create({'slug': slug, 'name': name or slug})

    def _route(self, tenant, kind, key):
        return self.Route.sudo().create({
            'tenant_id': tenant.id, 'kind': kind, 'key': key})

    @staticmethod
    def _delivery(path='/voip24h/v3/cdr/ABC/tok', method='GET',
                  query='id=1&did=02873007777', body=b'', content_type=None):
        return {'method': method, 'path': path, 'query': query,
                'body': body, 'content_type': content_type}

    @staticmethod
    @contextmanager
    def _tenant_env_yielding(env, on_enter=None):
        """A stand-in for ``_tenant_env`` that hands back the test env.

        A second database cannot be reached from inside a test transaction
        (ledger §5.63), so the stand-in yields THIS environment.
        """
        if on_enter:
            on_enter()
        yield env

    @staticmethod
    @contextmanager
    def _pg_cursor_yielding(rows):
        yield FakeCursor(rows)
