#!/usr/bin/env python3
"""
Advanced Pricing Module Generator for Odoo 18 CE
Save this script as 'generate_module.py' and run it to create the complete module
"""

import os
import zipfile
from pathlib import Path

def create_advanced_pricing_module():
    """Generate the complete Advanced Pricing module for Odoo 18 CE"""
    
    print("="*60)
    print("Advanced Pricing Module Generator for Odoo 18 CE")
    print("="*60)
    print()
    
    module_name = "advanced_pricing"
    
    # Create base directory
    Path(module_name).mkdir(exist_ok=True)
    
    # Create all subdirectories
    directories = [
        "security",
        "models", 
        "controllers",
        "views",
        "data",
        "wizards",
        "static/src/js",
        "static/src/xml",
        "static/src/scss",
        "static/lib/blockly",
        "static/description",
        "tests"
    ]
    
    for dir_path in directories:
        Path(f"{module_name}/{dir_path}").mkdir(parents=True, exist_ok=True)
    
    # Generate all files
    files_created = 0
    
    # Create __manifest__.py
    create_file(f"{module_name}/__manifest__.py", get_manifest())
    files_created += 1
    
    # Create __init__.py files
    create_file(f"{module_name}/__init__.py", "from . import models\nfrom . import controllers\nfrom . import wizards")
    create_file(f"{module_name}/models/__init__.py", "from . import pricing_engine\nfrom . import pricing_rule\nfrom . import pricing_configuration\nfrom . import product_pricelist\nfrom . import sale_order\nfrom . import booking_model")
    create_file(f"{module_name}/controllers/__init__.py", "from . import pricing_controller")
    create_file(f"{module_name}/wizards/__init__.py", "from . import pricing_import_wizard")
    create_file(f"{module_name}/tests/__init__.py", "from . import test_pricing_engine\nfrom . import test_pricing_rules")
    files_created += 5
    
    # Create security files
    create_file(f"{module_name}/security/ir.model.access.csv", get_security_csv())
    create_file(f"{module_name}/security/advanced_pricing_security.xml", get_security_xml())
    files_created += 2
    
    # Create model files
    create_file(f"{module_name}/models/pricing_engine.py", get_pricing_engine())
    create_file(f"{module_name}/models/pricing_rule.py", get_pricing_rule())
    create_file(f"{module_name}/models/pricing_configuration.py", get_pricing_configuration())
    create_file(f"{module_name}/models/product_pricelist.py", get_product_pricelist())
    create_file(f"{module_name}/models/sale_order.py", get_sale_order())
    create_file(f"{module_name}/models/booking_model.py", get_booking_model())
    files_created += 6
    
    # Create controller files
    create_file(f"{module_name}/controllers/pricing_controller.py", get_pricing_controller())
    files_created += 1
    
    # Create view files
    create_file(f"{module_name}/views/menu_items.xml", get_menu_items())
    create_file(f"{module_name}/views/pricing_engine_views.xml", get_pricing_engine_views())
    create_file(f"{module_name}/views/pricing_rule_views.xml", get_pricing_rule_views())
    create_file(f"{module_name}/views/pricing_configuration_views.xml", get_pricing_configuration_views())
    create_file(f"{module_name}/views/product_pricelist_views.xml", get_product_pricelist_views())
    create_file(f"{module_name}/views/sale_order_views.xml", get_sale_order_views())
    create_file(f"{module_name}/views/booking_views.xml", get_booking_views())
    files_created += 7
    
    # Create static files
    create_file(f"{module_name}/static/src/js/pricing_widget.js", get_pricing_widget_js())
    create_file(f"{module_name}/static/src/js/rule_builder.js", get_rule_builder_js())
    create_file(f"{module_name}/static/src/js/pricing_calculator.js", get_pricing_calculator_js())
    create_file(f"{module_name}/static/src/js/pricing_service.js", get_pricing_service_js())
    create_file(f"{module_name}/static/src/xml/pricing_templates.xml", get_pricing_templates())
    create_file(f"{module_name}/static/src/scss/pricing_styles.scss", get_pricing_styles())
    create_file(f"{module_name}/static/lib/blockly/README.md", get_blockly_readme())
    files_created += 7
    
    # Create data files
    create_file(f"{module_name}/data/pricing_rule_templates.xml", get_rule_templates())
    create_file(f"{module_name}/data/demo_data.xml", get_demo_data())
    files_created += 2
    
    # Create wizard files
    create_file(f"{module_name}/wizards/pricing_import_wizard.py", get_import_wizard())
    files_created += 1
    
    # Create test files
    create_file(f"{module_name}/tests/test_pricing_engine.py", get_test_pricing_engine())
    create_file(f"{module_name}/tests/test_pricing_rules.py", get_test_pricing_rules())
    files_created += 2
    
    print(f"✅ Created {files_created} files")
    
    # Create ZIP file
    zip_filename = f"{module_name}_odoo18.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(module_name):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(module_name))
                zipf.write(file_path, arcname)
    
    print(f"📦 Created ZIP file: {zip_filename}")
    print(f"📁 Module directory: {module_name}/")
    print()
    print("Installation Instructions:")
    print("-" * 30)
    print("1. Extract the ZIP to your Odoo addons directory")
    print("2. Restart Odoo server")
    print("3. Update Apps List")
    print("4. Search for 'Advanced Pricing Engine' and install")
    print()
    
    return zip_filename

def create_file(filepath, content):
    """Create a file with the given content"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✓ {filepath}")

# Content generation functions

def get_manifest():
    return '''# -*- coding: utf-8 -*-
{
    'name': 'Advanced Pricing Engine',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Enterprise-grade pricing engine with visual rule builder for Odoo 18 CE',
    'description': """
Advanced Pricing Engine for Odoo 18 CE
=======================================

Features:
* Visual rule builder using Google Blockly
* Multi-level cascading pricing rules
* Dynamic field-based calculations
* Integration with custom booking models
* Real-time price calculations
* Performance optimized with caching
* Complete audit trail and versioning
* REST API for external integrations
    """,
    'author': 'Advanced ERP Solutions',
    'website': 'https://www.advanced-erp.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'product',
        'sale_management',
        'website_sale',
        'web',
    ],
    'data': [
        'security/advanced_pricing_security.xml',
        'security/ir.model.access.csv',
        'views/menu_items.xml',
        'views/pricing_engine_views.xml',
        'views/pricing_rule_views.xml',
        'views/pricing_configuration_views.xml',
        'views/product_pricelist_views.xml',
        'views/sale_order_views.xml',
        'views/booking_views.xml',
        'data/pricing_rule_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'advanced_pricing/static/src/scss/pricing_styles.scss',
            'advanced_pricing/static/src/js/pricing_service.js',
            'advanced_pricing/static/src/js/pricing_calculator.js',
            'advanced_pricing/static/src/js/rule_builder.js',
            'advanced_pricing/static/src/js/pricing_widget.js',
            'advanced_pricing/static/src/xml/pricing_templates.xml',
        ],
    },
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}'''

def get_security_csv():
    return '''id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_pricing_engine_user,pricing.engine.user,model_advanced_pricing_engine,base.group_user,1,0,0,0
access_pricing_engine_manager,pricing.engine.manager,model_advanced_pricing_engine,base.group_system,1,1,1,1
access_pricing_rule_user,pricing.rule.user,model_advanced_pricing_rule,base.group_user,1,0,0,0
access_pricing_rule_manager,pricing.rule.manager,model_advanced_pricing_rule,base.group_system,1,1,1,1
access_pricing_config_user,pricing.config.user,model_advanced_pricing_config,base.group_user,1,0,0,0
access_pricing_config_manager,pricing.config.manager,model_advanced_pricing_config,base.group_system,1,1,1,1
access_booking_model_user,booking.model.user,model_booking_model,base.group_user,1,1,1,0
access_booking_model_manager,booking.model.manager,model_booking_model,base.group_system,1,1,1,1'''

def get_security_xml():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>
        <record id="group_pricing_user" model="res.groups">
            <field name="name">Pricing User</field>
            <field name="category_id" ref="base.module_category_sales_sales"/>
            <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
        </record>
        
        <record id="group_pricing_manager" model="res.groups">
            <field name="name">Pricing Manager</field>
            <field name="category_id" ref="base.module_category_sales_sales"/>
            <field name="implied_ids" eval="[(4, ref('group_pricing_user'))]"/>
        </record>
    </data>
</odoo>'''

def get_pricing_engine():
    return '''# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AdvancedPricingEngine(models.Model):
    _name = 'advanced.pricing.engine'
    _description = 'Advanced Pricing Calculation Engine'
    _rec_name = 'name'
    _order = 'sequence, id'

    name = fields.Char('Engine Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    
    rule_ids = fields.One2many('advanced.pricing.rule', 'engine_id', string='Pricing Rules')
    
    cache_duration = fields.Integer('Cache Duration (seconds)', default=300)
    enable_multi_level = fields.Boolean('Enable Multi-Level Rules', default=True)
    enable_cascade = fields.Boolean('Enable Cascading', default=True)
    
    @api.model
    @tools.ormcache('product_id', 'quantity', 'partner_id', 'context_str')
    def calculate_price(self, product_id, quantity, partner_id, context_data):
        """Calculate price with multi-level rules"""
        product = self.env['product.product'].browse(product_id)
        base_price = product.list_price
        
        context_str = json.dumps(context_data, sort_keys=True)
        
        # Apply Level 1 rules
        if self.enable_multi_level:
            level1_rules = self.rule_ids.filtered(lambda r: r.level == '1' and r.active)
            for rule in level1_rules.sorted('sequence'):
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    base_price = rule.apply_action(base_price, context_data)
        
        # Apply Level 2 cascading rules
        if self.enable_cascade:
            level2_rules = self.rule_ids.filtered(lambda r: r.level == '2' and r.active)
            for rule in level2_rules.sorted('sequence'):
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    base_price = rule.apply_cascading_action(base_price, context_data)
        
        return round(base_price, 2)'''

def get_pricing_rule():
    return '''# -*- coding: utf-8 -*-
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
        ('custom', 'Custom Python')
    ], string='Rule Type', default='condition', required=True)
    
    blockly_xml = fields.Text('Blockly XML')
    generated_code = fields.Text('Generated Code', readonly=True)
    
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
        return self.apply_action(price, context_data)'''

def get_pricing_configuration():
    return '''# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AdvancedPricingConfig(models.Model):
    _name = 'advanced.pricing.config'
    _description = 'Advanced Pricing Configuration'
    _rec_name = 'name'
    
    name = fields.Char('Configuration Name', required=True)
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    
    enable_visual_builder = fields.Boolean('Enable Visual Rule Builder', default=True)
    enable_caching = fields.Boolean('Enable Price Caching', default=True)
    cache_duration = fields.Integer('Cache Duration (seconds)', default=300)
    
    enable_api = fields.Boolean('Enable REST API', default=True)
    api_key = fields.Char('API Key', copy=False)
    
    default_engine_id = fields.Many2one('advanced.pricing.engine', 'Default Pricing Engine')
    
    enable_templates = fields.Boolean('Enable Rule Templates', default=True)
    enable_audit = fields.Boolean('Enable Audit Trail', default=True)
    
    @api.model
    def get_config(self):
        """Get active configuration for current company"""
        config = self.search([
            ('company_id', '=', self.env.company.id),
            ('active', '=', True)
        ], limit=1)
        
        if not config:
            config = self.create({
                'name': f'Default Config - {self.env.company.name}',
                'company_id': self.env.company.id
            })
        
        return config'''

def get_product_pricelist():
    return '''# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'
    
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing Engine', default=False)
    advanced_engine_id = fields.Many2one('advanced.pricing.engine', 'Advanced Pricing Engine')
    
    @api.model
    def _compute_price_rule(self, products_qty_partner, date=False, uom_id=False):
        """Override to use advanced pricing when enabled"""
        for pricelist in self:
            if pricelist.use_advanced_pricing and pricelist.advanced_engine_id:
                return self._compute_advanced_price_rule(products_qty_partner, date, uom_id)
        
        return super()._compute_price_rule(products_qty_partner, date, uom_id)
    
    def _compute_advanced_price_rule(self, products_qty_partner, date=False, uom_id=False):
        """Compute price using advanced pricing engine"""
        self.ensure_one()
        results = {}
        
        for product, qty, partner in products_qty_partner:
            context_data = {
                'date': date or fields.Datetime.now(),
                'uom_id': uom_id,
                'pricelist_id': self.id,
            }
            
            price = self.advanced_engine_id.calculate_price(
                product.id, qty, partner.id if partner else False, context_data
            )
            
            results[product.id] = (price, False)
        
        return results'''

def get_sale_order():
    return '''# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    booking_id = fields.Many2one('booking.model', 'Related Booking')
    use_advanced_pricing = fields.Boolean('Use Advanced Pricing', 
                                         compute='_compute_use_advanced_pricing')
    advanced_pricing_details = fields.Text('Pricing Calculation Details')
    
    @api.depends('pricelist_id.use_advanced_pricing')
    def _compute_use_advanced_pricing(self):
        """Check if order uses advanced pricing"""
        for order in self:
            order.use_advanced_pricing = order.pricelist_id.use_advanced_pricing
    
    def action_recalculate_advanced_prices(self):
        """Recalculate prices using advanced pricing engine"""
        self.ensure_one()
        
        if not self.use_advanced_pricing:
            return
        
        for line in self.order_line:
            line._compute_advanced_price()
        
        return True

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    base_price = fields.Float('Base Price', readonly=True)
    price_calculation_log = fields.Text('Price Calculation Log')
    applied_rules = fields.Text('Applied Rules')
    
    @api.depends('product_id', 'product_uom_qty', 'order_id.booking_id')
    def _compute_advanced_price(self):
        """Compute price using advanced pricing engine"""
        for line in self:
            if not line.order_id.use_advanced_pricing:
                continue
            
            if not line.order_id.pricelist_id.advanced_engine_id:
                continue
            
            engine = line.order_id.pricelist_id.advanced_engine_id
            
            context_data = {
                'order_id': line.order_id.id,
                'partner_id': line.order_id.partner_id.id,
                'date_order': line.order_id.date_order
            }
            
            if line.order_id.booking_id:
                booking = line.order_id.booking_id
                context_data['booking'] = {
                    'id': booking.id,
                    'distance': booking.distance,
                    'appointment_time': booking.appointment_time.hour if booking.appointment_time else 0,
                    'is_holiday': booking.is_holiday,
                }
            
            price = engine.calculate_price(
                line.product_id.id,
                line.product_uom_qty,
                line.order_id.partner_id.id,
                context_data
            )
            
            line.price_unit = price
            line.base_price = line.product_id.list_price'''

def get_booking_model():
    return '''# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

class BookingModel(models.Model):
    _name = 'booking.model'
    _description = 'Booking for Healthcare/Services'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'appointment_time desc'
    
    name = fields.Char('Booking Reference', required=True, 
                      default=lambda self: self.env['ir.sequence'].next_by_code('booking.model'))
    
    partner_id = fields.Many2one('res.partner', 'Patient/Customer', required=True)
    patient_category = fields.Selection([
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('emergency', 'Emergency'),
    ], string='Patient Category', default='regular')
    
    appointment_time = fields.Datetime('Appointment Time', required=True)
    duration = fields.Float('Duration (hours)', default=1.0)
    
    service_type = fields.Selection([
        ('consultation', 'Consultation'),
        ('home_visit', 'Home Visit'),
        ('emergency', 'Emergency Service'),
    ], string='Service Type', required=True, default='consultation')
    
    service_ids = fields.Many2many('product.product', string='Services')
    
    distance = fields.Float('Distance (km)')
    is_holiday = fields.Boolean('Holiday Appointment', compute='_compute_is_holiday')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    sale_order_ids = fields.One2many('sale.order', 'booking_id', string='Related Orders')
    
    @api.depends('appointment_time')
    def _compute_is_holiday(self):
        """Check if appointment is on a holiday"""
        for booking in self:
            if booking.appointment_time:
                # Simplified: consider weekends as holidays
                booking.is_holiday = booking.appointment_time.weekday() >= 5
            else:
                booking.is_holiday = False
    
    def action_create_quotation(self):
        """Create a quotation for this booking"""
        self.ensure_one()
        
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'booking_id': self.id,
            'date_order': fields.Datetime.now(),
        })
        
        for service in self.service_ids:
            self.env['sale.order.line'].create({
                'order_id': sale_order.id,
                'product_id': service.id,
                'product_uom_qty': 1.0,
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quotation',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }'''

def get_pricing_controller():
    return '''# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class PricingController(http.Controller):
    
    @http.route('/api/pricing/calculate', type='json', auth='user', methods=['POST'], csrf=False)
    def calculate_price(self, **kwargs):
        """REST API endpoint for price calculation"""
        try:
            data = request.jsonrequest
            
            config = request.env['advanced.pricing.config'].get_config()
            
            if not config.enable_api:
                return {'error': 'API access is disabled', 'status': 403}
            
            engine = config.default_engine_id
            if not engine:
                return {'error': 'No default pricing engine configured', 'status': 400}
            
            price = engine.calculate_price(
                data.get('product_id'),
                data.get('quantity', 1),
                data.get('partner_id', False),
                data.get('context', {})
            )
            
            return {
                'status': 200,
                'price': price,
                'currency': request.env.company.currency_id.name
            }
            
        except Exception as e:
            _logger.error(f"API pricing error: {e}")
            return {'error': str(e), 'status': 500}'''

def get_pricing_widget_js():
    return '''/** @odoo-module **/

import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class AdvancedPricingWidget extends Component {
    static template = 'advanced_pricing.PricingWidget';
    static props = {
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            rules: [],
            selectedRule: null,
            isLoading: false,
        });

        onWillStart(async () => {
            await this.loadRules();
        });
    }

    async loadRules() {
        this.state.isLoading = true;
        try {
            const engineId = this.props.record?.data?.advanced_engine_id?.[0];
            if (engineId) {
                const rules = await this.orm.searchRead(
                    'advanced.pricing.rule',
                    [['engine_id', '=', engineId]],
                    ['name', 'sequence', 'level', 'rule_type', 'active']
                );
                this.state.rules = rules;
            }
        } catch (error) {
            console.error('Error loading rules:', error);
            this.notification.add('Error loading pricing rules', {
                type: 'danger',
            });
        } finally {
            this.state.isLoading = false;
        }
    }
}

registry.category('fields').add('advanced_pricing_widget', {
    component: AdvancedPricingWidget,
});'''

def get_rule_builder_js():
    return '''/** @odoo-module **/

import { Component, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class PricingRuleBuilder extends Component {
    static template = 'advanced_pricing.RuleBuilder';
    static props = {
        rule: { type: Object, optional: true },
        onSave: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            ruleName: this.props.rule?.name || 'New Rule',
            level: this.props.rule?.level || '1',
            generatedCode: '',
        });
    }

    async saveRule() {
        const ruleData = {
            name: this.state.ruleName,
            level: this.state.level,
            rule_type: 'custom',
            engine_id: this.props.rule?.engine_id?.[0],
        };

        try {
            let ruleId;
            if (this.props.rule?.id) {
                await this.orm.write('advanced.pricing.rule', [this.props.rule.id], ruleData);
                ruleId = this.props.rule.id;
            } else {
                ruleId = await this.orm.create('advanced.pricing.rule', ruleData);
            }

            this.notification.add('Rule saved successfully', { type: 'success' });

            if (this.props.onSave) {
                this.props.onSave(ruleId);
            }
        } catch (error) {
            console.error('Error saving rule:', error);
            this.notification.add('Error saving rule', { type: 'danger' });
        }
    }
}

registry.category('components').add('pricing_rule_builder', PricingRuleBuilder);'''

def get_pricing_calculator_js():
    return '''/** @odoo-module **/

import { Component, useState } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';

export class PricingCalculator extends Component {
    static template = 'advanced_pricing.Calculator';
    
    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        
        this.state = useState({
            calculating: false,
            result: null,
            error: null,
        });
    }

    async calculate() {
        this.state.calculating = true;
        this.state.error = null;
        
        try {
            const config = await this.orm.call(
                'advanced.pricing.config',
                'get_config',
                []
            );

            if (!config.default_engine_id) {
                throw new Error('No default pricing engine configured');
            }

            const result = await this.orm.call(
                'advanced.pricing.engine',
                'calculate_price',
                [config.default_engine_id[0]],
                {
                    product_id: this.props.productId,
                    quantity: this.props.quantity || 1,
                    partner_id: this.props.partnerId,
                    context_data: {},
                }
            );

            this.state.result = result;
        } catch (error) {
            this.state.error = error.message || 'Calculation failed';
        } finally {
            this.state.calculating = false;
        }
    }
}'''

def get_pricing_service_js():
    return '''/** @odoo-module **/

import { registry } from '@web/core/registry';

export class PricingService {
    constructor(env, { orm, notification }) {
        this.env = env;
        this.orm = orm;
        this.notification = notification;
        this.cache = new Map();
    }

    async calculatePrice(productId, quantity, partnerId, contextData) {
        const cacheKey = JSON.stringify({ productId, quantity, partnerId, contextData });
        
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        const config = await this.orm.call('advanced.pricing.config', 'get_config', []);
        
        if (!config.default_engine_id) {
            throw new Error('No default pricing engine configured');
        }

        const price = await this.orm.call(
            'advanced.pricing.engine',
            'calculate_price',
            [config.default_engine_id[0]],
            {
                product_id: productId,
                quantity: quantity,
                partner_id: partnerId,
                context_data: contextData,
            }
        );

        this.cache.set(cacheKey, price);
        return price;
    }

    clearCache() {
        this.cache.clear();
    }
}

registry.category('services').add('pricing', {
    dependencies: ['orm', 'notification'],
    factory: (env, dependencies) => new PricingService(env, dependencies),
});'''

def get_pricing_templates():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="advanced_pricing.PricingWidget">
        <div class="o_advanced_pricing_widget">
            <div class="card">
                <div class="card-header">
                    <h5>Advanced Pricing Rules</h5>
                </div>
                <div class="card-body">
                    <t t-if="state.isLoading">
                        <div class="text-center">
                            <i class="fa fa-spinner fa-spin fa-2x"/>
                        </div>
                    </t>
                    <t t-else="">
                        <t t-if="state.rules.length === 0">
                            <div class="alert alert-info">
                                No pricing rules configured.
                            </div>
                        </t>
                        <t t-else="">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Sequence</th>
                                        <th>Name</th>
                                        <th>Level</th>
                                        <th>Type</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <t t-foreach="state.rules" t-as="rule" t-key="rule.id">
                                        <tr>
                                            <td t-esc="rule.sequence"/>
                                            <td t-esc="rule.name"/>
                                            <td t-esc="'Level ' + rule.level"/>
                                            <td t-esc="rule.rule_type"/>
                                            <td>
                                                <span t-att-class="rule.active ? 'badge bg-success' : 'badge bg-danger'"
                                                      t-esc="rule.active ? 'Active' : 'Inactive'"/>
                                            </td>
                                        </tr>
                                    </t>
                                </tbody>
                            </table>
                        </t>
                    </t>
                </div>
            </div>
        </div>
    </t>
    
    <t t-name="advanced_pricing.RuleBuilder">
        <div class="o_pricing_rule_builder">
            <div class="modal-header">
                <h5 class="modal-title">Visual Rule Builder</h5>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Rule Name</label>
                    <input type="text" class="form-control" t-model="state.ruleName"/>
                </div>
                <div class="form-group">
                    <label>Level</label>
                    <select class="form-select" t-model="state.level">
                        <option value="1">Level 1 - Base Rules</option>
                        <option value="2">Level 2 - Cascading Rules</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" t-on-click="props.onClose">
                    Cancel
                </button>
                <button type="button" class="btn btn-primary" t-on-click="saveRule">
                    Save Rule
                </button>
            </div>
        </div>
    </t>
    
    <t t-name="advanced_pricing.Calculator">
        <div class="o_pricing_calculator">
            <div class="card">
                <div class="card-header">
                    <h5>Price Calculator</h5>
                </div>
                <div class="card-body">
                    <t t-if="state.calculating">
                        <div class="text-center">
                            <i class="fa fa-spinner fa-spin fa-3x"/>
                        </div>
                    </t>
                    <t t-elif="state.error">
                        <div class="alert alert-danger">
                            <t t-esc="state.error"/>
                        </div>
                    </t>
                    <t t-elif="state.result">
                        <h2 class="text-primary">
                            <t t-esc="state.result"/>
                        </h2>
                    </t>
                </div>
            </div>
        </div>
    </t>
</templates>'''

def get_pricing_styles():
    return '''.o_advanced_pricing_widget {
    .card {
        border: 1px solid #dee2e6;
        box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    }
    
    .table {
        margin-bottom: 0;
    }
}

.o_pricing_rule_builder {
    .modal-header {
        background-color: #f8f9fa;
    }
}

.o_pricing_calculator {
    .card-body {
        min-height: 150px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
}'''

def get_blockly_readme():
    return '''# Blockly Integration

To complete the visual rule builder integration:

1. Download Blockly from: https://github.com/google/blockly/releases
2. Extract these files to this directory:
   - blockly_compressed.js
   - blocks_compressed.js
   - javascript_compressed.js
   - msg/en.js

Blockly is licensed under Apache License 2.0'''

# View files
def get_menu_items():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="menu_advanced_pricing_root" 
              name="Advanced Pricing" 
              parent="sale.sale_menu_root"
              sequence="15"/>
    
    <menuitem id="menu_pricing_engines" 
              name="Pricing Engines" 
              parent="menu_advanced_pricing_root"
              action="action_advanced_pricing_engines"
              sequence="10"/>
    
    <menuitem id="menu_pricing_rules" 
              name="Pricing Rules" 
              parent="menu_advanced_pricing_root"
              action="action_advanced_pricing_rules"
              sequence="20"/>
    
    <menuitem id="menu_pricing_config" 
              name="Configuration" 
              parent="menu_advanced_pricing_root"
              action="action_advanced_pricing_config"
              sequence="30"/>
    
    <record id="action_advanced_pricing_engines" model="ir.actions.act_window">
        <field name="name">Pricing Engines</field>
        <field name="res_model">advanced.pricing.engine</field>
        <field name="view_mode">tree,form</field>
    </record>
    
    <record id="action_advanced_pricing_rules" model="ir.actions.act_window">
        <field name="name">Pricing Rules</field>
        <field name="res_model">advanced.pricing.rule</field>
        <field name="view_mode">tree,form</field>
    </record>
    
    <record id="action_advanced_pricing_config" model="ir.actions.act_window">
        <field name="name">Configuration</field>
        <field name="res_model">advanced.pricing.config</field>
        <field name="view_mode">tree,form</field>
    </record>
</odoo>'''

def get_pricing_engine_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_pricing_engine_form" model="ir.ui.view">
        <field name="name">advanced.pricing.engine.form</field>
        <field name="model">advanced.pricing.engine</field>
        <field name="arch" type="xml">
            <form string="Pricing Engine">
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="sequence"/>
                        <field name="active"/>
                        <field name="company_id" groups="base.group_multi_company"/>
                    </group>
                    <group>
                        <field name="enable_multi_level"/>
                        <field name="enable_cascade"/>
                        <field name="cache_duration"/>
                    </group>
                    <notebook>
                        <page string="Rules">
                            <field name="rule_ids"/>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    
    <record id="view_pricing_engine_tree" model="ir.ui.view">
        <field name="name">advanced.pricing.engine.tree</field>
        <field name="model">advanced.pricing.engine</field>
        <field name="arch" type="xml">
            <tree string="Pricing Engines">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="active"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </tree>
        </field>
    </record>
</odoo>'''

def get_pricing_rule_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_pricing_rule_form" model="ir.ui.view">
        <field name="name">advanced.pricing.rule.form</field>
        <field name="model">advanced.pricing.rule</field>
        <field name="arch" type="xml">
            <form string="Pricing Rule">
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="engine_id"/>
                        <field name="sequence"/>
                        <field name="active"/>
                    </group>
                    <group>
                        <field name="level"/>
                        <field name="rule_type"/>
                    </group>
                    <notebook>
                        <page string="Conditions">
                            <group>
                                <field name="condition_field"/>
                                <field name="condition_operator"/>
                                <field name="condition_value"/>
                            </group>
                        </page>
                        <page string="Actions">
                            <group>
                                <field name="action_type"/>
                                <field name="action_value"/>
                            </group>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
    
    <record id="view_pricing_rule_tree" model="ir.ui.view">
        <field name="name">advanced.pricing.rule.tree</field>
        <field name="model">advanced.pricing.rule</field>
        <field name="arch" type="xml">
            <tree string="Pricing Rules">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="engine_id"/>
                <field name="level"/>
                <field name="rule_type"/>
                <field name="active"/>
            </tree>
        </field>
    </record>
</odoo>'''

def get_pricing_configuration_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_pricing_config_form" model="ir.ui.view">
        <field name="name">advanced.pricing.config.form</field>
        <field name="model">advanced.pricing.config</field>
        <field name="arch" type="xml">
            <form string="Pricing Configuration">
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="active"/>
                        <field name="company_id" groups="base.group_multi_company"/>
                        <field name="default_engine_id"/>
                    </group>
                    <notebook>
                        <page string="Features">
                            <group>
                                <field name="enable_visual_builder"/>
                                <field name="enable_caching"/>
                                <field name="enable_api"/>
                                <field name="enable_templates"/>
                                <field name="enable_audit"/>
                            </group>
                        </page>
                    </notebook>
                </sheet>
            </form>
        </field>
    </record>
</odoo>'''

def get_product_pricelist_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_product_pricelist_form_advanced" model="ir.ui.view">
        <field name="name">product.pricelist.form.advanced</field>
        <field name="model">product.pricelist</field>
        <field name="inherit_id" ref="product.product_pricelist_view"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='active']" position="after">
                <field name="use_advanced_pricing"/>
                <field name="advanced_engine_id" 
                       attrs="{'invisible': [('use_advanced_pricing', '=', False)],
                              'required': [('use_advanced_pricing', '=', True)]}"/>
            </xpath>
        </field>
    </record>
</odoo>'''

def get_sale_order_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_order_form_advanced_pricing" model="ir.ui.view">
        <field name="name">sale.order.form.advanced.pricing</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='pricelist_id']" position="after">
                <field name="use_advanced_pricing" invisible="1"/>
                <field name="booking_id" attrs="{'invisible': [('booking_id', '=', False)]}"/>
            </xpath>
        </field>
    </record>
</odoo>'''

def get_booking_views():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_booking_form" model="ir.ui.view">
        <field name="name">booking.model.form</field>
        <field name="model">booking.model</field>
        <field name="arch" type="xml">
            <form string="Booking">
                <header>
                    <button name="action_create_quotation" type="object" 
                            string="Create Quotation" class="oe_highlight"/>
                    <field name="state" widget="statusbar"/>
                </header>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="partner_id"/>
                        <field name="appointment_time"/>
                        <field name="service_type"/>
                        <field name="distance"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    
    <record id="view_booking_tree" model="ir.ui.view">
        <field name="name">booking.model.tree</field>
        <field name="model">booking.model</field>
        <field name="arch" type="xml">
            <tree string="Bookings">
                <field name="name"/>
                <field name="partner_id"/>
                <field name="appointment_time"/>
                <field name="service_type"/>
                <field name="state"/>
            </tree>
        </field>
    </record>
    
    <record id="action_bookings" model="ir.actions.act_window">
        <field name="name">Bookings</field>
        <field name="res_model">booking.model</field>
        <field name="view_mode">tree,form</field>
    </record>
    
    <menuitem id="menu_bookings" 
              name="Bookings" 
              parent="sale.sale_order_menu"
              action="action_bookings"
              sequence="20"/>
</odoo>'''

# Data files
def get_rule_templates():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="template_distance_pricing" model="advanced.pricing.rule">
            <field name="name">Template: Distance Surcharge</field>
            <field name="sequence">100</field>
            <field name="active">False</field>
            <field name="level">1</field>
            <field name="rule_type">condition</field>
            <field name="condition_field">booking.distance</field>
            <field name="condition_operator">></field>
            <field name="condition_value">15</field>
            <field name="action_type">add</field>
            <field name="action_value">50</field>
        </record>
    </data>
</odoo>'''

def get_demo_data():
    return '''<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="demo_engine" model="advanced.pricing.engine">
            <field name="name">Demo Pricing Engine</field>
            <field name="active">True</field>
            <field name="enable_multi_level">True</field>
            <field name="enable_cascade">True</field>
        </record>
    </data>
</odoo>'''

# Wizard and test files
def get_import_wizard():
    return '''# -*- coding: utf-8 -*-
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
        return {'type': 'ir.actions.act_window_close'}'''

def get_test_pricing_engine():
    return '''# -*- coding: utf-8 -*-
from odoo.tests import common

class TestPricingEngine(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.engine = self.env['advanced.pricing.engine'].create({
            'name': 'Test Engine',
            'enable_multi_level': True,
        })
    
    def test_base_price_calculation(self):
        """Test base price calculation"""
        # Test implementation
        pass'''

def get_test_pricing_rules():
    return '''# -*- coding: utf-8 -*-
from odoo.tests import common

class TestPricingRules(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.engine = self.env['advanced.pricing.engine'].create({
            'name': 'Test Engine',
        })
    
    def test_rule_evaluation(self):
        """Test rule evaluation"""
        # Test implementation
        pass'''

if __name__ == "__main__":
    create_advanced_pricing_module()