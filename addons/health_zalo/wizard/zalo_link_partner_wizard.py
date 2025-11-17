# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZaloLinkPartnerWizard(models.TransientModel):
    """
    Wizard to link Zalo conversation to a res.partner contact.

    Allows searching for existing contacts or creating new ones.
    """
    _name = 'zalo.link.partner.wizard'
    _description = 'Link Zalo to Contact Wizard'

    conversation_id = fields.Many2one(
        'zalo.conversation',
        string='Zalo Conversation',
        required=True,
    )

    zalo_user_id = fields.Char(
        string='Zalo User ID',
        related='conversation_id.zalo_user_id',
        readonly=True,
    )

    zalo_user_name = fields.Char(
        string='Zalo User Name',
        related='conversation_id.zalo_user_name',
        readonly=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Link to Contact',
        domain=[],
        help='Select existing contact to link to this Zalo conversation',
    )

    create_new_partner = fields.Boolean(
        string='Create New Contact',
        default=False,
    )

    new_partner_name = fields.Char(
        string='Contact Name',
    )

    new_partner_phone = fields.Char(
        string='Phone',
    )

    new_partner_email = fields.Char(
        string='Email',
    )

    new_partner_is_patient = fields.Boolean(
        string='Is Patient',
        default=True,
    )

    @api.onchange('zalo_user_name')
    def _onchange_zalo_user_name(self):
        """Pre-fill new partner name from Zalo user name"""
        if self.zalo_user_name and not self.new_partner_name:
            self.new_partner_name = self.zalo_user_name

    def action_link_partner(self):
        """Link conversation to partner"""
        self.ensure_one()

        if self.create_new_partner:
            # Create new partner
            if not self.new_partner_name:
                raise UserError(_('Please enter a name for the new contact.'))

            partner = self.env['res.partner'].create({
                'name': self.new_partner_name,
                'phone': self.new_partner_phone,
                'email': self.new_partner_email,
                'is_patient': self.new_partner_is_patient,
                'zalo_user_id': self.zalo_user_id,
            })

            self.conversation_id.partner_id = partner

            message = _('Created new contact and linked to Zalo conversation: %s') % partner.name

        else:
            # Link to existing partner
            if not self.partner_id:
                raise UserError(_('Please select a contact to link.'))

            self.partner_id.zalo_user_id = self.zalo_user_id
            self.conversation_id.partner_id = self.partner_id

            message = _('Linked Zalo conversation to contact: %s') % self.partner_id.name

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
