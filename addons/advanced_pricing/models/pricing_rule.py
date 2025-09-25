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
    
    condition_field = fields.Selection([
        ('order_total', 'Order Total'),
        ('quantity', 'Quantity'),
        ('customer_type', 'Customer Type'),
        ('distance', 'Distance (km)'),
        ('appointment_hour', 'Appointment Hour'),
        ('service_type', 'Service Type'),
        ('service_location', 'Service Location'),
        ('urgency', 'Urgency Level'),
        ('priority', 'Priority'),
        ('service_units', 'Service Units'),
        ('service_city', 'Service City'),
        ('is_weekend', 'Is Weekend'),
        ('is_holiday', 'Is Holiday'),
        ('is_after_hours', 'Is After Hours')
    ], string='Condition Field')
    condition_operator = fields.Selection([
        ('=', 'Equal'),
        ('>', 'Greater Than'),
        ('<', 'Less Than'),
        ('>=', 'Greater or Equal'),
        ('<=', 'Less or Equal'),
        ('between', 'Between')
    ], string='Operator')
    condition_value = fields.Char('Condition Value')
    
    # FSO-based condition fields for pricing rules
    distance_min = fields.Float('Minimum Distance (km)', help='Minimum travel distance to apply this rule')
    distance_max = fields.Float('Maximum Distance (km)', help='Maximum travel distance to apply this rule')
    
    appointment_hour_min = fields.Integer('Minimum Hour', help='Minimum appointment hour (0-23) to apply this rule')
    appointment_hour_max = fields.Integer('Maximum Hour', help='Maximum appointment hour (0-23) to apply this rule')
    
    is_weekend_required = fields.Boolean('Weekend Only', help='Apply only for weekend appointments')
    is_holiday_required = fields.Boolean('Holiday Only', help='Apply only for holiday appointments')
    is_after_hours_required = fields.Boolean('After Hours Only', help='Apply only for after-hours appointments')
    
    service_type = fields.Selection([
        ('home_visit', 'Home Visit'),
        ('clinic_visit', 'Clinic Visit'),
        ('telemedicine', 'Telemedicine'),
        ('emergency', 'Emergency'),
        ('routine_checkup', 'Routine Checkup'),
        ('follow_up', 'Follow-up'),
        ('vaccination', 'Vaccination'),
        ('consultation', 'Consultation')
    ], string='Service Type', help='Apply only for this service type')
    
    service_location = fields.Selection([
        ('home', 'Home'),
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('care_facility', 'Care Facility'),
        ('remote', 'Remote/Online')
    ], string='Service Location', help='Apply only for this service location')
    
    urgency_level = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency')
    ], string='Urgency Level', help='Apply only for this urgency level')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string='Priority', help='Apply only for this priority level')
    
    service_units_min = fields.Integer('Minimum Service Units', help='Minimum service units for bulk pricing')
    service_units_max = fields.Integer('Maximum Service Units', help='Maximum service units for bulk pricing')
    
    service_city = fields.Char('Service City', help='Apply only for services in this city')
    
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
    
    # Product/Category targeting (like standard pricelist rules)
    applied_on = fields.Selection([
        ('3_global', 'All Products'),
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')
    ], string='Apply On', required=True, default='3_global',
       help='Pricelist Item applicable on selected option')
    
    product_tmpl_id = fields.Many2one('product.template', 'Product Template',
                                     help='Specify a template if this rule only applies to one product template. Keep empty otherwise.')
    product_id = fields.Many2one('product.product', 'Product',
                                help='Specify a product if this rule only applies to one product. Keep empty otherwise.')
    categ_id = fields.Many2one('product.category', 'Product Category',
                              help='Specify a product category if this rule only applies to products belonging to this category or its children categories. Keep empty otherwise.')
    
    # Legacy fields for backward compatibility
    product_ids = fields.Many2many('product.product', string='Products (Legacy)', 
                                  help='Legacy field - use Product field instead')
    category_ids = fields.Many2many('product.category', string='Categories (Legacy)',
                                   help='Legacy field - use Product Category field instead')
    
    def evaluate_condition(self, product_id, partner_id, quantity, context_data):
        """Evaluate if this rule applies"""
        self.ensure_one()
        
        _logger.info(f"  Rule {self.name}: Checking product applicability for product {product_id}")
        # Check product applicability (like standard pricelist rules)
        if not self._check_product_applicability(product_id):
            _logger.info(f"  Rule {self.name}: FAILED - Product not applicable")
            return False
        
        _logger.info(f"  Rule {self.name}: Product check passed")
        
        # Check quantity
        if self.min_quantity and quantity < self.min_quantity:
            _logger.info(f"  Rule {self.name}: FAILED - Quantity {quantity} < min {self.min_quantity}")
            return False
        if self.max_quantity and quantity > self.max_quantity:
            _logger.info(f"  Rule {self.name}: FAILED - Quantity {quantity} > max {self.max_quantity}")
            return False
        
        _logger.info(f"  Rule {self.name}: Quantity check passed")
        
        # Check FSO-based conditions
        if not self._evaluate_fso_conditions(context_data):
            _logger.info(f"  Rule {self.name}: FAILED - FSO conditions not met")
            return False
        
        _logger.info(f"  Rule {self.name}: FSO conditions passed")
        
        # Evaluate field condition
        if self.rule_type == 'condition':
            result = self._evaluate_field_condition(context_data)
            _logger.info(f"  Rule {self.name}: Field condition result: {result}")
            return result
        
        _logger.info(f"  Rule {self.name}: All checks passed")
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
    
    def _evaluate_fso_conditions(self, context_data):
        """Evaluate FSO-based conditions"""
        # Distance conditions
        if self.distance_min or self.distance_max:
            distance = context_data.get('distance', 0)
            if self.distance_min and distance < self.distance_min:
                return False
            if self.distance_max and distance > self.distance_max:
                return False
        
        # Appointment hour conditions
        if self.appointment_hour_min is not None or self.appointment_hour_max is not None:
            hour = context_data.get('appointment_hour', 0)
            if self.appointment_hour_min is not None and hour < self.appointment_hour_min:
                return False
            if self.appointment_hour_max is not None and hour > self.appointment_hour_max:
                return False
        
        # Weekend condition
        if self.is_weekend_required:
            if not context_data.get('is_weekend', False):
                return False
        
        # Holiday condition
        if self.is_holiday_required:
            if not context_data.get('is_holiday', False):
                return False
        
        # After hours condition
        if self.is_after_hours_required:
            is_after_hours = context_data.get('is_after_hours', False)
            _logger.info(f"    After-hours required: {self.is_after_hours_required}, context is_after_hours: {is_after_hours}")
            if not is_after_hours:
                _logger.info(f"    After-hours condition FAILED")
                return False
        
        # Service type condition
        if self.service_type:
            if context_data.get('service_type') != self.service_type:
                return False
        
        # Service location condition
        if self.service_location:
            if context_data.get('service_location') != self.service_location:
                return False
        
        # Urgency level condition
        if self.urgency_level:
            if context_data.get('urgency') != self.urgency_level:
                return False
        
        # Priority condition
        if self.priority:
            if context_data.get('priority') != self.priority:
                return False
        
        # Service units conditions
        if self.service_units_min or self.service_units_max:
            units = context_data.get('service_units', 0)
            if self.service_units_min and units < self.service_units_min:
                return False
            if self.service_units_max and units > self.service_units_max:
                return False
        
        # Service city condition
        if self.service_city:
            if context_data.get('service_city', '').lower() != self.service_city.lower():
                return False
        
        return True
    
    def _check_product_applicability(self, product_id):
        """Check if rule applies to this product (like standard pricelist rules)"""
        self.ensure_one()
        
        if self.applied_on == '3_global':
            return True  # Applies to all products
        
        if not product_id:
            return False
        
        product = self.env['product.product'].browse(product_id)
        
        if self.applied_on == '0_product_variant':
            return self.product_id.id == product_id
        elif self.applied_on == '1_product':
            return self.product_tmpl_id.id == product.product_tmpl_id.id
        elif self.applied_on == '2_product_category':
            return product.categ_id.id == self.categ_id.id or \
                   self.categ_id.id in product.categ_id.parent_path.split('/')[:-1]
        
        return False
    
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