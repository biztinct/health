# -*- coding: utf-8 -*-
"""Call recordings: metadata first, bytes only on purpose.

The supplied documentation advertises up to four different links per call
(``play``, ``eplay``, ``download`` and a fourth, ``recording``, that appears in
the sample but not in the field table). None of them is a proven audio file:
the sample filename ends ``.gsm``, and any of those endpoints may equally serve
an HTML playback wrapper. So this model:

* records every advertised link separately and calls none of them on sight,
* never assumes a MIME type (the old default of ``audio/mpeg`` on a ``.gsm``
  file was a content-type fiction),
* streams through an authorised server endpoint by default rather than handing
  a token-bearing URL to a browser,
* and treats a failed recording as a recording problem, never as a reason a
  call, a call back or a live conversation stops working.
"""

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

# Audio types we will serve. Anything else is offered as a download with its
# real type, never relabelled.
PLAYABLE_MIMETYPES = frozenset({
    'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/ogg',
    'audio/webm', 'audio/mp4', 'audio/aac',
})


class VoIPCallRecording(models.Model):
    _name = 'voip.call.recording'
    _description = 'VoIP Call Recording'
    _order = 'create_date desc'

    name = fields.Char(string='Recording Name', compute='_compute_name',
                       store=True)
    call_log_id = fields.Many2one('voip.call.log', string='Call Log',
                                  required=True, ondelete='cascade',
                                  index=True)
    session_id = fields.Many2one('voip.call.session',
                                 related='call_log_id.session_id', store=True,
                                 index=True)
    company_id = fields.Many2one('res.company',
                                 related='call_log_id.company_id', store=True,
                                 index=True)

    recording_id = fields.Char(string='Recording Id', index=True)

    # The advertised links, kept apart. `recording_url` is the one the rest of
    # the module uses; the others are preserved because we do not yet know
    # which of them yields audio.
    recording_url = fields.Char(string='Preferred Link',
                                groups='base.group_system')
    play_url = fields.Char(string='Play Link', groups='base.group_system')
    eplay_url = fields.Char(string='Alternate Play Link',
                            groups='base.group_system')
    download_url = fields.Char(string='Download Link',
                               groups='base.group_system')
    alt_recording_url = fields.Char(string='Extra Link',
                                    groups='base.group_system')
    has_link = fields.Boolean(string='Link Advertised', compute='_compute_has_link',
                              store=True)

    access_mode = fields.Selection([
        ('stream', 'Stream through this server'),
        ('stored', 'Download and keep a copy'),
    ], string='How It Is Served', default='stream', required=True)

    recording_file = fields.Binary(string='Recording File', attachment=True)
    recording_filename = fields.Char(string='Filename')

    duration_seconds = fields.Integer(string='Duration (seconds)')
    file_size_bytes = fields.Integer(string='File Size (bytes)')
    file_format = fields.Char(
        string='Format',
        help='What the file actually is, once it has been fetched. Empty '
             'means we have not looked.')
    mimetype = fields.Char(
        string='Media Type',
        help='Observed, never assumed. A .gsm file is not relabelled as MP3.')
    is_playable = fields.Boolean(string='Plays in a Browser',
                                 compute='_compute_is_playable', store=True)
    checksum = fields.Char(string='Checksum', readonly=True)

    is_downloaded = fields.Boolean(string='Downloaded', default=False)
    downloaded_date = fields.Datetime(string='Downloaded On')
    download_error = fields.Text(string='Download Error')
    available_until = fields.Datetime(
        string='Link Expires',
        help='When the supplier’s link is known to stop working.')
    retention_deadline = fields.Datetime(string='Delete After')

    state = fields.Selection([
        ('advertised', 'A link exists'),
        ('pending', 'Waiting to fetch'),
        ('downloading', 'Fetching'),
        ('available', 'Available'),
        ('unavailable', 'Not available'),
        ('error', 'Could not be fetched'),
    ], string='State', default='advertised', required=True, index=True)

    play_count = fields.Integer(string='Times Played', readonly=True,
                                default=0)
    last_played_at = fields.Datetime(readonly=True)
    last_played_by = fields.Many2one('res.users', readonly=True)

    # ==================================================================

    @api.depends('call_log_id.call_id', 'recording_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Recording — %s') % (
                rec.call_log_id.call_id or rec.recording_id or _('unknown call'))

    @api.depends('recording_url', 'play_url', 'download_url',
                 'alt_recording_url', 'eplay_url')
    def _compute_has_link(self):
        for rec in self:
            sudo = rec.sudo()
            rec.has_link = bool(sudo.recording_url or sudo.play_url
                                or sudo.download_url or sudo.alt_recording_url
                                or sudo.eplay_url)

    @api.depends('mimetype')
    def _compute_is_playable(self):
        for rec in self:
            rec.is_playable = (rec.mimetype or '').lower() in PLAYABLE_MIMETYPES

    # ==================================================================
    # Access
    # ==================================================================

    def _check_playback_access(self):
        """Authorise on EVERY request, including a Range request.

        Recording access is its own permission — being able to see that a call
        happened is not the same as being allowed to hear it.
        """
        self.ensure_one()
        user = self.env.user
        if not user.has_group('health_voip24h.group_voip_recording'):
            raise AccessError(_(
                'You do not have permission to listen to call recordings.'))
        config = self.call_log_id.voip_config_id
        if not config.recording_access_enabled:
            raise AccessError(_(
                'Recording playback is switched off for this phone system.'))
        if self.company_id and self.company_id not in user.company_ids:
            raise AccessError(_('This recording belongs to another company.'))
        # Patient-scoped rules apply through the call log's own record rules.
        self.call_log_id.check_access('read')
        return True

    def _note_playback(self):
        """Audit WHO listened. Never logs the signed URL they listened to."""
        self.ensure_one()
        self.sudo().write({
            'play_count': (self.play_count or 0) + 1,
            'last_played_at': fields.Datetime.now(),
            'last_played_by': self.env.user.id,
        })

    def _best_source_url(self):
        """The link most likely to be audio, in the order worth trying."""
        self.ensure_one()
        sudo = self.sudo()
        for candidate in (sudo.download_url, sudo.recording_url, sudo.play_url,
                          sudo.alt_recording_url, sudo.eplay_url):
            if candidate:
                return candidate
        return None

    # ==================================================================
    # Actions
    # ==================================================================

    def action_play_recording(self):
        """Open the authorised stream. Never returns a provider URL."""
        self.ensure_one()
        self._check_playback_access()
        if not (self.is_downloaded or self._best_source_url()):
            raise UserError(_('This recording is not available.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/voip24h/recording/%s/stream' % self.id,
            'target': 'new',
        }

    def action_fetch_recording(self):
        """Fetch the bytes and keep them, when the tenant has chosen to."""
        self.ensure_one()
        self._check_playback_access()
        from ..services.recording_fetch import fetch_recording
        result = fetch_recording(self)
        if not result.get('ok'):
            raise UserError(result.get('message')
                            or _('The recording could not be fetched.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recording saved'),
                'message': self.recording_filename or '',
                'type': 'success',
            },
        }

    # Legacy name, kept so existing buttons and the cron keep working.
    def action_download_recording(self):
        return self.action_fetch_recording()

    @api.model
    def cron_download_pending_recordings(self):
        """Fetch only where the tenant asked for stored copies.

        The default is streaming, so this cron does nothing at all on a normal
        deployment — which is the point. It used to fetch every recording it
        could see, through an unverified endpoint, every five minutes.
        """
        from ..services.recording_fetch import fetch_recording
        pending = self.sudo().search([
            ('access_mode', '=', 'stored'),
            ('state', 'in', ('advertised', 'pending')),
            ('is_downloaded', '=', False),
            ('call_log_id.voip_config_id.recording_access_enabled', '=', True),
        ], limit=25)
        for recording in pending:
            try:
                with self.env.cr.savepoint():
                    fetch_recording(recording)
            except Exception as exc:  # noqa: BLE001
                _logger.error('Recording fetch failed for %s: %s',
                              recording.id, exc)
                recording.write({'state': 'error',
                                 'download_error': str(exc)[:500]})

    @api.model
    def cron_apply_recording_retention(self):
        """Delete stored bytes past the clinic's chosen retention.

        Nothing is deleted while the retention is zero, which is the default:
        retention is a decision the organisation makes, not one this module
        imposes on data that already exists.
        """
        now = fields.Datetime.now()
        expired = self.sudo().search([
            ('retention_deadline', '!=', False),
            ('retention_deadline', '<', now),
            ('is_downloaded', '=', True),
        ], limit=500)
        for recording in expired:
            recording.write({
                'recording_file': False,
                'is_downloaded': False,
                'state': 'unavailable',
                'download_error': _('Removed under the retention policy.'),
            })
        if expired:
            _logger.info('Applied recording retention to %s recording(s)',
                         len(expired))
