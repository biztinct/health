# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class ZaloMessage(models.Model):
    """
    Individual Zalo message in a conversation.

    Stores message content, metadata, and delivery status.
    Supports text messages and attachments (images, files).
    """
    _name = 'zalo.message'
    _description = 'Zalo Message'
    _order = 'sent_date desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Message',
        compute='_compute_display_name',
    )

    # Conversation
    conversation_id = fields.Many2one(
        'zalo.conversation',
        string='Conversation',
        required=True,
        index=True,
        ondelete='cascade',
    )

    # Message Identification
    zalo_message_id = fields.Char(
        string='Zalo Message ID',
        index=True,
        help='Unique message identifier from Zalo',
    )

    # Direction & Type
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ], string='Direction', required=True, index=True)

    message_type = fields.Selection([
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('location', 'Location'),
        ('sticker', 'Sticker'),
        ('link', 'Link'),
        ('template', 'Template'),
    ], string='Message Type', required=True, default='text')

    # Content
    text = fields.Text(
        string='Message Text',
    )

    # Attachments
    attachment_ids = fields.One2many(
        'zalo.attachment',
        'message_id',
        string='Attachments',
    )
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
    )

    # Sender/Recipient
    from_id = fields.Char(
        string='From ID',
        help='Zalo user ID of sender',
    )
    to_id = fields.Char(
        string='To ID',
        help='Zalo user ID of recipient',
    )

    # Timestamps
    sent_date = fields.Datetime(
        string='Sent Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    delivered_date = fields.Datetime(
        string='Delivered Date',
    )
    read_date = fields.Datetime(
        string='Read Date',
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', required=True, index=True)

    is_read = fields.Boolean(
        string='Read',
        default=False,
        help='Whether message has been read (for incoming messages)',
    )

    # Error Info (for failed messages)
    error_message = fields.Text(
        string='Error Message',
    )

    # Additional Data
    raw_data = fields.Text(
        string='Raw Data',
        help='Raw JSON data from Zalo API',
    )

    # Quote/Reply
    quote_message_id = fields.Many2one(
        'zalo.message',
        string='Quoted Message',
        help='Message being replied to',
    )

    @api.depends('text', 'message_type', 'sent_date')
    def _compute_display_name(self):
        """Compute display name for message"""
        for message in self:
            if message.text:
                preview = message.text[:50]
                if len(message.text) > 50:
                    preview += '...'
                message.display_name = preview
            else:
                message.display_name = f"[{message.message_type.title()}]"

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for message in self:
            message.attachment_count = len(message.attachment_ids)

    def action_send_message(self):
        """Send outgoing message via Zalo API"""
        self.ensure_one()

        if self.direction != 'outgoing':
            raise UserError(_('Only outgoing messages can be sent'))

        if self.state not in ['draft', 'failed']:
            raise UserError(_('Message has already been sent'))

        try:
            self.write({'state': 'sending'})

            # Get API service
            api_service = self.env['zalo.api.client']

            # Prepare message data
            message_data = {
                'recipient': {
                    'user_id': self.conversation_id.zalo_user_id,
                },
            }

            # Send based on message type
            if self.message_type == 'text':
                message_data['message'] = {
                    'text': self.text,
                }
                result = api_service.send_text_message(
                    self.conversation_id.config_id,
                    message_data
                )

            elif self.message_type == 'image':
                # Send image attachment
                if not self.attachment_ids:
                    raise UserError(_('No image attachment found'))

                attachment = self.attachment_ids[0]
                result = api_service.send_image_message(
                    self.conversation_id.config_id,
                    self.conversation_id.zalo_user_id,
                    attachment.attachment_url
                )

            else:
                raise UserError(_('Message type %s not yet implemented') % self.message_type)

            # Update message with Zalo message ID
            if result.get('message_id'):
                self.write({
                    'zalo_message_id': result['message_id'],
                    'state': 'sent',
                    'delivered_date': fields.Datetime.now(),
                })

                # Update conversation last message
                self.conversation_id.update_last_message(self)

                _logger.info(f'Sent Zalo message {self.id} successfully')
            else:
                raise Exception(f"API error: {result.get('error', 'Unknown error')}")

        except Exception as e:
            _logger.error(f'Failed to send Zalo message {self.id}: {e}')
            self.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise UserError(_('Failed to send message: %s') % str(e))

    def action_mark_as_read(self):
        """Mark message as read"""
        self.ensure_one()

        if self.direction == 'incoming' and not self.is_read:
            self.write({
                'is_read': True,
                'read_date': fields.Datetime.now(),
            })

            # Decrement conversation unread count
            if self.conversation_id.unread_count > 0:
                self.conversation_id.unread_count -= 1

    def action_retry_send(self):
        """Retry sending failed message"""
        self.ensure_one()

        if self.state != 'failed':
            raise UserError(_('Only failed messages can be retried'))

        self.write({'state': 'draft', 'error_message': False})
        return self.action_send_message()

    @api.model
    def create_incoming_message(self, conversation, message_data):
        """
        Create incoming message from webhook data.

        Args:
            conversation: zalo.conversation record
            message_data: Dict with message data from Zalo webhook

        Returns:
            zalo.message record
        """
        vals = {
            'conversation_id': conversation.id,
            'direction': 'incoming',
            'from_id': message_data.get('from_id'),
            'to_id': message_data.get('to_id'),
            'sent_date': fields.Datetime.now(),
            'state': 'delivered',
            'raw_data': json.dumps(message_data),
        }

        # Parse message content based on type
        msg_content = message_data.get('message', {})

        if 'text' in msg_content:
            vals['message_type'] = 'text'
            vals['text'] = msg_content['text']

        elif 'attachments' in msg_content:
            # Handle attachments (image, file, etc.)
            attachments = msg_content['attachments']
            if attachments:
                first_attachment = attachments[0]
                attachment_type = first_attachment.get('type', 'file')

                if attachment_type == 'image':
                    vals['message_type'] = 'image'
                elif attachment_type == 'file':
                    vals['message_type'] = 'file'

        # Zalo message ID from webhook
        if 'msg_id' in message_data:
            vals['zalo_message_id'] = message_data['msg_id']

        # Create message
        message = self.create(vals)

        # Create attachment records if present
        if 'attachments' in msg_content:
            for attachment_data in msg_content['attachments']:
                self.env['zalo.attachment'].create({
                    'message_id': message.id,
                    'attachment_type': attachment_data.get('type', 'file'),
                    'attachment_url': attachment_data.get('payload', {}).get('url'),
                    'name': attachment_data.get('payload', {}).get('name', 'Attachment'),
                })

        # Update conversation
        conversation.update_last_message(message)
        conversation.increment_unread_count()

        _logger.info(f'Created incoming Zalo message {message.id} in conversation {conversation.id}')

        return message

    @api.model
    def create_outgoing_message(self, conversation, text, message_type='text'):
        """
        Create and send outgoing message.

        Args:
            conversation: zalo.conversation record
            text: Message text
            message_type: Type of message (default: 'text')

        Returns:
            zalo.message record
        """
        vals = {
            'conversation_id': conversation.id,
            'direction': 'outgoing',
            'message_type': message_type,
            'text': text,
            'from_id': conversation.config_id.oa_id,
            'to_id': conversation.zalo_user_id,
        }

        message = self.create(vals)
        message.action_send_message()

        return message
