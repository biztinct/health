# -*- coding: utf-8 -*-
from odoo.tests import common
from datetime import datetime

class TestPricingRules(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        self.engine = self.env['advanced.pricing.engine'].create({
            'name': 'Test Engine',
        })
        
        # Create test customer
        self.customer = self.env['res.partner'].create({
            'name': 'Test Customer',
            'is_company': False,
        })
        
        # Create test product
        self.product = self.env['product.product'].create({
            'name': 'Test Healthcare Service',
            'type': 'service',
            'list_price': 100.0,
        })
    
    def test_fso_field_conditions(self):
        """Test FSO-based condition evaluation"""
        # Create distance-based rule
        rule = self.env['advanced.pricing.rule'].create({
            'name': 'Distance Surcharge Test',
            'engine_id': self.engine.id,
            'rule_type': 'condition',
            'distance_min': 10.0,
            'distance_max': 50.0,
            'action_type': 'add',
            'action_value': 25.0,
        })
        
        # Test distance condition
        context_data = {'distance': 15.0}
        self.assertTrue(rule._evaluate_fso_conditions(context_data))
        
        context_data = {'distance': 5.0}  # Below minimum
        self.assertFalse(rule._evaluate_fso_conditions(context_data))
        
        context_data = {'distance': 60.0}  # Above maximum
        self.assertFalse(rule._evaluate_fso_conditions(context_data))
    
    def test_weekend_condition(self):
        """Test weekend condition evaluation"""
        rule = self.env['advanced.pricing.rule'].create({
            'name': 'Weekend Premium Test',
            'engine_id': self.engine.id,
            'rule_type': 'condition',
            'is_weekend_required': True,
            'action_type': 'percentage',
            'action_value': 20.0,
        })
        
        # Test weekend condition
        context_data = {'is_weekend': True}
        self.assertTrue(rule._evaluate_fso_conditions(context_data))
        
        context_data = {'is_weekend': False}
        self.assertFalse(rule._evaluate_fso_conditions(context_data))
    
    def test_service_type_condition(self):
        """Test service type condition evaluation"""
        rule = self.env['advanced.pricing.rule'].create({
            'name': 'Home Visit Premium Test',
            'engine_id': self.engine.id,
            'rule_type': 'condition',
            'service_type': 'home_visit',
            'action_type': 'add',
            'action_value': 50.0,
        })
        
        # Test service type condition
        context_data = {'service_type': 'home_visit'}
        self.assertTrue(rule._evaluate_fso_conditions(context_data))
        
        context_data = {'service_type': 'clinic_visit'}
        self.assertFalse(rule._evaluate_fso_conditions(context_data))
    
    def test_pricing_action_application(self):
        """Test pricing action application"""
        rule = self.env['advanced.pricing.rule'].create({
            'name': 'Action Test',
            'engine_id': self.engine.id,
            'action_type': 'add',
            'action_value': 30.0,
        })
        
        # Test add action
        result = rule.apply_action(100.0, {})
        self.assertEqual(result, 130.0)
        
        # Test percentage action
        rule.action_type = 'percentage'
        rule.action_value = 15.0
        result = rule.apply_action(100.0, {})
        self.assertEqual(result, 115.0)
        
        # Test multiply action
        rule.action_type = 'multiply'
        rule.action_value = 1.25
        result = rule.apply_action(100.0, {})
        self.assertEqual(result, 125.0)