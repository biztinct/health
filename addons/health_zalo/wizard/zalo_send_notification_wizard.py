# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZaloSendNotificationWizard(models.TransientModel):
    """
    Wizard to send Zalo notification to a patient/contact.

    Supports quick messages and template-based notifications.
    """
    _name = 'zalo.send.notification.wizard'
    _description = 'Send Zalo Notification Wizard'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
    )

    zalo_user_id = fields.Char(
        string='Zalo User ID',
        related='partner_id.zalo_user_id',
        readonly=True,
    )

    has_zalo = fields.Boolean(
        string='Has Zalo',
        related='partner_id.has_zalo',
        readonly=True,
    )

    message_type = fields.Selection([
        ('text', 'Text Message'),
        ('template', 'Template Notification (ZNS)'),
    ], string='Message Type', default='text', required=True)

    message_text = fields.Text(
        string='Message',
        help='Message to send to the contact via Zalo',
    )

    # Template fields (for future ZNS support)
    template_id = fields.Many2one(
        'zalo.template',
        string='Template',
        help='Zalo Notification Service template',
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Check if partner has Zalo"""
        if self.partner_id and not self.partner_id.has_zalo:
            return {
                'warning': {
                    'title': _('No Zalo Integration'),
                    'message': _('This contact does not have a Zalo User ID configured. Please link their Zalo account first.'),
                }
            }

    def action_send_message(self):
        """Send Zalo message to contact"""
        self.ensure_one()

        if not self.partner_id.has_zalo:
            raise UserError(_('This contact does not have a Zalo User ID. Please link their Zalo account first.'))

        if self.message_type == 'text' and not self.message_text:
            raise UserError(_('Please enter a message to send.'))

        try:
            # Get or create conversation
            conversation = self.env['zalo.conversation'].find_or_create_conversation(
                self.partner_id.zalo_user_id,
                {'display_name': self.partner_id.name}
            )

            # Link conversation to partner if not already linked
            if not conversation.partner_id:
                conversation.partner_id = self.partner_id

            # Create and send message
            message = self.env['zalo.message'].create_outgoing_message(
                conversation,
                self.message_text,
                self.message_type
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Message Sent'),
                    'message': _('Zalo message sent successfully to %s') % self.partner_id.name,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f'Failed to send Zalo message: {e}')
            raise UserError(_('Failed to send Zalo message: %s') % str(e))
