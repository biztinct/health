# -*- coding: utf-8 -*-

from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_hub_spoke(self):
        """Open hub-and-spoke dashboard for this patient"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'health_landing_patient_hub',
            'name': f'Patient Hub: {self.name}',
            'params': {
                'patient_id': self.id,
                'patient_name': self.name,
            },
        }
