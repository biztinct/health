# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import json

class PricingImportWizard(models.TransientModel):
    _name = 'advanced.pricing.import.wizard'
    _description = 'Import Pricing Rules Wizard'
    
    file = fields.Binary('File', required=True)
    filename = fields.Char('Filename')
    engine_id = fields.Many2one('advanced.pricing.engine', 'Target Engine', required=True)
    
    def import_rules(self):
        """Import rules from file"""
        self.ensure_one()
        # Implementation here
        return {'type': 'ir.actions.act_window_close'}