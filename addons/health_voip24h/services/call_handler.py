# -*- coding: utf-8 -*-

import logging
from .cdr_sync import (
    parse_datetime,
    process_call_record,
    schedule_recording_download,
)

_logger = logging.getLogger(__name__)


def process_call_event(env, event_data):
    """
    Process incoming webhook event from VoIP24h.

    Args:
        env: Odoo environment
        event_data: Event data from webhook

    Returns:
        dict: Processing result
    """
    try:
        event_type = event_data.get('event_type')
        call_data = event_data.get('call_data', {})
        account_id = event_data.get('account_id')

        _logger.info(f'Processing webhook event: {event_type} for call {call_data.get("call_id")}')

        # Find configuration
        config = env['voip.config'].search([
            ('account_id', '=', account_id),
            ('active', '=', True),
        ], limit=1)

        if not config:
            _logger.warning(f'No configuration found for account {account_id}')
            return {'status': 'error', 'message': 'Configuration not found'}

        # Process based on event type
        if event_type == 'call.started':
            return handle_call_started(env, config, call_data)

        elif event_type == 'call.answered':
            return handle_call_answered(env, config, call_data)

        elif event_type == 'call.ended':
            return handle_call_ended(env, config, call_data)

        elif event_type == 'call.missed':
            return handle_call_missed(env, config, call_data)

        elif event_type == 'recording.available':
            return handle_recording_available(env, config, call_data)

        else:
            _logger.warning(f'Unknown event type: {event_type}')
            return {'status': 'ignored', 'message': f'Unknown event type: {event_type}'}

    except Exception as e:
        _logger.error(f'Webhook processing error: {e}', exc_info=True)
        return {'status': 'error', 'message': str(e)}


def handle_call_started(env, config, call_data):
    """Handle call.started event"""
    try:
        # Create or update call log
        result = process_call_record(config, call_data)

        # Trigger incoming call popup if enabled
        if call_data.get('direction') == 'incoming' and config.can_show_incoming_popups():
            call_log = env['voip.call.log'].search([
                ('call_id', '=', call_data.get('call_id')),
                ('voip_config_id', '=', config.id)
            ], limit=1)

            if call_log:
                send_incoming_call_notification(call_log)

        return {'status': 'success', 'result': result}

    except Exception as e:
        _logger.error(f'Failed to handle call.started: {e}')
        return {'status': 'error', 'message': str(e)}


def handle_call_answered(env, config, call_data):
    """Handle call.answered event"""
    try:
        call_log = env['voip.call.log'].search([
            ('call_id', '=', call_data.get('call_id')),
            ('voip_config_id', '=', config.id)
        ], limit=1)

        if call_log:
            call_log.write({
                'call_type': 'answered',
                'answer_time': parse_datetime(call_data.get('answer_time')),
            })

        return {'status': 'success'}

    except Exception as e:
        _logger.error(f'Failed to handle call.answered: {e}')
        return {'status': 'error', 'message': str(e)}


def handle_call_ended(env, config, call_data):
    """Handle call.ended event"""
    try:
        result = process_call_record(config, call_data)

        call_log = env['voip.call.log'].search([
            ('call_id', '=', call_data.get('call_id')),
            ('voip_config_id', '=', config.id)
        ], limit=1)

        if call_log:
            # Update call log with final data
            call_status = call_data.get('status', 'completed')
            if call_status not in ('completed', 'no_answer', 'busy', 'failed', 'cancelled'):
                call_status = 'completed'
            call_log.write({
                'end_time': parse_datetime(call_data.get('end_time')),
                'duration_seconds': call_data.get('duration', 0),
                'talk_duration_seconds': call_data.get('talk_duration', 0),
                'call_status': call_status,
            })

            # Send call ended notification
            send_call_ended_notification(call_log)

        return {'status': 'success', 'result': result}

    except Exception as e:
        _logger.error(f'Failed to handle call.ended: {e}')
        return {'status': 'error', 'message': str(e)}


def handle_call_missed(env, config, call_data):
    """Handle call.missed event"""
    try:
        # Process call record
        result = process_call_record(config, call_data)

        call_log = env['voip.call.log'].search([
            ('call_id', '=', call_data.get('call_id')),
            ('voip_config_id', '=', config.id)
        ], limit=1)

        if call_log:
            call_log.write({'call_type': 'missed'})

            # Auto-create activity for missed call if partner/lead is matched
            if call_log.partner_id or call_log.lead_id:
                try:
                    call_log.action_create_activity()
                except Exception as e:
                    _logger.error(f'Failed to create activity: {e}')

        return {'status': 'success', 'result': result}

    except Exception as e:
        _logger.error(f'Failed to handle call.missed: {e}')
        return {'status': 'error', 'message': str(e)}


def handle_recording_available(env, config, call_data):
    """Handle recording.available event"""
    try:
        call_log = env['voip.call.log'].search([
            ('call_id', '=', call_data.get('call_id')),
            ('voip_config_id', '=', config.id)
        ], limit=1)

        if call_log:
            call_log.write({'has_recording': True})
            schedule_recording_download(call_log, call_data)

        return {'status': 'success'}

    except Exception as e:
        _logger.error(f'Failed to handle recording.available: {e}')
        return {'status': 'error', 'message': str(e)}


def send_incoming_call_notification(call_log):
    """
    Send bus notification for incoming call popup.

    Args:
        call_log: voip.call.log record
    """
    try:
        payload = {
            'call_id': call_log.call_id,
            'call_log_id': call_log.id,
            'caller_number': call_log.caller_number,
            'partner_id': call_log.partner_id.id if call_log.partner_id else False,
            'partner_name': call_log.partner_id.name if call_log.partner_id else False,
            'lead_id': call_log.lead_id.id if call_log.lead_id else False,
            'lead_name': call_log.lead_id.name if call_log.lead_id else False,
        }

        # Clone of health_zalo message_handler bus pattern
        # (services/message_handler.py:256): _sendone(channel, type, payload)
        call_log.env['bus.bus']._sendone(
            'voip_notifications',
            'voip_incoming_call',
            payload,
        )

        _logger.info('Sent incoming call notification for %s', call_log.call_id)

    except Exception as e:
        _logger.error('Failed to send incoming call notification: %s', e)


def send_call_ended_notification(call_log):
    """
    Send bus notification for call ended.

    Args:
        call_log: voip.call.log record
    """
    try:
        payload = {
            'call_id': call_log.call_id,
            'call_log_id': call_log.id,
            'duration_display': call_log.duration_display,
        }

        call_log.env['bus.bus']._sendone(
            'voip_notifications',
            'voip_call_ended',
            payload,
        )

    except Exception as e:
        _logger.error('Failed to send call ended notification: %s', e)
