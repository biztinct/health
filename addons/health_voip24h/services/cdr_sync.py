# -*- coding: utf-8 -*-
"""Legacy polling path.

Kept because historical rows and an existing wizard reference it, and because a
confirmed past-calls interface is a real possibility (gate G11). What has
changed is what it is allowed to invent.

The previous version defaulted an unknown call type to ``answered``, an unknown
status to ``completed``, and a missing call date to ``now``. Each of those
turns "we do not know" into "it went fine", which is the one thing a call
record must never do. All three now produce an explicit ``unknown``, and a
record with no usable call time is SKIPPED rather than stamped with the time
the sync happened to run.

Nothing in this module reaches the network unless
``voip.config.history_sync_verified`` is on — the adapter refuses first.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from odoo import fields

_logger = logging.getLogger(__name__)

VALID_DIRECTIONS = ('incoming', 'outgoing', 'internal')
VALID_CALL_TYPES = ('answered', 'missed', 'abandoned', 'voicemail', 'failed',
                    'busy')
VALID_STATUSES = ('completed', 'no_answer', 'busy', 'failed', 'cancelled')


def sync_call_history(config, from_date=None, to_date=None,
                      create_recordings=True):
    """Pull past calls. Refuses unless the interface has been confirmed."""
    from .voip24h_api import VoIP24hAPI

    config._check_credentials()
    api = VoIP24hAPI(config)

    if not from_date:
        if config.last_sync_date:
            from_date = config.last_sync_date - timedelta(minutes=5)
        else:
            from_date = datetime.utcnow() - timedelta(
                days=config.sync_history_days or 30)
    if not to_date:
        to_date = datetime.utcnow()

    _logger.info('Syncing call history from %s to %s', from_date, to_date)
    page_size, offset, calls = 500, 0, []
    while True:
        batch = api.get_call_history(from_date=from_date, to_date=to_date,
                                     limit=page_size, offset=offset)
        calls.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
        if offset >= 50000:
            _logger.warning('CDR sync stopped at %s records (backstop)', offset)
            break

    created = updated = errors = skipped = 0
    for call_data in calls:
        try:
            with config.env.cr.savepoint():
                result = process_call_record(
                    config, call_data, create_recordings=create_recordings)
            if result == 'created':
                created += 1
            elif result == 'updated':
                updated += 1
            elif result == 'skipped':
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            _logger.error('Failed to process call %s: %s',
                          call_data.get('call_id'), exc)
            errors += 1

    config.write({
        'last_sync_date': fields.Datetime.now(),
        'total_calls_synced': (config.total_calls_synced or 0) + created,
    })
    result = {'created': created, 'updated': updated, 'errors': errors,
              'skipped': skipped, 'total': len(calls)}
    _logger.info('Sync completed: %s', result)
    return result


def process_call_record(config, call_data, create_recordings=True):
    """One record from the polling path. Returns created/updated/skipped."""
    env = config.env
    call_id = call_data.get('call_id')
    if not call_id:
        return 'skipped'

    vals = parse_call_data(config, call_data)
    if vals is None:
        return 'skipped'

    existing = env['voip.call.log'].sudo().search([
        ('call_id', '=', call_id),
        ('voip_config_id', '=', config.id),
    ], limit=1)

    if existing:
        existing.with_context(voip_reducer=True).write(vals)
        return 'updated'

    call_log = env['voip.call.log'].with_context(voip_reducer=True).create(vals)
    auto_match_call(call_log)
    if create_recordings and call_data.get('has_recording'):
        schedule_recording_download(call_log, call_data)
    return 'created'


def parse_call_data(config, call_data):
    """Values for one call log, or None when there is nothing safe to write.

    An unrecognised value becomes ``unknown`` and is flagged; a record with no
    parsable call time is refused outright, because ``fields.Datetime.now()``
    would file a call from last Tuesday under this afternoon.
    """
    quality = []

    direction = call_data.get('direction')
    if direction not in VALID_DIRECTIONS:
        quality.append('direction=%s' % direction)
        direction = 'unknown'

    call_type = call_data.get('call_type')
    if call_type not in VALID_CALL_TYPES:
        quality.append('call_type=%s' % call_type)
        call_type = 'unknown'

    call_status = call_data.get('status')
    if call_status not in VALID_STATUSES:
        quality.append('status=%s' % call_status)
        call_status = 'unknown'

    call_date = (parse_datetime(call_data.get('call_date'))
                 or parse_datetime(call_data.get('start_time')))
    if not call_date:
        _logger.warning('Skipping call %s: no usable call time',
                        call_data.get('call_id'))
        return None

    return {
        'call_id': call_data.get('call_id'),
        'voip_config_id': config.id,
        'source_profile': 'legacy',
        'import_source': 'history_poll',
        'direction': direction,
        'call_type': call_type,
        'call_status': call_status,
        'caller_number': call_data.get('caller_number'),
        'called_number': call_data.get('called_number'),
        'extension_number': call_data.get('extension'),
        'call_date': call_date,
        'start_time': parse_datetime(call_data.get('start_time')),
        'answer_time': parse_datetime(call_data.get('answer_time')),
        'end_time': parse_datetime(call_data.get('end_time')),
        'duration_seconds': _non_negative(call_data.get('duration')),
        'talk_duration_seconds': _non_negative(call_data.get('talk_duration')),
        'wait_duration_seconds': _non_negative(call_data.get('wait_duration')),
        'hangup_cause': call_data.get('hangup_cause'),
        'has_recording': bool(call_data.get('has_recording')),
        'raw_data': json.dumps(call_data, default=str),
        'timestamp_timezone': config.provider_timezone,
        'data_quality_state': 'flagged' if quality else 'ok',
        'data_quality_note': '\n'.join(quality) or False,
        'state': 'new',
    }


def _non_negative(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def parse_datetime(date_string):
    """ISO-ish string -> naive UTC, or False. Never returns "now"."""
    if not date_string:
        return False
    try:
        parsed = datetime.fromisoformat(str(date_string).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return False
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def auto_match_call(call_log):
    """Link the call to exactly one person, or leave it unmatched.

    The old version fell back to a ``like`` search on the last nine digits and
    took the first hit — which is how a call gets filed against whichever
    patient happens to sort first. One match or none.
    """
    try:
        number = (call_log.called_number if call_log.direction == 'outgoing'
                  else call_log.caller_number)
        if not number:
            return
        partner = call_log.auto_match_contact_from_phone(number)
        if partner:
            call_log.write({'partner_id': partner.id, 'auto_matched': True,
                            'match_confidence': 'high'})
            return
        from . import phone_ident
        key = phone_ident.matching_key(number)
        if not key:
            return
        # crm.lead has no `mobile` field on this build (ledger §5.16).
        leads = call_log.env['crm.lead'].search([('phone', '=', key)], limit=2)
        if len(leads) == 1:
            call_log.write({'lead_id': leads.id, 'auto_matched': True,
                            'match_confidence': 'high'})
    except Exception as exc:  # noqa: BLE001 — matching never breaks a sync
        _logger.error('Auto-match failed for call %s: %s',
                      call_log.call_id, exc)


def schedule_recording_download(call_log, call_data):
    """Record that a recording is advertised. Fetches nothing."""
    try:
        url = call_data.get('recording_url')
        if not url:
            return
        call_log.env['voip.call.recording'].sudo().create({
            'call_log_id': call_log.id,
            'recording_url': url,
            'download_url': url,
            'recording_id': call_data.get('recording_id'),
            'duration_seconds': _non_negative(call_data.get('talk_duration')),
            'state': 'advertised',
        })
    except Exception as exc:  # noqa: BLE001
        _logger.error('Failed to record the recording link: %s', exc)


def sync_recordings(call_logs):
    """Fetch recordings for the given logs, through the guarded fetcher."""
    from .recording_fetch import fetch_recording
    for call_log in call_logs:
        for recording in call_log.recording_ids:
            if recording.is_downloaded:
                continue
            fetch_recording(recording)
