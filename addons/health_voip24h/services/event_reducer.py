# -*- coding: utf-8 -*-
"""From a stored provider message to what we believe happened.

The reducer is the only place allowed to write a call fact. It runs after the
receiver has already answered, so it can take its time, fail, retry and be
replayed — and because every write it makes is keyed on the event's own
identity, replaying an old message produces no second call, no second task and
no second notification.

Evidence ranking, applied everywhere:

    final CDR  >  live state estimate  >  browser telemetry

A late ``Ring`` cannot reopen a settled leg. ``Up`` before ``Ring`` establishes
an answered leg without inventing a ringing time. ``Hangup`` ends ITS leg —
another transferred leg may still be up — and a session stays open until every
known leg has ended plus a configurable grace period. Missing terminal evidence
produces ``stale_unconfirmed``, which is an admission, not a disposition.
"""

import logging
from datetime import timedelta

from odoo import fields, _


_logger = logging.getLogger(__name__)

PROJECTION_VERSION = 2


class ReduceError(Exception):
    """Transient: the event stays, backs off and is retried."""


class ReduceQuarantine(Exception):
    """Permanent: the event is kept whole and nothing is projected from it."""


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def reduce_event(env, event):
    """Process one inbox row. Raises to signal retry/quarantine."""
    payload = event.payload_dict()
    data = payload.get('data') or {}
    if not data:
        raise ReduceQuarantine('no_normalised_payload')

    config = event.voip_config_id
    if event.feed == 'cdr':
        return _reduce_final_record(env, event, config, data)
    if event.feed == 'state':
        return _reduce_state_event(env, event, config, data)
    raise ReduceQuarantine('unsupported_feed')


# ----------------------------------------------------------------------
# Correlation
# ----------------------------------------------------------------------

def _session_by_identity(env, config, namespace, value):
    if not value:
        return env['voip.call.session'].browse()
    identity = env['voip.call.identity'].sudo().search([
        ('voip_config_id', '=', config.id),
        ('namespace', '=', namespace),
        ('value', '=', value),
    ], limit=1)
    return identity.session_id


def _correlate(env, config, *, cdr_id=None, uniqueid=None, linkedid=None,
               callid=None, sip_callid=None, direction=None, peer_key=None,
               extension_number=None, at=None):
    """Find the interaction this message belongs to, in evidence order.

    Returns ``(session, how)`` where ``how`` names the rung that matched, so
    the caller can record HOW confident the link is. An ambiguous candidate
    match returns no session at all: keeping a message unresolved for review
    is right, and picking one of several plausible calls is not.
    """
    Session = env['voip.call.session'].sudo()

    # 1 — exact final-record identity.
    session = _session_by_identity(env, config, 'cdr', cdr_id)
    if session:
        return session, 'cdr_id'

    # 2 — verified leg/call aliases. `linkedid` groups related legs; its
    # semantics are only confirmed where the tenant's captures agree, so it
    # sits below `uniqueid`.
    for namespace, value in (('uniqueid', uniqueid),
                             ('linkedid', linkedid),
                             ('callid', callid)):
        session = _session_by_identity(env, config, namespace, value)
        if session:
            return session, namespace

    # 3 — a browser-reported SIP call id, only once the vendor has confirmed
    # it corresponds to a provider identifier.
    if sip_callid and config.rest_originate_verified:
        session = _session_by_identity(env, config, 'sip_callid', sip_callid)
        if session:
            return session, 'sip_callid'

    # 4 — a candidate match inside a narrow window. Configurable, and never
    # authoritative.
    if direction and peer_key and at:
        window = timedelta(seconds=config.correlation_window_seconds or 15)
        domain = [
            ('voip_config_id', '=', config.id),
            ('direction', '=', direction),
            ('external_peer_key', '=', peer_key),
            ('started_at', '>=', at - window),
            ('started_at', '<=', at + window),
            ('is_final', '=', False),
        ]
        if extension_number:
            domain.append(('extension_id.extension_number', '=',
                           extension_number))
        candidates = Session.search(domain, limit=3)
        if len(candidates) == 1:
            return candidates, 'window'
        if len(candidates) > 1:
            return Session.browse(), 'ambiguous'
    return Session.browse(), 'none'


def _resolve_extension(env, config, extension_number):
    if not extension_number:
        return env['voip.extension'].browse()
    return env['voip.extension'].sudo().search([
        ('voip_config_id', '=', config.id),
        ('extension_number', '=', extension_number),
    ], limit=1)


# ----------------------------------------------------------------------
# Feed A — final records
# ----------------------------------------------------------------------

def _reduce_final_record(env, event, config, data):
    if not config.cdr_ingest_enabled:
        # Authenticated traffic for a switched-off feed is acknowledged and
        # audited, and changes no business record.
        event._mark_quarantined('ingest_disabled',
                                'completed-call feed is switched off')
        return {'ignored': True}

    Session = env['voip.call.session'].sudo()
    peer = data.get('external_peer') or {}
    extension = _resolve_extension(env, config, data.get('internal_extension'))

    session, how = _correlate(
        env, config,
        cdr_id=data.get('provider_cdr_id'),
        callid=data.get('callid'),
        direction=data.get('direction'),
        peer_key=peer.get('key'),
        extension_number=data.get('internal_extension'),
        at=data.get('call_date'),
    )

    if how == 'ambiguous':
        # Two plausible open calls with the same number in the same fifteen
        # seconds. Guessing would put a call on the wrong person's timeline.
        raise ReduceQuarantine('ambiguous_correlation')

    created = False
    if not session:
        session = Session.with_context(voip_reducer=True).create(
            _session_vals_from_cdr(config, data, extension))
        created = True

    session = session.with_context(voip_reducer=True)

    # Register every exact name this record gave us.
    session._add_identity('cdr', data.get('provider_cdr_id'))
    session._add_identity('callid', data.get('callid'))

    call_log = _upsert_call_log(env, config, session, data, extension, event)
    _apply_final_to_session(session, data, extension)
    _match_contact(env, session)
    _apply_callback_rules(env, session)

    version = session._bump_projection()
    _enqueue_effects(env, session, version, reason='final')

    if not config.ready_cdr_at:
        config.sudo().write({'ready_cdr_at': fields.Datetime.now()})

    _record_recordings(env, call_log, data)

    return {'session': session, 'call_log': call_log, 'created': created,
            'correlated_by': how, 'version': version}


def _session_vals_from_cdr(config, data, extension):
    peer = data.get('external_peer') or {}
    return {
        'voip_config_id': config.id,
        'direction': data.get('direction') or 'unknown',
        'external_peer_raw': peer.get('raw') or False,
        'external_peer_key': peer.get('key') or False,
        'external_peer_e164': peer.get('e164') or False,
        'is_anonymous': bool(peer.get('is_anonymous')),
        'did': data.get('did') or False,
        'extension_id': extension.id if extension else False,
        'started_at': data.get('call_date') or False,
        'live_state': 'unknown',
    }


def _apply_final_to_session(session, data, extension):
    """Fold a final record into the interaction aggregate.

    SPARSE: only fields actually supplied and validated are written. A record
    that omits a duration does not zero one, does not remove a recording, does
    not overwrite a staff note and does not reset the review state.
    """
    vals = {}
    peer = data.get('external_peer') or {}

    if data.get('direction') and data['direction'] != 'unknown' \
            and session.direction == 'unknown':
        vals['direction'] = data['direction']
    if peer.get('raw') and not session.external_peer_raw:
        vals['external_peer_raw'] = peer['raw']
    if peer.get('key') and not session.external_peer_key:
        vals['external_peer_key'] = peer['key']
    if peer.get('e164') and not session.external_peer_e164:
        vals['external_peer_e164'] = peer['e164']
    if data.get('did') and not session.did:
        vals['did'] = data['did']
    if extension and not session.extension_id:
        vals['extension_id'] = extension.id
    if data.get('call_date') and not session.started_at:
        vals['started_at'] = data['call_date']

    # Outcome: a later ANSWERED beats an earlier NO ANSWER, because in a ring
    # group the losing legs each produce their own unanswered record and one
    # answered leg means the customer was reached.
    outcome = data.get('outcome') or 'unknown'
    if outcome == 'answered' or session.outcome == 'unknown':
        vals['outcome'] = outcome

    billsec = data.get('billsec')
    duration = data.get('duration')
    if billsec is not None and billsec > (session.talk_seconds or 0):
        vals['talk_seconds'] = billsec
    if duration is not None and duration > (session.total_seconds or 0):
        vals['total_seconds'] = duration

    if data.get('call_date') and billsec:
        answered = data['call_date'] + timedelta(
            seconds=max((duration or billsec) - billsec, 0))
        if not session.answered_at:
            vals['answered_at'] = answered
    if data.get('call_date') and duration is not None and not session.ended_at:
        vals['ended_at'] = data['call_date'] + timedelta(seconds=duration)

    quality = list(data.get('data_quality') or [])
    if quality:
        vals['data_quality_state'] = 'conflict' if any(
            'disagree' in q for q in quality) else 'incomplete'
        existing = (session.data_quality_note or '').splitlines()
        vals['data_quality_note'] = '\n'.join(
            sorted(set(existing) | set(quality)))

    vals['live_state'] = 'final'
    vals['is_final'] = True
    vals['finalised_at'] = fields.Datetime.now()
    session.write(vals)


def _upsert_call_log(env, config, session, data, extension, event):
    """Create or enrich the customer-facing final record.

    When both feeds describe the SAME final record we enrich the one row; a
    second visible call would be a lie about how many times the phone rang.
    When an interaction legitimately contains several final CDRs (after a
    transfer), each keeps its own row — they are not discarded to make a
    dashboard count look right.
    """
    Log = env['voip.call.log'].sudo()
    provider_cdr_id = data.get('provider_cdr_id')
    existing = Log.browse()
    if provider_cdr_id:
        existing = Log.search([
            ('voip_config_id', '=', config.id),
            ('provider_cdr_id', '=', provider_cdr_id),
        ], limit=1)
    if not existing and not provider_cdr_id and data.get('callid'):
        # Only when this record has NO provider CDR id of its own. `callid` is
        # NOT unique: in a ring group every leg's final record carries the
        # same one, so matching on it merged the losing leg's record into the
        # winner's — two pieces of evidence collapsed into one, and a transfer
        # would have lost a leg the same way. (Found by the live test run:
        # test_45 saw one final record where there were two.)
        existing = Log.search([
            ('voip_config_id', '=', config.id),
            ('provider_call_id', '=', data['callid']),
            ('provider_cdr_id', '=', False),
            ('source_profile', '=', 'feed_a'),
        ], limit=1)

    peer = data.get('external_peer') or {}
    vals = {
        'voip_config_id': config.id,
        'session_id': session.id,
        'provider_cdr_id': provider_cdr_id or False,
        'provider_call_id': data.get('callid') or False,
        'source_profile': 'feed_a',
        'direction': data.get('direction') or 'unknown',
        'call_type': data.get('call_type') or 'unknown',
        'call_status': data.get('call_status') or 'unknown',
        'disposition_raw': data.get('disposition_raw') or False,
        'status_raw': data.get('status_raw') or False,
        'hangup_cause': data.get('note') or False,
        'caller_number': data.get('src') or False,
        'called_number': data.get('dst') or False,
        'did': data.get('did') or False,
        'extension_id': extension.id if extension else False,
        'extension_number': data.get('internal_extension') or False,
        'external_peer_e164': peer.get('e164') or False,
        'is_final': True,
        'finalised_at': fields.Datetime.now(),
        'timestamp_timezone': config.provider_timezone,
        'import_source': 'webhook_v3',
        'data_quality_state': 'flagged' if data.get('data_quality') else 'ok',
        'data_quality_note': '\n'.join(data.get('data_quality') or []) or False,
    }
    if data.get('call_date'):
        vals['call_date'] = data['call_date']
        vals['start_time'] = data['call_date']
    if data.get('duration') is not None:
        vals['duration_seconds'] = data['duration']
    if data.get('billsec') is not None:
        vals['talk_duration_seconds'] = data['billsec']
    if data.get('wait_seconds') is not None:
        vals['wait_duration_seconds'] = data['wait_seconds']
    if data.get('recording_urls'):
        vals['has_recording'] = True

    if existing:
        # A correction. Keep staff work: notes, outcome and review state are
        # NOT in vals and are never touched here.
        existing.with_context(voip_reducer=True).write(vals)
        log = existing
    else:
        # `call_id` is the legacy human-facing reference. Namespaced so it can
        # never be mistaken for one of the four provider identifiers.
        vals['call_id'] = 'cdr:%s' % (provider_cdr_id or data.get('callid')
                                      or event.fingerprint[:24])
        log = Log.with_context(voip_reducer=True).create(vals)

    session._add_identity('cdr', provider_cdr_id)
    if provider_cdr_id:
        env['voip.call.identity']._register_reference(
            config, 'cdr', provider_cdr_id, session=session, call_log=log)
    return log


def _record_recordings(env, call_log, data):
    """Create recording METADATA from advertised links. Downloads nothing."""
    urls = data.get('recording_urls') or {}
    if not urls or not call_log:
        return
    Recording = env['voip.call.recording'].sudo()
    existing = Recording.search([('call_log_id', '=', call_log.id)], limit=1)
    vals = {
        'call_log_id': call_log.id,
        'play_url': urls.get('play') or False,
        'eplay_url': urls.get('eplay') or False,
        'download_url': urls.get('download') or False,
        'alt_recording_url': urls.get('recording') or False,
        'recording_url': (urls.get('download') or urls.get('play')
                          or urls.get('recording') or urls.get('eplay')),
        'state': 'advertised',
    }
    if existing:
        existing.write({k: v for k, v in vals.items() if v})
    else:
        Recording.create(vals)


# ----------------------------------------------------------------------
# Feed B — live states
# ----------------------------------------------------------------------

def _reduce_state_event(env, event, config, data):
    if not config.state_ingest_enabled:
        event._mark_quarantined('ingest_disabled',
                                'live-events feed is switched off')
        return {'ignored': True}

    Session = env['voip.call.session'].sudo()
    Leg = env['voip.call.leg'].sudo()
    state = data.get('state')
    peer = data.get('external_peer') or {}
    extension = _resolve_extension(env, config, data.get('extension_number'))

    session, how = _correlate(
        env, config,
        uniqueid=data.get('uniqueid'),
        linkedid=data.get('linkedid'),
        callid=data.get('callid'),
        direction=data.get('direction'),
        peer_key=peer.get('key'),
        extension_number=data.get('extension_number'),
        at=data.get('cdr', {}).get('start_time') or event.provider_time,
    )
    if how == 'ambiguous':
        raise ReduceQuarantine('ambiguous_correlation')

    if not session:
        if state == 'unknown':
            raise ReduceQuarantine('unknown_state_no_session')
        session = Session.with_context(voip_reducer=True).create({
            'voip_config_id': config.id,
            'direction': data.get('direction') or 'unknown',
            'external_peer_raw': peer.get('raw') or data.get('phone') or False,
            'external_peer_key': peer.get('key') or False,
            'external_peer_e164': peer.get('e164') or False,
            'is_anonymous': bool(peer.get('is_anonymous')),
            'extension_id': extension.id if extension else False,
            'started_at': (data.get('cdr', {}).get('start_time')
                           or event.provider_time or fields.Datetime.now()),
            'live_state': 'unknown',
        })

    session = session.with_context(voip_reducer=True)
    for namespace in ('uniqueid', 'linkedid', 'callid'):
        session._add_identity(namespace, data.get(namespace))

    # The leg. `uniqueid` names it; without one we cannot tell legs apart and
    # the event updates the session only.
    leg = Leg.browse()
    if data.get('uniqueid'):
        leg = Leg.search([('voip_config_id', '=', config.id),
                          ('provider_unique_id', '=', data['uniqueid'])],
                         limit=1)
        if not leg:
            leg = Leg.create({
                'session_id': session.id,
                'voip_config_id': config.id,
                'provider_unique_id': data['uniqueid'],
                'provider_linked_id': data.get('linkedid') or False,
                'channel': data.get('channel') or False,
                'extension_number': data.get('extension_number') or False,
                'extension_id': extension.id if extension else False,
                'source_event_id': event.id,
            })

    now_provider = event.provider_time or fields.Datetime.now()

    if state == 'ringing':
        if leg:
            if not leg.ringing_at:
                leg.write({'ringing_at': now_provider})
            leg._advance_state('ringing')
        session._advance_state('ringing')
    elif state == 'answered':
        # `Up` before `Ring` is legitimate. An answered leg is established
        # WITHOUT back-filling a ringing time we never observed.
        if leg:
            if not leg.answered_at:
                leg.write({'answered_at': now_provider})
            leg._advance_state('answered')
        session._advance_state('answered')
        if not session.answered_at:
            session.write({'answered_at': now_provider})
    elif state == 'ended_pending_cdr':
        # Ends THIS leg. Another transferred leg may still be up, so the
        # session is not closed here and no duration is manufactured.
        if leg:
            if not leg.ended_at:
                leg.write({'ended_at': now_provider})
            leg._advance_state('ended_pending_cdr')
        _maybe_close_session(session)
    elif state == 'final_cdr':
        _apply_nested_cdr(env, config, session, leg, data, extension)
    else:
        raise ReduceQuarantine('unknown_state')

    if not config.ready_state_at:
        config.sudo().write({'ready_state_at': fields.Datetime.now()})

    _match_contact(env, session)
    version = session._bump_projection()
    _enqueue_effects(env, session, version, reason=state)
    return {'session': session, 'leg': leg, 'correlated_by': how,
            'version': version}


def _maybe_close_session(session):
    """Close only when every known leg has ended."""
    legs = session.leg_ids
    if legs and any(leg.state not in ('ended_pending_cdr', 'final')
                    for leg in legs):
        return False
    session._advance_state('ended_pending_cdr')
    return True


def _apply_nested_cdr(env, config, session, leg, data, extension):
    """The final record delivered inside the live feed.

    Feed A and Feed B can both describe the same call and can disagree. Feed A
    is the preferred final source once the vendor confirms it (gate G06); until
    then the rule here is conservative: a Feed B record never overwrites a
    settled Feed A one, it only fills gaps, and any disagreement is recorded.
    """
    cdr = data.get('cdr') or {}
    if not cdr:
        raise ReduceQuarantine('final_state_without_cdr')

    if session.is_final:
        conflicts = []
        if cdr.get('billsec') is not None and session.talk_seconds and \
                cdr['billsec'] != session.talk_seconds:
            conflicts.append('talk time %s vs %s'
                             % (cdr['billsec'], session.talk_seconds))
        if cdr.get('outcome') and cdr['outcome'] != session.outcome:
            conflicts.append('outcome %s vs %s'
                             % (cdr['outcome'], session.outcome))
        if conflicts:
            session.write({
                'data_quality_state': 'conflict',
                'data_quality_note': '\n'.join(filter(None, [
                    session.data_quality_note,
                    'live-feed record disagrees: ' + '; '.join(conflicts)])),
            })
        return

    vals = {'live_state': 'final', 'is_final': True,
            'finalised_at': fields.Datetime.now()}
    if cdr.get('start_time') and not session.started_at:
        vals['started_at'] = cdr['start_time']
    if cdr.get('answer_time') and not session.answered_at:
        vals['answered_at'] = cdr['answer_time']
    if cdr.get('end_time') and not session.ended_at:
        vals['ended_at'] = cdr['end_time']
    if cdr.get('billsec') is not None:
        vals['talk_seconds'] = cdr['billsec']
    if cdr.get('duration') is not None:
        vals['total_seconds'] = cdr['duration']
    if cdr.get('outcome') and (cdr['outcome'] == 'answered'
                               or session.outcome == 'unknown'):
        vals['outcome'] = cdr['outcome']
    if data.get('data_quality'):
        vals['data_quality_state'] = 'incomplete'
        vals['data_quality_note'] = '\n'.join(data['data_quality'])
    session.write(vals)

    if leg:
        leg.write({
            'disposition_raw': cdr.get('disposition_raw') or False,
            'outcome': cdr.get('outcome') or 'unknown',
            'talk_seconds': cdr.get('billsec') or 0,
            'total_seconds': cdr.get('duration') or 0,
        })
        leg._advance_state('final')

    # A Feed B record with no Feed A id gets its own stable source identity, so
    # a later Feed A delivery enriches rather than duplicating.
    Log = env['voip.call.log'].sudo()
    reference = data.get('uniqueid') or data.get('callid')
    if reference and not Log.search_count([
            ('voip_config_id', '=', config.id),
            ('call_id', '=', 'state:%s' % reference)]):
        Log.with_context(voip_reducer=True).create({
            'call_id': 'state:%s' % reference,
            'voip_config_id': config.id,
            'session_id': session.id,
            'provider_call_id': data.get('callid') or False,
            'provider_unique_id': data.get('uniqueid') or False,
            'source_profile': 'feed_b',
            'direction': data.get('direction') or 'unknown',
            'call_type': cdr.get('call_type') or 'unknown',
            'call_status': cdr.get('call_status') or 'unknown',
            'disposition_raw': cdr.get('disposition_raw') or False,
            'caller_number': cdr.get('source') or False,
            'called_number': cdr.get('destination') or False,
            'extension_id': extension.id if extension else False,
            'extension_number': data.get('extension_number') or False,
            'call_date': cdr.get('start_time') or session.started_at,
            'start_time': cdr.get('start_time') or False,
            'answer_time': cdr.get('answer_time') or False,
            'end_time': cdr.get('end_time') or False,
            'duration_seconds': cdr.get('duration') or 0,
            'talk_duration_seconds': cdr.get('billsec') or 0,
            'is_final': True,
            'finalised_at': fields.Datetime.now(),
            'timestamp_timezone': config.provider_timezone,
            'import_source': 'webhook_v3',
        })


# ----------------------------------------------------------------------
# Contact matching
# ----------------------------------------------------------------------

def _match_contact(env, session):
    """Link the interaction to a person — or say we cannot.

    Scoped to the connection's company. A unique valid match is automatic;
    several people sharing a family number is an AMBIGUOUS state that a human
    resolves, not a coin toss. Caller-ID is never proof of identity, and no
    contact is ever created here.
    """
    if session.match_state in ('manual', 'internal'):
        return
    if session.direction == 'internal':
        session.write({'match_state': 'internal'})
        return
    if session.partner_id or session.lead_id:
        if session.match_state == 'unmatched':
            session.write({'match_state': 'auto'})
        return

    key = session.external_peer_key
    if not key:
        return

    company = session.company_id
    Partner = env['res.partner'].sudo()
    domain = ['|', ('phone', '=', key), ('mobile', '=', key)]
    if company:
        domain = ['&', '|', ('company_id', '=', False),
                  ('company_id', '=', company.id)] + domain
    partners = Partner.search(domain, limit=5)

    if len(partners) == 1:
        session.write({'partner_id': partners.id, 'match_state': 'auto',
                       'match_candidate_count': 1})
        return
    if len(partners) > 1:
        # A family share one number. Do not pick; do not show the candidates
        # to an agent who may not be allowed to see them.
        session.write({'match_state': 'ambiguous',
                       'match_candidate_count': len(partners)})
        return

    # crm.lead has no `mobile` field on this build (ledger §5.16).
    leads = env['crm.lead'].sudo().search(
        ([('company_id', 'in', (False, company.id))] if company else [])
        + [('phone', '=', key)], limit=5)
    if len(leads) == 1:
        session.write({'lead_id': leads.id, 'match_state': 'auto',
                       'match_candidate_count': 1})
    elif len(leads) > 1:
        session.write({'match_state': 'ambiguous',
                       'match_candidate_count': len(leads)})


# ----------------------------------------------------------------------
# Callback rules
# ----------------------------------------------------------------------

def _apply_callback_rules(env, session):
    """Who still owes this person a ring back.

    Direction-aware, and deliberately unwilling to close anything on weak
    evidence: an outbound attempt that failed is an attempt, not a resolution,
    and an answered callback with zero reported talk time needs a human to
    confirm because provider rounding is real.
    """
    config = session.voip_config_id
    if session.direction == 'internal':
        session.write({'callback_state': 'none'})
        return

    if session.direction == 'incoming':
        answered = session.outcome == 'answered' or any(
            leg.outcome == 'answered' for leg in session.leg_ids)
        if answered:
            session.write({'callback_state': 'none'})
            _resolve_prior_obligation(env, session)
            return
        due_at = False
        minutes = config.callback_target_minutes or 0
        if minutes > 0:
            due_at = fields.Datetime.now() + timedelta(minutes=minutes)
        session._open_callback(due_at=due_at)
        return

    # Outgoing: this call may RESOLVE an earlier obligation.
    session.write({'callback_state': 'none'})
    if session.outcome != 'answered':
        _record_attempt(env, session)
        return
    if not session.talk_seconds:
        # Answered with zero reported talk time. Possible, and also what a
        # rounding artefact looks like. Counted as an attempt and left for a
        # person unless the clinic has explicitly allowed auto-resolution.
        _record_attempt(env, session)
        return
    _resolve_prior_obligation(env, session)


def _open_obligation_for(env, session):
    """The open call-back this call is about, if there is one."""
    if not session.external_peer_key and not session.partner_id:
        return env['voip.call.session'].browse()
    domain = [('voip_config_id', '=', session.voip_config_id.id),
              ('callback_state', '=', 'due'),
              ('id', '!=', session.id)]
    if session.partner_id:
        domain.append(('partner_id', '=', session.partner_id.id))
    else:
        domain.append(('external_peer_key', '=', session.external_peer_key))
    return env['voip.call.session'].sudo().search(
        domain, order='started_at asc', limit=1)


def _record_attempt(env, session):
    obligation = _open_obligation_for(env, session)
    if obligation:
        obligation.with_context(voip_reducer=True).write({
            'callback_attempts': (obligation.callback_attempts or 0) + 1})


def _resolve_prior_obligation(env, session):
    obligation = _open_obligation_for(env, session)
    if not obligation:
        return
    obligation = obligation.with_context(voip_reducer=True)
    resolution = ('answered' if session.direction == 'outgoing'
                  else 'superseded')
    obligation._resolve_callback(resolution, by_session=session)
    obligation.message_post(body=_(
        'This call back was closed because call %s reached them.')
        % session.session_uuid)


# ----------------------------------------------------------------------
# Effects
# ----------------------------------------------------------------------

def _recipients_for(env, session):
    """Who is entitled to hear about this call.

    The assigned agent first; their supervisors only where the team model
    already says so. An obscure bus topic is not access control, so the
    recipient set is computed here and each notification is addressed to one
    person's own channel.
    """
    users = env['res.users'].sudo().browse()
    if session.extension_id and session.extension_id.user_id:
        users |= session.extension_id.user_id
    if session.callback_owner_id:
        users |= session.callback_owner_id
    if not users:
        # Nobody is assigned. Reception/triage is the team that owns unrouted
        # contact, expressed as the VoIP user group scoped to the company.
        group = env.ref('health_voip24h.group_voip_user',
                        raise_if_not_found=False)
        if group:
            users = group.sudo().user_ids.filtered(
                lambda u: not session.company_id
                or session.company_id in u.company_ids)
    return users.filtered(lambda u: u.active)


def _enqueue_effects(env, session, version, reason='final'):
    """Everything this change owes the world, in the SAME transaction."""
    Effect = env['voip.call.effect'].sudo()

    Effect._enqueue(
        session, 'care_projection',
        dedupe_key='%s:%s' % (reason, version),
        projection_version=version,
        payload={'reason': reason})

    if session.callback_state == 'due' and not session.activity_id:
        Effect._enqueue(
            session, 'activity',
            dedupe_key='callback:%s' % session.id,
            projection_version=version,
            payload={'reason': 'missed_inbound'})

    kind = _notification_kind(session, reason)
    if not kind:
        return
    if not session.voip_config_id.live_notifications_enabled and \
            kind not in ('missed_inbound', 'callback_due'):
        return
    for user in _recipients_for(env, session):
        Effect._enqueue(
            session, 'notify',
            dedupe_key='%s:%s:%s' % (kind, version, user.id),
            recipient_uid=user.id,
            notification_kind=kind,
            projection_version=version,
            payload={'reason': reason})


def _notification_kind(session, reason):
    if reason == 'ringing':
        return 'incoming_ring'
    if reason == 'answered':
        return 'answered'
    if reason == 'ended_pending_cdr':
        return 'ended'
    if reason in ('final', 'final_cdr'):
        if session.direction == 'incoming' and session.callback_state == 'due':
            return 'missed_inbound'
        if session.direction == 'outgoing' and session.outcome != 'answered':
            return 'outbound_unanswered'
        if session.match_state == 'ambiguous' or (
                not session.partner_id and not session.lead_id
                and session.direction == 'incoming'):
            return 'unmatched_caller'
        return 'call_recorded'
    return None


# ----------------------------------------------------------------------
# Finalisation sweep
# ----------------------------------------------------------------------

def finalise_stale_sessions(env, config=None):
    """Close calls whose legs ended but whose final record never arrived.

    The result is ``stale_unconfirmed`` — an admission that we do not know how
    it ended. It is deliberately NOT ``missed`` and deliberately NOT
    ``completed``: both would be an invented outcome, and one of them would put
    a call back on somebody's list that may not be owed.
    """
    Session = env['voip.call.session'].sudo()
    domain = [('is_final', '=', False),
              ('live_state', 'in', ('ringing', 'answered',
                                    'ended_pending_cdr'))]
    if config:
        domain.append(('voip_config_id', '=', config.id))
    closed = 0
    for session in Session.search(domain, limit=500):
        grace = session.voip_config_id.finalisation_grace_seconds or 30
        reference = session.ended_at or session.answered_at or session.started_at
        if not reference:
            continue
        # A ringing call that never ended gets a much longer rope than one we
        # have already seen hang up.
        window = grace if session.live_state == 'ended_pending_cdr' else 3600
        if (fields.Datetime.now() - reference).total_seconds() < window:
            continue
        session.with_context(voip_reducer=True).write({
            'live_state': 'stale_unconfirmed',
            'is_final': True,
            'finalised_at': fields.Datetime.now(),
            'data_quality_state': 'incomplete',
            'data_quality_note': '\n'.join(filter(None, [
                session.data_quality_note,
                'no final record arrived from the phone system'])),
        })
        _apply_callback_rules(env, session.with_context(voip_reducer=True))
        version = session._bump_projection()
        _enqueue_effects(env, session, version, reason='final')
        closed += 1
    return closed
