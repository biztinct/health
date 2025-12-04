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

        # Check if Zalo is configured (allow opening widget even without config for testing)
        zalo_config = self.env['zalo.config'].search([], limit=1)  # Get any config, not just connected

        # NOTE: Configuration check disabled for testing - widget can open without active config
        # if not zalo_config or zalo_config.state != 'connected':
        #     raise UserError(_(
        #         'Zalo Official Account is not configured.\n\n'
        #         'Please configure Zalo integration first:\n'
        #         '1. Go to Zalo > Configuration > Zalo Settings\n'
        #         '2. Create a new configuration with your App ID, App Secret, and OA ID\n'
        #         '3. Click "Connect to Zalo" to authorize\n'
        #         '4. Enable webhook to receive messages'
        #     ))

        # Create conversation for this lead (allow creation even without active config)
        try:
            conversation = self.env['zalo.conversation'].find_or_create_conversation(
                self.zalo_user_id,
                {'display_name': self.name or self.contact_name}
            )
            return conversation.action_open_chat()
        except ValueError as e:
            # If config is missing, create a demo conversation for testing
            _logger.warning(f'Creating demo Zalo conversation for lead without config: {str(e)}')

            # Get or create a demo config for testing
            demo_config = self.env['zalo.config'].search([], limit=1)
            if not demo_config:
                # Create a minimal demo config
                demo_config = self.env['zalo.config'].create({
                    'name': 'Demo Zalo Config (Testing)',
                    'app_id': 'demo',
                    'app_secret': 'demo',
                    'oa_id': 'demo',
                    'state': 'draft',
                })

            conversation = self.env['zalo.conversation'].create({
                'zalo_user_id': self.zalo_user_id,
                'zalo_user_name': self.name or self.contact_name or 'Unknown',
                'config_id': demo_config.id,
                'state': 'active',
            })
            return conversation.action_open_chat()

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
