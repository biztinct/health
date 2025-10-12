# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class AdvancedPricingRule(models.Model):
    _name = 'advanced.pricing.rule'
    _description = 'Advanced Pricing Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char('Rule Name', required=True, tracking=True)
    sequence = fields.Integer('Sequence', default=10, tracking=True)
    active = fields.Boolean('Active', compute='_compute_active', store=True, tracking=True)
    engine_id = fields.Many2one('advanced.pricing.engine', 'Pricing Engine', required=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, tracking=True)

    # Approval workflow fields
    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Board Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True, required=True, string='Approval Status',
       help='Approval required for all changes - any modification resets to draft')

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approval_date = fields.Datetime('Approval Date', readonly=True, tracking=True)
    approval_notes = fields.Text('Approval Notes', tracking=True)
    rejection_reason = fields.Text('Rejection Reason', tracking=True)
    
    level = fields.Selection([
        ('1', 'Level 1 - Base Rules'),
        ('2', 'Level 2 - Cascading Rules')
    ], string='Rule Level', default='1', required=True, tracking=True)

    rule_type = fields.Selection([
        ('condition', 'Conditional'),
        ('formula', 'Formula-based'),
        ('matrix', 'Matrix'),
        ('custom', 'Custom Python'),
        ('visual', 'Visual Rule')
    ], string='Rule Type', default='condition', required=True, tracking=True)
    
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
    holiday_type = fields.Selection([
        ('national', 'National Holiday'),
        ('tet', 'TET Holiday'),
        ('regional', 'Regional Holiday'),
        ('observance', 'Observance'),
    ], string='Holiday Type', help='Apply only for specific holiday type (requires Holiday Only to be checked)')
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
    ], string='Action Type', default='add', tracking=True)

    action_value = fields.Float('Action Value', tracking=True)
    action_formula = fields.Text('Action Formula', tracking=True)
    
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

    @api.depends('approval_status')
    def _compute_active(self):
        """Only approved rules are active"""
        for rule in self:
            rule.active = (rule.approval_status == 'approved')

    def write(self, vals):
        """
        STRICT APPROVAL: Any modification to approved rule resets to draft
        Requires re-approval before rule becomes active again
        """
        from odoo.exceptions import UserError, AccessError

        # Check if this is an approval action (these fields can be updated without triggering reset)
        approval_action_fields = {
            'approval_status', 'approved_by', 'approval_date',
            'approval_notes', 'rejection_reason'
        }
        is_approval_action = set(vals.keys()).issubset(approval_action_fields)

        # Track which rules need notifications
        rules_to_notify = {}

        # If modifying an approved rule (and not an approval action), reset to draft
        for rule in self:
            if rule.approval_status == 'approved' and not is_approval_action and vals:
                # Store who made the change
                modified_by = self.env.user.name
                modified_fields = ', '.join([k for k in vals.keys() if k not in approval_action_fields])

                if modified_fields:  # Only reset if actual content fields changed
                    vals.update({
                        'approval_status': 'draft',
                        'approved_by': False,
                        'approval_date': False,
                        'approval_notes': f'Rule modified by {modified_by}. Fields changed: {modified_fields}. Re-approval required.',
                    })

                    # Track this rule for notification after write
                    rules_to_notify[rule.id] = {
                        'modified_by': modified_by,
                        'modified_fields': modified_fields
                    }

        result = super().write(vals)

        # Send notifications after write
        for rule in self:
            if rule.id in rules_to_notify:
                notif = rules_to_notify[rule.id]
                rule.message_post(
                    body=f"⚠️ Pricing rule modified by <b>{notif['modified_by']}</b>. "
                         f"Rule has been reset to Draft status and requires re-approval before becoming active again.<br/>"
                         f"<b>Fields modified:</b> {notif['modified_fields']}",
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )

                # Create activity for board approval
                board_group = self.env.ref('health_base.group_healthcare_owner')
                if board_group and board_group.users:
                    rule.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=board_group.users[0].id,
                        summary=f'Re-approval Required: {rule.name}',
                        note=f'Pricing rule was modified and requires board re-approval before it can be used again.'
                    )

        return result

    def action_submit_for_approval(self):
        """Submit rule for board approval"""
        from odoo.exceptions import UserError

        self.ensure_one()
        if self.approval_status != 'draft':
            raise UserError('Only draft rules can be submitted for approval')

        self.write({
            'approval_status': 'pending',
        })

        # Create activity for all board members
        board_group = self.env.ref('health_base.group_healthcare_owner')
        if board_group:
            for board_member in board_group.users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=board_member.id,
                    summary=f'Pricing Rule Approval Required: {self.name}',
                    note=f'Please review and approve pricing rule.<br/>'
                         f'<b>Action:</b> {dict(self._fields["action_type"].selection).get(self.action_type)}<br/>'
                         f'<b>Value:</b> {self.action_value}'
                )

        self.message_post(
            body=f'📋 Rule submitted for board approval by {self.env.user.name}',
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    def action_approve(self):
        """Approve pricing rule (Board/Owner only)"""
        from odoo.exceptions import UserError, AccessError

        self.ensure_one()

        if not self.env.user.has_group('health_base.group_healthcare_owner'):
            raise AccessError('Only Board members can approve pricing rules')

        if self.approval_status != 'pending':
            raise UserError('Only pending rules can be approved')

        self.write({
            'approval_status': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

        self.message_post(
            body=f'✅ Rule approved by <b>{self.env.user.name}</b> and is now active',
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        # Mark activities as done
        self.activity_ids.action_done()

    def action_reject(self):
        """Reject pricing rule with reason (opens wizard)"""
        from odoo.exceptions import AccessError

        self.ensure_one()

        if not self.env.user.has_group('health_base.group_healthcare_owner'):
            raise AccessError('Only Board members can reject pricing rules')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pricing.rule.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_rule_id': self.id}
        }

    def action_reset_to_draft(self):
        """Reset rejected rule back to draft for editing"""
        self.ensure_one()
        self.write({
            'approval_status': 'draft',
            'rejection_reason': False,
        })

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
        _logger.info(f"    Evaluating FSO conditions for rule {self.name}")
        _logger.info(f"    Distance min: {self.distance_min}, Distance max: {self.distance_max}")
        _logger.info(f"    Hour min: {self.appointment_hour_min}, Hour max: {self.appointment_hour_max}")
        _logger.info(f"    After hours required: {self.is_after_hours_required}")
        _logger.info(f"    Context data: {context_data}")
        
        # Distance conditions (only apply if values are set and positive)
        if self.distance_min and self.distance_min > 0:
            distance = context_data.get('distance', 0)
            _logger.info(f"    Distance min check: {distance} >= {self.distance_min}")
            if distance < self.distance_min:
                _logger.info(f"    FAILED: Distance too low")
                return False
        if self.distance_max and self.distance_max > 0:
            distance = context_data.get('distance', 0)
            _logger.info(f"    Distance max check: {distance} <= {self.distance_max}")
            if distance > self.distance_max:
                _logger.info(f"    FAILED: Distance too high")
                return False
        
        # Appointment hour conditions (skip if 0 since 0 means "not set")
        if self.appointment_hour_min and self.appointment_hour_min > 0:
            hour = context_data.get('appointment_hour', 0)
            _logger.info(f"    Hour min check: {hour} >= {self.appointment_hour_min}")
            if hour < self.appointment_hour_min:
                _logger.info(f"    FAILED: Hour too low")
                return False
        if self.appointment_hour_max and self.appointment_hour_max > 0:
            hour = context_data.get('appointment_hour', 0)
            _logger.info(f"    Hour max check: {hour} <= {self.appointment_hour_max}")
            if hour > self.appointment_hour_max:
                _logger.info(f"    FAILED: Hour too high")
                return False
        
        # Weekend condition
        if self.is_weekend_required:
            if not context_data.get('is_weekend', False):
                return False
        
        # Holiday condition
        if self.is_holiday_required:
            if not context_data.get('is_holiday', False):
                return False
            # Check specific holiday type if specified
            if self.holiday_type:
                if context_data.get('holiday_type') != self.holiday_type:
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
        
        # Service units conditions (only apply if values are set and positive)
        if self.service_units_min and self.service_units_min > 0:
            units = context_data.get('service_units', 0)
            _logger.info(f"    Service units min check: {units} >= {self.service_units_min}")
            if units < self.service_units_min:
                _logger.info(f"    FAILED: Service units too low")
                return False
        if self.service_units_max and self.service_units_max > 0:
            units = context_data.get('service_units', 0)
            _logger.info(f"    Service units max check: {units} <= {self.service_units_max}")
            if units > self.service_units_max:
                _logger.info(f"    FAILED: Service units too high")
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