# -*- coding: utf-8 -*-
"""Clinical form question — authoring row compiled into the §4.2 schema."""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

KEY_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')

QUESTION_TYPES = [
    ('number', 'Number'),
    ('selection', 'Selection'),
    ('multiselect', 'Multi-select'),
    ('text', 'Text'),
    ('boolean', 'Yes/No'),
    ('date', 'Date'),
    ('photo', 'Photo'),
    ('signature', 'Signature'),
    ('computed_score', 'Computed Score'),
]


class HealthFormQuestion(models.Model):
    _name = 'health.form.question'
    _description = 'Clinical Form Question'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'health.form.template', required=True, ondelete='cascade',
        index=True, string='Template')
    sequence = fields.Integer(default=10)
    key = fields.Char(
        required=True,
        help='Answer key (snake_case, unique per template).')
    question_type = fields.Selection(
        QUESTION_TYPES, required=True, string='Type',
        help='Renderer widget.')
    label = fields.Char(required=True, translate=True,
                        help='Question text.')
    label_vi = fields.Char(string='Vietnamese Label')
    required = fields.Boolean(default=False)
    options_json = fields.Json(
        string='Options',
        help="[{value, label, label_vi, score}] for "
             "selection/multiselect/boolean.")
    min_value = fields.Float(help='Lower bound for number questions.')
    max_value = fields.Float(help='Upper bound for number questions.')
    score_weight = fields.Float(
        default=0.0, help='Number contribution multiplier.')
    loinc_code = fields.Char(
        string='LOINC Code',
        help='Per-question coded extraction '
             '(numeric / selection-with-scores only).')
    vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Observation Type',
        help='Extraction target for this question '
             '(overrides the LOINC lookup).')
    ucum_unit = fields.Char(
        string='UCUM Unit', help='Unit for the extracted observation.')
    visible_if_json = fields.Json(
        string='Visible If',
        help='{"key": "<other question key>", '
             '"operator": "=|!=|in|>=|<=", "value": ...} — '
             'single-condition show/hide.')
    help = fields.Char(translate=True, help='Hint text.')
    help_vi = fields.Char(string='Vietnamese Hint')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('key', 'template_id')
    def _check_key(self):
        for question in self:
            if not question.key or not KEY_PATTERN.match(question.key):
                raise ValidationError(_(
                    'Question key "%s" must be snake_case '
                    '(pattern ^[a-z][a-z0-9_]*$).', question.key or ''))
            duplicates = self.search_count([
                ('template_id', '=', question.template_id.id),
                ('key', '=', question.key),
                ('id', '!=', question.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    'Question key "%s" is already used in this template.',
                    question.key))

    # ------------------------------------------------------------------
    # Published-template immutability (belt-and-braces with the guard on
    # health.form.template.write — inline o2m edits hit these directly).
    # ------------------------------------------------------------------
    def _check_template_mutable(self):
        published = self.mapped('template_id').filtered(
            lambda t: t.state == 'published')
        if published:
            raise UserError(_(
                'Questions of a published form template are immutable. '
                'Create a new version instead.'))

    @api.model_create_multi
    def create(self, vals_list):
        template_ids = [vals.get('template_id') for vals in vals_list
                        if vals.get('template_id')]
        templates = self.env['health.form.template'].browse(template_ids)
        if any(t.state == 'published' for t in templates):
            raise UserError(_(
                'Questions of a published form template are immutable. '
                'Create a new version instead.'))
        return super().create(vals_list)

    def write(self, vals):
        self._check_template_mutable()
        return super().write(vals)

    def unlink(self):
        self._check_template_mutable()
        return super().unlink()
