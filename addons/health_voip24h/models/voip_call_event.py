# -*- coding: utf-8 -*-
"""The durable inbox: everything the phone system tells us, before we believe it.

One row per semantically distinct delivery. The receiver's only job is to get a
row committed and answer; all interpretation happens afterwards and can be
retried, replayed and audited. This is the model that makes "acknowledge only
after durable ingestion" true rather than aspirational — the old route returned
HTTP 200 from an outer ``except`` with nothing written anywhere.

Four records are kept apart on purpose, and this is the first of them:

* this inbox — what the provider SAID (never a customer timeline),
* ``voip.call.log`` / ``voip.call.session`` — what we believe HAPPENED,
* ``voip.call.action`` — what a USER asked for,
* the integration audit/log — how the plumbing is BEHAVING.

Counting deliveries as calls is how a duplicate webhook becomes a duplicate
patient interaction, so analytics never reads this model.
"""

import json
import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Transient retry ladder, in seconds. After the last one an operator looks.
RETRY_SCHEDULE = (5, 30, 120, 600, 1800)

MAX_PAYLOAD_CHARS = 32 * 1024


class VoIPCallEvent(models.Model):
    _name = 'voip.call.event'
    _description = 'VoIP Provider Event (inbox)'
    _order = 'received_at desc, id desc'
    _rec_name = 'display_reference'

    def init(self):
        # §5.1 — the uniqueness contract that makes duplicate delivery free.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_event_fingerprint_uidx
            ON voip_call_event (voip_config_id, feed, fingerprint)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS voip_call_event_worklist_idx
            ON voip_call_event (processing_state, next_retry_at)
            WHERE processing_state IN ('pending', 'retry')
        """)

    voip_config_id = fields.Many2one(
        'voip.config', string='Connection', required=True, ondelete='cascade',
        index=True)
    company_id = fields.Many2one(
        'res.company', related='voip_config_id.company_id', store=True,
        index=True)

    feed = fields.Selection([
        ('cdr', 'Completed call record'),
        ('state', 'Live call event'),
        ('client', 'Browser telemetry'),
    ], string='Feed', required=True, index=True)

    received_at = fields.Datetime(string='Received', required=True,
                                  default=fields.Datetime.now, index=True)
    provider_time = fields.Datetime(
        string='Phone System Time',
        help='The time the phone system says this happened, converted from '
             'its own time zone. Independent of when we received it.')
    delivery_id = fields.Char(
        string='Delivery Reference', index=True,
        help='The supplier’s msgid. Kept as text; whether it is unique per '
             'delivery has not been confirmed, so it is not used as the only '
             'duplicate key.')
    fingerprint = fields.Char(
        string='Content Fingerprint', required=True, index=True,
        help='A hash of the meaningful content. Two deliveries that say the '
             'same thing collapse to one row.')

    canonical_type = fields.Selection([
        ('final_cdr', 'Final call record'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('ended_pending_cdr', 'Ended, record pending'),
        ('client_event', 'Browser event'),
        ('unknown', 'Not recognised'),
    ], string='Meaning', required=True, default='unknown', index=True)
    raw_state_token = fields.Char(
        string='Raw State',
        help='Exactly what the phone system sent, before interpretation.')

    transport = fields.Selection([
        ('get', 'GET query'),
        ('post_json', 'POST JSON'),
        ('post_form', 'POST form'),
        ('internal', 'Internal'),
    ], string='Transport', default='get')
    auth_method = fields.Selection([
        ('url_token', 'Address token'),
        ('url_token_param_auth', 'Address token + auth value'),
        ('hmac', 'Signature'),
        ('session', 'Signed-in user'),
    ], string='Authenticated By', default='url_token')

    payload_redacted = fields.Text(
        string='Message (redacted)',
        help='What arrived, with recording links and any auth value removed.')
    payload_raw = fields.Text(
        string='Message (raw)', groups='base.group_system',
        help='Kept only while the connection’s raw-event retention allows it.')

    processing_state = fields.Selection([
        ('pending', 'Waiting'),
        ('retry', 'Retrying'),
        ('processed', 'Processed'),
        ('quarantined', 'Needs review'),
        ('ignored', 'Ignored'),
    ], string='Processing', required=True, default='pending', index=True,
        tracking=False)
    attempts = fields.Integer(default=0)
    next_retry_at = fields.Datetime(index=True)
    processed_at = fields.Datetime(readonly=True)
    error_code = fields.Char(string='Reason')
    error_detail = fields.Text(string='Detail', groups='base.group_system')
    parser_version = fields.Char(readonly=True)
    projection_version = fields.Integer(default=0, readonly=True)

    session_id = fields.Many2one('voip.call.session', string='Call',
                                 ondelete='set null', index=True)
    leg_id = fields.Many2one('voip.call.leg', string='Leg',
                             ondelete='set null', index=True)
    call_log_id = fields.Many2one('voip.call.log', string='Call Record',
                                  ondelete='set null', index=True)

    display_reference = fields.Char(compute='_compute_display_reference')

    @api.depends('feed', 'canonical_type', 'delivery_id', 'received_at')
    def _compute_display_reference(self):
        for event in self:
            event.display_reference = '%s · %s · %s' % (
                dict(self._fields['feed'].selection).get(event.feed, event.feed),
                dict(self._fields['canonical_type'].selection).get(
                    event.canonical_type, event.canonical_type),
                event.delivery_id or event.received_at or '')

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    @api.model
    def _ingest(self, config, feed, normalised, *, transport, auth_method,
                payload_redacted, payload_raw=None):
        """Insert one inbox row. Returns ``(record, created)``.

        Duplicate deliveries are NOT an error: the unique index is the
        contract, and a duplicate returns the existing row so the receiver can
        answer 200 without pretending it stored something twice.

        §5.3 — pre-check before ``super()``: a raw IntegrityError here would
        poison the request transaction, and the receiver still has to answer.
        """
        existing = self.sudo().search([
            ('voip_config_id', '=', config.id),
            ('feed', '=', feed),
            ('fingerprint', '=', normalised['fingerprint']),
        ], limit=1)
        if existing:
            existing._note_repeat(normalised)
            return existing, False

        keep_raw = (config.event_retention_days or 0) > 0
        vals = {
            'voip_config_id': config.id,
            'feed': feed,
            'fingerprint': normalised['fingerprint'],
            'delivery_id': normalised.get('delivery_id') or False,
            'canonical_type': normalised.get('canonical_type') or 'unknown',
            'raw_state_token': normalised.get('raw_state_token') or False,
            'provider_time': normalised.get('provider_time') or False,
            'transport': transport,
            'auth_method': auth_method,
            'payload_redacted': (payload_redacted or '')[:MAX_PAYLOAD_CHARS],
            'payload_raw': ((payload_raw or '')[:MAX_PAYLOAD_CHARS]
                            if keep_raw else False),
            'parser_version': normalised.get('parser_version') or False,
            'processing_state': (
                'quarantined' if normalised.get('quarantine_reason')
                else 'pending'),
            'error_code': normalised.get('quarantine_reason') or False,
        }
        try:
            with self.env.cr.savepoint():
                record = self.sudo().create(vals)
        except Exception as exc:  # noqa: BLE001 — concurrent identical delivery
            # §5.55: the savepoint is what keeps the receiver's transaction
            # alive so it can still answer, instead of dying with "current
            # transaction is aborted".
            _logger.info('VoIP24h event insert collided (config %s, feed %s): '
                         '%s', config.id, feed, type(exc).__name__)
            record = self.sudo().search([
                ('voip_config_id', '=', config.id),
                ('feed', '=', feed),
                ('fingerprint', '=', normalised['fingerprint']),
            ], limit=1)
            if not record:
                raise
            return record, False
        return record, True

    def _note_repeat(self, normalised):
        """A second delivery of content we already hold.

        Nothing about the business record changes. We record only that it
        happened, because a provider that re-delivers constantly is an
        operational fact worth seeing.
        """
        self.ensure_one()
        _logger.debug('VoIP24h duplicate delivery for event %s', self.id)

    # ------------------------------------------------------------------
    # Worker protocol
    # ------------------------------------------------------------------

    @api.model
    def _claim_batch(self, limit=50, config=None):
        """Lock a batch of due events for this worker.

        ``FOR UPDATE SKIP LOCKED`` is what lets several workers drain the
        inbox at once without processing the same row twice.
        """
        params = [fields.Datetime.now()]
        config_clause = ''
        if config:
            config_clause = 'AND voip_config_id = %s'
            params.append(config.id)
        params.append(limit)
        self.env.cr.execute("""
            SELECT id FROM voip_call_event
             WHERE processing_state IN ('pending', 'retry')
               AND (next_retry_at IS NULL OR next_retry_at <= %%s)
               %s
             ORDER BY received_at, id
             LIMIT %%s
             FOR UPDATE SKIP LOCKED
        """ % config_clause, tuple(params))
        ids = [row[0] for row in self.env.cr.fetchall()]
        return self.sudo().browse(ids)

    def _mark_processed(self, *, session=None, leg=None, call_log=None,
                        projection_version=0):
        self.ensure_one()
        self.sudo().write({
            'processing_state': 'processed',
            'processed_at': fields.Datetime.now(),
            'error_code': False,
            'error_detail': False,
            'next_retry_at': False,
            'session_id': session.id if session else False,
            'leg_id': leg.id if leg else False,
            'call_log_id': call_log.id if call_log else False,
            'projection_version': projection_version,
        })

    def _mark_retry(self, code, detail=''):
        """A transient failure. Backs off; never loses the event."""
        self.ensure_one()
        attempts = (self.attempts or 0) + 1
        if attempts > len(RETRY_SCHEDULE):
            return self._mark_quarantined(
                code, detail or 'retries exhausted')
        delay = RETRY_SCHEDULE[attempts - 1]
        self.sudo().write({
            'processing_state': 'retry',
            'attempts': attempts,
            'next_retry_at': fields.Datetime.now() + timedelta(seconds=delay),
            'error_code': code,
            'error_detail': (detail or '')[:4000],
        })

    def _mark_quarantined(self, code, detail=''):
        """A permanent failure, or one we refuse to guess our way past.

        Quarantine is deliberately visible and deliberately inert: the event
        is kept whole, nothing is projected from it, and no default answered
        call is invented to make the number tidy.
        """
        self.ensure_one()
        self.sudo().write({
            'processing_state': 'quarantined',
            'attempts': (self.attempts or 0) + 1,
            'next_retry_at': False,
            'error_code': code,
            'error_detail': (detail or '')[:4000],
        })

    def action_replay(self):
        """Re-run the original, immutable event through the normal reducer.

        Replay must not duplicate calls, activities or notifications — which
        it cannot, because every downstream write is keyed on the event's own
        identity and the effect outbox dedupes on a business key.
        """
        self.ensure_one()
        if not self.env.user.has_group('health_voip24h.group_voip_operator'):
            raise UserError(_(
                'Only an integration operator can replay phone system '
                'messages.'))
        self.sudo().write({
            'processing_state': 'pending',
            'next_retry_at': False,
            'attempts': 0,
            'error_code': False,
            'error_detail': False,
        })
        self.voip_config_id.sudo().message_post(body=_(
            '%(user)s re-processed phone system message %(ref)s.',
            user=self.env.user.display_name, ref=self.display_reference))
        from ..services.event_worker import drain_events
        drain_events(self.env, config=self.voip_config_id, limit=1)
        return True

    def action_ignore(self):
        self.ensure_one()
        if not self.env.user.has_group('health_voip24h.group_voip_operator'):
            raise UserError(_(
                'Only an integration operator can set a message aside.'))
        self.sudo().write({'processing_state': 'ignored', 'next_retry_at': False})
        return True

    # ------------------------------------------------------------------

    @api.model
    def _cron_drain(self):
        """Safety net for anything the inline projection did not finish."""
        from ..services.event_worker import drain_events
        return drain_events(self.env, limit=200)

    # ------------------------------------------------------------------

    def payload_dict(self):
        """The normalised payload this event was built from.

        Reads the redacted copy, which is the one that always exists. The raw
        copy is subject to retention and is never required for reprocessing —
        normalisation happened before storage on purpose.

        Datetimes come back as datetimes. JSON has none, so they are written
        out and read back through an explicit converter; leaving them as
        strings is the kind of defect that only fires on the branch that does
        arithmetic with them.
        """
        self.ensure_one()
        from ..services.event_normalizer import load_normalised
        return load_normalised(self.payload_redacted)
