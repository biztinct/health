# -*- coding: utf-8 -*-

import logging
import json
from datetime import datetime, timedelta, timezone
from odoo import fields

_logger = logging.getLogger(__name__)


def sync_call_history(config, from_date=None, to_date=None, create_recordings=True):
    """
    Synchronize call history from VoIP24h.

    Args:
        config: voip.config record
        from_date: Start date (defaults to last sync or 30 days ago)
        to_date: End date (defaults to now)
        create_recordings: also create pending voip.call.recording stubs

    Returns:
        dict: Sync results
    """
    from .voip24h_api import VoIP24hAPI

    try:
        api = VoIP24hAPI(config)

        # Determine date range (naive UTC — Odoo Datetime convention).
        # Overlap the last sync window by a few minutes so late-written
        # CDRs on the provider side are not skipped.
        if not from_date:
            if config.last_sync_date:
                from_date = config.last_sync_date - timedelta(minutes=5)
            else:
                from_date = datetime.utcnow() - timedelta(days=config.sync_history_days or 30)

        if not to_date:
            to_date = datetime.utcnow()

        # Fetch call history with pagination
        _logger.info('Syncing call history from %s to %s', from_date, to_date)
        page_size = 500
        offset = 0
        calls = []
        while True:
            batch = api.get_call_history(
                from_date=from_date, to_date=to_date,
                limit=page_size, offset=offset)
            calls.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
            if offset >= 50000:  # runaway backstop
                _logger.warning('CDR sync stopped at %s records (backstop)', offset)
                break

        # Process calls in batches
        created_count = 0
        updated_count = 0
        error_count = 0

        for call_data in calls:
            try:
                result = process_call_record(config, call_data,
                                             create_recordings=create_recordings)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
            except Exception as e:
                _logger.error(f'Failed to process call {call_data.get("call_id")}: {e}')
                error_count += 1

        # Update sync statistics
        config.write({
            'last_sync_date': fields.Datetime.now(),
            'total_calls_synced': config.total_calls_synced + created_count,
        })

        result = {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count,
            'total': len(calls),
        }

        _logger.info(f'Sync completed: {result}')
        return result

    except Exception as e:
        _logger.error(f'Call history sync failed: {e}', exc_info=True)
        raise


def process_call_record(config, call_data, create_recordings=True):
    """
    Process a single call record from VoIP24h.

    Args:
        config: voip.config record
        call_data: Call data from API
        create_recordings: create a pending recording stub when advertised

    Returns:
        str: 'created', 'updated', or 'skipped'
    """
    env = config.env

    # Check if call already exists
    call_id = call_data.get('call_id')
    existing_call = env['voip.call.log'].search([
        ('call_id', '=', call_id),
        ('voip_config_id', '=', config.id)
    ], limit=1)

    # Parse call data
    vals = parse_call_data(config, call_data)

    if existing_call:
        # Update existing call
        existing_call.write(vals)
        return 'updated'
    else:
        # Create new call log
        call_log = env['voip.call.log'].create(vals)

        # Auto-match to contact/lead
        auto_match_call(call_log)

        # Download recording if available
        if create_recordings and call_data.get('has_recording'):
            schedule_recording_download(call_log, call_data)

        return 'created'


def parse_call_data(config, call_data):
    """
    Parse call data from VoIP24h API into Odoo fields.

    Args:
        config: voip.config record
        call_data: Raw call data from API

    Returns:
        dict: Values for voip.call.log
    """
    # Clamp API values onto our Selection fields — an unknown value from the
    # provider must not crash the whole sync batch.
    direction = call_data.get('direction', 'incoming')
    if direction not in ('incoming', 'outgoing', 'internal'):
        direction = 'incoming'
    call_type = call_data.get('call_type', 'answered')
    if call_type not in ('answered', 'missed', 'abandoned', 'voicemail', 'failed', 'busy'):
        call_type = 'answered'
    call_status = call_data.get('status', 'completed')
    if call_status not in ('completed', 'no_answer', 'busy', 'failed', 'cancelled'):
        call_status = 'completed'

    return {
        'call_id': call_data.get('call_id'),
        'voip_config_id': config.id,
        'direction': direction,
        'call_type': call_type,
        'caller_number': call_data.get('caller_number'),
        'called_number': call_data.get('called_number'),
        'extension_number': call_data.get('extension'),
        'call_date': parse_datetime(call_data.get('call_date'))
                     or parse_datetime(call_data.get('start_time'))
                     or fields.Datetime.now(),  # field is required
        'start_time': parse_datetime(call_data.get('start_time')),
        'answer_time': parse_datetime(call_data.get('answer_time')),
        'end_time': parse_datetime(call_data.get('end_time')),
        'duration_seconds': call_data.get('duration', 0),
        'talk_duration_seconds': call_data.get('talk_duration', 0),
        'wait_duration_seconds': call_data.get('wait_duration', 0),
        'call_status': call_status,
        'hangup_cause': call_data.get('hangup_cause'),
        'has_recording': call_data.get('has_recording', False),
        'raw_data': json.dumps(call_data),
        'state': 'new',
    }


def parse_datetime(date_string):
    """Parse an ISO datetime string from the API into naive UTC.

    Odoo Datetime fields reject timezone-aware values — convert aware
    datetimes to UTC and strip the tzinfo.
    """
    if not date_string:
        return False

    try:
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return False

    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def auto_match_call(call_log):
    """
    Auto-match call to contact or lead.

    Args:
        call_log: voip.call.log record
    """
    try:
        phone_number = call_log.caller_number if call_log.direction == 'incoming' else call_log.called_number

        if not phone_number:
            return

        # Try to match to partner
        partner = call_log.auto_match_contact_from_phone(phone_number)

        if partner:
            call_log.write({
                'partner_id': partner.id,
                'auto_matched': True,
                'match_confidence': 'high',
            })
            _logger.info(f'Auto-matched call {call_log.call_id} to partner {partner.name}')
        else:
            # Try to match to lead
            # NOTE: crm.lead has no `mobile` field in this Odoo 19 build
            lead = call_log.env['crm.lead'].search([
                ('phone', '=', phone_number),
            ], limit=1)

            if lead:
                call_log.write({
                    'lead_id': lead.id,
                    'auto_matched': True,
                    'match_confidence': 'high',
                })
                _logger.info(f'Auto-matched call {call_log.call_id} to lead {lead.name}')

    except Exception as e:
        _logger.error(f'Auto-match failed for call {call_log.call_id}: {e}')


def schedule_recording_download(call_log, call_data):
    """
    Schedule recording download for a call.

    Args:
        call_log: voip.call.log record
        call_data: Raw call data from API
    """
    try:
        recording_url = call_data.get('recording_url')

        if not recording_url:
            return

        # Create recording record
        call_log.env['voip.call.recording'].create({
            'call_log_id': call_log.id,
            'recording_url': recording_url,
            'recording_id': call_data.get('recording_id'),
            'duration_seconds': call_data.get('talk_duration', 0),
            'state': 'pending',
        })

    except Exception as e:
        _logger.error(f'Failed to schedule recording download: {e}')


def sync_recordings(call_logs):
    """
    Download recordings for call logs.

    Args:
        call_logs: voip.call.log recordset
    """
    from .voip24h_api import VoIP24hAPI

    for call_log in call_logs:
        if not call_log.has_recording:
            continue

        try:
            api = VoIP24hAPI(call_log.voip_config_id)

            # Get recording URL
            recording_url = api.get_recording_url(call_log.call_id)

            if recording_url:
                # Download recording
                file_data = api.download_recording(recording_url)

                # Update recording record
                for recording in call_log.recording_ids:
                    recording.write({
                        'recording_file': file_data,
                        'is_downloaded': True,
                        'downloaded_date': fields.Datetime.now(),
                        'state': 'available',
                    })

                call_log.voip_config_id.total_recordings_synced += 1

        except Exception as e:
            _logger.error(f'Failed to download recording for call {call_log.call_id}: {e}')
