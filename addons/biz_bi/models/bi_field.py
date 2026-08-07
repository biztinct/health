# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .bi_expression import ExpressionError, validate_expression


class BiField(models.Model):
    """One semantic field of a dataset. Dimensions, measures, dates, geo and
    calculated fields are all rows of this model — a 'measure' is simply
    role='measure' with a default aggregation, so the field well, the query
    engine, translation and masking share a single code path."""
    _name = 'bi.field'
    _description = 'BI Semantic Field'
    _order = 'node_id, sequence, id'

    dataset_id = fields.Many2one('bi.dataset', required=True,
                                 ondelete='cascade', index=True)
    node_id = fields.Many2one('bi.dataset.node', required=True,
                              ondelete='cascade', index=True)

    # Identity
    technical_name = fields.Char(
        required=True,
        help="Column name on the node's table, or a slug for calculated "
             "fields. Never shown to business users.")
    name = fields.Char(string='Business Name', required=True, translate=True)
    description = fields.Text(translate=True)

    origin = fields.Selection([
        ('stored', 'Stored Column'),
        ('calculated', 'Calculated'),
    ], required=True, default='stored')
    expression = fields.Text(
        help="Calculated fields only. Example: "
             "([Revenue] - [Cost]) / NULLIF-safe division is automatic.")

    # Semantics
    data_type = fields.Selection([
        ('text', 'Text'),
        ('integer', 'Integer'),
        ('float', 'Decimal'),
        ('monetary', 'Monetary'),
        ('boolean', 'Yes/No'),
        ('date', 'Date'),
        ('datetime', 'Date & Time'),
        ('selection', 'Selection'),
    ], required=True, default='text')
    role = fields.Selection([
        ('dimension', 'Dimension'),
        ('measure', 'Measure'),
        ('date', 'Date'),
        ('geo', 'Geography'),
        ('id', 'Identifier / Join Key'),
    ], required=True, default='dimension', index=True)
    default_agg = fields.Selection([
        ('sum', 'Sum'), ('avg', 'Average'), ('min', 'Minimum'),
        ('max', 'Maximum'), ('count', 'Count'),
        ('count_distinct', 'Count Distinct'), ('none', 'None'),
    ], default='none', string='Default Aggregation')

    # Presentation
    folder = fields.Char(
        help="Grouping folder in the field well (e.g. Financial, Location).")
    sequence = fields.Integer(default=100)
    format_json = fields.Json(
        help='{"decimals": 0, "currency": "VND", "prefix": "", "suffix": ""}')
    selection_labels_json = fields.Json(
        help="For selection columns, baked at scan time per installed "
             "language: {lang_code: {raw value: label}}. Legacy flat "
             "{value: label} maps are still understood.")
    is_translated_column = fields.Boolean(
        help="Underlying column is a translated jsonb — the engine extracts "
             "the user language with en_US fallback.")
    relation_model = fields.Char(
        string='Lookup Model',
        help="Set for many2one columns: the model the stored id points at. "
             "The column still groups by id, but results are LABELLED with "
             "the record's name instead of showing the raw id.")

    # Governance
    visibility = fields.Selection([
        ('visible', 'Visible'),
        ('hidden', 'Hidden'),
        ('sensitive', 'Sensitive'),
    ], default='visible', required=True,
        help="Hidden: not offered in the builder. Sensitive: additionally "
             "excluded from AI dataset cards.")
    is_filterable = fields.Boolean(
        default=True,
        help="Filterable fields get an index on the gold materialized view.")
    glossary_term_id = fields.Many2one('bi.glossary.term', string='Glossary Term')

    _sql_constraints = [
        ('technical_name_uniq', 'unique(node_id, technical_name)',
         'Field technical names must be unique per node.'),
    ]

    @api.constrains('origin', 'expression', 'role')
    def _check_expression(self):
        for field in self.filtered(lambda f: f.origin == 'calculated'):
            if not field.expression:
                raise ValidationError(
                    _("Calculated field %s needs an expression.", field.name))
            try:
                field._validate_expression()
            except ExpressionError as exc:
                raise ValidationError(
                    _("Invalid expression on %s: %s", field.name, exc))

    def _validate_expression(self):
        """Validate the expression against sibling stored fields.
        Calculated fields may only reference stored fields (no chains,
        which also rules out cycles)."""
        self.ensure_one()
        known = {}
        for sibling in self.dataset_id.field_ids:
            if sibling.origin != 'stored':
                continue
            known[sibling.technical_name] = True
            # source_env('en_US') gives the untranslated business name so
            # expressions keep validating whatever the author's language
            known[sibling.with_context(lang='en_US').name] = True
        return validate_expression(
            self.expression, known,
            allow_aggregates=self.role == 'measure')

    @api.model
    def _backfill_relation_models(self):
        """Fill relation_model on stored columns scanned before the field
        existed. Idempotent — safe to re-run after new datasets are added.

        MUST run with the full registry loaded (an `end-` migration, not
        `post-`): at post- time only biz_bi's own dependency closure is in
        the registry, so every many2one added by a health_* module is
        invisible and silently skipped.
        """
        candidates = self.search([
            ('origin', '=', 'stored'),
            ('relation_model', '=', False),
            ('node_id.source_id.type', '=', 'odoo_model'),
        ])
        filled = 0
        for bi_field in candidates:
            model = self.env.get(bi_field.node_id.source_id.model_name)
            if model is None:
                continue
            odoo_field = model._fields.get(bi_field.technical_name)
            if (odoo_field is None or odoo_field.type != 'many2one'
                    or not odoo_field.comodel_name
                    or self.env.get(odoo_field.comodel_name) is None):
                continue
            bi_field.relation_model = odoo_field.comodel_name
            filled += 1
        return filled

    def _selection_labels_for(self, lang=None):
        """Selection labels in the given (or user) language, with en_US then
        any-language fallback. Handles both the per-language format and
        legacy flat maps."""
        self.ensure_one()
        labels = self.selection_labels_json or {}
        if not labels:
            return {}
        first_value = next(iter(labels.values()), None)
        if not isinstance(first_value, dict):
            return labels  # legacy flat {value: label}
        lang = lang or self.env.user.lang or 'en_US'
        return (labels.get(lang) or labels.get('en_US')
                or next(iter(labels.values()), {}))

    def _expression_field_map(self):
        """ref name -> bi.field for expression compilation at query time."""
        self.ensure_one()
        mapping = {}
        for sibling in self.dataset_id.field_ids:
            if sibling.origin != 'stored':
                continue
            mapping[sibling.technical_name] = sibling
            mapping[sibling.with_context(lang='en_US').name] = sibling
        return mapping
