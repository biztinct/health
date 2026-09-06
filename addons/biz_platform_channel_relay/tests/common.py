# -*- coding: utf-8 -*-
"""Shared fixtures for the relay suites (T1–T17).

Built on ``health_care_command_channels``'s own ``ChannelHubCase`` rather than
beside it: that class already archives every live ``care.channel.connection``
and ``channel.platform.app`` row inside the test transaction (ledger §5.95), and
the relay's routing decision starts with exactly those two tables. A second,
parallel copy of that setup would drift.

Three more tables are neutralised here for the same reason, and the same way —
inside the transaction, so everything rolls back with the class:

* relay customers are ARCHIVED (never deleted): a live platform will hold a row
  per clinic, and ``_find`` / ``_sync_customers`` must see an empty world;
* pending deliveries are marked given-up so ``_cron_retry`` works on this
  suite's rows and nobody else's;
* the platform's real customer list is set to "not started" so a reconcile
  cannot walk a real clinic's database from a test.
"""
import json
from contextlib import contextmanager

from odoo.addons.health_care_command_channels.tests.common import ChannelHubCase

# None of these is a real credential.
META_APP_ID = '1234567890123'
META_SECRET = 'relay-app-secret-r1-fixture'
VERIFY_TOKEN = 'relay-verify-token-r1-fixture'

PAGE_LOCAL = 'PAGE_LOCAL_R1'
PAGE_X = 'PAGE_TENANT_X'
PAGE_Y = 'PAGE_TENANT_Y'
PAGE_UNKNOWN = 'PAGE_NOBODY_OWNS'
PHONE_1 = '100000000000001'
PHONE_2 = '100000000000002'


def fb_payload(*page_ids, sender='PSID_1', text='xin chào'):
    """One Messenger batch with one entry per page."""
    return {
        'object': 'page',
        'entry': [{
            'id': page_id,
            'time': 1757000000000 + index,
            'messaging': [{
                'sender': {'id': '%s_%s' % (sender, index)},
                'recipient': {'id': page_id},
                'timestamp': 1757000000000 + index,
                'message': {'mid': 'mid_%s' % page_id, 'text': text},
            }],
        } for index, page_id in enumerate(page_ids)],
    }


def wa_payload(*phone_number_ids, waba='WABA_R1', text='xin chào'):
    """ONE WhatsApp entry carrying one change per phone number id."""
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': waba,
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'metadata': {'display_phone_number': '84900000%s' % index,
                                 'phone_number_id': phone_number_id},
                    'messages': [{
                        'from': '8490000000%s' % index,
                        'id': 'wamid_%s' % phone_number_id,
                        'timestamp': '1757000000',
                        'type': 'text',
                        'text': {'body': text},
                    }],
                },
            } for index, phone_number_id in enumerate(phone_number_ids)],
        }],
    }


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.text = ''


class FakeCursor:
    """What ``biz.tenants._pg_cursor`` hands back, without another database.

    ``rows`` is a list of ``(channel, resource id)``; ``None`` means the
    customer's system has no channel connection table yet.
    """

    def __init__(self, rows):
        self.rows = rows
        self._wants_regclass = False

    def execute(self, sql, params=None):
        self._wants_regclass = 'to_regclass' in sql

    def fetchone(self):
        if self._wants_regclass:
            return ('care_channel_connection',) if self.rows is not None \
                else (None,)
        return None

    def fetchall(self):
        return list(self.rows or [])


class RelayCase(ChannelHubCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Relay = env['channel.relay.tenant']
        cls.Route = env['channel.relay.route']
        cls.Delivery = env['channel.relay.delivery']
        cls.Router = env['channel.relay.router']
        cls.Message = env['care.channel.message']
        cls.Capture = env['care.contact.capture']
        cls.Service = env['biz.tenants']

        # A live platform carries these; this suite must not see them.
        cls.Relay.sudo().with_context(active_test=False).search([]).write(
            {'active': False})
        cls.Delivery.sudo().search([('state', '=', 'pending')]).write(
            {'state': 'dead'})
        if 'biz.tenant' in env:
            env['biz.tenant'].sudo().search([]).write({'state': 'draft'})

        cls.meta_app = cls.App.create({
            'provider': 'meta',
            'client_id': META_APP_ID,
            'extra_json': json.dumps({'verify_token': VERIFY_TOKEN}),
        })
        cls.meta_app.action_set_secret(META_SECRET)

    # -- helpers -------------------------------------------------------
    def _relay_tenant(self, slug, name=None, state='live', with_biz=True):
        """A relay customer, and by default the platform row behind it.

        `biz.tenant.slug` is unique across the WHOLE table and a real platform
        already holds the slug a fixture reaches for (`hhh` is a live clinic),
        so this reuses the row rather than creating a second one — everything
        it writes rolls back with the transaction either way.
        """
        if with_biz and 'biz.tenant' in self.env:
            Biz = self.env['biz.tenant'].sudo()
            row = Biz.search([('slug', '=', slug)], limit=1)
            if row:
                row.write({'state': state})
            else:
                Biz.create({'slug': slug, 'name': name or slug.upper(),
                            'state': state})
        existing = self.Relay.sudo().with_context(active_test=False).search(
            [('slug', '=', slug)], limit=1)
        if existing:
            existing.write({'active': True, 'name': name or slug})
            return existing
        return self.Relay.sudo().create({'slug': slug, 'name': name or slug})

    def _route(self, tenant, channel, resource_id):
        return self.Route.sudo().create({
            'tenant_id': tenant.id, 'channel': channel,
            'resource_external_id': resource_id})

    def _audit_count(self, event):
        return self.Audit.sudo().search_count([('event', '=', event)])

    @staticmethod
    @contextmanager
    def _tenant_env_yielding(env, on_enter=None):
        """A stand-in for ``_tenant_env`` that hands back the test env.

        A second database cannot be reached from inside a test transaction
        (ledger §5.63), so the stand-in yields THIS environment. ``on_enter``
        is what lets a test make the row the push finds a different one from
        the row it is copying.
        """
        if on_enter:
            on_enter()
        yield env
