# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    """
    Extend crm.lead to add Zalo integration fields.

    Adds Zalo user ID and quick action buttons.
    """
    _inherit = 'crm.lead'

    # Zalo Integration
    zalo_user_id = fields.Char(
        string='Zalo User ID',
        index=True,
        help='Unique Zalo user identifier for this lead/contact',
    )

    has_zalo = fields.Boolean(
        string='Has Zalo',
        compute='_compute_has_zalo',
        help='Whether this lead has Zalo integration',
    )

    @api.depends('zalo_user_id')
    def _compute_has_zalo(self):
        """Check if lead has Zalo integration"""
        for lead in self:
            lead.has_zalo = bool(lead.zalo_user_id)

    def action_open_zalo_chat(self):
        """Open Zalo chat window for this lead - delegates to partner if exists"""
        self.ensure_one()
        from odoo.exceptions import UserError

        if not self.zalo_user_id:
            raise UserError(_('This contact does not have a Zalo User ID configured.'))

        # If partner exists, use partner's action
        if self.partner_id:
            return self.partner_id.action_open_zalo_chat()

        # Z9: this branch used to auto-create a "Demo Zalo Config (Testing)"
        # row with fake credentials whenever Zalo was not configured — which
        # then satisfied the ZNS contract's active-config search for every
        # module in the system. Refusing honestly is the fix.
        try:
            conversation = self.env['zalo.conversation'].find_or_create_conversation(
                self.zalo_user_id,
                {'display_name': self.name or self.contact_name}
            )
            return conversation.action_open_chat()
        except ValueError as exc:
            _logger.info('Zalo chat unavailable for lead %s: %s', self.id, exc)
            raise UserError(_(
                'Zalo is not connected yet. Open Care Command Setup → '
                'Channel Center and connect your Official Account.')) from exc

    def action_call_zalo(self):
        """Initiate Zalo call for this lead"""
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

    def _create_lead_partner_data(self, name, is_company, parent_id=False):
        """
        Override to include Zalo data when creating partner from lead.
        This ensures Zalo User ID is copied to the created partner/patient.
        """
        vals = super()._create_lead_partner_data(name, is_company, parent_id=parent_id)

        # Add Zalo User ID if available
        if self.zalo_user_id:
            vals['zalo_user_id'] = self.zalo_user_id

        return vals
