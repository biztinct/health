# -*- coding: utf-8 -*-
"""The authenticated API the phone panel talks to.

Everything here is an application interface. None of it is a VoIP24h endpoint,
and none of it dials anything: the browser dials, through the supplier's SDK,
and this server decides whether it is allowed to and records that it asked.

Two rules run through the file:

* **Server-side authority.** Hiding a button is not access control. Every
  route re-checks the user, the company, the extension assignment and the
  capability flags, and a crafted RPC payload that names another agent's
  extension is refused exactly as a crafted UI would be.
* **Browser evidence is provisional.** ``client_event`` accepts what the SDK
  reports and stores it as telemetry. It can never set a duration, settle an
  outcome or close a call back as answered — only a provider record does that.
"""

import logging
import uuid

from markupsafe import Markup

from odoo import http, _
from odoo.exceptions import UserError, AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


def _no_store():
    """Mark the response uncacheable. Bootstrap carries a SIP password."""
    try:
        request.future_response.headers['Cache-Control'] = \
            'no-store, no-cache, must-revalidate, private'
        request.future_response.headers['Pragma'] = 'no-cache'
    except Exception:  # noqa: BLE001 — header support is version-dependent
        pass


def _config_for_user():
    config = request.env['voip.config'].sudo().search([
        ('company_id', '=', request.env.company.id),
        ('active', '=', True),
    ], limit=1)
    if not config:
        raise UserError(_('No phone system is set up for this company.'))
    return config


def _require_voip_user():
    if not request.env.user.has_group('health_voip24h.group_voip_user'):
        raise AccessError(_('You do not have access to the phone system.'))


def _my_extension(config):
    """The extension assigned to the CURRENT user. Never a supplied id.

    The old click-to-dial route accepted an ``extension_id`` and checked only
    that it belonged to the chosen config — which let any VoIP user place a
    call as any colleague. Ownership is not something the client gets to
    assert.
    """
    extension = request.env['voip.extension'].sudo().search([
        ('voip_config_id', '=', config.id),
        ('user_id', '=', request.env.user.id),
        ('active', '=', True),
    ], limit=1)
    return extension


def _ok(**payload):
    return dict(payload, ok=True)


def _error(message, code='refused'):
    return {'ok': False, 'error': message, 'code': code}


class VoIP24hPhoneController(http.Controller):

    # ==================================================================
    # Profile and lease
    # ==================================================================

    @http.route('/voip24h/phone/profile', type='jsonrpc', auth='user',
                methods=['POST'])
    def profile(self, **kwargs):
        """What this user's browser may show. No credentials."""
        try:
            _require_voip_user()
            config = _config_for_user()
        except (UserError, AccessError) as exc:
            return _error(str(exc), 'unavailable')
        return _ok(profile=config._client_profile())

    @http.route('/voip24h/phone/bootstrap', type='jsonrpc', auth='user',
                methods=['POST'])
    def bootstrap(self, browser_uuid=None, takeover=False, **kwargs):
        """Claim the extension and hand this browser what it needs to register.

        The SIP password necessarily reaches the browser: the documented SDK
        takes it in clear. This module does not pretend otherwise. What it does
        is give it only to the assigned user, only over this authenticated
        no-store response, and only while they hold the lease — and the panel
        keeps it in memory, out of storage, out of the DOM and out of error
        reports.
        """
        _no_store()
        try:
            _require_voip_user()
            config = _config_for_user()
            if not config.webrtc_enabled or not config.enable_call_functionality:
                return _error(_('Calling in the browser is switched off for '
                                'this phone system.'), 'disabled')
            extension = _my_extension(config)
            if not extension:
                return _error(_('You do not have an extension assigned. Ask '
                                'an administrator to assign one.'),
                              'no_extension')
            if not extension.browser_enabled:
                return _error(_('Your extension is not set up for the browser '
                                'phone.'), 'not_browser_enabled')
            credentials = extension._sip_credentials()
            if not credentials:
                return _error(_('Your extension has no sign-in details yet. '
                                'Ask an administrator to add them.'),
                              'no_credentials')

            browser_uuid = (browser_uuid or '').strip() or str(uuid.uuid4())
            lease, token = request.env['voip.client.lease']._acquire(
                config, extension, browser_uuid, takeover=bool(takeover))
        except UserError as exc:
            return _error(str(exc), 'conflict')
        except AccessError as exc:
            return _error(str(exc), 'denied')

        request.env['voip.call.action']._record(
            config, 'register', uuid_value='lease:%s' % lease.id,
            extension=extension)

        return _ok(
            lease={'id': lease.id, 'token': token, 'fence': lease.fence,
                   'browser_uuid': browser_uuid,
                   'heartbeat_seconds': config.lease_heartbeat_seconds or 10},
            sdk={'library_url': config.sdk_library_url,
                 'gateway_url': config.sdk_gateway_url,
                 'host_url': '/voip24h/phone/sdk_host'},
            sip=credentials,
            profile=config._client_profile(),
        )

    @http.route('/voip24h/phone/heartbeat', type='jsonrpc', auth='user',
                methods=['POST'])
    def heartbeat(self, lease_id=None, token=None, fence=None, state=None,
                  diagnostic=None, **kwargs):
        _no_store()
        lease = request.env['voip.client.lease']._authenticate(
            lease_id, token, fence)
        if not lease:
            # A replaced or expired lease: the panel must stop, not retry.
            return _error(_('Your phone session was taken over or timed out.'),
                          'lease_lost')
        lease._beat(sdk_state=state, diagnostic=diagnostic)
        return _ok(state=lease.sdk_state, fence=lease.fence)

    @http.route('/voip24h/phone/release', type='jsonrpc', auth='user',
                methods=['POST'])
    def release(self, lease_id=None, token=None, fence=None, **kwargs):
        _no_store()
        lease = request.env['voip.client.lease']._authenticate(
            lease_id, token, fence)
        if not lease:
            return _ok(released=True)
        lease._release('user released')
        return _ok(released=True)

    @http.route('/voip24h/phone/sdk_host', type='http', auth='user',
                methods=['GET'], csrf=False)
    def sdk_host(self, **kwargs):
        """The isolated host page the supplier's SDK runs inside.

        The supplied libraries are legacy globals that want jQuery 1.9 and an
        old WebRTC adapter. Loading those into the Odoo backend would replace
        the framework's own JavaScript dependencies — so they run in a
        same-origin iframe of their own, and the panel talks to it through
        explicit, origin-checked messages. Confirm with the supplier that this
        hosting arrangement is supported before shipping it (gate G07).
        """
        config = request.env['voip.config'].sudo().search([
            ('company_id', '=', request.env.company.id), ('active', '=', True),
        ], limit=1)
        if not config or not config.webrtc_enabled:
            return request.not_found()
        if not request.env.user.has_group('health_voip24h.group_voip_user'):
            return request.not_found()
        html = request.env['ir.qweb']._render(
            'health_voip24h.sdk_host_page', {
                'library_url': config.sdk_library_url,
                'gateway_url': config.sdk_gateway_url,
            })
        # §5.64: a QWeb template whose root is <html> is served with no
        # doctype, and the browser then renders in quirks mode. `Markup + html`
        # in this order keeps it raw — `str + Markup` would escape it and ship
        # a literal `&lt;!DOCTYPE html&gt;` (§5.20).
        html = Markup('<!DOCTYPE html>') + html
        response = request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store, private'),
            # The host frame may only be embedded by us.
            ('X-Frame-Options', 'SAMEORIGIN'),
        ])
        return response

    # ==================================================================
    # Call intent and telemetry
    # ==================================================================

    @http.route('/voip24h/calls/intent', type='jsonrpc', auth='user',
                methods=['POST'])
    def call_intent(self, action_uuid=None, number=None, lease_id=None,
                    token=None, fence=None, res_model=None, res_id=None,
                    **kwargs):
        """Authorise ONE dial. Idempotent by ``action_uuid``.

        The same reference twice returns the same intent and does not authorise
        a second call. There is no queue and no replay: a dial command that
        could be replayed after a reconnect is a dial command that eventually
        rings a patient twice.
        """
        _no_store()
        try:
            _require_voip_user()
            config = _config_for_user()
        except (UserError, AccessError) as exc:
            return _error(str(exc), 'unavailable')

        if not config.can_make_outgoing_calls():
            return _error(_('Outgoing calls are switched off.'), 'disabled')

        lease = request.env['voip.client.lease']._authenticate(
            lease_id, token, fence)
        if not lease:
            return _error(_('Start your phone before calling.'), 'lease_lost')
        extension = lease.extension_id
        if extension.user_id != request.env.user:
            return _error(_('That extension is not yours.'), 'denied')

        action_uuid = (action_uuid or '').strip()
        if not action_uuid:
            return _error(_('The call request was incomplete.'), 'bad_request')

        from ..services import phone_ident
        dial = phone_ident.dial_string(number)
        if not dial:
            return _error(_('That is not a number this phone can call.'),
                          'bad_number')

        allowed, reason = extension._destination_allowed(dial)
        if not allowed:
            action, _created = request.env['voip.call.action']._record(
                config, 'dial', uuid_value=action_uuid, extension=extension,
                destination=number, normalised=dial)
            action.sudo().write({'result': 'refused', 'refusal_reason': reason})
            return _error(reason, 'not_allowed')

        action, created = request.env['voip.call.action']._record(
            config, 'dial', uuid_value=action_uuid, extension=extension,
            destination=number, normalised=dial,
            related_model=res_model, related_id=res_id and int(res_id))

        if not created:
            # A repeat of a request we already answered. Same answer, no
            # second dial.
            return _ok(repeat=True, action_id=action.id,
                       dial=action.normalised_destination,
                       caller_id=extension.caller_id_did or False,
                       result=action.result)

        action.sudo().write({'result': 'authorised', 'authorised_at': _now()})
        return _ok(action_id=action.id, dial=dial,
                   caller_id=extension.caller_id_did or False)

    @http.route('/voip24h/calls/client_event', type='jsonrpc', auth='user',
                methods=['POST'])
    def client_event(self, action_id=None, event=None, diagnostic=None,
                     sip_call_id=None, lease_id=None, token=None, fence=None,
                     **kwargs):
        """Provisional browser telemetry. Never a trusted call fact."""
        _no_store()
        lease = request.env['voip.client.lease']._authenticate(
            lease_id, token, fence)
        if not lease:
            return _error(_('Your phone session ended.'), 'lease_lost')

        action = request.env['voip.call.action'].sudo().browse(
            int(action_id or 0)).exists()
        if action and action.user_id != request.env.user:
            return _error(_('That call request is not yours.'), 'denied')

        mapping = {
            'progress': 'reported_ok',
            'accepted': 'reported_ok',
            'ended': 'reported_ok',
            'failed': 'reported_failed',
            'timeout': 'unresolved',
        }
        if action:
            action.write({
                'result': mapping.get(event, 'unresolved'),
                'evidence_class': 'browser',
                'diagnostic': (diagnostic or '')[:64] or False,
            })
            if sip_call_id and action.session_id:
                request.env['voip.call.identity']._register_reference(
                    action.voip_config_id, 'sip_callid', sip_call_id,
                    session=action.session_id)

        config = lease.voip_config_id
        if event == 'accepted' and not config.ready_outbound_call_at:
            config.sudo().write({'ready_outbound_call_at': _now()})
        if event == 'incoming_answered' and not config.ready_inbound_call_at:
            config.sudo().write({'ready_inbound_call_at': _now()})
        return _ok(accepted=True)

    # ==================================================================
    # Work surfaces
    # ==================================================================

    @http.route('/voip24h/calls/active', type='jsonrpc', auth='user',
                methods=['POST'])
    def active_calls(self, **kwargs):
        """What is live and what still needs writing up, from the server.

        Bus delivery is not durable, so this is how a browser that reconnected
        after missing an event catches up. It is also the only place caller
        details are ever resolved — the bus carries identifiers, not names.
        """
        _no_store()
        try:
            _require_voip_user()
            config = _config_for_user()
        except (UserError, AccessError) as exc:
            return _error(str(exc), 'unavailable')

        Session = request.env['voip.call.session']
        live = Session.search([
            ('voip_config_id', '=', config.id),
            ('is_final', '=', False),
        ], order='started_at desc', limit=20)
        pending = Session.search([
            ('voip_config_id', '=', config.id),
            ('wrap_up_state', '=', 'pending'),
            '|', ('extension_id.user_id', '=', request.env.user.id),
            ('callback_owner_id', '=', request.env.user.id),
        ], order='ended_at desc', limit=20)
        callbacks = Session.search([
            ('voip_config_id', '=', config.id),
            ('callback_state', '=', 'due'),
        ], order='callback_due_at asc, started_at asc', limit=50)

        return _ok(
            live=[_session_payload(s) for s in live],
            wrap_up=[_session_payload(s) for s in pending],
            callbacks=[_session_payload(s) for s in callbacks],
            profile=config._client_profile(),
        )

    @http.route('/voip24h/calls/session', type='jsonrpc', auth='user',
                methods=['POST'])
    def session_detail(self, session_id=None, **kwargs):
        """Permitted caller details for one call, resolved server-side."""
        _no_store()
        _require_voip_user()
        session = request.env['voip.call.session'].browse(
            int(session_id or 0)).exists()
        if not session:
            return _error(_('That call is no longer available.'), 'not_found')
        return _ok(session=_session_payload(session, detailed=True))

    @http.route('/voip24h/calls/disposition', type='jsonrpc', auth='user',
                methods=['POST'])
    def disposition(self, session_id=None, notes=None, outcome=None,
                    version=None, **kwargs):
        _no_store()
        try:
            _require_voip_user()
            session = request.env['voip.call.session'].browse(
                int(session_id or 0)).exists()
            if not session:
                return _error(_('That call is no longer available.'),
                              'not_found')
            result = session.update_disposition(
                notes=notes, business_outcome=outcome, version=version)
        except (UserError, AccessError) as exc:
            return _error(str(exc), 'refused')
        return _ok(**result)

    @http.route('/voip24h/calls/mark_called_back', type='jsonrpc',
                auth='user', methods=['POST'])
    def mark_called_back(self, session_id=None, **kwargs):
        _no_store()
        try:
            _require_voip_user()
            session = request.env['voip.call.session'].browse(
                int(session_id or 0)).exists()
            if not session:
                return _error(_('That call is no longer available.'),
                              'not_found')
            session.action_mark_called_back()
        except (UserError, AccessError) as exc:
            return _error(str(exc), 'refused')
        return _ok(done=True)


class VoIP24hLegacyAPIController(http.Controller):
    """The two pre-existing frontend routes, kept working."""

    @http.route('/voip24h/get_config', type='jsonrpc', auth='user',
                methods=['POST'])
    def get_config(self, **kwargs):
        try:
            _require_voip_user()
            config = _config_for_user()
        except (UserError, AccessError) as exc:
            return {'error': str(exc)}
        profile = config._client_profile()
        # The legacy keys the old widget reads, plus the current profile.
        return dict(profile, **{
            'enable_call_functionality': profile['calling_enabled'],
            'enable_outgoing_calls': profile['outgoing_enabled'],
            'enable_incoming_call_popups': profile['alerts_enabled'],
        })

    @http.route('/voip24h/click_to_dial', type='jsonrpc', auth='user',
                methods=['POST'])
    def click_to_dial(self, phone_number, extension_id=None, **kwargs):
        """Kept so old callers get a clear answer instead of a broken dial.

        Dialling now happens in the browser: the server has no confirmed way to
        originate a call on this account. The panel is what places it.
        """
        return {
            'error': _('Calls are placed from the phone panel in your browser. '
                       'Open the phone, then press call.'),
            'use_panel': True,
            'number': phone_number,
        }


# ----------------------------------------------------------------------

def _now():
    from odoo import fields
    return fields.Datetime.now()


def _session_payload(session, detailed=False):
    """A small, permission-aware view of one call.

    Caller identity is included only where the reader may already see the
    record — the recordset the caller searched with is their own, so a session
    they cannot read never reaches this function.
    """
    payload = {
        'id': session.id,
        'uuid': session.session_uuid,
        'direction': session.direction,
        'state': session.live_state,
        'outcome': session.outcome,
        'is_final': session.is_final,
        'version': session.projection_version,
        'peer': session.external_peer_key or session.external_peer_raw or '',
        'anonymous': session.is_anonymous,
        'name': session.display_name_c,
        'partner_id': session.partner_id.id or False,
        'lead_id': session.lead_id.id or False,
        'match_state': session.match_state,
        'started_at': str(session.started_at or ''),
        'answered_at': str(session.answered_at or ''),
        'ended_at': str(session.ended_at or ''),
        'talk_seconds': session.talk_seconds or 0,
        'callback_state': session.callback_state,
        'callback_due_at': str(session.callback_due_at or ''),
        'wrap_up_state': session.wrap_up_state,
        'extension': session.extension_id.extension_number or '',
    }
    if detailed:
        payload.update({
            'notes': session.notes or '',
            'business_outcome': session.business_outcome or '',
            'data_quality': session.data_quality_state,
            'data_quality_note': session.data_quality_note or '',
            'legs': [{
                'id': leg.id,
                'extension': leg.extension_number or '',
                'state': leg.state,
                'outcome': leg.outcome,
                'talk_seconds': leg.talk_seconds or 0,
            } for leg in session.leg_ids],
            'recordings': [{
                'id': rec.id,
                'state': rec.state,
                'playable': rec.is_playable,
                'url': '/voip24h/recording/%s/stream' % rec.id,
            } for rec in session.log_ids.mapped('recording_ids')
                if session.voip_config_id.recording_access_enabled],
        })
    return payload
