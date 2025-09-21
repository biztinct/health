# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class AdvancedPricingRule(models.Model):
    _name = 'advanced.pricing.rule'
    _description = 'Advanced Pricing Rule'
    _order = 'sequence, id'
    
    name = fields.Char('Rule Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    engine_id = fields.Many2one('advanced.pricing.engine', 'Pricing Engine', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    
    level = fields.Selection([
        ('1', 'Level 1 - Base Rules'),
        ('2', 'Level 2 - Cascading Rules')
    ], string='Rule Level', default='1', required=True)
    
    rule_type = fields.Selection([
        ('condition', 'Conditional'),
        ('formula', 'Formula-based'),
        ('matrix', 'Matrix'),
        ('custom', 'Custom Python'),
        ('visual', 'Visual Rule')
    ], string='Rule Type', default='condition', required=True)
    
    blockly_xml = fields.Text('Blockly XML')
    generated_code = fields.Text('Generated Code', readonly=True)
    visual_config = fields.Text('Visual Configuration', help='Blockly workspace configuration')
    
    # Visual builder fields
    is_visual_rule = fields.Boolean('Is Visual Rule', compute='_compute_is_visual_rule', store=True)
    
    condition_field = fields.Char('Condition Field')
    condition_operator = fields.Selection([
        ('=', 'Equal'),
        ('>', 'Greater Than'),
        ('<', 'Less Than'),
        ('>=', 'Greater or Equal'),
        ('<=', 'Less or Equal'),
        ('between', 'Between')
    ], string='Operator')
    condition_value = fields.Char('Condition Value')
    
    action_type = fields.Selection([
        ('add', 'Add Amount'),
        ('multiply', 'Multiply by Factor'),
        ('percentage', 'Apply Percentage'),
        ('fixed', 'Set Fixed Price'),
        ('formula', 'Apply Formula')
    ], string='Action Type', default='add')
    
    action_value = fields.Float('Action Value')
    action_formula = fields.Text('Action Formula')
    
    min_quantity = fields.Float('Minimum Quantity', default=0.0)
    max_quantity = fields.Float('Maximum Quantity', default=0.0)
    
    product_ids = fields.Many2many('product.product', string='Products')
    category_ids = fields.Many2many('product.category', string='Categories')
    
    def evaluate_condition(self, product_id, partner_id, quantity, context_data):
        """Evaluate if this rule applies"""
        self.ensure_one()
        
        # Check quantity
        if self.min_quantity and quantity < self.min_quantity:
            return False
        if self.max_quantity and quantity > self.max_quantity:
            return False
        
        # Evaluate condition
        if self.rule_type == 'condition':
            return self._evaluate_field_condition(context_data)
        
        return True
    
    def _evaluate_field_condition(self, context_data):
        """Evaluate field-based condition"""
        if not self.condition_field:
            return True
        
        value = context_data
        for field_part in self.condition_field.split('.'):
            if isinstance(value, dict):
                value = value.get(field_part)
            else:
                return False
        
        if self.condition_operator == '=':
            return value == self._parse_value(self.condition_value)
        elif self.condition_operator == '>':
            return value > self._parse_value(self.condition_value)
        elif self.condition_operator == '<':
            return value < self._parse_value(self.condition_value)
        
        return False
    
    def _parse_value(self, value_str):
        """Parse string value to appropriate type"""
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except:
            return value_str
    
    def apply_action(self, price, context_data):
        """Apply the pricing action"""
        self.ensure_one()
        
        if self.action_type == 'add':
            return price + self.action_value
        elif self.action_type == 'multiply':
            return price * self.action_value
        elif self.action_type == 'percentage':
            return price * (1 + self.action_value / 100)
        elif self.action_type == 'fixed':
            return self.action_value
        
        return price
    
    def apply_cascading_action(self, price, context_data):
        """Apply cascading action for Level 2 rules"""
        return self.apply_action(price, context_data)
    
    @api.depends('rule_type')
    def _compute_is_visual_rule(self):
        """Compute if this is a visual rule"""
        for rule in self:
            rule.is_visual_rule = rule.rule_type == 'visual'
    
    def action_open_visual_builder(self):
        """Open the visual rule builder interface"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'visual_rule_builder',
            'target': 'fullscreen',
            'context': {
                'rule_data': {
                    'id': self.id,
                    'name': self.name,
                    'engine_id': self.engine_id.id,
                    'level': self.level,
                    'sequence': self.sequence,
                    'active': self.active,
                    'visual_config': self.visual_config or '',
                    'generated_code': self.generated_code or '',
                }
            }
        }
    
    def action_create_visual_rule(self):
        """Create a new visual rule"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visual Rule Builder',
            'res_model': 'advanced.pricing.visual.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_engine_id': self.engine_id.id,
                'default_name': f'{self.name} - Visual Rule',
            }
        }