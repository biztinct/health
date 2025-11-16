# -*- coding: utf-8 -*-

from odoo import models, api, _
import logging
import json

_logger = logging.getLogger(__name__)


class ZaloMessageHandler(models.AbstractModel):
    """
    Service model for processing incoming Zalo messages from webhooks.

    Handles message parsing, conversation management, and notification dispatch.
    """
    _name = 'zalo.message.handler'
    _description = 'Zalo Message Handler Service'

    @api.model
    def process_webhook_event(self, event_data):
        """
        Process incoming webhook event from Zalo.

        Args:
            event_data: Dict with webhook event data

        Returns:
            Boolean indicating success
        """
        try:
            event_name = event_data.get('event_name')

            _logger.info(f'Processing Zalo webhook event: {event_name}')

            if event_name == 'user_send_text':
                return self._handle_incoming_text_message(event_data)

            elif event_name == 'user_send_image':
                return self._handle_incoming_image_message(event_data)

            elif event_name == 'user_send_file':
                return self._handle_incoming_file_message(event_data)

            elif event_name == 'user_send_sticker':
                return self._handle_incoming_sticker(event_data)

            elif event_name == 'user_send_link':
                return self._handle_incoming_link(event_data)

            elif event_name == 'follow':
                return self._handle_user_follow(event_data)

            elif event_name == 'unfollow':
                return self._handle_user_unfollow(event_data)

            elif event_name == 'user_submit_info':
                return self._handle_user_submit_info(event_data)

            else:
                _logger.warning(f'Unknown webhook event type: {event_name}')
                return True

        except Exception as e:
            _logger.error(f'Error processing webhook event: {e}', exc_info=True)
            return False

    def _handle_incoming_text_message(self, event_data):
        """Handle incoming text message from user"""
        sender_id = event_data.get('sender', {}).get('id')
        message_text = event_data.get('message', {}).get('text')
        timestamp = event_data.get('timestamp')

        _logger.info(f'Incoming text message from {sender_id}: {message_text}')

        # Get or create conversation
        conversation = self._get_or_create_conversation(sender_id, event_data.get('sender'))

        # Create message record
        message_data = {
            'from_id': sender_id,
            'to_id': event_data.get('recipient', {}).get('id'),
            'message': {
                'text': message_text,
            },
            'timestamp': timestamp,
        }

        message = self.env['zalo.message'].create_incoming_message(conversation, message_data)

        # Send bus notification for real-time UI update
        self._send_bus_notification(conversation, message)

        return True

    def _handle_incoming_image_message(self, event_data):
        """Handle incoming image from user"""
        sender_id = event_data.get('sender', {}).get('id')
        attachments = event_data.get('message', {}).get('attachments', [])

        _logger.info(f'Incoming image message from {sender_id}')

        # Get or create conversation
        conversation = self._get_or_create_conversation(sender_id, event_data.get('sender'))

        # Create message with image attachment
        message_data = {
            'from_id': sender_id,
            'to_id': event_data.get('recipient', {}).get('id'),
            'message': {
                'attachments': attachments,
            },
            'timestamp': event_data.get('timestamp'),
        }

        message = self.env['zalo.message'].create_incoming_message(conversation, message_data)

        # Send bus notification
        self._send_bus_notification(conversation, message)

        return True

    def _handle_incoming_file_message(self, event_data):
        """Handle incoming file attachment from user"""
        sender_id = event_data.get('sender', {}).get('id')

        _logger.info(f'Incoming file message from {sender_id}')

        # Get or create conversation
        conversation = self._get_or_create_conversation(sender_id, event_data.get('sender'))

        # Create message with file attachment
        message_data = {
            'from_id': sender_id,
            'to_id': event_data.get('recipient', {}).get('id'),
            'message': {
                'attachments': event_data.get('message', {}).get('attachments', []),
            },
            'timestamp': event_data.get('timestamp'),
        }

        message = self.env['zalo.message'].create_incoming_message(conversation, message_data)

        # Send bus notification
        self._send_bus_notification(conversation, message)

        return True

    def _handle_incoming_sticker(self, event_data):
        """Handle incoming sticker from user"""
        sender_id = event_data.get('sender', {}).get('id')

        _logger.info(f'Incoming sticker from {sender_id}')

        # Similar to image handling
        return self._handle_incoming_image_message(event_data)

    def _handle_incoming_link(self, event_data):
        """Handle incoming link from user"""
        sender_id = event_data.get('sender', {}).get('id')

        _logger.info(f'Incoming link from {sender_id}')

        # Similar to text message handling
        return self._handle_incoming_text_message(event_data)

    def _handle_user_follow(self, event_data):
        """Handle user following the OA"""
        user_id = event_data.get('follower', {}).get('id')

        _logger.info(f'User {user_id} followed the OA')

        # Get or create conversation
        conversation = self._get_or_create_conversation(user_id, event_data.get('follower'))

        # Mark as follower
        conversation.write({'is_follower': True})

        return True

    def _handle_user_unfollow(self, event_data):
        """Handle user unfollowing the OA"""
        user_id = event_data.get('follower', {}).get('id')

        _logger.info(f'User {user_id} unfollowed the OA')

        # Find conversation
        conversation = self.env['zalo.conversation'].search([
            ('zalo_user_id', '=', user_id),
        ], limit=1)

        if conversation:
            conversation.write({'is_follower': False})

        return True

    def _handle_user_submit_info(self, event_data):
        """Handle user submitting info (e.g., phone number)"""
        user_id = event_data.get('sender', {}).get('id')
        info = event_data.get('info', {})

        _logger.info(f'User {user_id} submitted info: {info}')

        # Get or create conversation
        conversation = self._get_or_create_conversation(user_id, event_data.get('sender'))

        # Update partner/patient info if linked
        if conversation.partner_id and info.get('phone'):
            conversation.partner_id.write({'phone': info['phone']})

        return True

    def _get_or_create_conversation(self, zalo_user_id, user_info):
        """
        Get or create conversation for Zalo user.

        Args:
            zalo_user_id: Zalo user ID
            user_info: Dict with user info from webhook

        Returns:
            zalo.conversation record
        """
        user_data = {
            'display_name': user_info.get('name') if user_info else None,
            'avatar': user_info.get('avatar') if user_info else None,
        }

        conversation = self.env['zalo.conversation'].find_or_create_conversation(
            zalo_user_id,
            user_data
        )

        return conversation

    def _send_bus_notification(self, conversation, message):
        """
        Send bus notification for real-time UI update.

        Args:
            conversation: zalo.conversation record
            message: zalo.message record
        """
        notification_data = {
            'type': 'zalo_message',
            'conversation_id': conversation.id,
            'message_id': message.id,
            'from_id': message.from_id,
            'text': message.text,
            'message_type': message.message_type,
            'sent_date': message.sent_date.isoformat() if message.sent_date else None,
        }

        # Send to bus for current company users
        channel = f'zalo_notification_{conversation.company_id.id}'

        self.env['bus.bus']._sendone(channel, 'zalo.message', notification_data)

        _logger.debug(f'Sent bus notification for message {message.id} on channel {channel}')

    @api.model
    def send_message_to_user(self, conversation_id, text, message_type='text'):
        """
        Send outgoing message to Zalo user.

        Args:
            conversation_id: ID of zalo.conversation
            text: Message text
            message_type: Type of message (default: 'text')

        Returns:
            zalo.message record
        """
        conversation = self.env['zalo.conversation'].browse(conversation_id)

        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create and send message
        message = self.env['zalo.message'].create_outgoing_message(
            conversation,
            text,
            message_type
        )

        return message
