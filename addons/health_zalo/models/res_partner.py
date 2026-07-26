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
        from odoo.exceptions import UserError

        if not self.zalo_user_id:
            raise UserError(_('This contact does not have a Zalo User ID configured.'))

        if not self.zalo_conversation_id:
            # Z9: the old branch here silently created a "Demo Zalo Config
            # (Testing)" row with app_id/app_secret/oa_id all set to "demo"
            # whenever no real configuration existed — a permanent, live,
            # fake credential record that then satisfied every
            # `search([('active','=',True)])` in the ZNS contract. An honest
            # refusal is the whole fix.
            try:
                conversation = self.env['zalo.conversation'].find_or_create_conversation(
                    self.zalo_user_id,
                    {'display_name': self.name}
                )
                conversation.partner_id = self.id
            except ValueError as exc:
                _logger.info('Zalo chat unavailable for partner %s: %s',
                             self.id, exc)
                raise UserError(_(
                    'Zalo is not connected yet. Open Care Command Setup → '
                    'Channel Center and connect your Official Account.')) from exc
        else:
            conversation = self.zalo_conversation_id

        return conversation.action_open_chat()

    def action_call_zalo(self):
        """Initiate Zalo call (opens Zalo app)"""
        self.ensure_one()
        from odoo.exceptions import UserError

        if not self.zalo_user_id:
            raise UserError(_('This contact does not have a Zalo User ID configured.'))

        # Check if Zalo is configured
        zalo_config = self.env['zalo.config'].search([('state', '=', 'connected')], limit=1)
        if not zalo_config:
            raise UserError(_(
                'Zalo Official Account is not configured.\n\n'
                'Please configure Zalo integration first by going to:\n'
                'Zalo > Configuration > Zalo Settings'
            ))

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

    # Z9: `action_link_zalo_user` pointed at `zalo.link.user.wizard`, a model
    # that has never existed (the real one is `zalo.link.partner.wizard`, and
    # it links a CONVERSATION to a contact — there is nothing to link from a
    # contact with no conversation). The button raised a bare KeyError for
    # every user who pressed it; it is removed here along with the two view
    # buttons that called it.

    @api.model
    def find_partner_by_zalo_id(self, zalo_user_id):
        """Find partner by Zalo user ID"""
        return self.search([('zalo_user_id', '=', zalo_user_id)], limit=1)
