# -*- coding: utf-8 -*-
"""Handlers for the LEGACY ``/voip24h/webhook`` route.

The five event names below — ``call.started``, ``call.answered``,
``call.ended``, ``call.missed``, ``recording.available`` — are **ours**. No
supplied VoIP24h document mentions any of them. They are kept as internal
canonical names for whatever producer is actually posting to the old route, and
nothing in this module ever REQUIRES VoIP24h to send them.

Everything the v3 receivers handle goes through the inbox, the normaliser and
the reducer instead. This file exists so a deployment with an identified legacy
producer keeps working, and it deliberately does not grow.

The global ``voip_notifications`` bus topic is gone. A topic name is not access
control: anything sent there reached every signed-in browser on the server,
including the caller's number. Notifications now go to one named person's own
channel (``services/event_worker.py``), and this legacy path reuses that.
"""

import logging

from .cdr_sync import parse_datetime, process_call_record, \
    schedule_recording_download

_logger = logging.getLogger(__name__)

_VALID_STATUSES = ('completed', 'no_answer', 'busy', 'failed', 'cancelled')


def process_call_event(env, event_data):
    event_type = event_data.get('event_type')
    call_data = event_data.get('call_data') or {}
    account_id = event_data.get('account_id')

    config = env['voip.config'].sudo().search([
        ('account_id', '=', account_id), ('active', '=', True),
    ], limit=1)
    if not config:
        return {'status': 'error', 'message': 'Configuration not found'}

    handler = {
        'call.started': _handle_started,
        'call.answered': _handle_answered,
        'call.ended': _handle_ended,
        'call.missed': _handle_missed,
        'recording.available': _handle_recording,
    }.get(event_type)
    if not handler:
        _logger.info('Legacy webhook: unrecognised event %r', event_type)
        return {'status': 'ignored', 'message': 'Unknown event type'}

    try:
        return handler(env, config, call_data)
    except Exception as exc:  # noqa: BLE001
        _logger.exception('Legacy webhook handler failed for %s', event_type)
        return {'status': 'error', 'message': str(exc)}


def _find_log(env, config, call_data):
    return env['voip.call.log'].sudo().search([
        ('call_id', '=', call_data.get('call_id')),
        ('voip_config_id', '=', config.id),
    ], limit=1)


def _handle_started(env, config, call_data):
    result = process_call_record(config, call_data)
    if call_data.get('direction') == 'incoming' and \
            config.can_show_incoming_popups():
        log = _find_log(env, config, call_data)
        if log:
            _notify_assigned(env, config, log, 'incoming_ring')
    return {'status': 'success', 'result': result}


def _handle_answered(env, config, call_data):
    log = _find_log(env, config, call_data)
    if log:
        log.with_context(voip_reducer=True).write({
            'call_type': 'answered',
            'answer_time': parse_datetime(call_data.get('answer_time')),
        })
    return {'status': 'success'}


def _handle_ended(env, config, call_data):
    result = process_call_record(config, call_data)
    log = _find_log(env, config, call_data)
    if log:
        status = call_data.get('status')
        # Unknown stays unknown. It is not quietly promoted to "completed".
        if status not in _VALID_STATUSES:
            status = 'unknown'
        vals = {'call_status': status}
        end_time = parse_datetime(call_data.get('end_time'))
        if end_time:
            vals['end_time'] = end_time
        for key, field in (('duration', 'duration_seconds'),
                           ('talk_duration', 'talk_duration_seconds')):
            if call_data.get(key) is not None:
                try:
                    vals[field] = max(int(call_data[key]), 0)
                except (TypeError, ValueError):
                    pass
        log.with_context(voip_reducer=True).write(vals)
        _notify_assigned(env, config, log, 'ended')
    return {'status': 'success', 'result': result}


def _handle_missed(env, config, call_data):
    result = process_call_record(config, call_data)
    log = _find_log(env, config, call_data)
    if log:
        log.with_context(voip_reducer=True).write({'call_type': 'missed'})
        if log.partner_id or log.lead_id:
            try:
                with env.cr.savepoint():
                    log.action_create_activity()
            except Exception as exc:  # noqa: BLE001
                _logger.error('Failed to create activity: %s', exc)
        _notify_assigned(env, config, log, 'missed_inbound')
    return {'status': 'success', 'result': result}


def _handle_recording(env, config, call_data):
    log = _find_log(env, config, call_data)
    if log:
        log.with_context(voip_reducer=True).write({'has_recording': True})
        schedule_recording_download(log, call_data)
    return {'status': 'success'}


def _notify_assigned(env, config, call_log, kind):
    """Tell the people entitled to know. One person, one channel, each.

    Small payload: identifiers and a state. The caller's name and number are
    fetched afterwards through an authenticated call that checks who is asking.
    """
    try:
        users = env['res.users'].sudo().browse()
        if call_log.extension_id and call_log.extension_id.user_id:
            users |= call_log.extension_id.user_id
        if not users:
            group = env.ref('health_voip24h.group_voip_user',
                            raise_if_not_found=False)
            if group:
                users = group.sudo().user_ids.filtered(
                    lambda u: u.active and config.company_id in u.company_ids)
        payload = {
            'kind': kind,
            'session_id': call_log.session_id.id or False,
            'call_log_id': call_log.id,
            'state': 'legacy',
            'version': 0,
        }
        for user in users:
            user._bus_send('voip24h_call', payload)
    except Exception as exc:  # noqa: BLE001 — a bus hiccup never fails ingest
        _logger.error('Legacy call notification failed: %s', exc)
