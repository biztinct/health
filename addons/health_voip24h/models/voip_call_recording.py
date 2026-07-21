# -*- coding: utf-8 -*-

import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIPCallRecording(models.Model):
    """
    VoIP Call Recordings.

    Stores call recording files and metadata with download management.
    """
    _name = 'voip.call.recording'
    _description = 'VoIP Call Recording'
    _order = 'create_date desc'

    name = fields.Char(
        string='Recording Name',
        compute='_compute_name',
        store=True,
    )
    call_log_id = fields.Many2one(
        'voip.call.log',
        string='Call Log',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # Recording Details
    recording_id = fields.Char(
        string='Recording ID',
        index=True,
        help='Unique recording identifier from VoIP24h',
    )
    recording_url = fields.Char(
        string='Recording URL',
        required=True,
    )
    recording_file = fields.Binary(
        string='Recording File',
        attachment=True,
    )
    recording_filename = fields.Char(
        string='Filename',
    )

    # Metadata
    duration_seconds = fields.Integer(
        string='Duration (seconds)',
    )
    file_size_bytes = fields.Integer(
        string='File Size (bytes)',
    )
    file_format = fields.Char(
        string='Format',
        default='mp3',
    )
    mimetype = fields.Char(
        string='MIME Type',
        default='audio/mpeg',
    )

    # Download Status
    is_downloaded = fields.Boolean(
        string='Downloaded',
        default=False,
    )
    downloaded_date = fields.Datetime(
        string='Downloaded On',
    )
    download_error = fields.Text(
        string='Download Error',
    )

    # State
    state = fields.Selection([
        ('pending', 'Pending Download'),
        ('downloading', 'Downloading'),
        ('available', 'Available'),
        ('error', 'Download Error'),
    ], string='State', default='pending', required=True)

    @api.depends('call_log_id.call_id', 'recording_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f"Recording - {rec.call_log_id.call_id or 'Unknown'}"

    def action_download_recording(self):
        """Download recording file from VoIP24h into the Binary field."""
        self.ensure_one()

        if not self.recording_url:
            raise UserError(_('This recording has no download URL.'))

        try:
            api = self.call_log_id.voip_config_id._get_api_client()
            file_data = api.download_recording(self.recording_url)

            filename = self.recording_filename or "%s.%s" % (
                self.call_log_id.call_id or self.recording_id or self.id,
                self.file_format or 'mp3',
            )
            self.write({
                'recording_file': base64.b64encode(file_data),
                'recording_filename': filename,
                'file_size_bytes': len(file_data),
                'is_downloaded': True,
                'downloaded_date': fields.Datetime.now(),
                'download_error': False,
                'state': 'available',
            })
            config = self.call_log_id.voip_config_id.sudo()
            config.total_recordings_synced += 1

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Recording Downloaded'),
                    'message': filename,
                    'type': 'success',
                }
            }

        except UserError:
            raise
        except Exception as e:
            _logger.error('Recording download failed: %s', e, exc_info=True)
            self.write({
                'state': 'error',
                'download_error': str(e),
            })
            raise UserError(_('Download failed: %s') % e)

    def action_play_recording(self):
        """Play/stream the recording in the browser.

        Serves the downloaded attachment when available; falls back to the
        external VoIP24h URL otherwise.
        """
        self.ensure_one()

        if self.is_downloaded and self.recording_file:
            filename = self.recording_filename or 'recording.mp3'
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/voip.call.recording/{self.id}/recording_file/{filename}',
                'target': 'new',
            }

        if not self.recording_url:
            raise UserError(_('Recording not available'))

        return {
            'type': 'ir.actions.act_url',
            'url': self.recording_url,
            'target': 'new',
        }

    @api.model
    def cron_download_pending_recordings(self):
        """Cron job to download pending recordings"""
        pending_recordings = self.search([
            ('state', '=', 'pending'),
            ('is_downloaded', '=', False),
            ('recording_url', '!=', False),
        ], limit=50)

        for recording in pending_recordings:
            try:
                with self.env.cr.savepoint():
                    recording.action_download_recording()
            except Exception as e:
                # savepoint rolled back the partial write — persist the error
                # state so the cron does not retry a dead URL forever
                # (manual retry stays available via the Download button).
                _logger.error('Cron download failed for recording %s: %s', recording.id, e)
                recording.write({'state': 'error', 'download_error': str(e)})
