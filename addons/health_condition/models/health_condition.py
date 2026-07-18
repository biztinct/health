# -*- coding: utf-8 -*-
"""``health.condition`` — the patient problem list (condition-spine handover).

ONE record per (patient, ICD-10 code), evidence-linked to the clinical notes
that assert it. Populated ADDITIVELY by the note-write sync hook
(``health_clinical_note.py``) — every sidecar write path (manual ICD-10 tag,
AI-coding approve, future scribe) converges here. Clinical-status transitions
(resolve / inactivate / reactivate) are a HUMAN act on this form; the sync
never resolves and never deletes.

FHIR: serialized as an R4 ``Condition`` (``serializers/condition.py``), joined
into ``Patient/$everything`` automatically by the compartment convention.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# Groups allowed to change a diagnosis' clinical status (resolve / reactivate)
# — the same create+write ladder as the ACL (doctor / head_nurse / manager+).
_STATUS_GROUPS = (
    'health_base.group_healthcare_doctor',
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)


class HealthCondition(models.Model):
    _name = 'health.condition'
    _description = 'Condition / Diagnosis (Problem List)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'recorded_date desc, id desc'
    _rec_name = 'display_name'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='restrict', domain=[('is_patient', '=', True)],
        tracking=True,
        help='FHIR Condition.subject.')
    code_id = fields.Many2one(
        'medical.code', string='ICD-10 Code', required=True, index=True,
        ondelete='restrict', domain="[('system_id.code', '=', 'icd10')]",
        tracking=True,
        help='FHIR Condition.code (ICD-10).')
    display_name = fields.Char(compute='_compute_display_name', store=True)

    clinical_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('resolved', 'Resolved'),
    ], string='Clinical Status', default='active', required=True,
        tracking=True,
        help='FHIR Condition.clinicalStatus. Transitions are a human act — '
             'the coded-diagnosis sync never resolves or inactivates.')
    verification_status = fields.Selection([
        ('provisional', 'Provisional'),
        ('confirmed', 'Confirmed'),
    ], string='Verification Status', default='confirmed', required=True,
        tracking=True,
        help='FHIR Condition.verificationStatus. Everything reaching the '
             'coded sidecar is human-asserted (manual tag or human-approved '
             'AI suggestion), so the default is confirmed.')

    recorded_date = fields.Date(
        string='Recorded Date', default=fields.Date.context_today,
        tracking=True,
        help='First assertion (from the first evidence note). Provenance — '
             'never moved by the sync after creation; editable by doctors '
             'for corrections.')
    last_asserted_date = fields.Date(
        string='Last Asserted', readonly=True,
        help='Latest evidence assertion (advanced by the sync).')
    note_ids = fields.Many2many(
        'health.clinical.note', 'health_condition_note_rel',
        'condition_id', 'note_id', string='Evidence Notes',
        help='The clinical notes whose coded-diagnosis sidecar asserts this '
             'condition (FHIR Condition.evidence.detail → DocumentReference).')
    note_count = fields.Integer(
        string='Evidence', compute='_compute_note_count')
    recorder_id = fields.Many2one(
        'res.users', string='Recorder', readonly=True,
        help="First asserting note's author (provenance — never moved).")

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True,
        help='Catchment area used for filtering and access control.')
    active = fields.Boolean(
        default=True,
        help='Archive removes the condition from the working problem list. '
             'It is NEVER unlinked in normal flows — a fresh assertion '
             'reactivates it.')

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------
    def init(self):
        # Odoo 19 does not materialize _sql_constraints (conventions §5.1).
        # ONE condition per (patient, code) — the idempotency backstop for
        # the additive sync. active_test-independent (covers archived rows).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_condition_patient_code_uidx
            ON health_condition (patient_id, code_id)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('code_id.code', 'code_id.display_vi', 'code_id.display',
                 'patient_id.name')
    def _compute_display_name(self):
        for rec in self:
            code = rec.code_id
            label = (code.display_vi or code.display or '') if code else ''
            code_txt = '[%s] %s' % (code.code or '', label) if code else ''
            rec.display_name = '%s — %s' % (
                code_txt.strip(), rec.patient_id.name or '')

    @api.depends('note_ids')
    def _compute_note_count(self):
        for rec in self:
            rec.note_count = len(rec.note_ids)

    @api.depends('patient_id.catchment_province_id',
                 'patient_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.patient_id._get_health_catchment_province()
                if rec.patient_id else False)

    # ------------------------------------------------------------------
    # CRUD — duplicate (patient, code) is caught in Python BEFORE the unique
    # index fires (conventions §5.3: an IntegrityError would poison the txn).
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seen = set()
        for vals in vals_list:
            pid, cid = vals.get('patient_id'), vals.get('code_id')
            if pid and cid:
                key = (pid, cid)
                if key in seen or self.with_context(
                        active_test=False).search_count([
                            ('patient_id', '=', pid), ('code_id', '=', cid)]):
                    raise ValidationError(_(
                        'This patient already has a problem-list entry for '
                        'this ICD-10 code.'))
                seen.add(key)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Status transitions (human act — defense in depth: buttons carry
    # groups=..., methods additionally check).
    # ------------------------------------------------------------------
    def _check_status_change(self):
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        if not any(user.has_group(group) for group in _STATUS_GROUPS):
            raise AccessError(_(
                'Only a doctor, head nurse or manager may change a '
                'diagnosis status.'))

    def action_mark_resolved(self):
        self._check_status_change()
        for rec in self:
            rec.write({'clinical_status': 'resolved'})
            rec.message_post(body=_('Diagnosis marked resolved.'))
        return True

    def action_mark_inactive(self):
        self._check_status_change()
        for rec in self:
            rec.write({'clinical_status': 'inactive'})
            rec.message_post(body=_('Diagnosis marked inactive.'))
        return True

    def action_reactivate(self):
        self._check_status_change()
        for rec in self:
            rec.write({'clinical_status': 'active', 'active': True})
            rec.message_post(body=_('Diagnosis reactivated.'))
        return True

    def action_view_evidence(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evidence Notes'),
            'res_model': 'health.clinical.note',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.note_ids.ids)],
        }
