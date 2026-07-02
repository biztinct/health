# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL


class BiAccessRule(models.Model):
    """Dataset-level row and column security.

    Row rules: a list of [field_id, op, value] conditions (engine operator
    enum) ANDed within a rule; rules applying to the same user are OR-merged
    (ir.rule semantics). Values support variable substitution: 'user.id',
    'user.company_ids', 'user.employee_id', 'user.partner_id'.

    Column rules: masked fields are hidden ('hide' — absent from metadata,
    explicit references error) or nulled ('null' — SELECTed as NULL so shared
    charts keep rendering).
    """
    _name = 'bi.access.rule'
    _description = 'BI Access Rule'

    name = fields.Char(required=True)
    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    active = fields.Boolean(default=True)
    rule_type = fields.Selection([('row', 'Row Filter'),
                                  ('column', 'Column Mask')],
                                 required=True, default='row')
    group_ids = fields.Many2many('res.groups', string='Apply to Groups')
    user_ids = fields.Many2many('res.users', string='Apply to Users')

    # row rules
    domain_json = fields.Json(
        help='[[field_id, op, value], ...] — engine operator enum; values '
             'may be "user.id", "user.company_ids", "user.employee_id", '
             '"user.partner_id".')

    # column rules
    field_ids = fields.Many2many('bi.field', string='Masked Fields')
    mask_mode = fields.Selection([('hide', 'Hide Completely'),
                                  ('null', 'Show as Empty')],
                                 default='hide')

    def write(self, vals):
        result = super().write(vals)
        self._log_change()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._log_change()
        return records

    def _log_change(self):
        for rule in self:
            self.env['bi.audit.log'].sudo().log(
                'rls_change', dataset=rule.dataset_id,
                payload={'rule': rule.name, 'type': rule.rule_type})

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _rule_applies_to_user(self):
        """A rule constrains the current user when they are listed in it.
        Users matched by NO rule of a dataset are unconstrained (matching
        ir.rule semantics where rules attach to groups)."""
        self.ensure_one()
        user = self.env.user
        if self.user_ids and user in self.user_ids:
            return True
        if self.group_ids and (self.group_ids & user.all_group_ids):
            return True
        return False

    @api.model
    def _applicable_rules(self, dataset, rule_type=None):
        domain = [('dataset_id', '=', dataset.id), ('active', '=', True)]
        if rule_type:
            domain.append(('rule_type', '=', rule_type))
        rules = self.sudo().search(domain)
        return rules.filtered(lambda r: r._rule_applies_to_user())

    @api.model
    def _masked_field_ids(self, dataset):
        if self.env.user.has_group('biz_bi.group_bi_admin'):
            return set()
        rules = self._applicable_rules(dataset, 'column')
        return {f.id for rule in rules if rule.mask_mode == 'hide'
                for f in rule.field_ids}

    @api.model
    def _nulled_field_ids(self, dataset):
        if self.env.user.has_group('biz_bi.group_bi_admin'):
            return set()
        rules = self._applicable_rules(dataset, 'column')
        return {f.id for rule in rules if rule.mask_mode == 'null'
                for f in rule.field_ids}

    @api.model
    def _compile_row_rules(self, dataset, field_expr, engine):
        """OR-merge the row rules constraining the current user into one SQL
        predicate. `field_expr(bi.field) -> SQL` comes from the engine so the
        same rule compiles against live tables and gold matviews."""
        if self.env.user.has_group('biz_bi.group_bi_admin'):
            return None
        rules = self._applicable_rules(dataset, 'row')
        if not rules:
            return None
        rule_sqls = []
        for rule in rules:
            condition_sqls = []
            for triplet in (rule.domain_json or []):
                if not isinstance(triplet, (list, tuple)) or len(triplet) != 3:
                    raise UserError(_(
                        "Malformed access rule %s.", rule.name))
                field_id, op, value = triplet
                field = self.env['bi.field'].browse(int(field_id))
                if not field.exists() or field.dataset_id != dataset:
                    raise UserError(_(
                        "Access rule %s references an unknown field.",
                        rule.name))
                condition_sqls.append(engine._compile_filter_op(
                    field_expr(field), op,
                    self._substitute_value(value), field))
            if condition_sqls:
                rule_sqls.append(SQL(
                    "(%s)", SQL(" AND ").join(condition_sqls)))
        if not rule_sqls:
            return None
        return SQL("(%s)", SQL(" OR ").join(rule_sqls))

    def _substitute_value(self, value):
        user = self.env.user
        substitutions = {
            'user.id': lambda: user.id,
            'user.company_ids': lambda: user.company_ids.ids,
            'user.partner_id': lambda: user.partner_id.id,
            'user.employee_id': lambda: (
                'employee_id' in user._fields and user.employee_id.id or 0),
        }
        if isinstance(value, str) and value in substitutions:
            return substitutions[value]()
        if isinstance(value, list):
            return [self._substitute_value(v) for v in value]
        return value

    # ------------------------------------------------------------------
    # "View as" preview for modelers
    # ------------------------------------------------------------------

    def action_preview(self):
        """Show the compiled predicate and a 10-row sample as the selected
        rule's audience would see it."""
        self.ensure_one()
        engine = self.env['bi.query.engine']
        dataset = self.dataset_id
        lang = self.env.user.lang or 'en_US'
        preview_user = self.user_ids[:1] or self.env.user
        rls = self.with_user(preview_user).env['bi.access.rule'] \
            ._compile_row_rules(
                dataset,
                lambda f: engine._field_expr(f, 'live', lang),
                engine)
        raise UserError(_(
            "Compiled predicate for %(audience)s:\n%(sql)s",
            audience=preview_user.name,
            sql=self.env.cr.mogrify(rls).decode() if rls else _("(no filter)")))
