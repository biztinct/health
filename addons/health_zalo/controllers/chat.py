# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class ZaloChatController(http.Controller):
    """
    Controller for Zalo chat interface.

    Provides endpoints for chat widget to fetch/send messages.
    """

    @http.route('/zalo/chat/conversations', type='jsonrpc', auth='user', methods=['POST'])
    def get_conversations(self, **kwargs):
        """
        Get list of Zalo conversations for current user.

        Returns:
            List of conversation data
        """
        try:
            limit = kwargs.get('limit', 20)
            offset = kwargs.get('offset', 0)
            search = kwargs.get('search')

            domain = [('state', '=', 'active')]

            if search:
                domain.append('|')
                domain.append(('name', 'ilike', search))
                domain.append(('zalo_user_name', 'ilike', search))

            conversations = request.env['zalo.conversation'].search(
                domain,
                limit=limit,
                offset=offset,
                order='last_message_date desc',
            )

            return {
                'conversations': [{
                    'id': conv.id,
                    'name': conv.name,
                    'zalo_user_id': conv.zalo_user_id,
                    'zalo_user_name': conv.zalo_user_name,
                    'zalo_user_avatar': conv.zalo_user_avatar,
                    'last_message_text': conv.last_message_text,
                    'last_message_date': conv.last_message_date.isoformat() if conv.last_message_date else None,
                    'last_message_from_us': conv.last_message_from_us,
                    'unread_count': conv.unread_count,
                } for conv in conversations],
                'total': request.env['zalo.conversation'].search_count(domain),
            }

        except Exception as e:
            _logger.error(f'Error fetching conversations: {e}', exc_info=True)
            return {'error': str(e)}

    @http.route('/zalo/chat/conversation/<int:conversation_id>/messages', type='jsonrpc', auth='user', methods=['POST'])
    def get_messages(self, conversation_id, **kwargs):
        """
        Get messages for a conversation.

        Args:
            conversation_id: ID of conversation

        Returns:
            List of message data
        """
        try:
            limit = kwargs.get('limit', 50)
            offset = kwargs.get('offset', 0)

            conversation = request.env['zalo.conversation'].browse(conversation_id)

            if not conversation.exists():
                return {'error': 'Conversation not found'}

            messages = request.env['zalo.message'].search(
                [('conversation_id', '=', conversation_id)],
                limit=limit,
                offset=offset,
                order='sent_date asc',
            )

            # Mark messages as read
            conversation.action_mark_as_read()

            return {
                'messages': [{
                    'id': msg.id,
                    'direction': msg.direction,
                    'message_type': msg.message_type,
                    'text': msg.text,
                    'sent_date': msg.sent_date.isoformat() if msg.sent_date else None,
                    'state': msg.state,
                    'from_id': msg.from_id,
                    'to_id': msg.to_id,
                    'attachments': [{
                        'id': att.id,
                        'name': att.name,
                        'type': att.attachment_type,
                        'url': att.attachment_url,
                        'thumbnail_url': att.thumbnail_url,
                    } for att in msg.attachment_ids],
                } for msg in messages],
                'conversation': {
                    'id': conversation.id,
                    'name': conversation.name,
                    'zalo_user_avatar': conversation.zalo_user_avatar,
                },
            }

        except Exception as e:
            _logger.error(f'Error fetching messages: {e}', exc_info=True)
            return {'error': str(e)}

    @http.route('/zalo/chat/send_message', type='jsonrpc', auth='user', methods=['POST'])
    def send_message(self, **kwargs):
        """
        Send message to Zalo user.

        Args:
            conversation_id: ID of conversation
            text: Message text
            message_type: Type of message (default: 'text')

        Returns:
            Message data
        """
        try:
            conversation_id = kwargs.get('conversation_id')
            text = kwargs.get('text')
            message_type = kwargs.get('message_type', 'text')

            if not conversation_id or not text:
                return {'error': 'Missing required parameters'}

            conversation = request.env['zalo.conversation'].browse(conversation_id)

            if not conversation.exists():
                return {'error': 'Conversation not found'}

            # Create and send message
            message = request.env['zalo.message'].create_outgoing_message(
                conversation,
                text,
                message_type
            )

            return {
                'message': {
                    'id': message.id,
                    'direction': message.direction,
                    'message_type': message.message_type,
                    'text': message.text,
                    'sent_date': message.sent_date.isoformat() if message.sent_date else None,
                    'state': message.state,
                }
            }

        except Exception as e:
            _logger.error(f'Error sending message: {e}', exc_info=True)
            return {'error': str(e)}

    @http.route('/zalo/chat/mark_as_read', type='jsonrpc', auth='user', methods=['POST'])
    def mark_as_read(self, **kwargs):
        """
        Mark conversation as read.

        Args:
            conversation_id: ID of conversation

        Returns:
            Success status
        """
        try:
            conversation_id = kwargs.get('conversation_id')

            if not conversation_id:
                return {'error': 'Missing conversation_id'}

            conversation = request.env['zalo.conversation'].browse(conversation_id)

            if not conversation.exists():
                return {'error': 'Conversation not found'}

            conversation.action_mark_as_read()

            return {'success': True}

        except Exception as e:
            _logger.error(f'Error marking as read: {e}', exc_info=True)
            return {'error': str(e)}

    @http.route('/zalo/chat/conversations/active', type='json', auth='user', methods=['POST'])
    def get_active_conversations(self, **kwargs):
        """
        Get active conversations for Chat Hub widget.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            Dict with conversations list and total_unread count
        """
        try:
            limit = kwargs.get('limit', 50)

            result = request.env['zalo.conversation'].search_active_conversations(limit=limit)

            return result

        except Exception as e:
            _logger.error(f'Error fetching active conversations: {e}', exc_info=True)
            return {
                'conversations': [],
                'total_unread': 0,
                'error': str(e)
            }

    @http.route('/zalo/chat/mark_all_read', type='json', auth='user', methods=['POST'])
    def mark_all_read(self, **kwargs):
        """
        Mark all conversations as read.

        Returns:
            Success status
        """
        try:
            # Get all active conversations with unread messages
            conversations = request.env['zalo.conversation'].search([
                ('state', '=', 'active'),
                ('unread_count', '>', 0),
            ])

            # Mark each as read
            for conversation in conversations:
                conversation.action_mark_as_read()

            return {'success': True}

        except Exception as e:
            _logger.error(f'Error marking all as read: {e}', exc_info=True)
            return {'error': str(e)}
