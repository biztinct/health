# -*- coding: utf-8 -*-
"""``health.scribe.job`` — one transcription job per audio recording.

A recording uploaded from the PWA becomes a pending job; the 30-minute
``cron_scribe_transcribe`` sweep POSTs the audio to a pluggable OpenAI-
compatible STT endpoint and appends the returned text into the note's
``clinical_notes`` (encrypted at rest via health_phi_encryption — §5.19: the
append is a read-modify-WRITE through the ORM field, never SQL, never the
`_enc` column). The sweep is inert with no endpoint and ends green with the
backend down (vietuat's reality: no STT server).

Sovereignty: the endpoint host must be private (localhost / RFC-1918) unless
``health_scribe.allow_cloud`` is set — default-deny, one warning, zero calls.
"""
import base64
import hashlib
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# OpenAI-compatible STT servers (whisper.cpp / faster-whisper) accept this
# model token; local servers ignore it. Not a config param by design (§3).
_STT_MODEL = 'whisper-1'

_DEFAULTS = {
    'max_attempts': 3,
    'batch_cap': 10,
    'max_bytes': 15728640,   # 15 MB
    'stt_timeout_s': 120,
    'max_seconds': 300,
}


class HealthScribeJob(models.Model):
    _name = 'health.scribe.job'
    _description = 'Ambient Scribe Transcription Job'
    _order = 'id asc'

    note_id = fields.Many2one(
        'health.clinical.note', string='Clinical Note',
        required=True, index=True, ondelete='cascade')
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Service Order',
        related='note_id.order_id', store=True, index=True)
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        related='note_id.order_id.patient_id', store=True, index=True)
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Province',
        compute='_compute_catchment_province_id', store=True, index=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='Audio', ondelete='set null')
    audio_sha256 = fields.Char(string='Audio SHA-256', index=True)
    duration_s = fields.Float(string='Duration (s)')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], default='pending', required=True, index=True)
    attempts = fields.Integer(string='Attempts', default=0)
    last_attempt = fields.Datetime(string='Last Attempt')
    transcript = fields.Text(
        string='Transcript',
        help='Raw STT output (NOT encrypted — the authoritative copy is the '
             'appended, encrypted clinical note).')
    error = fields.Char(string='Last Error')

    @api.depends('patient_id', 'patient_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for job in self:
            job.catchment_province_id = job.patient_id.catchment_province_id

    # ==================================================================
    # Config helpers
    # ==================================================================
    @api.model
    def _cfg(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_scribe.%s' % key)

    @api.model
    def _cfg_bool(self, key, default=False):
        val = self._cfg(key)
        if val in (None, False, ''):
            return default
        return str(val).lower() in ('1', 'true', 'yes')

    @api.model
    def _cfg_int(self, key):
        val = self._cfg(key)
        try:
            return int(val) if val not in (None, False, '') else _DEFAULTS[key]
        except (TypeError, ValueError):
            return _DEFAULTS[key]

    # ==================================================================
    # Upload registration (called by the controller, sudo-safe)
    # ==================================================================
    @api.model
    def register_upload(self, order, note, audio_bytes, mimetype,
                        filename=None, duration_s=0.0):
        """Validate + persist a recording. Raises ValueError on a bad mimetype
        or oversize payload (the controller maps that to HTTP 400). Replay-safe:
        the same (sha256, note) returns the existing job — no duplicate.
        Returns the job (a manager-only record; created with sudo)."""
        if not (mimetype or '').startswith('audio/'):
            raise ValueError(_('Uploaded file is not audio.'))
        max_bytes = self._cfg_int('max_bytes')
        if len(audio_bytes) > max_bytes:
            raise ValueError(_('Audio exceeds the %s-byte limit.') % max_bytes)
        sha = hashlib.sha256(audio_bytes).hexdigest()
        existing = self.sudo().search(
            [('audio_sha256', '=', sha), ('note_id', '=', note.id)], limit=1)
        if existing:
            return existing
        # sudo the mutations: the note ACL gives the nurse read/create but NOT
        # write (health_fieldservice: nurse note perms are 1,0,1,0), so linking
        # the attachment needs sudo. The controller already authorized this call
        # (_check_api_access + note.order_id == order).
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename or 'scribe_%s.webm' % sha[:12],
            'type': 'binary',
            'datas': base64.b64encode(audio_bytes),
            'res_model': 'health.clinical.note',
            'res_id': note.id,
            'mimetype': mimetype,
        })
        note.sudo().write({'audio_ids': [(4, attachment.id)]})
        job = self.sudo().create({
            'note_id': note.id,
            'attachment_id': attachment.id,
            'audio_sha256': sha,
            'duration_s': duration_s or 0.0,
            'state': 'pending',
        })
        # Recording is media capture — log-only photography-consent evidence
        # (never blocks a nurse mid-visit; the check-log row is the record).
        patient = note.order_id.patient_id
        if patient:
            self.env['health.consent'].check_consent(patient, 'photography')
        return job

    # ==================================================================
    # Sovereignty: private-host rule
    # ==================================================================
    @api.model
    def _endpoint_is_private(self, endpoint):
        """True iff every address the endpoint host resolves to is private /
        loopback. A hostname that fails to resolve, or any public address,
        yields False (refuse)."""
        host = urlparse(endpoint or '').hostname
        if not host:
            return False
        if host == 'localhost':
            return True
        try:
            return ipaddress.ip_address(host).is_private or \
                ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass  # a hostname — resolve it
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        addrs = {info[4][0].split('%')[0] for info in infos}
        if not addrs:
            return False
        for addr in addrs:
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                return False
            if not (ip.is_private or ip.is_loopback):
                return False
        return True

    # ==================================================================
    # STT call (tests patch requests.post at this module)
    # ==================================================================
    @api.model
    def _stt_call(self, endpoint, audio_bytes, filename, language, timeout):
        """POST the audio to an OpenAI-compatible transcription endpoint and
        return the text. Raises on any HTTP/transport error (caller wraps)."""
        files = {'file': (filename or 'audio.webm', audio_bytes)}
        data = {'model': _STT_MODEL, 'language': language or 'vi',
                'response_format': 'json'}
        resp = requests.post(endpoint, files=files, data=data, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json() or {}
        return payload.get('text', '') or ''

    # ==================================================================
    # Sweep + per-job processing
    # ==================================================================
    @api.model
    def cron_scribe_transcribe(self):
        if not self._cfg_bool('enabled', default=True):
            _logger.info('Scribe sweep: disabled (config param off).')
            return True
        jobs = self.search([('state', '=', 'pending')],
                           order='id asc', limit=self._cfg_int('batch_cap'))
        if not jobs:
            return True
        self._run_jobs(jobs)
        return True

    @api.model
    def _run_jobs(self, jobs):
        """Apply the endpoint/sovereignty gates once, then process each job in
        its own savepoint. Returns the number of jobs that reached 'done'."""
        endpoint = (self._cfg('stt_endpoint') or '').strip()
        if not endpoint:
            _logger.debug('Scribe: no STT endpoint configured — %s job(s) '
                         'stay pending.', len(jobs))
            return 0
        if not self._cfg_bool('allow_cloud') and \
                not self._endpoint_is_private(endpoint):
            _logger.warning(
                'Scribe: STT endpoint %s is not a private host and allow_cloud '
                'is off — refusing to send audio off-site.', endpoint)
            return 0
        language = self._cfg('language') or 'vi'
        timeout = self._cfg_int('stt_timeout_s')
        done = 0
        for job in jobs:
            try:
                with self.env.cr.savepoint():
                    if job._process_job(endpoint, language, timeout):
                        done += 1
            except Exception as exc:  # noqa: BLE001 — one bad job never aborts
                _logger.warning('Scribe: job %s failed: %s', job.id, exc)
        return done

    def _process_job(self, endpoint, language, timeout):
        """Process ONE pending job. Returns True when it reached 'done'."""
        self.ensure_one()
        if self.state != 'pending':
            return False
        patient = self.note_id.order_id.patient_id
        # Text (AI) processing gate — mirrors the ai_coding sweep.
        if not self.env['health.consent'].check_consent(patient, 'data_sharing'):
            self.write({'state': 'failed', 'error': 'consent'})
            return False
        attachment = self.attachment_id
        if not attachment or not attachment.datas:
            self._mark_attempt('no audio')
            return False
        audio_bytes = base64.b64decode(attachment.datas)
        try:
            text = self.env['health.scribe.job']._stt_call(
                endpoint, audio_bytes, attachment.name, language, timeout)
        except Exception as exc:  # noqa: BLE001 — sweep survives backend down
            self._mark_attempt(str(exc))
            return False
        text = (text or '').strip()
        if not text:
            self._mark_attempt('empty transcript')
            return False
        self.write({'transcript': text, 'state': 'done', 'error': False})
        self._append_transcript(text)
        return True

    def _append_transcript(self, text):
        """Append the marked transcript block to the note's clinical_notes
        through the ORM field (§5.19 — the compute/inverse encrypts).

        clinical_notes is an Html field: reading it yields a Markup, and
        ``Markup + str`` ESCAPES the str — so the block must itself be a Markup
        or the transcript tags render as literal text. ``Markup % text`` escapes
        the interpolated transcript for us (no manual html.escape)."""
        self.ensure_one()
        block = Markup(
            '<p><em>[Bản ghi âm tự động — vui lòng kiểm tra '
            '(auto transcript — please verify)]</em></p><p>%s</p>') % text
        note = self.note_id
        note.clinical_notes = (note.clinical_notes or '') + block

    def _mark_attempt(self, error):
        """Increment the attempt counter; exhausted attempts → 'failed'."""
        max_attempts = self._cfg_int('max_attempts')
        for job in self:
            attempts = job.attempts + 1
            vals = {'attempts': attempts, 'last_attempt': fields.Datetime.now(),
                    'error': error or False}
            if attempts >= max_attempts:
                vals['state'] = 'failed'
            job.write(vals)

    # ==================================================================
    # Manual retry (manager+)
    # ==================================================================
    def action_transcribe_now(self):
        """Retry-after-fix: run this job's transcription now. Manager+ only;
        a no-op on a job that is not pending."""
        self._check_manager()
        self._run_jobs(self.filtered(lambda j: j.state == 'pending'))
        return True

    @api.model
    def _check_manager(self):
        if any(self.env.user.has_group(g) for g in (
                'health_base.group_healthcare_manager',
                'health_base.group_healthcare_admin',
                'health_base.group_healthcare_owner')):
            return
        raise AccessError(_(
            "Only a manager may run or delete scribe transcription jobs."))
