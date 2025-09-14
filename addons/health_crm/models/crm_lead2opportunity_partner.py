# -*- coding: utf-8 -*-

from odoo import api, models


class Lead2OpportunityPartner(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner'

    def action_apply(self):
        """Override to use healthcare opportunity form after conversion"""
        result = super().action_apply()
        
        # If we successfully converted to opportunity, redirect to our healthcare form
        if result and isinstance(result, dict) and result.get('res_model') == 'crm.lead':
            # Get the converted lead/opportunity record
            lead_ids = result.get('res_id')
            if not isinstance(lead_ids, list):
                lead_ids = [lead_ids] if lead_ids else []
            
            # If we have a single converted opportunity, open it with our healthcare form
            if len(lead_ids) == 1:
                lead = self.env['crm.lead'].browse(lead_ids[0])
                if lead.type == 'opportunity':
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'crm.lead',
                        'res_id': lead.id,
                        'view_mode': 'form',
                        'view_id': self.env.ref('health_crm.view_healthcare_opportunity_form').id,
                        'target': 'current',
                        'context': {'default_type': 'opportunity'},
                    }
        
        return result