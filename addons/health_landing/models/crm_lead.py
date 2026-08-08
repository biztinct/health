# -*- coding: utf-8 -*-

from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_open_lead_hub(self):
        """Open this lead. The Lead Hub-Spoke dashboard is retired."""
        self.ensure_one()
        form = self.env.ref('health_crm.view_crm_contact_form_crm_center',
                            raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': self.name or 'Contact',
            'res_model': 'crm.lead',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(form.id if form else False, 'form')],
            'target': 'current',
        }
