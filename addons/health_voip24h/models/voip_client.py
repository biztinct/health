# -*- coding: utf-8 -*-
"""What a user asked for, which browser owns an extension, and what still owes
a notification.

Three small models with one thing in common: they are all about *us*, not about
the phone system. None of them is ever allowed to establish a call fact.

* ``voip.call.action`` — the audit of intent. A dial is an action; the call it
  produces is a session. Keeping them apart is what lets a double-click be
  answered with "you already asked for this" instead of a second real call.
* ``voip.client.lease`` — which browser instance owns an extension right now.
  A lease stops cooperative instances double-registering. It cannot revoke an
  exposed SIP password or push an unresponsive browser off the PBX, and the UI
  never claims it can.
* ``voip.call.effect`` — the transactional outbox. A bus notification, a Care
  Command projection and an activity are all *effects* created in the same
  transaction as the state change that justified them, and delivered
  afterwards. A bridge error can therefore no longer drop a provider event.
"""

import logging
import secrets
import hashlib
import hmac
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EFFECT_RETRY_SCHEDULE = (5, 30, 120, 600)


def _digest(value):
    return hashlib.sha256((value or '').encode('utf-8')).hexdigest()


class VoIPCallAction(models.Model):
    _name = 'voip.call.action'
    _description = 'VoIP User Action'
    _order = 'requested_at desc, id desc'

    def init(self):
        # The idempotency contract behind "a double-click is not a second
        # call". §5.3: the pre-check in _record happens before create, so a
        # racing duplicate returns the first row rather than poisoning the
        # transaction with an IntegrityError.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_action_uuid_uidx
            ON voip_call_action (voip_config_id, user_id, client_action_uuid)
        """)

    voip_config_id = fields.Many2one('voip.config', required=True,
                                     ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company',
                                 related='voip_config_id.company_id',
                                 store=True, index=True)
    client_action_uuid = fields.Char(string='Request Reference', required=True,
                                     index=True)
    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user)
    extension_id = fields.Many2one('voip.extension', index=True)
    session_id = fields.Many2one('voip.call.session', ondelete='set null',
                                 index=True)

    action = fields.Selection([
        ('dial', 'Dial'),
        ('answer', 'Answer'),
        ('reject', 'Reject'),
        ('hangup', 'Hang up'),
        ('mute', 'Mute'),
        ('hold', 'Hold'),
        ('transfer', 'Transfer'),
        ('dtmf', 'Keypad tone'),
        ('register', 'Register phone'),
        ('release', 'Release phone'),
    ], string='Action', required=True, index=True)

    requested_destination = fields.Char(string='Requested Number')
    normalised_destination = fields.Char(string='Number Dialled')
    related_model = fields.Char(string='From Record Type')
    related_id = fields.Integer(string='From Record')

    requested_at = fields.Datetime(default=fields.Datetime.now, required=True,
                                   index=True)
    authorised_at = fields.Datetime(readonly=True)
    result = fields.Selection([
        ('requested', 'Requested'),
        ('authorised', 'Allowed'),
        ('refused', 'Refused'),
        ('reported_ok', 'Browser reported success'),
        ('reported_failed', 'Browser reported failure'),
        ('unresolved', 'Outcome unknown'),
    ], string='Result', default='requested', required=True, index=True)
    refusal_reason = fields.Char()
    evidence_class = fields.Selection([
        ('intent', 'What the user asked for'),
        ('browser', 'What the browser reported'),
        ('provider', 'What the phone system confirmed'),
    ], string='Evidence', default='intent', required=True,
        help='Browser evidence is provisional. It can never set a billable '
             'duration or close a call back as answered.')
    diagnostic = fields.Char(string='Diagnostic Code',
                             help='A short code. Never a message from the '
                                  'phone system and never a phone number.')

    @api.model
    def _record(self, config, action, *, uuid_value, extension=None,
                destination=None, normalised=None, related_model=None,
                related_id=None, user=None):
        """Idempotent by ``(config, user, uuid)``. Returns ``(record, created)``."""
        user = user or self.env.user
        existing = self.sudo().search([
            ('voip_config_id', '=', config.id),
            ('user_id', '=', user.id),
            ('client_action_uuid', '=', uuid_value),
        ], limit=1)
        if existing:
            return existing, False
        try:
            with self.env.cr.savepoint():
                record = self.sudo().create({
                    'voip_config_id': config.id,
                    'client_action_uuid': uuid_value,
                    'user_id': user.id,
                    'extension_id': extension.id if extension else False,
                    'action': action,
                    'requested_destination': destination or False,
                    'normalised_destination': normalised or False,
                    'related_model': related_model or False,
                    'related_id': related_id or False,
                })
        except Exception:  # noqa: BLE001 — concurrent identical request
            record = self.sudo().search([
                ('voip_config_id', '=', config.id),
                ('user_id', '=', user.id),
                ('client_action_uuid', '=', uuid_value),
            ], limit=1)
            if not record:
                raise
            return record, False
        return record, True


class VoIPClientLease(models.Model):
    _name = 'voip.client.lease'
    _description = 'VoIP Browser Phone Lease'
    _order = 'id desc'

    def init(self):
        # One live owner per extension. The partial unique index is the
        # enforcement; the Python check is only the friendly error.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_client_lease_owner_uidx
            ON voip_client_lease (extension_id)
            WHERE NOT released
        """)

    voip_config_id = fields.Many2one('voip.config', required=True,
                                     ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company',
                                 related='voip_config_id.company_id',
                                 store=True, index=True)
    extension_id = fields.Many2one('voip.extension', required=True,
                                   ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    browser_uuid = fields.Char(string='Browser Instance', required=True,
                               index=True)
    token_digest = fields.Char(required=True, groups='base.group_system')
    fence = fields.Integer(string='Fence', default=1, required=True,
                           help='Increases every time ownership moves. A '
                                'request carrying an old fence is refused.')
    acquired_at = fields.Datetime(default=fields.Datetime.now, required=True)
    heartbeat_at = fields.Datetime(default=fields.Datetime.now, required=True,
                                   index=True)
    expires_at = fields.Datetime(required=True, index=True)
    released = fields.Boolean(default=False, index=True)
    released_reason = fields.Char()

    sdk_state = fields.Selection([
        ('off', 'Off'),
        ('initialising', 'Starting'),
        ('registering', 'Registering'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
        ('disconnected', 'Disconnected'),
    ], string='Phone State', default='off', required=True)
    sdk_diagnostic = fields.Char()

    # ------------------------------------------------------------------

    @api.model
    def _acquire(self, config, extension, browser_uuid, takeover=False):
        """Take ownership of an extension for one browser instance.

        Returns ``(lease, token)``. The token is returned ONCE and only its
        digest is stored, so a lease cannot be resumed from the database.
        """
        now = fields.Datetime.now()
        expiry_seconds = config.lease_expiry_seconds or 30
        Lease = self.sudo()

        # Expire anything already dead before looking for a conflict.
        Lease.search([('extension_id', '=', extension.id),
                      ('released', '=', False),
                      ('expires_at', '<', now)]).write({
            'released': True, 'released_reason': 'expired'})

        current = Lease.search([('extension_id', '=', extension.id),
                                ('released', '=', False)], limit=1)
        if current:
            if current.browser_uuid == browser_uuid and \
                    current.user_id == self.env.user:
                token = secrets.token_urlsafe(24)
                current.write({
                    'token_digest': _digest(token),
                    'heartbeat_at': now,
                    'expires_at': now + timedelta(seconds=expiry_seconds),
                })
                return current, token
            if not takeover:
                raise UserError(_(
                    'This extension is already in use in another browser '
                    '(%(who)s). Close it there, or choose to take over.',
                    who=current.user_id.display_name))
            if current.sdk_state in ('ready',) and \
                    current.heartbeat_at and \
                    (now - current.heartbeat_at).total_seconds() < 5:
                # Alive and registered: taking it over silently would drop an
                # active phone. The user has to be told what they are doing.
                raise UserError(_(
                    'That extension is signed in and active in another '
                    'browser right now. Ask %(who)s to hang up and sign out '
                    'first.', who=current.user_id.display_name))
            current.write({'released': True, 'released_reason': 'taken over'})

        token = secrets.token_urlsafe(24)
        fence = (Lease.search([('extension_id', '=', extension.id)],
                              order='fence desc', limit=1).fence or 0) + 1
        lease = Lease.create({
            'voip_config_id': config.id,
            'extension_id': extension.id,
            'user_id': self.env.user.id,
            'browser_uuid': browser_uuid,
            'token_digest': _digest(token),
            'fence': fence,
            'expires_at': now + timedelta(seconds=expiry_seconds),
        })
        return lease, token

    @api.model
    def _authenticate(self, lease_id, token, fence=None):
        """Resolve a lease from its credential. Refuses a replaced lease."""
        lease = self.sudo().browse(int(lease_id or 0)).exists()
        if not lease or lease.released:
            return self.browse()
        if lease.user_id != self.env.user:
            return self.browse()
        if not hmac.compare_digest(_digest(token), lease.token_digest or ''):
            return self.browse()
        if fence is not None and int(fence) != lease.fence:
            return self.browse()
        if lease.expires_at and lease.expires_at < fields.Datetime.now():
            lease.write({'released': True, 'released_reason': 'expired'})
            return self.browse()
        return lease

    def _beat(self, sdk_state=None, diagnostic=None):
        self.ensure_one()
        now = fields.Datetime.now()
        expiry = self.voip_config_id.lease_expiry_seconds or 30
        vals = {'heartbeat_at': now,
                'expires_at': now + timedelta(seconds=expiry)}
        if sdk_state:
            vals['sdk_state'] = sdk_state
        if diagnostic is not None:
            vals['sdk_diagnostic'] = diagnostic or False
        self.sudo().write(vals)
        if sdk_state == 'ready' and not self.voip_config_id.ready_registration_at:
            self.voip_config_id.sudo().write(
                {'ready_registration_at': now})
        return True

    def _release(self, reason='released'):
        self.sudo().write({'released': True, 'released_reason': reason,
                           'sdk_state': 'off'})
        return True

    @api.model
    def cron_expire_leases(self):
        now = fields.Datetime.now()
        stale = self.sudo().search([('released', '=', False),
                                    ('expires_at', '<', now)])
        if stale:
            stale.write({'released': True, 'released_reason': 'expired',
                         'sdk_state': 'disconnected'})
            _logger.info('Released %s expired browser phone lease(s)', len(stale))


class VoIPCallEffect(models.Model):
    """Transactional outbox for everything a state change owes the world."""
    _name = 'voip.call.effect'
    _description = 'VoIP Pending Effect'
    _order = 'id'

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_effect_dedupe_uidx
            ON voip_call_effect (session_id, effect_type, recipient_uid,
                                 dedupe_key)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS voip_call_effect_worklist_idx
            ON voip_call_effect (state, next_retry_at)
            WHERE state IN ('pending', 'retry')
        """)

    session_id = fields.Many2one('voip.call.session', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='session_id.company_id',
                                 store=True, index=True)
    effect_type = fields.Selection([
        ('notify', 'Notify a person'),
        ('care_projection', 'Update Care Command'),
        ('activity', 'Create a task'),
        ('readiness', 'Update readiness'),
    ], required=True, index=True)
    notification_kind = fields.Char(
        string='Notification',
        help='Which of the notification catalogue entries this is.')
    recipient_uid = fields.Integer(string='Recipient User', default=0,
                                   index=True,
                                   help='0 means the effect has no single '
                                        'recipient (a projection, say).')
    payload = fields.Text()
    projection_version = fields.Integer(default=0)
    dedupe_key = fields.Char(required=True, index=True)

    state = fields.Selection([
        ('pending', 'Waiting'),
        ('done', 'Delivered'),
        ('retry', 'Retrying'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(default=0)
    next_retry_at = fields.Datetime(index=True)
    error_code = fields.Char()
    delivered_at = fields.Datetime(readonly=True)

    @api.model
    def _enqueue(self, session, effect_type, *, dedupe_key, payload=None,
                 recipient_uid=0, notification_kind=None,
                 projection_version=0):
        """Idempotent by ``(session, type, recipient, dedupe_key)``."""
        existing = self.sudo().search([
            ('session_id', '=', session.id),
            ('effect_type', '=', effect_type),
            ('recipient_uid', '=', recipient_uid),
            ('dedupe_key', '=', dedupe_key),
        ], limit=1)
        if existing:
            return existing
        import json
        try:
            with self.env.cr.savepoint():
                return self.sudo().create({
                    'session_id': session.id,
                    'effect_type': effect_type,
                    'notification_kind': notification_kind or False,
                    'recipient_uid': recipient_uid,
                    'payload': json.dumps(payload or {}),
                    'dedupe_key': dedupe_key,
                    'projection_version': projection_version,
                })
        except Exception:  # noqa: BLE001 — concurrent identical enqueue
            return self.sudo().search([
                ('session_id', '=', session.id),
                ('effect_type', '=', effect_type),
                ('recipient_uid', '=', recipient_uid),
                ('dedupe_key', '=', dedupe_key),
            ], limit=1)

    def _mark_done(self):
        self.sudo().write({'state': 'done',
                           'delivered_at': fields.Datetime.now(),
                           'error_code': False, 'next_retry_at': False})

    def _mark_retry(self, code):
        for effect in self:
            attempts = (effect.attempts or 0) + 1
            if attempts > len(EFFECT_RETRY_SCHEDULE):
                effect.sudo().write({'state': 'failed', 'attempts': attempts,
                                     'error_code': code, 'next_retry_at': False})
                continue
            effect.sudo().write({
                'state': 'retry',
                'attempts': attempts,
                'error_code': code,
                'next_retry_at': fields.Datetime.now() + timedelta(
                    seconds=EFFECT_RETRY_SCHEDULE[attempts - 1]),
            })

    @api.model
    def _cron_drain(self):
        from ..services.event_worker import drain_effects
        return drain_effects(self.env, limit=300)

    @api.model
    def _claim_batch(self, limit=100):
        self.env.cr.execute("""
            SELECT id FROM voip_call_effect
             WHERE state IN ('pending', 'retry')
               AND (next_retry_at IS NULL OR next_retry_at <= %s)
             ORDER BY id
             LIMIT %s
             FOR UPDATE SKIP LOCKED
        """, (fields.Datetime.now(), limit))
        return self.sudo().browse([row[0] for row in self.env.cr.fetchall()])
