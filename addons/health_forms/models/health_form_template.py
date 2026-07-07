# -*- coding: utf-8 -*-
"""Clinical form template — the FHIR Questionnaire side of health_forms.

The template compiles its authoring rows into ``schema_json`` (the §4.2
shared JSON schema) which is the ONLY thing renderers (backend OWL widget
and PWA JS runner) ever read. Published templates are immutable; changes
go through ``action_new_version``.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Fields that may never change once a template is published (immutability —
#: instances pin their own schema_snapshot, but the published schema itself
#: must stay stable for FHIR Questionnaire versioning).
PROTECTED_PUBLISHED_FIELDS = {
    'code', 'version', 'question_ids', 'scoring_method',
    'scoring_bands_json', 'score_vitals_type_id',
}


class HealthFormTemplate(models.Model):
    _name = 'health.form.template'
    _description = 'Clinical Form Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, version desc'
    _rec_name = 'display_name'

    name = fields.Char(
        required=True, translate=True, tracking=True,
        help='FHIR Questionnaire.title')
    name_vi = fields.Char(string='Vietnamese Title')
    code = fields.Char(
        required=True, index=True,
        help='Family code (PAIN, BARTHEL, MNA_SF, BRADEN, AMTS); '
             'FHIR Questionnaire.name')
    version = fields.Integer(
        default=1, readonly=True, required=True,
        help='FHIR Questionnaire.version; unique together with code.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('retired', 'Retired'),
    ], default='draft', required=True, tracking=True,
        help='FHIR Questionnaire.status (published maps to active).')
    category = fields.Selection([
        ('assessment', 'Assessment'),
        ('screening', 'Screening'),
        ('intake', 'Intake'),
        ('outcome', 'Outcome Measure'),
        ('other', 'Other'),
    ], default='assessment', required=True)
    description = fields.Html(translate=True)
    service_type_ids = fields.Many2many(
        'health.service.type', 'health_form_template_service_type_rel',
        'template_id', 'service_type_id', string='Applicable Services',
        help='Which services this form applies to (PWA filtering). '
             'Empty means the form applies to all services.')
    question_ids = fields.One2many(
        'health.form.question', 'template_id', string='Questions')
    scoring_method = fields.Selection([
        ('sum', 'Sum of scores'),
        ('none', 'No scoring'),
    ], default='sum', help='Compiles into scoring.method of the schema.')
    scoring_bands_json = fields.Json(
        string='Scoring Bands',
        help="[{min, max, label, label_vi, color}] — inclusive bounds, "
             "flat mono colors.")
    score_vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Total Score Observation Type',
        help='Extraction target for the total score.')
    schema_json = fields.Json(
        compute='_compute_schema_json', store=True, readonly=True,
        string='Compiled Schema',
        help='The shared JSON schema (§4.2) — the only thing renderers read.')
    predecessor_id = fields.Many2one(
        'health.form.template', string='Previous Version', readonly=True)
    is_latest = fields.Boolean(
        compute='_compute_is_latest', store=True,
        help='No other template of the same code has a higher version in a '
             'state other than retired.')
    instance_count = fields.Integer(compute='_compute_instance_count')
    published_date = fields.Date(readonly=True)
    active = fields.Boolean(default=True)
    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('uniq_code_version', 'UNIQUE(code, version)',
         'Version already exists for this form code.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints — create the
        # unique index explicitly.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_form_template_code_version_uidx
            ON health_form_template (code, version)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('name', 'version')
    def _compute_display_name(self):
        for template in self:
            template.display_name = '%s (v%s)' % (
                template.name or template.code or '?', template.version)

    @api.depends(
        'code', 'version', 'name', 'name_vi', 'scoring_method',
        'scoring_bands_json',
        'score_vitals_type_id.code', 'score_vitals_type_id.loinc_code',
        'question_ids.sequence', 'question_ids.key',
        'question_ids.question_type', 'question_ids.label',
        'question_ids.label_vi', 'question_ids.required',
        'question_ids.options_json', 'question_ids.min_value',
        'question_ids.max_value', 'question_ids.score_weight',
        'question_ids.loinc_code', 'question_ids.vitals_type_id',
        'question_ids.ucum_unit', 'question_ids.visible_if_json',
        'question_ids.help', 'question_ids.help_vi')
    def _compute_schema_json(self):
        for template in self:
            template.schema_json = template._compile_schema()

    def _compile_schema(self):
        """Compile the authoring rows into the §4.2 schema document."""
        self.ensure_one()
        questions = []
        for question in self.question_ids.sorted(
                key=lambda q: (q.sequence, q.id or 0)):
            # Float fields cannot distinguish "unset" from 0.0 — a bounds
            # pair is only meaningful when it forms a real range.
            has_bounds = (question.question_type == 'number'
                          and question.max_value > question.min_value)
            questions.append({
                'key': question.key or '',
                'type': question.question_type,
                'label': question.label or '',
                'label_vi': question.label_vi or '',
                'required': bool(question.required),
                'options': question.options_json or [],
                'min': question.min_value if has_bounds else None,
                'max': question.max_value if has_bounds else None,
                'score_weight': question.score_weight or 0.0,
                'loinc_code': (question.loinc_code
                               or question.vitals_type_id.loinc_code
                               or None),
                'ucum_unit': (question.ucum_unit
                              or question.vitals_type_id.ucum_unit
                              or None),
                'visible_if': question.visible_if_json or None,
                'help': question.help or '',
                'help_vi': question.help_vi or '',
            })
        return {
            'code': self.code or '',
            'version': self.version,
            'title': self.name or '',
            'title_vi': self.name_vi or '',
            'questions': questions,
            'scoring': {
                'method': self.scoring_method or 'none',
                'bands': self.scoring_bands_json or [],
                'score_loinc_code':
                    self.score_vitals_type_id.loinc_code or None,
                'score_vitals_type_code':
                    self.score_vitals_type_id.code or None,
            },
        }

    @api.depends('code', 'version', 'state')
    def _compute_is_latest(self):
        for template in self:
            if not template.code:
                template.is_latest = True
                continue
            higher = template.with_context(active_test=False).search_count([
                ('code', '=', template.code),
                ('version', '>', template.version),
                ('state', '!=', 'retired'),
                ('id', '!=', template.id),
            ])
            template.is_latest = not higher

    def _recompute_family_latest(self):
        """Sibling templates share is_latest state — recompute the whole
        code family whenever code/version/state changes (stored computes
        cannot depend on other records)."""
        codes = [code for code in set(self.mapped('code')) if code]
        if not codes:
            return
        family = self.with_context(active_test=False).search(
            [('code', 'in', codes)])
        family._compute_is_latest()

    def _compute_instance_count(self):
        counts = {}
        if self.ids:
            for group in self.env['health.form.instance']._read_group(
                    [('template_id', 'in', self.ids)],
                    ['template_id'], ['__count']):
                counts[group[0].id] = group[1]
        for template in self:
            template.instance_count = counts.get(template.id, 0)

    # ------------------------------------------------------------------
    # Immutability / ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._recompute_family_latest()
        return templates

    def write(self, vals):
        protected = set(vals) & PROTECTED_PUBLISHED_FIELDS
        if protected and any(t.state == 'published' for t in self):
            raise UserError(_(
                'Published form templates are immutable (%s). '
                'Create a new version instead.',
                ', '.join(sorted(protected))))
        result = super().write(vals)
        if set(vals) & {'code', 'version', 'state', 'active'}:
            self._recompute_family_latest()
        return result

    def unlink(self):
        if any(t.state != 'draft' for t in self):
            raise UserError(_(
                'Only draft form templates can be deleted. '
                'Retire published templates instead.'))
        codes = [code for code in set(self.mapped('code')) if code]
        result = super().unlink()
        if codes:
            self.with_context(active_test=False).search(
                [('code', 'in', codes)])._compute_is_latest()
        return result

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_publish(self):
        for template in self:
            if template.state != 'draft':
                raise UserError(_(
                    'Only draft templates can be published.'))
            if not template.question_ids:
                raise UserError(_(
                    'Cannot publish a form template without questions.'))
            keys = template.question_ids.mapped('key')
            if len(keys) != len(set(keys)):
                raise UserError(_(
                    'Question keys must be unique within the template.'))
            template.write({
                'state': 'published',
                'published_date': fields.Date.today(),
            })
        return True

    def action_retire(self):
        for template in self:
            if template.state != 'published':
                raise UserError(_(
                    'Only published templates can be retired.'))
            template.write({'state': 'retired'})
        return True

    def action_new_version(self):
        self.ensure_one()
        if self.state != 'published':
            raise UserError(_(
                'Create new versions from the published template.'))
        highest = self.with_context(active_test=False).search(
            [('code', '=', self.code)], order='version desc', limit=1)
        new_template = self.copy({
            'version': (highest.version or self.version) + 1,
            'state': 'draft',
            'predecessor_id': self.id,
            'published_date': False,
        })
        if not new_template.question_ids:
            # Odoo 19's copy() does not reliably duplicate the o2m lines;
            # copy questions explicitly (guarded against double-copy).
            for question in self.question_ids:
                question.copy({'template_id': new_template.id})
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Version'),
            'res_model': 'health.form.template',
            'res_id': new_template.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('state', 'draft')
        default.setdefault('published_date', False)
        return super().copy(default)

    # ------------------------------------------------------------------
    # Smart button / PWA
    # ------------------------------------------------------------------
    def action_view_instances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Form Instances'),
            'res_model': 'health.form.instance',
            'view_mode': 'list,form,graph',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }

    @api.model
    def get_templates_for_service(self, service_type_ids=None):
        """Published + latest templates, filtered by service-type overlap
        (empty m2m = applies to all). Returns schema list for the PWA."""
        domain = [('state', '=', 'published'), ('is_latest', '=', True)]
        if service_type_ids:
            domain += ['|', ('service_type_ids', '=', False),
                       ('service_type_ids', 'in', list(service_type_ids))]
        templates = self.search(domain, order='name')
        result = []
        for template in templates:
            schema = dict(template.schema_json or template._compile_schema())
            schema.update({
                'id': template.id,
                'category': template.category,
                'service_type_ids': template.service_type_ids.ids,
            })
            result.append(schema)
        return result
