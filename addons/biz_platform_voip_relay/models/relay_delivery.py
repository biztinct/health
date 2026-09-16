# -*- coding: utf-8 -*-
"""A hand-off that did not land, kept so it can be tried again.

This is the ONLY place a call-back ever rests on the platform, and it rests
there **encrypted, briefly, and only because a customer's system could not be
reached**. The moment it lands the contents are cleared; a week later the row
itself is gone.

Be clear about what that means, because the rest of this module is careful to
hold nothing: a v3 call-back address carries the customer's token inside its
path, so a queued row holds that token too. It is encrypted at rest with this
database's own key, it is never shown on any screen, it is never logged, and it
is erased on delivery rather than on the purge. In flight — the ordinary case,
where the hand-off lands first time — nothing is written down at all.

We own the retry rather than answering the phone supplier with an error on
purpose: nothing in the supplier's documentation says what they do with a 5xx,
whether they re-send, how often, or for how long. Owning it is the only version
of this whose behaviour is known. The customer's own inbox refuses a repeat of
something it already has, so a re-send that crosses with a supplier re-send is
harmless.
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.health_voip24h.services import voip_crypto

from ..services import relay

_logger = logging.getLogger(__name__)

# Waiting time after each failed attempt: a minute, five, a quarter of an hour,
# an hour, six, then twelve until we give up.
BACKOFF = (60, 300, 900, 3600, 6 * 3600, 12 * 3600)
MAX_ATTEMPTS = 8
RETRY_BATCH = 200
PURGE_AFTER_DAYS = 7

FEEDS = [('cdr', 'Completed calls'), ('state', 'Live call events')]

STATES = [
    ('pending', 'Waiting'),
    ('delivered', 'Delivered'),
    ('dead', 'Given up'),
]


class VoipRelayDelivery(models.Model):
    _name = 'voip.relay.delivery'
    _description = 'Phone hand-off waiting to be tried again'
    _order = 'next_at, id'

    tenant_id = fields.Many2one(
        'voip.relay.tenant', string='Customer', required=True,
        ondelete='cascade', index=True)
    feed = fields.Selection(FEEDS, string='Kind', required=True)
    payload_enc = fields.Text(
        string='Call-back (encrypted)', groups='base.group_system',
        help='Encrypted at rest and cleared the moment the hand-off lands. '
             'Never shown on any screen.')
    attempts = fields.Integer(string='Attempts', default=0, readonly=True)
    next_at = fields.Datetime(string='Next try', index=True, readonly=True)
    state = fields.Selection(
        STATES, string='State', default='pending', required=True, index=True)
    last_error = fields.Char(string='Last problem', readonly=True)
    delivered_at = fields.Datetime(string='Delivered on', readonly=True)

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------
    @api.model
    def _queue(self, tenant, feed, delivery, error):
        """Keep a hand-off that could not be delivered, encrypted."""
        packed = json.dumps({
            'method': delivery.get('method') or 'GET',
            'path': delivery.get('path') or '',
            'query': delivery.get('query') or '',
            'content_type': delivery.get('content_type') or '',
            # latin-1 round-trips every byte 1:1, so a body that is not valid
            # UTF-8 is still replayed exactly as the supplier sent it.
            'body': (delivery.get('body') or b'').decode('latin-1'),
        }, separators=(',', ':'))
        return self.sudo().create({
            'tenant_id': tenant.id,
            'feed': feed,
            'payload_enc': voip_crypto.encrypt(self.env, packed),
            'attempts': 0,
            'next_at': fields.Datetime.now(),
            'state': 'pending',
            'last_error': str(error)[:200],
        })

    def _unpack(self):
        self.ensure_one()
        raw = voip_crypto.decrypt(self.env, self.sudo().payload_enc or '')
        if not raw:
            return None
        try:
            packed = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(packed, dict) or not packed.get('path'):
            return None
        return {
            'method': packed.get('method') or 'GET',
            'path': packed['path'],
            'query': packed.get('query') or '',
            'content_type': packed.get('content_type') or None,
            'body': (packed.get('body') or '').encode('latin-1'),
        }

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------
    def _attempt(self):
        """Try one hand-off again. Returns True when it landed."""
        self.ensure_one()
        record = self.sudo()
        delivery = record._unpack()
        if not delivery:
            record.write({'state': 'dead',
                          'last_error': 'the call is no longer held here'})
            return False
        try:
            status, _body = relay.forward(
                self.env, record.tenant_id.host, delivery)
        except relay.RelayError as exc:
            return record._failed(str(exc))
        except Exception as exc:  # noqa: BLE001 — every failure is a retry
            return record._failed(type(exc).__name__)
        # Any answer at all is the end of this hand-off. A refusal is the
        # customer's verdict, not a transport failure, and re-sending would not
        # change it — the reason is kept so an operator can see it.
        landed = 200 <= status < 300
        record.write({
            'state': 'delivered',
            'payload_enc': False,
            'delivered_at': fields.Datetime.now(),
            'last_error': False if landed else ('answered HTTP %s' % status),
        })
        record.tenant_id.write({'last_forward_at': fields.Datetime.now()})
        return landed

    def _failed(self, reason):
        self.ensure_one()
        attempts = self.attempts + 1
        vals = {'attempts': attempts, 'last_error': str(reason)[:200]}
        if attempts >= MAX_ATTEMPTS:
            # The call is KEPT: an operator can still press "Try this again".
            vals['state'] = 'dead'
        else:
            vals['next_at'] = fields.Datetime.now() + timedelta(
                seconds=BACKOFF[min(attempts, len(BACKOFF)) - 1])
        self.write(vals)
        self.tenant_id.write({'last_error': str(reason)[:200]})
        return False

    @api.model
    def _cron_retry(self):
        """Every minute: try the hand-offs whose waiting time is up."""
        rows = self.sudo().search(
            [('state', '=', 'pending'),
             ('next_at', '<=', fields.Datetime.now())],
            order='next_at asc, id asc', limit=RETRY_BATCH)
        landed = 0
        for row in rows:
            # One savepoint each: a poisoned row must never stop the run.
            try:
                with self.env.cr.savepoint():
                    if row._attempt():
                        landed += 1
            except Exception:  # noqa: BLE001
                _logger.exception('voip relay: retrying hand-off %s failed',
                                  row.id)
        if rows:
            _logger.info('voip relay: %s of %s hand-offs landed',
                         landed, len(rows))
        return {'tried': len(rows), 'landed': landed}

    @api.model
    def _cron_purge(self):
        """Daily: the queue is a queue, not an archive."""
        cutoff = fields.Datetime.now() - timedelta(days=PURGE_AFTER_DAYS)
        rows = self.sudo().search([
            '|',
            '&', ('state', '=', 'delivered'), ('delivered_at', '<=', cutoff),
            '&', ('state', '=', 'dead'), ('write_date', '<=', cutoff),
        ])
        count = len(rows)
        if rows:
            rows.unlink()
            _logger.info('voip relay: %s finished hand-offs removed', count)
        return count

    def action_retry_now(self):
        """Row button: stop waiting and try this one on the next run."""
        self.sudo().write({'state': 'pending',
                           'next_at': fields.Datetime.now()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('It will be tried again'),
                       'message': _('This call is back in the queue.'),
                       'type': 'success', 'sticky': False},
        }
