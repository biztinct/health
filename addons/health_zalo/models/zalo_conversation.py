# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ZaloConversation(models.Model):
    """
    Zalo conversation thread with a user.

    Represents a messaging conversation between the OA and a Zalo user.
    Linked to res.partner for patient/contact integration.
    """
    _name = 'zalo.conversation'
    _description = 'Zalo Conversation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_message_date desc, id desc'

    name = fields.Char(
        string='Conversation Name',
        compute='_compute_name',
        store=True,
        index=True,
    )

    # Zalo User Info
    zalo_user_id = fields.Char(
        string='Zalo User ID',
        required=True,
        index=True,
        help='Unique Zalo user identifier',
    )
    zalo_user_name = fields.Char(
        string='Zalo User Name',
        help='Display name from Zalo',
    )
    zalo_user_avatar = fields.Char(
        string='Zalo User Avatar URL',
        help='Profile picture URL from Zalo',
    )

    # Odoo Integration
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        index=True,
        tracking=True,
        help='Linked Odoo contact/patient',
    )

    # Configuration
    config_id = fields.Many2one(
        'zalo.config',
        string='Zalo Configuration',
        required=True,
        default=lambda self: self.env['zalo.config'].get_active_config(),
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True,
    )

    # Messages
    message_ids = fields.One2many(
        'zalo.message',
        'conversation_id',
        string='Messages',
    )
    message_count = fields.Integer(
        string='Message Count',
        compute='_compute_message_count',
        store=True,
    )
    unread_count = fields.Integer(
        string='Unread Messages',
        default=0,
        help='Number of unread messages from user',
    )

    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('blocked', 'Blocked'),
    ], string='Status', default='active', required=True, tracking=True)

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # Conversation Metadata
    last_message_date = fields.Datetime(
        string='Last Message',
        help='Timestamp of most recent message',
    )
    last_message_text = fields.Text(
        string='Last Message Text',
        help='Preview of last message',
    )
    last_message_from_us = fields.Boolean(
        string='Last Message From Us',
        help='True if last message was sent by us',
    )

    created_date = fields.Datetime(
        string='Conversation Started',
        default=fields.Datetime.now,
        readonly=True,
    )

    # User Follower (for Zalo following status)
    is_follower = fields.Boolean(
        string='Following OA',
        default=False,
        help='Whether user is following the Official Account',
    )

    @api.depends('zalo_user_name', 'partner_id.name', 'zalo_user_id')
    def _compute_name(self):
        """Compute conversation name from user or partner name"""
        for conv in self:
            if conv.partner_id:
                conv.name = f"{conv.partner_id.name} (Zalo)"
            elif conv.zalo_user_name:
                conv.name = conv.zalo_user_name
            else:
                conv.name = f"Zalo User {conv.zalo_user_id}"

    @api.depends('message_ids')
    def _compute_message_count(self):
        """Count total messages in conversation"""
        for conv in self:
            conv.message_count = len(conv.message_ids)

    def action_open_chat(self):
        """Open chat widget for this conversation"""
        self.ensure_one()

        return {
            'type': 'ir.actions.client',
            'tag': 'zalo_chat_window',
            'params': {
                'conversation_id': self.id,
            },
        }

    def action_mark_as_read(self):
        """Mark all messages as read"""
        self.ensure_one()

        # Mark unread messages as read
        unread_messages = self.message_ids.filtered(lambda m: not m.is_read and m.direction == 'incoming')
        unread_messages.write({'is_read': True})

        self.unread_count = 0

    def action_link_to_partner(self):
        """Open wizard to link conversation to contact/patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Link to Contact'),
            'res_model': 'zalo.link.partner.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
            },
        }

    def action_archive_conversation(self):
        """Archive conversation"""
        self.write({'state': 'archived', 'active': False})

    def action_unarchive_conversation(self):
        """Unarchive conversation"""
        self.write({'state': 'active', 'active': True})

    def action_block_user(self):
        """Block user (stop receiving messages)"""
        self.write({'state': 'blocked'})

    @api.model
    def find_or_create_conversation(self, zalo_user_id, user_info=None):
        """
        Find existing conversation or create new one for Zalo user.

        Args:
            zalo_user_id: Zalo user identifier
            user_info: Dict with user info (name, avatar, etc.)

        Returns:
            zalo.conversation record
        """
        config = self.env['zalo.config'].get_active_config()
        if not config:
            raise ValueError("No active Zalo configuration found")

        # Search for existing conversation
        conversation = self.search([
            ('zalo_user_id', '=', zalo_user_id),
            ('config_id', '=', config.id),
        ], limit=1)

        if conversation:
            # Update user info if provided
            if user_info:
                conversation.write({
                    'zalo_user_name': user_info.get('display_name', conversation.zalo_user_name),
                    'zalo_user_avatar': user_info.get('avatar', conversation.zalo_user_avatar),
                })
            return conversation

        # Create new conversation
        vals = {
            'zalo_user_id': zalo_user_id,
            'config_id': config.id,
        }

        if user_info:
            vals.update({
                'zalo_user_name': user_info.get('display_name'),
                'zalo_user_avatar': user_info.get('avatar'),
            })

        conversation = self.create(vals)
        _logger.info(f'Created new Zalo conversation for user {zalo_user_id}')

        return conversation

    def update_last_message(self, message):
        """Update last message metadata"""
        self.ensure_one()

        self.write({
            'last_message_date': message.sent_date,
            'last_message_text': message.text[:100] if message.text else '(Media)',
            'last_message_from_us': message.direction == 'outgoing',
        })

    def increment_unread_count(self):
        """Increment unread message counter"""
        self.ensure_one()
        self.unread_count += 1
