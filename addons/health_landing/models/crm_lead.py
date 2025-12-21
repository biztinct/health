# -*- coding: utf-8 -*-

from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_open_lead_hub(self):
        """Open hub-and-spoke dashboard for this lead."""
        self.ensure_one()

        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_lead_hub',
            'name': f'Lead Hub: {self.name}',
            'params': {
                'lead_id': self.id,
                'lead_name': self.name,
            },
        }
