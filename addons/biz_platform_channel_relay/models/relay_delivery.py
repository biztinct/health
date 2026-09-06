# -*- coding: utf-8 -*-
"""A forward that did not land, kept so it can be tried again.

This is the ONLY place a message body ever rests on the platform, and it rests
there **encrypted, briefly, and only because a delivery failed**. The moment it
lands the body is cleared; a week later the row itself is gone.

We own the retry rather than answering Meta with an error on purpose. A non-2xx
makes Meta redeliver the WHOLE batch — every customer in it, not just the one
that failed — and sustained failures get the application's Messenger webhook
switched off, which would take every customer's inbox down over one broken
system. So the platform always answers 200 after it has verified the signature,
and the queue is ours.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_care_command_channels.services.redact import redact

from ..services import relay

_logger = logging.getLogger(__name__)

# Waiting time after each failed attempt: a minute, five, a quarter of an hour,
# an hour, six, then twelve until we give up.
BACKOFF = (60, 300, 900, 3600, 6 * 3600, 12 * 3600)
MAX_ATTEMPTS = 8
RETRY_BATCH = 200
PURGE_AFTER_DAYS = 7

STATES = [
    ('pending', 'Waiting'),
    ('delivered', 'Delivered'),
    ('dead', 'Given up'),
]


class ChannelRelayDelivery(models.Model):
    _name = 'channel.relay.delivery'
    _description = 'Relay delivery waiting to be tried again'
    _order = 'next_at, id'

    tenant_id = fields.Many2one(
        'channel.relay.tenant', string='Customer', required=True,
        ondelete='cascade', index=True)
    channel = fields.Selection(
        [('whatsapp', 'WhatsApp'), ('fb', 'Messenger')],
        string='Channel', required=True)
    body_enc = fields.Text(
        string='Message (encrypted)', groups='base.group_system',
        help='Encrypted at rest and cleared the moment the delivery lands. '
             'Never shown on any screen.')
    signature = fields.Char(
        string='Signature', readonly=True,
        help='The signature this exact message was sent with. Re-used on every '
             'retry, because the customer checks it against these bytes.')
    attempts = fields.Integer(string='Attempts', default=0, readonly=True)
    next_at = fields.Datetime(string='Next try', index=True, readonly=True)
    state = fields.Selection(
        STATES, string='State', default='pending', required=True, index=True)
    last_error = fields.Char(string='Last problem', readonly=True)
    delivered_at = fields.Datetime(string='Delivered on', readonly=True)
    entry_count = fields.Integer(
        string='Entries', readonly=True,
        help='How many events were inside — never what they said.')

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------
    @api.model
    def _queue(self, tenant, channel, body, signature, entry_count, error):
        """Keep a failed forward. ``body`` is bytes; it is stored encrypted."""
        return self.sudo().create({
            'tenant_id': tenant.id,
            'channel': channel,
            'body_enc': channel_crypto.encrypt(
                self.env, body.decode('utf-8', 'replace')),
            'signature': signature,
            'attempts': 0,
            'next_at': fields.Datetime.now(),
            'state': 'pending',
            'entry_count': entry_count,
            'last_error': redact(error),
        })

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------
    def _attempt(self):
        """Try one delivery again. Returns True when it landed."""
        self.ensure_one()
        record = self.sudo()
        body = channel_crypto.decrypt(self.env, record.body_enc or '')
        if not body:
            record.write({'state': 'dead',
                          'last_error': 'the message is no longer held here'})
            return False
        try:
            relay.forward(self.env, record.tenant_id, record.channel,
                          body.encode('utf-8'), record.signature)
        except Exception as exc:  # noqa: BLE001 — every failure is a retry
            attempts = record.attempts + 1
            vals = {'attempts': attempts, 'last_error': redact(str(exc))}
            if attempts >= MAX_ATTEMPTS:
                # The body is KEPT: an operator can still press Retry now.
                vals['state'] = 'dead'
            else:
                wait = BACKOFF[min(attempts, len(BACKOFF)) - 1]
                vals['next_at'] = fields.Datetime.now() + timedelta(seconds=wait)
            record.write(vals)
            self.env['care.channel.audit']._log(
                'relay_failed', channel=record.channel,
                detail='%s retry %s failed' % (record.tenant_id.slug, attempts))
            return False
        record.write({'state': 'delivered', 'body_enc': False,
                      'delivered_at': fields.Datetime.now(),
                      'last_error': False})
        record.tenant_id.write({'last_forward_at': fields.Datetime.now()})
        self.env['care.channel.audit']._log(
            'relay_forwarded', channel=record.channel,
            detail='%s %s %s entries (retry)' % (
                record.tenant_id.slug, record.channel, record.entry_count))
        return True

    @api.model
    def _cron_retry(self):
        """Every minute: try the deliveries whose waiting time is up."""
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
                _logger.exception('channel relay: retrying delivery %s failed',
                                  row.id)
        if rows:
            _logger.info('channel relay: %s of %s deliveries landed',
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
            _logger.info('channel relay: %s finished deliveries removed', count)
        return count

    def action_retry_now(self):
        """Row button: stop waiting and try this one on the next run."""
        self.sudo().write({'state': 'pending',
                           'next_at': fields.Datetime.now()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('It will be tried again'),
                       'message': _('This delivery is back in the queue.'),
                       'type': 'success', 'sticky': False},
        }
