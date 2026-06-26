# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
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
    active = fields.Boolean('Active', default=True, tracking=True,
                           help='Uncheck to archive this rule. Note: Only approved rules will be used in pricing calculations.')
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

    # --- Guided form helpers (presentation only) ---
    rule_summary_html = fields.Html(
        'Rule Summary', compute='_compute_rule_summary_html', sanitize=False, readonly=True,
        help='Live plain-language summary of this rule (FOR … WHEN … THEN …).')
    show_advanced_conditions = fields.Boolean(
        'Show advanced conditions', store=False,
        help='UI-only toggle to reveal rarely-used condition fields.')

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
    
    # Region / Catchment area (flexible for future expansion)
    region = fields.Char('Region/Catchment Area', tracking=True,
                         help='Region this rule applies to, e.g., Hanoi, HCMC')
    
    # Rule metadata from Excel price list
    item_code = fields.Char('Item Code', tracking=True,
                            help='Reference code from price list (e.g., bs_010, dd_020)')
    trigger_source = fields.Selection([
        ('booking_form', 'Booking/Form'),
        ('app_clock', 'App Clock'),
        ('provider_after_service', 'Provider after Service'),
        ('public_holidays_table', 'Public Holidays Table'),
        ('cmf_booking_form', 'CMF + Booking Form'),
        ('quotation_booking_form', 'Quotation on Booking Form'),
        ('service_duration_log', 'Service Duration Log'),
        ('booking_form_provider', 'Booking/Form & Provider after Service'),
        ('manual', 'Manual Entry'),
    ], string='Trigger Source', tracking=True,
       help='Where the data for this rule condition comes from')
    data_required = fields.Char('Data Required', tracking=True,
                                help='What data the rule needs to evaluate (e.g., service_location, number of wounds)')
    notes = fields.Text('Rule Notes', tracking=True)
    
    # Validity period
    valid_from = fields.Date('Valid From', tracking=True)
    valid_to = fields.Date('Valid To', tracking=True)
    
    # Combined time condition (OR logic for after hours or weekend)
    is_after_hours_or_weekend = fields.Boolean('After Hours or Weekend',
        help='Apply when service is either after hours OR on weekend (OR logic)')
    
    # Service-specific quantity conditions (from Excel: number of wounds, injections, etc.)
    wound_count_min = fields.Integer('Min Wound Count',
        help='Minimum number of wounds to apply this rule')
    wound_count_max = fields.Integer('Max Wound Count',
        help='Maximum number of wounds to apply this rule')
    injection_count_min = fields.Integer('Min Injection Count',
        help='Minimum number of injections to apply this rule (e.g., after 1st injection)')
    iv_fluid_count_min = fields.Integer('Min IV Fluid Bottles',
        help='Minimum number of IV fluid bottles to apply this rule')
    medication_count_min = fields.Integer('Min Additional Medications',
        help='Minimum number of additional medications to apply this rule')
    
    # Compound conditions (modeled as separate booleans, evaluated as AND)
    requires_home_service = fields.Boolean('Requires Home Service',
        help='Apply only when service location is at home')
    requires_other_service_same_visit = fields.Boolean('Other Service Same Visit',
        help='Apply only when client receives another service on the same visit')
    requires_multi_client_same_location = fields.Boolean('Multiple Clients Same Location',
        help='Apply for clients after the first at the same location')
    requires_bilingual_provider = fields.Boolean('Requires Bilingual Provider',
        help='Apply only when client requires a bilingual provider')
    is_repeat_booking = fields.Boolean('Repeat/Multiple Booking',
        help='Apply for multiple and/or repeat bookings')
    is_manual_quote = fields.Boolean('Manual Quote/Override',
        help='This rule requires manual pricing — value set on booking form or receipt')
    
    action_type = fields.Selection([
        ('add', 'Add Amount'),
        ('multiply', 'Multiply by Factor'),
        ('percentage', 'Apply Percentage'),
        ('fixed', 'Set Fixed Price'),
        ('discount', 'Discount Base Price'),
        ('per_unit', 'Amount Per Unit'),
        ('formula', 'Apply Formula')
    ], string='Action Type', default='add', tracking=True)
    
    # Per-unit configuration (e.g., 10,000 per km)
    per_unit_field = fields.Selection([
        ('distance', 'Distance (km)'),
        ('wound_count', 'Wound Count'),
        ('injection_count', 'Injection Count'),
        ('iv_fluid_count', 'IV Fluid Count'),
        ('medication_count', 'Medication Count'),
        ('service_units', 'Service Units'),
    ], string='Per Unit Field',
       help='Which field to multiply the action value by when action_type is per_unit')

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
                    body=_(
                        "Pricing rule modified by <b>%(modified_by)s</b>. "
                        "The rule has been reset to Draft status and requires re-approval "
                        "before becoming active again.<br/>"
                        "<b>Fields modified:</b> %(modified_fields)s",
                        modified_by=notif['modified_by'],
                        modified_fields=notif['modified_fields'],
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )

                # Create activity for board approval
                board_group = self.env.ref('health_base.group_healthcare_owner')
                if board_group and board_group.user_ids:
                    rule.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=board_group.user_ids[0].id,
                        summary=_("Re-approval Required: %s", rule.name),
                        note=_(
                            "The pricing rule was modified and requires board re-approval "
                            "before it can be used again."
                        ),
                    )

        return result

    def action_submit_for_approval(self):
        """Submit rule for board approval"""
        from odoo.exceptions import UserError

        self.ensure_one()
        if self.approval_status != 'draft':
            raise UserError(_('Only draft rules can be submitted for approval.'))

        self.write({
            'approval_status': 'pending',
        })

        # Create activity for all board members
        board_group = self.env.ref('health_base.group_healthcare_owner')
        if board_group:
            for board_member in board_group.user_ids:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=board_member.id,
                    summary=_("Pricing Rule Approval Required: %s", self.name),
                    note=_(
                        "Please review and approve the pricing rule.<br/>"
                        "<b>Action:</b> %(action)s<br/>"
                        "<b>Value:</b> %(value)s",
                        action=dict(
                            self._fields["action_type"]._description_selection(self.env)
                        ).get(self.action_type),
                        value=self.action_value,
                    ),
                )

        self.message_post(
            body=_(
                "Rule submitted for board approval by %s",
                self.env.user.name,
            ),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    def action_approve(self):
        """Approve pricing rule (Board/Owner only)"""
        from odoo.exceptions import UserError, AccessError

        self.ensure_one()

        if not self.env.user.has_group('health_base.group_healthcare_owner'):
            raise AccessError(_('Only Board members can approve pricing rules.'))

        if self.approval_status != 'pending':
            raise UserError(_('Only pending rules can be approved.'))

        self.write({
            'approval_status': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })

        self.message_post(
            body=_(
                "Rule approved by <b>%s</b> and is now active.",
                self.env.user.name,
            ),
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
            raise AccessError(_('Only Board members can reject pricing rules.'))

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
        
        # Skip manual quote rules (they require manual pricing input)
        if self.is_manual_quote:
            _logger.info(f"  Rule {self.name}: SKIPPED - Manual quote rule")
            return False
        
        # Check validity period
        if self.valid_from or self.valid_to:
            from datetime import date
            today = date.today()
            if self.valid_from and today < self.valid_from:
                _logger.info(f"  Rule {self.name}: FAILED - Not yet valid (starts {self.valid_from})")
                return False
            if self.valid_to and today > self.valid_to:
                _logger.info(f"  Rule {self.name}: FAILED - Expired (ended {self.valid_to})")
                return False
        
        # Check region if set
        if self.region:
            service_region = context_data.get('region', '')
            if service_region and service_region.lower() != self.region.lower():
                _logger.info(f"  Rule {self.name}: FAILED - Region mismatch ({service_region} vs {self.region})")
                return False
        
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
        
        # Appointment hour conditions (skip if both 0 since 0 means "not set").
        # Supports overnight windows that wrap past midnight: when max < min
        # (e.g. 20:00–06:00) the window is [min..24) ∪ [0..max], so match if
        # hour >= min OR hour <= max. Otherwise it's a same-day range [min..max].
        hmin = self.appointment_hour_min or 0
        hmax = self.appointment_hour_max or 0
        if hmin > 0 or hmax > 0:
            hour = context_data.get('appointment_hour', 0)
            if hmin > 0 and hmax > 0 and hmax < hmin:
                # Wrap-around (overnight) window
                in_window = hour >= hmin or hour <= hmax
                _logger.info(f"    Hour overnight-window check: {hmin}..{hmax} hour={hour} -> {in_window}")
                if not in_window:
                    _logger.info(f"    FAILED: Hour outside overnight window")
                    return False
            else:
                # Same-day range
                if hmin > 0 and hour < hmin:
                    _logger.info(f"    FAILED: Hour too low ({hour} < {hmin})")
                    return False
                if hmax > 0 and hour > hmax:
                    _logger.info(f"    FAILED: Hour too high ({hour} > {hmax})")
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
        
        # Combined after-hours OR weekend condition
        if self.is_after_hours_or_weekend:
            is_after_hours = context_data.get('is_after_hours', False)
            is_weekend = context_data.get('is_weekend', False)
            if not (is_after_hours or is_weekend):
                _logger.info(f"    After-hours-or-weekend condition FAILED")
                return False
        
        # Service-specific quantity conditions
        if self.wound_count_min and self.wound_count_min > 0:
            wounds = context_data.get('wound_count', 0)
            if wounds < self.wound_count_min:
                return False
        if self.wound_count_max and self.wound_count_max > 0:
            wounds = context_data.get('wound_count', 0)
            if wounds > self.wound_count_max:
                return False
        
        if self.injection_count_min and self.injection_count_min > 0:
            injections = context_data.get('injection_count', 0)
            if injections < self.injection_count_min:
                return False
        
        if self.iv_fluid_count_min and self.iv_fluid_count_min > 0:
            iv_fluids = context_data.get('iv_fluid_count', 0)
            if iv_fluids < self.iv_fluid_count_min:
                return False
        
        if self.medication_count_min and self.medication_count_min > 0:
            medications = context_data.get('medication_count', 0)
            if medications < self.medication_count_min:
                return False
        
        # Compound boolean conditions
        if self.requires_home_service:
            if context_data.get('service_location') != 'home':
                return False
        
        if self.requires_other_service_same_visit:
            if not context_data.get('has_other_service_same_visit', False):
                return False
        
        if self.requires_multi_client_same_location:
            if not context_data.get('is_multi_client_same_location', False):
                return False
        
        if self.requires_bilingual_provider:
            if not context_data.get('requires_bilingual_provider', False):
                return False
        
        if self.is_repeat_booking:
            if not context_data.get('is_repeat_booking', False):
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
        elif self.action_type == 'discount':
            # Discount base price by percentage (e.g., 0.1 = 10% discount)
            return price * (1 - self.action_value)
        elif self.action_type == 'per_unit':
            # Amount per unit of a context field (e.g., 10,000 per km above threshold)
            unit_count = 0
            threshold = 0
            if self.per_unit_field:
                field_map = {
                    'distance': 'distance',
                    'wound_count': 'wound_count',
                    'injection_count': 'injection_count',
                    'iv_fluid_count': 'iv_fluid_count',
                    'medication_count': 'medication_count',
                    'service_units': 'service_units',
                }
                context_key = field_map.get(self.per_unit_field, self.per_unit_field)
                unit_count = context_data.get(context_key, 0)

                # Use the min condition as threshold (e.g., distance_min = 8 means
                # charge per km ABOVE 8km, so effective_units = distance - 8)
                threshold_map = {
                    'distance': self.distance_min or 0,
                    'wound_count': (self.wound_count_min or 1) - 1,  # "after 1st" = threshold 1
                    'injection_count': (self.injection_count_min or 1) - 1,
                    'iv_fluid_count': (self.iv_fluid_count_min or 1) - 1,
                    'medication_count': (self.medication_count_min or 1) - 1,
                    'service_units': self.service_units_min or 0,
                }
                threshold = threshold_map.get(self.per_unit_field, 0)

            effective_units = max(0, unit_count - threshold)
            return price + (self.action_value * effective_units)
        
        return price
    
    def apply_cascading_action(self, price, context_data):
        """Apply cascading action for Level 2 rules"""
        return self.apply_action(price, context_data)

    # ------------------------------------------------------------------
    # Plain-language helpers (shared by pricing panels + quick booking)
    # ------------------------------------------------------------------
    def _pricing_rule_short_label(self):
        """Human label for the rule, dropping the 'Region - ' prefix
        (e.g. 'Hanoi - Ultrasound - Is Service at home' -> 'Is Service at home')."""
        self.ensure_one()
        short = self.name or ''
        parts = short.split(' - ')
        if len(parts) >= 2:
            short = parts[-1]
        return short

    def _pricing_rule_action_desc(self):
        """Symbolic effect of this rule's action, e.g. '+200,000 đ', '×3', '-10%'."""
        self.ensure_one()
        av = self.action_value
        at = self.action_type
        if at == 'add':
            return '+%s đ' % '{:,.0f}'.format(av)
        if at == 'fixed':
            return '→ %s đ' % '{:,.0f}'.format(av)
        if at == 'multiply':
            return '×%s' % av
        if at == 'discount':
            return '-%.0f%%' % (av * 100)
        if at == 'per_unit':
            return '+%s đ/unit' % '{:,.0f}'.format(av)
        if at == 'percentage':
            return '+%s%%' % av
        return ''
    
    @api.depends('rule_type')
    def _compute_is_visual_rule(self):
        """Compute if this is a visual rule"""
        for rule in self:
            rule.is_visual_rule = rule.rule_type == 'visual'

    # ------------------------------------------------------------------
    # Guided form: live plain-language rule summary
    # ------------------------------------------------------------------
    _SUMMARY_ICON_PATHS = {
        'scope': "<path d='M3 7l9-4 9 4-9 4z'/><path d='M3 7v6l9 4 9-4V7'/>",
        'when': "<circle cx='12' cy='12' r='8'/><path d='M12 8v4l3 2'/>",
        'then': "<path d='M20 12l-8 8H6a2 2 0 0 1-2-2v-6l8-8 8 8z'/><circle cx='9' cy='9' r='1.2'/>",
        'home': "<path d='M3 11l9-7 9 7'/><path d='M5 10v9h14v-9'/>",
    }

    def _summary_icon(self, name):
        paths = self._SUMMARY_ICON_PATHS.get(name, '')
        return (
            "<svg viewBox='0 0 24 24' width='14' height='14' fill='none' stroke='currentColor' "
            "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' "
            "style='vertical-align:-2px;margin-right:5px;'>%s</svg>" % paths
        )

    @api.depends('applied_on', 'product_tmpl_id', 'product_id', 'categ_id', 'region',
                 'distance_min', 'distance_max', 'appointment_hour_min', 'appointment_hour_max',
                 'is_weekend_required', 'is_holiday_required', 'holiday_type',
                 'is_after_hours_required', 'is_after_hours_or_weekend',
                 'service_type', 'service_location', 'requires_home_service',
                 'wound_count_min', 'wound_count_max', 'injection_count_min',
                 'iv_fluid_count_min', 'medication_count_min',
                 'action_type', 'action_value', 'per_unit_field')
    def _compute_rule_summary_html(self):
        """Build a live FOR … WHEN … THEN sentence. Never raise (display only)."""
        type_labels = dict(self._fields['service_type']._description_selection(self.env))
        loc_labels = dict(self._fields['service_location']._description_selection(self.env))
        for rule in self:
            try:
                rule.rule_summary_html = rule._build_rule_summary(type_labels, loc_labels)
            except Exception:
                rule.rule_summary_html = False

    def _build_rule_summary(self, type_labels, loc_labels):
        self.ensure_one()
        fmt = lambda v: '{:,.0f}'.format(v or 0)

        # FOR (scope)
        if self.applied_on == '1_product' and self.product_tmpl_id:
            what = self.product_tmpl_id.display_name
        elif self.applied_on == '0_product_variant' and self.product_id:
            what = self.product_id.display_name
        elif self.applied_on == '2_product_category' and self.categ_id:
            what = self.categ_id.display_name
        else:
            what = _('all products')
        if self.region:
            what += ' · %s' % self.region

        # WHEN (conditions)
        conds = []
        if self.requires_home_service or self.service_location == 'home':
            conds.append(_("at the client's home"))
        elif self.service_location:
            conds.append(loc_labels.get(self.service_location, self.service_location))
        if self.service_type:
            conds.append(type_labels.get(self.service_type, self.service_type))
        if self.is_after_hours_or_weekend:
            conds.append(_("after-hours or weekend"))
        if self.is_after_hours_required:
            conds.append(_("after hours"))
        if self.is_weekend_required:
            conds.append(_("weekends"))
        if self.is_holiday_required:
            conds.append(_("holidays (%s)", self.holiday_type or _('public')))
        if self.appointment_hour_min and self.appointment_hour_max:
            conds.append(
                _("between %(start)02dh and %(end)02dh",
                  start=self.appointment_hour_min, end=self.appointment_hour_max)
            )
        if self.distance_min and self.distance_max:
            conds.append(
                _("distance %(minimum)g–%(maximum)g km",
                  minimum=self.distance_min, maximum=self.distance_max)
            )
        elif self.distance_min:
            conds.append(_("distance ≥ %g km", self.distance_min))
        elif self.distance_max:
            conds.append(_("distance ≤ %g km", self.distance_max))
        if self.wound_count_min:
            conds.append(_("≥ %d wounds", self.wound_count_min))
        if self.injection_count_min:
            conds.append(_("≥ %d injections", self.injection_count_min))
        if self.iv_fluid_count_min:
            conds.append(_("≥ %d IV bags", self.iv_fluid_count_min))
        if self.medication_count_min:
            conds.append(_("≥ %d medications", self.medication_count_min))
        when = ", ".join(conds) if conds else _("always")

        # THEN (action)
        at = self.action_type
        v = self.action_value
        if at == 'add':
            then = _("add %s đ", fmt(v))
        elif at == 'fixed':
            then = _("set the price to %s đ", fmt(v))
        elif at == 'multiply':
            then = _("multiply the price ×%g", v or 0)
        elif at == 'percentage':
            then = _("increase the price by %g%%", v or 0)
        elif at == 'discount':
            then = _("give a %g%% discount", (v or 0) * 100)
        elif at == 'per_unit':
            then = _(
                "add %(amount)s đ per %(unit)s",
                amount=fmt(v),
                unit=self.per_unit_field or _('unit'),
            )
        else:
            then = None

        seg = lambda icon, label, body: (
            "<span class='apr-sum__seg'>%s<b>%s</b> %s</span>"
            % (self._summary_icon(icon), label, body))
        parts = [seg('scope', _('For'), what), seg('when', _('When'), when)]
        if then:
            parts.append(seg('then', _('Then'), then))
        else:
            parts.append(
                "<span class='apr-sum__hint'>%s</span>"
                % _("Pick a price action below to finish the rule.")
            )
        return "<div class='apr-sum'>%s</div>" % "<span class='apr-sum__arrow'>→</span>".join(parts)
    
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
