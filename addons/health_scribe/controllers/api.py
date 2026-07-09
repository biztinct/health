# -*- coding: utf-8 -*-
"""Audio upload endpoint — mirrors health_pwa's ``upload_image`` (auth, access
check, JSON envelope) but for scribe recordings."""
import json
import logging

from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class HealthScribeController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers duplicated verbatim from health_pwa/controllers/api.py
    # (conventions §4: duplicate, don't cross-import controllers).
    # ------------------------------------------------------------------
    def _check_api_access(self):
        if not request.env.user or request.env.user.id == \
                request.env.ref('base.public_user').id:
            return False
        try:
            request.env['res.partner'].check_access_rights('read')
            return True
        except Exception:  # noqa: BLE001 — access probe, deny on any failure
            return False

    def _prepare_json_response(self, data=None, error=None, status_code=200):
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
        }
        if error:
            response_data['error'] = error
        else:
            response_data['data'] = data
        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False, indent=2),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ],
            status=status_code)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    @http.route('/health_pwa/api/fso/<int:order_id>/upload_audio',
                type='http', auth='user', methods=['POST'], csrf=False)
    def api_fso_upload_audio(self, order_id, **kwargs):
        """Upload a scribe recording, attach it to the clinical note, and queue
        a transcription job. Replay-safe on (sha256, note)."""
        if not self._check_api_access():
            return self._prepare_json_response(
                error=_('Access denied'), status_code=403)
        try:
            order = request.env['health.fieldservice.order'].browse(order_id)
            if not order.exists():
                return self._prepare_json_response(
                    error=_('Order not found'), status_code=404)

            audio_file = request.httprequest.files.get('audio')
            if not audio_file:
                return self._prepare_json_response(
                    error=_('No audio provided'), status_code=400)

            note_id = kwargs.get('note_id') or \
                request.httprequest.form.get('note_id')
            try:
                note = request.env['health.clinical.note'].browse(
                    int(note_id)) if note_id \
                    else request.env['health.clinical.note']
            except (TypeError, ValueError):
                return self._prepare_json_response(
                    error=_('Invalid note id'), status_code=400)
            if not note.exists() or note.order_id.id != order.id:
                return self._prepare_json_response(
                    error=_('Clinical note not found for this order'),
                    status_code=400)

            duration_s = 0.0
            try:
                duration_s = float(
                    kwargs.get('duration_s')
                    or request.httprequest.form.get('duration_s') or 0.0)
            except (TypeError, ValueError):
                duration_s = 0.0

            audio_bytes = audio_file.read()
            mimetype = audio_file.content_type or ''
            try:
                job = request.env['health.scribe.job'].register_upload(
                    order, note, audio_bytes, mimetype,
                    filename=audio_file.filename, duration_s=duration_s)
            except ValueError as exc:
                return self._prepare_json_response(
                    error=str(exc), status_code=400)

            return self._prepare_json_response(data={
                'job_id': job.id,
                'attachment_id': job.attachment_id.id,
                'state': job.state,
            })
        except Exception as exc:  # noqa: BLE001
            _logger.error('Scribe upload_audio failed: %s', exc)
            return self._prepare_json_response(error=str(exc), status_code=500)
