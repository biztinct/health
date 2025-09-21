# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class VisualRuleBuilderWizard(models.TransientModel):
    _name = 'advanced.pricing.visual.wizard'
    _description = 'Visual Rule Builder Wizard'

    name = fields.Char('Rule Name', required=True, default='New Visual Rule')
    engine_id = fields.Many2one('advanced.pricing.engine', 'Pricing Engine', required=True)
    rule_id = fields.Many2one('advanced.pricing.rule', 'Existing Rule', help='Leave empty to create new rule')
    
    level = fields.Selection([
        ('1', 'Level 1 - Base Rules'),
        ('2', 'Level 2 - Conditional Rules'),
        ('3', 'Level 3 - Advanced Rules'),
    ], string='Rule Level', default='1', required=True)
    
    sequence = fields.Integer('Sequence', default=100)
    active = fields.Boolean('Active', default=True)
    
    # Visual builder data
    visual_config = fields.Text('Visual Configuration', help='Blockly workspace configuration')
    generated_code = fields.Text('Generated Code', help='Code generated from visual blocks')
    
    @api.model
    def default_get(self, fields_list):
        """Set defaults from context"""
        res = super().default_get(fields_list)
        
        # Get engine from context or use default
        if self.env.context.get('default_engine_id'):
            res['engine_id'] = self.env.context['default_engine_id']
        elif not res.get('engine_id'):
            default_engine = self.env['advanced.pricing.engine'].search([('active', '=', True)], limit=1)
            if default_engine:
                res['engine_id'] = default_engine.id
        
        # Load existing rule if editing
        if self.env.context.get('default_rule_id'):
            rule = self.env['advanced.pricing.rule'].browse(self.env.context['default_rule_id'])
            if rule.exists():
                res.update({
                    'rule_id': rule.id,
                    'name': rule.name,
                    'engine_id': rule.engine_id.id,
                    'level': rule.level,
                    'sequence': rule.sequence,
                    'active': rule.active,
                    'visual_config': rule.visual_config or '',
                    'generated_code': rule.generated_code or '',
                })
        
        return res

    def action_open_visual_builder(self):
        """Open the visual rule builder interface"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'visual_rule_builder',
            'target': 'fullscreen',
            'context': {
                'wizard_id': self.id,
                'rule_data': {
                    'name': self.name,
                    'engine_id': self.engine_id.id,
                    'level': self.level,
                    'sequence': self.sequence,
                    'active': self.active,
                    'visual_config': self.visual_config,
                    'generated_code': self.generated_code,
                }
            }
        }

    def action_save_rule(self):
        """Save the visual rule to database"""
        self.ensure_one()
        
        if not self.visual_config:
            raise UserError(_('Please build your rule using the visual builder first.'))
        
        # Prepare rule data
        rule_data = {
            'name': self.name,
            'engine_id': self.engine_id.id,
            'level': self.level,
            'sequence': self.sequence,
            'active': self.active,
            'rule_type': 'visual',
            'visual_config': self.visual_config,
            'generated_code': self.generated_code,
            # Convert visual config to standard rule fields
            'condition_field': 'visual_condition',
            'condition_operator': 'custom',
            'condition_value': 'visual_rule',
            'action_type': 'custom',
            'action_value': 0,
        }
        
        if self.rule_id:
            # Update existing rule
            self.rule_id.write(rule_data)
            rule = self.rule_id
        else:
            # Create new rule
            rule = self.env['advanced.pricing.rule'].create(rule_data)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pricing Rule'),
            'res_model': 'advanced.pricing.rule',
            'res_id': rule.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def save_visual_rule_data(self, wizard_id, rule_data):
        """Save visual rule data from JavaScript"""
        wizard = self.browse(wizard_id)
        if not wizard.exists():
            raise UserError(_('Wizard session expired. Please start again.'))
        
        wizard.write({
            'name': rule_data.get('name', wizard.name),
            'visual_config': rule_data.get('visual_config', ''),
            'generated_code': rule_data.get('generated_code', ''),
        })
        
        return wizard.action_save_rule()