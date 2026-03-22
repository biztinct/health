# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class PricingRuleBulkLine(models.TransientModel):
    _name = 'pricing.rule.bulk.wizard.line'
    _description = 'Pricing Rule Bulk Wizard Line'

    wizard_id = fields.Many2one('pricing.rule.bulk.wizard', required=True, ondelete='cascade')
    rule_id = fields.Many2one('advanced.pricing.rule', string='Pricing Rule')
    selected = fields.Boolean('Select', default=True)

    # Stored display fields (populated at creation)
    name = fields.Char(string='Rule Name', readonly=True)
    region = fields.Char(string='Region', readonly=True)
    item_code = fields.Char(string='Item Code', readonly=True)
    engine_name = fields.Char(string='Pricing Engine', readonly=True)
    action_type_display = fields.Char(string='Action', readonly=True)
    action_value = fields.Float(string='Value', readonly=True)


class PricingRuleBulkWizard(models.TransientModel):
    _name = 'pricing.rule.bulk.wizard'
    _description = 'Pricing Rule Bulk Submit/Approve Wizard'

    mode = fields.Selection([
        ('submit', 'Submit for Approval'),
        ('approve', 'Approve'),
    ], string='Action', required=True, readonly=True)

    line_ids = fields.One2many(
        'pricing.rule.bulk.wizard.line', 'wizard_id',
        string='Pricing Rules',
    )

    rule_count = fields.Integer('Total Rules', compute='_compute_counts')
    selected_count = fields.Integer('Selected Rules', compute='_compute_counts')

    @api.depends('line_ids', 'line_ids.selected')
    def _compute_counts(self):
        for wizard in self:
            wizard.rule_count = len(wizard.line_ids)
            wizard.selected_count = len(wizard.line_ids.filtered('selected'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mode = self.env.context.get('default_mode', 'submit')

        if mode == 'submit':
            domain = [('approval_status', '=', 'draft')]
        else:
            domain = [('approval_status', '=', 'pending')]

        # Build action type display mapping
        action_labels = dict(
            self.env['advanced.pricing.rule']._fields['action_type'].selection
        )

        rules = self.env['advanced.pricing.rule'].search(domain, order='sequence, name')
        lines = []
        for rule in rules:
            lines.append((0, 0, {
                'rule_id': rule.id,
                'selected': True,
                'name': rule.name,
                'region': rule.region or '',
                'item_code': rule.item_code or '',
                'engine_name': rule.engine_id.name if rule.engine_id else '',
                'action_type_display': action_labels.get(rule.action_type, rule.action_type or ''),
                'action_value': rule.action_value,
            }))
        res['line_ids'] = lines
        return res

    def action_confirm(self):
        """Execute the bulk action on selected rules"""
        self.ensure_one()
        selected_lines = self.line_ids.filtered('selected')

        if not selected_lines:
            raise UserError(_('Please select at least one pricing rule.'))

        rules = selected_lines.mapped('rule_id')

        if self.mode == 'submit':
            self._bulk_submit(rules)
        elif self.mode == 'approve':
            self._bulk_approve(rules)

        return {'type': 'ir.actions.act_window_close'}

    def _bulk_submit(self, rules):
        """Submit selected rules for approval"""
        for rule in rules:
            if rule.approval_status != 'draft':
                continue
            rule.action_submit_for_approval()

        _logger.info('Bulk submitted %d pricing rules for approval by %s',
                     len(rules), self.env.user.name)

    def _bulk_approve(self, rules):
        """Approve selected rules (board only)"""
        if not self.env.user.has_group('health_base.group_healthcare_owner'):
            raise AccessError(_('Only Board members can approve pricing rules.'))

        for rule in rules:
            if rule.approval_status != 'pending':
                continue
            rule.action_approve()

        _logger.info('Bulk approved %d pricing rules by %s',
                     len(rules), self.env.user.name)
