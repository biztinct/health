# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AdvancedPricingEngine(models.Model):
    _name = 'advanced.pricing.engine'
    _description = 'Advanced Pricing Calculation Engine'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'sequence, id'

    name = fields.Char('Engine Name', required=True, tracking=True)
    sequence = fields.Integer('Sequence', default=10, tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, tracking=True)

    rule_ids = fields.One2many('advanced.pricing.rule', 'engine_id', string='Pricing Rules')

    cache_duration = fields.Integer('Cache Duration (seconds)', default=300, tracking=True)
    enable_multi_level = fields.Boolean('Enable Multi-Level Rules', default=True, tracking=True)
    enable_cascade = fields.Boolean('Enable Cascading', default=True, tracking=True)
    
    def explain_applied_rules(self, product_id, partner_id, quantity, context_data):
        """Plain-language list of the approved rules that match this context:
        ``[{'label': <short name>, 'desc': <e.g. +200,000 đ / ×3 / -10%>}]``.

        Lets pricing panels and the quick-booking dialog show WHY a price was
        adjusted, not just the final number. Same rule evaluation as
        ``calculate_price`` but returns descriptions instead of a price."""
        self.ensure_one()
        out = []
        approved = self.rule_ids.filtered(
            lambda r: r.active and r.approval_status == 'approved')
        for rule in approved.sorted('sequence'):
            try:
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    out.append({
                        'label': rule._pricing_rule_short_label(),
                        'desc': rule._pricing_rule_action_desc(),
                    })
            except Exception:
                continue
        return out

    @api.model
    def calculate_price(self, product_id, quantity, partner_id, context_data):
        """Calculate price with multi-level rules"""
        product = self.env['product.product'].browse(product_id)
        base_price = product.list_price
        
        # Convert datetime objects to strings for JSON serialization
        serializable_context = {}
        for key, value in context_data.items():
            if hasattr(value, 'strftime'):  # datetime object
                serializable_context[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                serializable_context[key] = value
        
        context_str = json.dumps(serializable_context, sort_keys=True)
        
        # Track whether an explicit holiday rule already applied the multiplier,
        # so the engine-level holiday step below does not double-apply it.
        holiday_handled = False

        # Apply Level 1 rules (only approved rules are used in pricing)
        if self.enable_multi_level:
            level1_rules = self.rule_ids.filtered(lambda r: r.level == '1' and r.active and r.approval_status == 'approved')
            _logger.info(f"Found {len(level1_rules)} approved Level 1 rules")
            for rule in level1_rules.sorted('sequence'):
                _logger.info(f"Evaluating rule: {rule.name} (ID: {rule.id})")
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    _logger.info(f"Rule {rule.name} MATCHES - applying action")
                    old_price = base_price
                    base_price = rule.apply_action(base_price, context_data)
                    if rule.is_holiday_required and rule.action_type == 'multiply':
                        holiday_handled = True
                    _logger.info(f"Price changed by rule {rule.name}: {old_price} → {base_price}")
                else:
                    _logger.info(f"Rule {rule.name} does NOT match")

        # Apply Level 2 cascading rules (only approved rules are used in pricing)
        if self.enable_cascade:
            level2_rules = self.rule_ids.filtered(lambda r: r.level == '2' and r.active and r.approval_status == 'approved')
            for rule in level2_rules.sorted('sequence'):
                if rule.evaluate_condition(product_id, partner_id, quantity, context_data):
                    base_price = rule.apply_cascading_action(base_price, context_data)
                    if rule.is_holiday_required and rule.action_type == 'multiply':
                        holiday_handled = True

        # Apply holiday multiplier after all rules ONLY if no explicit holiday rule
        # already handled it. This is the safety net for products/regions that have
        # no dedicated holiday rule; without the guard the multiplier double-applies
        # (e.g. ×3 rule + ×3 engine step = ×9).
        holiday_multiplier = context_data.get('holiday_multiplier', 1.0)
        if holiday_multiplier and holiday_multiplier > 1.0 and not holiday_handled:
            _logger.info(f"Applying holiday multiplier: {holiday_multiplier}x")
            old_price = base_price
            base_price = base_price * holiday_multiplier
            _logger.info(f"Price after holiday multiplier: {old_price} → {base_price}")

        return round(base_price, 2)