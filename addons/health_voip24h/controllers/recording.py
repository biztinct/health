# -*- coding: utf-8 -*-
"""Authorised recording playback.

The route takes a STORED recording id. It never takes a URL: a client-supplied
address would make this server a general-purpose fetcher for whoever asks, and
the provider's own links carry query tokens that must never travel back out
through us.

Authorisation runs on every request, Range requests included — a partial
request is still a request for the audio, and a player will issue several of
them for one listen.
"""

import logging

from odoo import http, _
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


class VoIP24hRecordingController(http.Controller):

    @http.route('/voip24h/recording/<int:recording_id>/stream', type='http',
                auth='user', methods=['GET'], csrf=False, sitemap=False)
    def stream(self, recording_id, **kwargs):
        recording = request.env['voip.call.recording'].browse(
            recording_id).exists()
        if not recording:
            return request.not_found()
        try:
            recording._check_playback_access()
        except AccessError:
            # Same answer as "no such recording": guessing an id must not tell
            # you whether it exists.
            _logger.info('Recording %s playback denied for uid %s',
                         recording_id, request.env.uid)
            return request.not_found()

        from ..services.recording_fetch import (
            RecordingFetchError, stream_recording,
        )
        range_header = request.httprequest.headers.get('Range')
        try:
            status, headers, body = stream_recording(
                recording.sudo(), range_header=range_header)
        except RecordingFetchError as exc:
            _logger.info('Recording %s could not be served: %s',
                         recording_id, exc)
            recording.sudo().write({'state': 'unavailable',
                                    'download_error': str(exc)[:500]})
            return request.make_response(
                _('This recording is not available right now.'),
                headers=[('Content-Type', 'text/plain; charset=utf-8'),
                         ('Cache-Control', 'no-store')],
                status=503)
        except Exception:  # noqa: BLE001
            _logger.exception('Recording %s stream failed', recording_id)
            return request.make_response(
                _('This recording could not be played.'),
                headers=[('Content-Type', 'text/plain; charset=utf-8'),
                         ('Cache-Control', 'no-store')],
                status=502)

        recording._note_playback()
        response = request.make_response(body, headers=headers)
        response.status_code = status
        return response
