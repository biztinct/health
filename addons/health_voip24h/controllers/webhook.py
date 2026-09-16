# -*- coding: utf-8 -*-
"""Where the phone system talks to us.

Three routes, and the difference between them matters:

``/voip24h/v3/cdr/<receiver>/<token>``     completed call records (Feed A)
``/voip24h/v3/events/<receiver>/<token>``  live call events (Feed B)
``/voip24h/webhook``                       LEGACY, HMAC, kept for identified
                                           producers only

The v3 receivers are authenticated by a 256-bit token in the address. That is
an honest description of what it proves — possession of the address — and not
a signature: it does not prove the body is untouched or the request is fresh.
No supplied VoIP24h document describes a signature, so requiring the invented
HMAC headers the old route used would simply mean refusing every real delivery.
Where a tenant's policy requires signed callbacks, that stays an explicit
activation blocker rather than something this file pretends to satisfy.

The ordering the whole file exists to get right:

1. cheap refusals first — method, size, rate — before any database work;
2. resolve the receiver by its id ALONE (never a query parameter, never
   ``account_id``, never an extension: the database was already chosen by the
   hostname and dbfilter, and nothing in a request body may re-select a
   tenant);
3. constant-time token check, then the connection's ingest lifecycle;
4. decode exactly the transport that arrived;
5. insert the inbox row and let the request transaction commit it;
6. only then answer — and answer 200 only for something that is durably
   stored, deliberately quarantined, or a duplicate of one that already is.

The old route returned HTTP 200 out of a blanket ``except``. That is the one
behaviour this file will not reproduce: a 200 the provider believes and a row
that does not exist is a call that silently never happened.
"""

import json
import logging
import time
from collections import defaultdict

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Proposed limits, to be tuned once real vendor deliveries are captured.
MAX_BODY_BYTES = 256 * 1024
MAX_QUERY_CHARS = 32 * 1024

# Per-receiver sliding window. In-process and therefore per-worker, which is
# fine for its purpose: it is a cheap shield against a delivery storm, not a
# security control. The security control is the token.
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_WINDOW = 600
_rate_buckets = defaultdict(list)

# Query keys whose duplication would be parameter pollution rather than a
# harmless repeat: two different `disposition` values in one URL have no
# honest interpretation.
_CRITICAL_KEYS = ('id', 'callid', 'uniqueid', 'linkedid', 'msgid', 'state',
                  'type', 'disposition', 'src', 'dst', 'calldate', 'billsec',
                  'duration')


def _rate_limited(receiver_id):
    now = time.monotonic()
    bucket = _rate_buckets[receiver_id]
    cutoff = now - _RATE_WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= _RATE_MAX_PER_WINDOW:
        return True
    bucket.append(now)
    return False


def _answer(status, payload=None):
    """A small, uninformative body. No patient data, no diagnostics."""
    return request.make_json_response(payload or {'status': 'ok'},
                                      status=status)


class VoIP24hReceiverController(http.Controller):

    # ==================================================================
    # v3 receivers
    # ==================================================================

    @http.route('/voip24h/v3/cdr/<string:receiver_id>/<string:token>',
                type='http', auth='public', methods=['GET', 'POST'],
                csrf=False, save_session=False, sitemap=False)
    def receive_cdr(self, receiver_id, token, **kwargs):
        return self._receive('cdr', receiver_id, token)

    @http.route('/voip24h/v3/events/<string:receiver_id>/<string:token>',
                type='http', auth='public', methods=['GET', 'POST'],
                csrf=False, save_session=False, sitemap=False)
    def receive_events(self, receiver_id, token, **kwargs):
        return self._receive('state', receiver_id, token)

    # ------------------------------------------------------------------

    def _receive(self, feed, receiver_id, token):
        http_request = request.httprequest

        # --- 1. cheap refusals ----------------------------------------
        if len(http_request.query_string or b'') > MAX_QUERY_CHARS:
            return _answer(413, {'status': 'too_large'})
        content_length = http_request.content_length or 0
        if content_length > MAX_BODY_BYTES:
            return _answer(413, {'status': 'too_large'})
        if _rate_limited(receiver_id):
            _logger.warning('VoIP24h receiver rate limit hit (receiver %s)',
                            receiver_id)
            return _answer(429, {'status': 'slow_down'})

        # --- 2/3. resolve and authenticate ----------------------------
        # A public route: escalate deliberately, and note that every lookup
        # below is scoped by the receiver we resolve here and nothing else.
        env = request.env(su=True)
        config = env['voip.config']._resolve_receiver(receiver_id, feed, token)
        if not config:
            # Same answer for an unknown receiver and a wrong token, so the
            # route is not an oracle for which clinics live here. The log line
            # carries the receiver id (public) and never the token.
            _logger.warning('VoIP24h %s callback refused (receiver %r)',
                            feed, receiver_id)
            return _answer(403, {'status': 'denied'})

        if not self._source_allowed(config):
            _logger.warning('VoIP24h %s callback from a disallowed source '
                            '(config %s)', feed, config.id)
            return _answer(403, {'status': 'denied'})

        enabled = (config.cdr_ingest_enabled if feed == 'cdr'
                   else config.state_ingest_enabled)
        if not config.active or not enabled:
            # Authenticated traffic for a switched-off feed: acknowledge, audit
            # in bounded form, change no business record and touch no readiness
            # timestamp.
            _logger.info('VoIP24h %s callback ignored: feed disabled '
                         '(config %s)', feed, config.id)
            self._note_channel_ignore(env, config, feed)
            return _answer(200, {'status': 'ignored'})

        # --- 4. decode exactly what arrived ---------------------------
        try:
            data, transport = self._decode(http_request)
        except _MalformedTransport as exc:
            _logger.info('VoIP24h %s callback malformed (config %s): %s',
                         feed, config.id, exc)
            return _answer(400, {'status': 'malformed'})

        if not data:
            return _answer(400, {'status': 'empty'})

        # --- 5. normalise and store -----------------------------------
        from ..services import event_normalizer

        try:
            if feed == 'cdr':
                normalised = event_normalizer.normalise_final_record(config, data)
            else:
                normalised = event_normalizer.normalise_state_event(config, data)
        except Exception:  # noqa: BLE001 — a parser bug must not lose the event
            _logger.exception('VoIP24h %s normalisation failed (config %s)',
                              feed, config.id)
            normalised = {
                'fingerprint': event_normalizer._fingerprint(
                    config.id, feed, {'raw': sorted(data.items())}),
                'delivery_id': '',
                'canonical_type': 'unknown',
                'raw_state_token': '',
                'provider_time': None,
                'parser_version': 'error',
                'quarantine_reason': 'normaliser_error',
                'data': {},
            }

        redacted = event_normalizer.redact(data)
        try:
            event, created = env['voip.call.event']._ingest(
                config, feed, normalised,
                transport=transport,
                auth_method=config.callback_auth_profile,
                payload_redacted=event_normalizer.dump_normalised(
                    normalised, payload=redacted),
                payload_raw=json.dumps(data, default=str),
            )
        except Exception:  # noqa: BLE001
            # The one case that MUST NOT be a 200: we could not durably store
            # it. A retryable status is the only honest answer, and losing the
            # event behind a false success is exactly what this replaces.
            _logger.exception('VoIP24h %s callback could not be stored '
                              '(config %s)', feed, config.id)
            return _answer(503, {'status': 'retry'})

        self._note_channel_inbound(env, config)

        # --- short inline projection ----------------------------------
        # A one-minute cron is not adequate for a ringing alert, so the state
        # feed is reduced inline, inside a savepoint, with the event left
        # retryable if that fails. All external I/O (recording downloads,
        # provider calls) stays out of the receiver.
        if created and feed == 'state':
            try:
                from ..services.event_worker import drain_events
                drain_events(env, config=config, limit=5)
            except Exception:  # noqa: BLE001
                _logger.exception('VoIP24h inline projection failed; the event '
                                  'is stored and will be retried')

        return _answer(200, {'status': 'accepted' if created else 'duplicate'})

    # ------------------------------------------------------------------

    def _source_allowed(self, config):
        allowed = (config.callback_source_ips or '').strip()
        if not allowed:
            return True
        remote = request.httprequest.remote_addr or ''
        return remote in {ip.strip() for ip in allowed.split(',') if ip.strip()}

    @staticmethod
    def _decode(http_request):
        """Exactly one transport, decoded once.

        V2 documents GET deliveries and the registration API offers POST, but
        a configured POST may carry form data rather than JSON — the vendor
        only ever *demonstrates* GET. All three are accepted and the one that
        actually arrived is recorded on the event, so the capture answers the
        question rather than an assumption doing it.

        URL-decoding happens once, in werkzeug. Nothing here re-decodes, and
        nothing here evaluates a source string.
        """
        method = http_request.method
        if method == 'GET':
            args = http_request.args
            for key in _CRITICAL_KEYS:
                if len(args.getlist(key)) > 1:
                    raise _MalformedTransport('duplicate %s' % key)
            data = {k: args.getlist(k)[0] for k in args.keys()}
            # Bracketed nesting (`cdr[source]=…`) is one of the encodings a
            # GET-delivered object could plausibly use. Assembled here so the
            # normaliser receives a real dict either way.
            nested = {}
            for key in list(data):
                if key.startswith('cdr[') and key.endswith(']'):
                    nested[key[4:-1]] = data.pop(key)
            if nested:
                data['cdr'] = nested
            return data, 'get'

        content_type = (http_request.content_type or '').split(';')[0].strip()
        raw = http_request.get_data() or b''
        if content_type == 'application/json':
            try:
                parsed = json.loads(raw.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError) as exc:
                raise _MalformedTransport('bad json') from exc
            if not isinstance(parsed, dict):
                raise _MalformedTransport('json is not an object')
            return parsed, 'post_json'
        if content_type in ('application/x-www-form-urlencoded',
                            'multipart/form-data'):
            form = http_request.form
            for key in _CRITICAL_KEYS:
                if len(form.getlist(key)) > 1:
                    raise _MalformedTransport('duplicate %s' % key)
            return {k: form.getlist(k)[0] for k in form.keys()}, 'post_form'
        # An unlabelled body that happens to be JSON is common enough to be
        # worth one attempt, and refusing it outright would lose real calls.
        try:
            parsed = json.loads(raw.decode('utf-8') or '{}')
            if isinstance(parsed, dict) and parsed:
                return parsed, 'post_json'
        except (ValueError, UnicodeDecodeError):
            pass
        raise _MalformedTransport('unsupported content type %r' % content_type)

    @staticmethod
    def _note_channel_inbound(env, config):
        try:
            conn = config._channel_connection()
            if conn:
                conn._note_inbound()
        except Exception:  # noqa: BLE001 — bookkeeping never fails a receipt
            _logger.debug('Channel inbound note failed for config %s',
                          config.id)

    @staticmethod
    def _note_channel_ignore(env, config, feed):
        try:
            if 'care.channel.audit' in env:
                conn = config._channel_connection()
                if conn:
                    env['care.channel.audit']._log(
                        'webhook_ignored', connection=conn,
                        detail='%s feed disabled' % feed)
        except Exception:  # noqa: BLE001
            _logger.debug('Channel ignore note failed for config %s', config.id)


class _MalformedTransport(Exception):
    pass


class VoIP24hLegacyWebhookController(http.Controller):
    """The pre-v3 route. Kept ONLY for producers that are known to use it.

    Nothing in the supplied VoIP24h documentation produces this shape, so on a
    deployment with no identified legacy producer this route should be retired
    outright. Until that is established it keeps working exactly as it did —
    including its fail-closed HMAC — and it is deliberately NOT extended to
    understand v3 payloads. Re-pointing it at the new parsers would mean
    accepting an anonymous GET on a route whose whole contract is a signed
    POST.
    """

    @http.route('/voip24h/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def handle_webhook(self, **kwargs):
        try:
            from ..services.call_handler import process_call_event
            from ..models.voip_config import verify_voip_signature

            raw_body = request.httprequest.get_data()
            if len(raw_body or b'') > MAX_BODY_BYTES:
                return request.make_json_response({'status': 'too_large'}, 413)
            try:
                event_data = json.loads(raw_body) if raw_body else {}
            except ValueError:
                return request.make_json_response(
                    {'status': 'error', 'message': 'Invalid JSON'}, 400)
            if not isinstance(event_data, dict) or not event_data:
                return request.make_json_response(
                    {'status': 'error', 'message': 'Empty payload'}, 400)

            env = request.env(su=True)
            account_id = event_data.get('account_id')
            config = env['voip.config'].search(
                [('account_id', '=', account_id)], limit=1)
            connection = env['voip.config']._route_channel_connection(
                config, account_id)

            if not config and not connection:
                _logger.warning('VoIP24h legacy webhook for unknown account')
                return request.make_json_response({'status': 'ignored'}, 200)

            signature = (
                request.httprequest.headers.get('X-Voip24h-Signature')
                or request.httprequest.headers.get('X-Signature'))

            if config:
                if not connection and not config.webhook_enabled:
                    return request.make_json_response(
                        {'status': 'ignored', 'message': 'Webhook disabled'},
                        200)
                verified = config._verify_webhook_signature(
                    raw_body, signature, connection=connection)
            else:
                secret = connection.sudo()._get_secret('provider_secret')
                verified = verify_voip_signature(secret, raw_body, signature)

            if not verified:
                return request.make_json_response(
                    {'status': 'error', 'message': 'Invalid signature'}, 403)

            if config:
                if config._note_channel_event(
                        event_data.get('event_type'),
                        connection=connection) == 'ignored':
                    return request.make_json_response({'status': 'ignored'}, 200)
                result = process_call_event(env, event_data)
                return request.make_json_response(result, 200)

            if not connection._may_ingest():
                env['care.channel.audit']._log(
                    'webhook_ignored', connection=connection,
                    detail='call event while %s' % connection.state)
                self._capture_call(env, connection, event_data, 'not_ingestable')
                return request.make_json_response({'status': 'ignored'}, 200)
            self._capture_call(env, connection, event_data, 'no_voip_config')
            connection._note_inbound()
            return request.make_json_response({'status': 'success'}, 200)

        except Exception:  # noqa: BLE001
            _logger.exception('Legacy webhook processing error')
            # 503, not 200. A provider that retries is better than an event
            # nobody ever hears about again.
            return request.make_json_response({'status': 'retry'}, 503)

    @staticmethod
    def _capture_call(env, connection, event_data, reason):
        if 'care.contact.capture' not in env:
            return
        data = event_data or {}
        caller = (data.get('caller_number') or data.get('from')
                  or data.get('caller') or '')
        env['care.contact.capture']._capture(
            reason, 'call', connection=connection,
            peer_hint=caller, phone=caller,
            body=data.get('event_type') or '',
            external_event_id=data.get('call_id') or data.get('uuid') or None,
            raw=str(data))
