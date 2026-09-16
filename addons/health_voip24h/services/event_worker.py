# -*- coding: utf-8 -*-
"""Drain the inbox, then deliver what the inbox produced.

Two drains, deliberately separate:

* :func:`drain_events` turns stored provider messages into call facts. Each
  event is processed in its own savepoint, so one poisonous message cannot take
  the batch down with it (§5.55 — a caught IntegrityError still leaves the
  transaction aborted unless the body ran inside a savepoint).
* :func:`drain_effects` performs what those facts owe: a bus notification to
  one named person, the Care Command projection, a call-back task. Effects are
  delivered AFTER the fact is committed, which is what makes a bridge failure a
  retry instead of a lost call.

``drain_events`` is called inline by the receiver after a durable insert, and
again by a short cron for anything that failed or arrived while a worker was
busy. A one-minute cron alone is not adequate for a ringing notification, which
is precisely why the inline call exists.
"""

import json
import logging

from odoo import fields, _

from .event_reducer import ReduceError, ReduceQuarantine, reduce_event

_logger = logging.getLogger(__name__)


def drain_events(env, config=None, limit=50):
    """Process due inbox rows. Returns a small summary dict."""
    events = env['voip.call.event']._claim_batch(limit=limit, config=config)
    summary = {'processed': 0, 'retried': 0, 'quarantined': 0,
               'ignored': 0, 'total': len(events)}
    for event in events:
        try:
            with env.cr.savepoint():
                result = reduce_event(env, event)
                if result.get('ignored'):
                    summary['ignored'] += 1
                    continue
                event._mark_processed(
                    session=result.get('session'),
                    leg=result.get('leg'),
                    call_log=result.get('call_log'),
                    projection_version=result.get('version') or 0)
                summary['processed'] += 1
        except ReduceQuarantine as exc:
            event._mark_quarantined(str(exc))
            summary['quarantined'] += 1
        except ReduceError as exc:
            event._mark_retry('transient', str(exc))
            summary['retried'] += 1
        except Exception as exc:  # noqa: BLE001 — unknown failures retry
            _logger.exception('VoIP24h reducer failed on event %s', event.id)
            event._mark_retry('unexpected', '%s: %s'
                              % (type(exc).__name__, exc))
            summary['retried'] += 1
    if summary['total']:
        _logger.info('VoIP24h event drain: %s', summary)
    return summary


def drain_effects(env, limit=100):
    """Deliver pending effects. Returns a small summary dict."""
    effects = env['voip.call.effect']._claim_batch(limit=limit)
    summary = {'delivered': 0, 'retried': 0, 'total': len(effects)}
    for effect in effects:
        try:
            with env.cr.savepoint():
                _dispatch(env, effect)
                effect._mark_done()
                summary['delivered'] += 1
        except Exception as exc:  # noqa: BLE001
            _logger.exception('VoIP24h effect %s failed', effect.id)
            effect._mark_retry('%s' % type(exc).__name__)
            summary['retried'] += 1
    if summary['total']:
        _logger.info('VoIP24h effect drain: %s', summary)
    return summary


# ----------------------------------------------------------------------

def _dispatch(env, effect):
    handler = {
        'notify': _deliver_notification,
        'care_projection': _deliver_care_projection,
        'activity': _deliver_activity,
        'readiness': _deliver_readiness,
    }.get(effect.effect_type)
    if not handler:
        raise ValueError('unknown effect type %r' % effect.effect_type)
    handler(env, effect)


def _deliver_notification(env, effect):
    """One small message, to one named person's own channel.

    The payload carries identifiers and a state, never the caller's details:
    who is allowed to see a patient's name is decided when the client asks for
    it through an authenticated, scoped call — not by what happened to be put
    on a bus. No SIP password, no provider token and no recording link ever
    travels this way.
    """
    user = env['res.users'].sudo().browse(effect.recipient_uid).exists()
    if not user:
        return
    session = effect.session_id
    if session.company_id and session.company_id not in user.company_ids:
        # The recipient set is recomputed here rather than trusted from when
        # the effect was queued: company membership can change in between.
        return
    payload = {
        'kind': effect.notification_kind,
        'session_id': session.id,
        'session_uuid': session.session_uuid,
        'version': effect.projection_version,
        'state': session.live_state,
        'direction': session.direction,
        'outcome': session.outcome,
        'callback_state': session.callback_state,
        'at': fields.Datetime.to_string(fields.Datetime.now()),
    }
    user._bus_send('voip24h_call', payload)


def _deliver_care_projection(env, effect):
    """Hand the settled interaction to whoever bridges it into Care Command.

    Core does not know Care Command exists. ``health_care_command_voip``
    overrides ``_voip_project_session`` on ``voip.call.session``; where the
    bridge is absent this is a no-op, and the effect still completes so the
    queue does not fill with work nobody can do.
    """
    session = effect.session_id
    if not hasattr(session, '_voip_project_session'):
        return
    payload = json.loads(effect.payload or '{}')
    session.sudo()._voip_project_session(
        reason=payload.get('reason') or 'final',
        projection_version=effect.projection_version)


def _deliver_activity(env, effect):
    """Exactly one call-back task per obligation, on the person's record.

    An unknown or anonymous caller gets no activity — there is nothing to hang
    it on — and stays visible in the call-back queue instead, which is where
    that work already lives.
    """
    session = effect.session_id.sudo()
    if session.activity_id or session.callback_state != 'due':
        return
    target = session.partner_id or session.lead_id
    if not target:
        return
    owner = session.callback_owner_id or session.extension_id.user_id
    try:
        activity = target.activity_schedule(
            'mail.mail_activity_data_call',
            date_deadline=fields.Date.context_today(env.user),
            summary=_('Call back %s') % (session.external_peer_key
                                         or session.display_name_c),
            user_id=(owner or env.user).id,
        )
    except Exception:  # noqa: BLE001 — the call activity type may be absent
        activity = target.activity_schedule(
            date_deadline=fields.Date.context_today(env.user),
            summary=_('Call back %s') % (session.external_peer_key
                                         or session.display_name_c),
            user_id=(owner or env.user).id,
        )
    session.with_context(voip_reducer=True).write({'activity_id': activity.id})


def _deliver_readiness(env, effect):
    payload = json.loads(effect.payload or '{}')
    field = payload.get('field')
    if field and field in env['voip.config']._fields:
        config = effect.session_id.voip_config_id.sudo()
        if not config[field]:
            config.write({field: fields.Datetime.now()})
