# -*- coding: utf-8 -*-
"""Device-reading ingestion endpoint (Phase 2).

``POST /api/v1/telemonitoring/readings`` — a gateway-authenticated,
scope-gated, rate-limited, idempotent batch ingestion that maps home-device
readings onto ``health.observation.create_coded`` / ``create_panel``. From
there the Phase 1 engines (thresholds → inbox, NEWS2, nightly trends) pick the
readings up with zero extra wiring.

Auth/scope/rate/envelope are hand-rolled here (mirroring api_v1.py:164-223)
rather than via the gateway ``@api_route`` decorator: that decorator's broad
``except Exception`` swallows the ``ReadOnlySqlTransaction`` that Odoo's
readonly-first cursor raises on the FIRST write, defeating the framework's
retry-on-read/write mechanism (an ingestion is a write path). The route
therefore declares ``readonly=False`` so it runs on a read/write cursor from
the start. The gateway auth/scope/envelope helpers are IMPORTED (documented
interface contract — health_fhir_core imports the same) so no gateway code is
edited.
"""
import json
import logging

import werkzeug.exceptions

from odoo import _, fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.health_api_gateway.controllers.gateway import (
    ApiError, _envelope_response, _gateway_authenticate, _scopes_satisfied)

from ..models import tm_config

_logger = logging.getLogger(__name__)

_BP_CODES = ('bp_sys', 'bp_dia')
_FUTURE_SKEW_SECONDS = 10 * 60
_REQUIRED_SCOPE = 'telemonitoring.ingest'


def _parse_client_datetime(value):
    """'2026-07-15T02:10:00Z' / '2026-07-15 02:10:00' → naive-UTC Datetime.

    Clone of ``health_vitals/controllers/api.py::_parse_client_datetime``.
    Devices send UTC (trailing 'Z'); stripping it stores the wall-clock as
    UTC, which is Odoo's storage convention."""
    if not value:
        return False
    if isinstance(value, str):
        value = value.replace('Z', '').replace('T', ' ')
    try:
        return fields.Datetime.to_datetime(value)
    except (ValueError, TypeError):
        return False


class TelemonitoringIngestController(http.Controller):

    @http.route('/api/v1/telemonitoring/readings', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False,
                readonly=False)
    def ingest_readings(self, **kwargs):
        # -- 1. Authenticate → scope → rate limit (mirror api_v1.py) ----
        try:
            user, granted = _gateway_authenticate(request)
        except werkzeug.exceptions.Unauthorized as exc:
            return _envelope_response(
                error=exc.description or _('Unauthorized'), status_code=401)
        if not _scopes_satisfied((_REQUIRED_SCOPE,), granted):
            return _envelope_response(
                error=_('Token is missing a required scope (%s)',
                        _REQUIRED_SCOPE), status_code=403)
        allowed, retry_after = request.env['gateway.rate.counter'].sudo().hit(
            'tm-ingest:%s' % user.id)
        if not allowed:
            return _envelope_response(
                error=_('Rate limit exceeded'), status_code=429,
                extra_headers=[('Retry-After', str(retry_after))])
        # Run the ORM as the service user (record rules apply where used).
        request.update_env(user=user.id)

        # -- 2. Parse body ---------------------------------------------
        raw = request.httprequest.data
        try:
            payload = json.loads(raw.decode('utf-8')) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return _envelope_response(
                error=_('Request body is not valid JSON'), status_code=400)

        try:
            data = self._ingest(payload)
            return _envelope_response(data=data, status_code=200)
        except ApiError as exc:
            return _envelope_response(error=exc.message,
                                      status_code=exc.status_code)
        except Exception as exc:  # noqa: BLE001 — 500 envelope, no receipt
            _logger.exception('Telemonitoring ingest: unhandled error')
            return _envelope_response(error=str(exc), status_code=500)

    # ------------------------------------------------------------------
    # Handler (steps 2-8 of handover §2.3)
    # ------------------------------------------------------------------
    def _ingest(self, payload):
        env = request.env
        data = payload if isinstance(payload, dict) else {}

        external_id = (data.get('device_external_id') or '').strip()
        batch_uuid = (data.get('client_batch_uuid') or '').strip()
        readings = data.get('readings')
        if not external_id:
            raise ApiError(_('device_external_id is required'), 422)
        if not batch_uuid:
            raise ApiError(_('client_batch_uuid is required'), 422)
        if len(batch_uuid) > 64:
            raise ApiError(
                _('client_batch_uuid must be at most 64 characters'), 422)
        if not isinstance(readings, list) or not readings:
            raise ApiError(_('readings must be a non-empty list'), 422)
        max_batch = tm_config.get_int(env, 'ingest_max_batch', 50)
        if len(readings) > max_batch:
            raise ApiError(
                _('Batch too large: %(n)s readings (max %(max)s)',
                  n=len(readings), max=max_batch), 422)

        # -- 3. Resolve device -----------------------------------------
        Device = env['health.monitor.device'].sudo()
        device = Device.search([('external_id', '=', external_id)], limit=1)
        if not device:
            # Neutral 404 — no existence oracle beyond the partner's devices.
            raise ApiError(_('Device not found'), 404)
        if device.state != 'active':
            raise ApiError(_('Device is not active'), 422)

        # -- 4. Idempotent replay --------------------------------------
        Receipt = env['health.device.receipt'].sudo()
        existing = Receipt.search([
            ('device_id', '=', device.id),
            ('client_batch_uuid', '=', batch_uuid)], limit=1)
        if existing:
            try:
                return json.loads(existing.result_json or '{}')
            except (ValueError, TypeError):
                return {'accepted': 0, 'rejected': []}

        # -- 5. Per-device daily flood cap -----------------------------
        cap = tm_config.get_int(env, 'ingest_daily_cap_per_device', 288)
        marker = '(%s)' % external_id
        today_start = fields.Datetime.to_string(
            fields.Datetime.now().replace(hour=0, minute=0, second=0,
                                          microsecond=0))
        Obs = env['health.observation'].sudo()
        todays = Obs.search_count([
            ('device', 'like', marker),
            ('create_date', '>=', today_start)])
        if todays >= cap:
            _logger.warning(
                'Telemonitoring ingest: daily flood cap hit for device %s '
                '(%s today >= %s). Batch %s dropped, no receipt.',
                external_id, todays, cap, batch_uuid)
            raise ApiError(
                _('Daily reading cap reached for this device'), 429)

        # -- 6. Per-reading validation ---------------------------------
        max_age_days = tm_config.get_int(env, 'ingest_max_age_days', 7)
        now = fields.Datetime.now()
        Type = env['health.vitals.type'].sudo()
        rejected = []
        valid = []
        for index, reading in enumerate(readings):
            if not isinstance(reading, dict):
                rejected.append({'index': index, 'reason': 'malformed'})
                continue
            code = (reading.get('code') or '').strip()
            vtype = Type.get_by_code(code) if code else False
            if not vtype:
                rejected.append({'index': index, 'reason': 'unknown_code'})
                continue
            if reading.get('value') in (None, ''):
                rejected.append({'index': index, 'reason': 'missing_value'})
                continue
            taken_at = _parse_client_datetime(reading.get('taken_at'))
            if not taken_at:
                rejected.append({'index': index, 'reason': 'missing_taken_at'})
                continue
            if (taken_at - now).total_seconds() > _FUTURE_SKEW_SECONDS:
                rejected.append({'index': index, 'reason': 'future_reading'})
                continue
            if (now - taken_at).days > max_age_days:
                rejected.append({'index': index, 'reason': 'stale_reading'})
                continue
            valid.append({'index': index, 'code': code, 'vtype': vtype,
                          'value': reading.get('value'), 'taken_at': taken_at})

        device_marker = '%s (%s)' % (device.name, external_id)
        performer_id = env.user.id
        client_id = device.client_id.id
        accepted = 0

        # BP pairing: bp_sys + bp_dia sharing one taken_at → one panel.
        paired_indices = set()
        by_taken = {}
        for item in valid:
            if item['code'] in _BP_CODES:
                by_taken.setdefault(item['taken_at'], {})[item['code']] = item
        for taken_at, halves in by_taken.items():
            if 'bp_sys' in halves and 'bp_dia' in halves:
                sys_item, dia_item = halves['bp_sys'], halves['bp_dia']
                try:
                    with env.cr.savepoint():
                        Obs.create_panel(
                            client_id, 'bp_panel',
                            [{'code': 'bp_sys', 'value': sys_item['value']},
                             {'code': 'bp_dia', 'value': dia_item['value']}],
                            effective_datetime=taken_at,
                            performer_id=performer_id,
                            device=device_marker)
                    accepted += 2
                except ValidationError:
                    rejected.append({'index': sys_item['index'],
                                     'reason': 'implausible'})
                    rejected.append({'index': dia_item['index'],
                                     'reason': 'implausible'})
                paired_indices.add(sys_item['index'])
                paired_indices.add(dia_item['index'])

        # Everything else (incl. unpaired BP halves) → create_coded.
        for item in valid:
            if item['index'] in paired_indices:
                continue
            try:
                with env.cr.savepoint():
                    obs = Obs.create_coded(
                        client_id, item['code'], item['value'],
                        effective_datetime=item['taken_at'],
                        performer_id=performer_id, source='device',
                        note='device:%s' % external_id)
                    # create_coded has no `device` param (only create_panel
                    # does) — set the provenance marker with a plain Char
                    # write (no value change → no amendment path).
                    obs.device = device_marker
                accepted += 1
            except ValidationError:
                rejected.append({'index': item['index'],
                                 'reason': 'implausible'})

        # -- 7. Result + receipt + stamp -------------------------------
        rejected.sort(key=lambda r: r['index'])
        result = {'accepted': accepted, 'rejected': rejected}
        if accepted and not rejected:
            state = 'applied'
        elif accepted:
            state = 'partial'
        else:
            state = 'rejected'
        Receipt.create({
            'device_id': device.id,
            'client_batch_uuid': batch_uuid,
            'state': state,
            'result_json': json.dumps(result, sort_keys=True),
            'received_at': now,
        })
        device.write({'last_reading_at': now})
        return result
