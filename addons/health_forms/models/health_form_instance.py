# -*- coding: utf-8 -*-
"""Clinical form instance — the FHIR QuestionnaireResponse side.

Every instance pins the exact schema it was answered against
(``schema_snapshot``) so it renders identically forever, even after the
template is retired. Scoring and coded-observation extraction run against
the snapshot, never the live template.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HealthFormInstance(models.Model):
    _name = 'health.form.instance'
    _description = 'Clinical Form Instance (Response)'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(readonly=True, copy=False, default=lambda self: _('New'))
    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    template_id = fields.Many2one(
        'health.form.template', required=True, ondelete='restrict',
        domain=[('state', '=', 'published')], string='Form Template',
        index=True)
    template_code = fields.Char(
        related='template_id.code', store=True, string='Form Code')
    template_version = fields.Integer(
        readonly=True, copy=False,
        help='Template version pinned at creation.')
    schema_snapshot = fields.Json(
        readonly=True, copy=False,
        help='Copy of the template schema_json at creation — the instance '
             'renders from this forever.')
    client_id = fields.Many2one(
        'res.partner', required=True, domain=[('is_patient', '=', True)],
        ondelete='restrict', index=True, tracking=True, string='Client',
        help='FHIR QuestionnaireResponse.subject')
    order_id = fields.Many2one(
        'health.fieldservice.order', ondelete='set null', index=True,
        string='Booking', help='FHIR QuestionnaireResponse.encounter')
    performer_id = fields.Many2one(
        'res.users', default=lambda self: self.env.uid, readonly=True,
        string='Performer', help='FHIR QuestionnaireResponse.author')
    answers_json = fields.Json(
        string='Answers',
        help='{key: value}; photo/signature values = {"attachment_id": id}.')
    total_score = fields.Float(readonly=True, copy=False, tracking=True)
    score_label = fields.Char(readonly=True, copy=False)
    score_label_vi = fields.Char(readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('completed', 'Completed'),
        ('amended', 'Amended'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False,
        help='FHIR QuestionnaireResponse.status '
             '(completed/amended verbatim, cancelled maps to stopped).')
    completed_datetime = fields.Datetime(
        readonly=True, copy=False, help='FHIR QuestionnaireResponse.authored')
    observation_ids = fields.One2many(
        'health.observation', 'form_instance_id',
        string='Extracted Observations')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'health_form_instance_attachment_rel',
        'instance_id', 'attachment_id', string='Photos & Signatures')
    client_uuid = fields.Char(
        readonly=True, index=True, copy=False,
        help='Client-generated idempotency key for offline PWA replay.')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True,
        help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — partial unique
        # index backs the unique-if-set client_uuid contract.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_form_instance_client_uuid_uidx
            ON health_form_instance (client_uuid)
            WHERE client_uuid IS NOT NULL AND client_uuid != ''
        """)

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
    @api.depends('template_id.name', 'client_id.name', 'completed_datetime',
                 'name')
    def _compute_display_name(self):
        for instance in self:
            parts = '%s — %s' % (
                instance.template_id.name or instance.name or '?',
                instance.client_id.name or '?')
            if instance.completed_datetime:
                parts += ' (%s)' % fields.Date.to_string(
                    instance.completed_datetime.date())
            instance.display_name = parts

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    @api.constrains('client_uuid')
    def _check_client_uuid(self):
        for instance in self:
            if not instance.client_uuid:
                continue
            duplicates = self.search_count([
                ('client_uuid', '=', instance.client_uuid),
                ('id', '!=', instance.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    'A form instance with this client UUID already exists '
                    '(idempotency key must be unique).'))

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Pin the schema in the UI before the record is saved so the
        renderer can draw immediately."""
        for instance in self:
            if instance.template_id:
                instance.template_version = instance.template_id.version
                instance.schema_snapshot = instance.template_id.schema_json
                instance.answers_json = {}

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            template = self.env['health.form.template'].browse(
                vals.get('template_id'))
            if template and template.state != 'published':
                raise UserError(_(
                    'Form instances can only be created from published '
                    'templates.'))
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.form.instance') or _('New')
            if template:
                vals.setdefault('template_version', template.version)
                if not vals.get('schema_snapshot'):
                    vals['schema_snapshot'] = (
                        template.schema_json or template._compile_schema())
        return super().create(vals_list)

    def write(self, vals):
        amended = self.browse()
        if 'answers_json' in vals:
            amended = self.filtered(
                lambda i: i.state in ('completed', 'amended'))
            if amended and not self._is_head_nurse_plus():
                raise UserError(_(
                    'Only head nurses and above can amend a completed '
                    'form instance.'))
        result = super().write(vals)
        if amended:
            amended._reprocess_amendment()
        return result

    def unlink(self):
        if not self._is_admin_plus():
            blocked = self.filtered(
                lambda i: i.state in ('completed', 'amended'))
            if blocked:
                raise UserError(_(
                    'Completed form instances cannot be deleted '
                    '(clinical record integrity). Cancel or amend instead.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Group helpers
    # ------------------------------------------------------------------
    def _is_head_nurse_plus(self):
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_head_nurse')
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    def _is_admin_plus(self):
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    # ------------------------------------------------------------------
    # Schema evaluation (§4.2 contract — mirrored by both renderers)
    # ------------------------------------------------------------------
    @api.model
    def _evaluate_visible_if(self, condition, answers):
        """Single-condition show/hide: {'key', 'operator', 'value'}."""
        if not condition:
            return True
        answer = (answers or {}).get(condition.get('key'))
        operator = condition.get('operator') or '='
        value = condition.get('value')
        try:
            if operator == '=':
                return answer == value
            if operator == '!=':
                return answer != value
            if operator == 'in':
                if isinstance(answer, (list, tuple)):
                    if isinstance(value, (list, tuple)):
                        return bool(set(answer) & set(value))
                    return value in answer
                if isinstance(value, (list, tuple)):
                    return answer in value
                return answer == value
            if answer is None:
                return False
            if operator == '>=':
                return float(answer) >= float(value)
            if operator == '<=':
                return float(answer) <= float(value)
        except (TypeError, ValueError):
            return False
        return True

    @api.model
    def _question_contribution(self, question, answer):
        """Score contribution of one answered question (§4.2 rules)."""
        qtype = question.get('type')
        options = question.get('options') or []
        if answer is None:
            return 0.0
        if qtype == 'number':
            weight = question.get('score_weight') or 0.0
            if weight > 0:
                try:
                    return float(answer) * weight
                except (TypeError, ValueError):
                    return 0.0
            return 0.0
        if qtype == 'selection':
            for option in options:
                if option.get('value') == answer:
                    return float(option.get('score') or 0.0)
            return 0.0
        if qtype == 'multiselect':
            if not isinstance(answer, (list, tuple)):
                return 0.0
            return float(sum(
                option.get('score') or 0.0 for option in options
                if option.get('value') in answer))
        if qtype == 'boolean':
            key = 'true' if answer else 'false'
            for option in options:
                if str(option.get('value')).lower() == key:
                    return float(option.get('score') or 0.0)
            return 0.0
        # text / date / photo / signature / computed_score: never scored
        return 0.0

    def _visible_questions(self):
        self.ensure_one()
        schema = self.schema_snapshot or {}
        answers = self.answers_json or {}
        return [question for question in schema.get('questions', [])
                if self._evaluate_visible_if(
                    question.get('visible_if'), answers)]

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------
    def _compute_score(self):
        """Explicit scoring pass (not @api.depends — answers are Json).

        Walks schema_snapshot.questions against answers_json per the §4.2
        contribution rules, honoring visible_if (hidden questions
        contribute 0), then resolves the band labels."""
        for instance in self:
            schema = instance.schema_snapshot or {}
            answers = instance.answers_json or {}
            scoring = schema.get('scoring') or {}
            if (scoring.get('method') or 'none') != 'sum':
                instance.total_score = 0.0
                instance.score_label = False
                instance.score_label_vi = False
                continue
            total = 0.0
            for question in instance._visible_questions():
                total += self._question_contribution(
                    question, answers.get(question.get('key')))
            band = self._resolve_band(scoring.get('bands') or [], total)
            instance.total_score = total
            instance.score_label = band.get('label') if band else False
            instance.score_label_vi = (
                band.get('label_vi') if band else False)

    @api.model
    def _resolve_band(self, bands, total):
        for band in bands:
            band_min = band.get('min')
            band_max = band.get('max')
            if ((band_min is None or total >= band_min)
                    and (band_max is None or total <= band_max)):
                return band
        return None

    def _validate_answers(self):
        """Required + bounds validation against schema_snapshot. Hidden
        questions are exempt from required and never scored."""
        for instance in self:
            answers = instance.answers_json or {}
            for question in instance._visible_questions():
                key = question.get('key')
                qtype = question.get('type')
                answer = answers.get(key)
                is_empty = (
                    answer is None or answer == ''
                    or (isinstance(answer, (list, dict)) and not answer))
                # A boolean False is a valid answer (not "empty").
                if (question.get('required') and qtype != 'computed_score'
                        and is_empty):
                    raise UserError(_(
                        'Required question "%s" is not answered.',
                        question.get('label') or key))
                if qtype == 'number' and answer not in (None, ''):
                    try:
                        value = float(answer)
                    except (TypeError, ValueError):
                        raise UserError(_(
                            'Answer to "%s" must be a number.',
                            question.get('label') or key))
                    q_min = question.get('min')
                    q_max = question.get('max')
                    if q_min is not None and value < q_min:
                        raise UserError(_(
                            'Answer to "%s" is below the minimum (%s).',
                            question.get('label') or key, q_min))
                    if q_max is not None and value > q_max:
                        raise UserError(_(
                            'Answer to "%s" is above the maximum (%s).',
                            question.get('label') or key, q_max))

    def _extract_observations(self):
        """Extract coded observations into health_vitals (source='form').

        Every create is wrapped so an extraction failure never blocks the
        clinical form submission itself."""
        Observation = self.env['health.observation']
        VitalsType = self.env['health.vitals.type']
        for instance in self:
            answers = instance.answers_json or {}
            schema = instance.schema_snapshot or {}
            extracted_loincs = set()
            # (1) Per-question extraction: numeric contribution only
            # (number value, or selected option score).
            for question in instance._visible_questions():
                loinc_code = question.get('loinc_code')
                if not loinc_code:
                    continue
                answer = answers.get(question.get('key'))
                value = None
                qtype = question.get('type')
                if qtype == 'number' and answer not in (None, ''):
                    try:
                        value = float(answer)
                    except (TypeError, ValueError):
                        value = None
                elif qtype == 'selection' and answer:
                    for option in question.get('options') or []:
                        if (option.get('value') == answer
                                and option.get('score') is not None):
                            value = float(option['score'])
                            break
                if value is None:
                    continue
                if instance._create_form_observation(
                        Observation, loinc_code, value,
                        uom=question.get('ucum_unit')):
                    extracted_loincs.add(loinc_code)
            # (2) Total score extraction.
            scoring = schema.get('scoring') or {}
            if (scoring.get('method') or 'none') != 'sum':
                continue
            loinc_code = None
            type_code = scoring.get('score_vitals_type_code')
            if type_code:
                vitals_type = VitalsType.search(
                    [('code', '=', type_code)], limit=1)
                loinc_code = vitals_type.loinc_code or None
            if not loinc_code:
                loinc_code = scoring.get('score_loinc_code')
            # Single-question instruments (e.g. PAIN) point the total at
            # the same observation type as the question — never emit the
            # same coded value twice.
            if loinc_code and loinc_code not in extracted_loincs:
                instance._create_form_observation(
                    Observation, loinc_code, instance.total_score)

    def _create_form_observation(self, Observation, loinc_code, value,
                                 uom=None):
        """One coded observation via the health_vitals contract; failure
        is logged, never raised (form submission must not block)."""
        self.ensure_one()
        try:
            observation = Observation.create_coded(
                self.client_id.id, loinc_code, value,
                uom=uom or None,
                fso_id=self.order_id.id or None,
                effective_datetime=(self.completed_datetime
                                    or fields.Datetime.now()),
                performer_id=self.performer_id.id or None,
                source='form',
            )
            observation.write({'form_instance_id': self.id})
            return observation
        except Exception as exc:  # noqa: BLE001 — extraction never blocks
            _logger.warning(
                'health_forms: observation extraction skipped for '
                'instance %s (LOINC %s): %s', self.id, loinc_code, exc)
            return Observation.browse()

    def _reprocess_amendment(self):
        """Amendment of a completed instance: previous extracted
        observations are marked entered_in_error, score re-runs, fresh
        observations are extracted."""
        for instance in self:
            previous = instance.observation_ids.filtered(
                lambda o: o.state != 'entered_in_error')
            if previous:
                try:
                    previous.write({'state': 'entered_in_error'})
                except Exception as exc:  # noqa: BLE001
                    _logger.warning(
                        'health_forms: could not mark previous '
                        'observations entered_in_error for instance %s: %s',
                        instance.id, exc)
            instance._compute_score()
            instance._extract_observations()
            if instance.state == 'completed':
                instance.state = 'amended'

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_complete(self):
        for instance in self:
            if instance.state != 'draft':
                raise UserError(_(
                    'Only draft form instances can be completed.'))
            instance._validate_answers()
            instance.completed_datetime = fields.Datetime.now()
            instance._compute_score()
            instance.state = 'completed'
            instance._extract_observations()
        return True

    def action_cancel(self):
        if not self._is_head_nurse_plus():
            raise UserError(_(
                'Only head nurses and above can cancel form instances.'))
        for instance in self:
            if instance.state not in ('draft', 'completed'):
                raise UserError(_(
                    'Only draft or completed form instances can be '
                    'cancelled.'))
            instance.state = 'cancelled'
        return True
