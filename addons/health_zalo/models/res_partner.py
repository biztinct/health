# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """
    Extend res.partner to add Zalo integration fields.

    Adds Zalo user ID, conversation link, and quick action buttons.
    """
    _inherit = 'res.partner'

    # Zalo Integration
    zalo_user_id = fields.Char(
        string='Zalo User ID',
        index=True,
        help='Unique Zalo user identifier for this contact',
    )

    zalo_conversation_id = fields.Many2one(
        'zalo.conversation',
        string='Zalo Conversation',
        compute='_compute_zalo_conversation',
        store=True,
        help='Active Zalo conversation with this contact',
    )

    zalo_conversation_count = fields.Integer(
        string='Zalo Conversations',
        compute='_compute_zalo_conversation_count',
    )

    has_zalo = fields.Boolean(
        string='Has Zalo',
        compute='_compute_has_zalo',
        search='_search_has_zalo',
        help='Whether this contact has Zalo integration',
    )

    zalo_last_message_date = fields.Datetime(
        string='Last Zalo Message',
        related='zalo_conversation_id.last_message_date',
        store=True,
    )

    @api.depends('zalo_user_id')
    def _compute_zalo_conversation(self):
        """Find active Zalo conversation for this partner"""
        for partner in self:
            if partner.zalo_user_id:
                conversation = self.env['zalo.conversation'].search([
                    ('partner_id', '=', partner.id),
                    ('state', '=', 'active'),
                ], limit=1, order='last_message_date desc')
                partner.zalo_conversation_id = conversation
            else:
                partner.zalo_conversation_id = False

    def _compute_zalo_conversation_count(self):
        """Count all Zalo conversations for this partner"""
        for partner in self:
            partner.zalo_conversation_count = self.env['zalo.conversation'].search_count([
                ('partner_id', '=', partner.id),
            ])

    @api.depends('zalo_user_id')
    def _compute_has_zalo(self):
        """Check if partner has Zalo integration"""
        for partner in self:
            partner.has_zalo = bool(partner.zalo_user_id)

    def _search_has_zalo(self, operator, value):
        """Search for partners with/without Zalo"""
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('zalo_user_id', '!=', False)]
        else:
            return [('zalo_user_id', '=', False)]

    def action_open_zalo_chat(self):
        """Open Zalo chat window for this contact"""
        self.ensure_one()

        if not self.zalo_conversation_id:
            # Create conversation if doesn't exist
            if not self.zalo_user_id:
                from odoo.exceptions import UserError
                raise UserError(_('This contact does not have a Zalo User ID configured.'))

            conversation = self.env['zalo.conversation'].find_or_create_conversation(
                self.zalo_user_id,
                {'display_name': self.name}
            )
            conversation.partner_id = self.id
        else:
            conversation = self.zalo_conversation_id

        return conversation.action_open_chat()

    def action_call_zalo(self):
        """Initiate Zalo call (opens Zalo app)"""
        self.ensure_one()

        if not self.zalo_user_id:
            from odoo.exceptions import UserError
            raise UserError(_('This contact does not have a Zalo User ID configured.'))

        # Zalo call URL scheme (opens Zalo app if installed)
        zalo_call_url = f"zalo://call?to={self.zalo_user_id}"

        return {
            'type': 'ir.actions.act_url',
            'url': zalo_call_url,
            'target': 'new',
        }

    def action_view_zalo_conversations(self):
        """View all Zalo conversations for this contact"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Zalo Conversations'),
            'res_model': 'zalo.conversation',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_link_zalo_user(self):
        """Open wizard to link Zalo user to this contact"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Link Zalo User'),
            'res_model': 'zalo.link.user.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }

    @api.model
    def find_partner_by_zalo_id(self, zalo_user_id):
        """Find partner by Zalo user ID"""
        return self.search([('zalo_user_id', '=', zalo_user_id)], limit=1)
