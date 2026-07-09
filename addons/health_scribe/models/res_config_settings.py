# -*- coding: utf-8 -*-
"""Settings for the ambient scribe (handover §3).

Capture ships enabled (harmless — the sweep is inert without an endpoint);
``allow_cloud`` ships OFF so a non-private STT host is refused.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    scribe_enabled = fields.Boolean(
        string='Enable Ambient Scribe',
        config_parameter='health_scribe.enabled', default=True)
    scribe_stt_endpoint = fields.Char(
        string='STT Endpoint (OpenAI-compatible)',
        config_parameter='health_scribe.stt_endpoint',
        help='Full URL of the transcription endpoint, e.g. '
             'http://127.0.0.1:8123/v1/audio/transcriptions. Empty → recordings '
             'queue and wait. Must be a private host unless "Allow cloud STT".')
    scribe_allow_cloud = fields.Boolean(
        string='Allow Cloud STT',
        config_parameter='health_scribe.allow_cloud',
        help='Off by default (data sovereignty): only a private-host endpoint '
             '(localhost / RFC-1918) is called; a public host is refused.')
    scribe_language = fields.Char(
        string='STT Language',
        config_parameter='health_scribe.language', default='vi')
    scribe_max_seconds = fields.Integer(
        string='Max Recording Seconds',
        config_parameter='health_scribe.max_seconds', default=300)
    scribe_max_bytes = fields.Integer(
        string='Max Audio Bytes',
        config_parameter='health_scribe.max_bytes', default=15728640)
    scribe_max_attempts = fields.Integer(
        string='Max Attempts per Recording',
        config_parameter='health_scribe.max_attempts', default=3)
    scribe_batch_cap = fields.Integer(
        string='Recordings per Sweep',
        config_parameter='health_scribe.batch_cap', default=10)
    scribe_stt_timeout_s = fields.Integer(
        string='STT Timeout (s)',
        config_parameter='health_scribe.stt_timeout_s', default=120)
