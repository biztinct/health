# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

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
        """Download recording file from VoIP24h"""
        self.ensure_one()

        try:
            self.state = 'downloading'
            # TODO: Implement recording download
            # from ..services.voip24h_api import VoIP24hAPI
            # api = VoIP24hAPI(self.call_log_id.voip_config_id)
            # file_data = api.download_recording(self.recording_url)
            # self.recording_file = file_data
            # self.is_downloaded = True
            # self.downloaded_date = fields.Datetime.now()
            # self.state = 'available'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Download Started'),
                    'message': _('Recording download initiated'),
                    'type': 'info',
                }
            }

        except Exception as e:
            _logger.error(f'Recording download failed: {e}', exc_info=True)
            self.write({
                'state': 'error',
                'download_error': str(e),
            })
            raise UserError(_('Download failed: %s') % str(e))

    def action_play_recording(self):
        """Play recording in browser"""
        self.ensure_one()

        if not self.is_downloaded and not self.recording_url:
            raise UserError(_('Recording not available'))

        # Return action to play audio
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
        ], limit=50)

        for recording in pending_recordings:
            try:
                recording.action_download_recording()
            except Exception as e:
                _logger.error(f'Cron download failed for {recording.id}: {e}')
