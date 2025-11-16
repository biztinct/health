# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ZaloAttachment(models.Model):
    """
    Attachment for Zalo messages (images, files, etc.).

    Stores media files sent/received via Zalo messaging.
    """
    _name = 'zalo.attachment'
    _description = 'Zalo Message Attachment'
    _order = 'id desc'

    name = fields.Char(
        string='Filename',
        required=True,
    )

    message_id = fields.Many2one(
        'zalo.message',
        string='Message',
        required=True,
        index=True,
        ondelete='cascade',
    )

    attachment_type = fields.Selection([
        ('image', 'Image'),
        ('file', 'File'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('location', 'Location'),
    ], string='Type', required=True, default='file')

    # Zalo URLs
    attachment_url = fields.Char(
        string='Attachment URL',
        help='URL to download attachment from Zalo',
    )

    thumbnail_url = fields.Char(
        string='Thumbnail URL',
        help='Thumbnail preview URL (for images/videos)',
    )

    # File Storage
    datas = fields.Binary(
        string='File Content',
        attachment=True,
        help='Downloaded file content stored in Odoo',
    )

    mimetype = fields.Char(
        string='MIME Type',
    )

    file_size = fields.Integer(
        string='File Size (bytes)',
    )

    # Metadata
    downloaded = fields.Boolean(
        string='Downloaded',
        default=False,
        help='Whether file has been downloaded from Zalo to Odoo',
    )

    downloaded_date = fields.Datetime(
        string='Downloaded Date',
    )

    # For images
    width = fields.Integer(string='Width')
    height = fields.Integer(string='Height')

    # For location attachments
    latitude = fields.Float(string='Latitude')
    longitude = fields.Float(string='Longitude')
    location_name = fields.Char(string='Location Name')

    def action_download_file(self):
        """Download file from Zalo to Odoo storage"""
        self.ensure_one()

        if not self.attachment_url:
            return

        try:
            import requests

            response = requests.get(self.attachment_url, timeout=30)
            response.raise_for_status()

            self.write({
                'datas': response.content,
                'mimetype': response.headers.get('content-type'),
                'file_size': len(response.content),
                'downloaded': True,
                'downloaded_date': fields.Datetime.now(),
            })

            _logger.info(f'Downloaded Zalo attachment {self.id}: {self.name}')

        except Exception as e:
            _logger.error(f'Failed to download Zalo attachment {self.id}: {e}')
            raise

    def action_preview(self):
        """Open attachment preview"""
        self.ensure_one()

        if self.attachment_type == 'image':
            # Return image preview
            return {
                'type': 'ir.actions.act_url',
                'url': self.attachment_url or f'/web/image/zalo.attachment/{self.id}/datas',
                'target': 'new',
            }
        else:
            # Download file
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/zalo.attachment/{self.id}/datas/{self.name}',
                'target': 'self',
            }
