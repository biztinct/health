# -*- coding: utf-8 -*-
"""Incident / adverse event (clinical spec §5.2.1).

FHIR AdverseEvent: actuality = actual (near_miss → potential),
event = local coding health19-incident-types, subject = client,
date = incident_datetime, detected/recordedDate = reported_datetime,
severity 1-2 → mild / 3 → moderate / 4-5 → severe, recorder = reporter,
contributor = investigator, mitigation.description = immediate_actions,
encounter = order_id. A standing Flag is derived by the future
serializer for clients with an open fall or severity ≥4 incident (no
separate Odoo model). Corrective actions map to Task.

PHI note: `description`, `immediate_actions`, `investigation_notes`,
`root_cause` and `contributing_factors` are plain (unencrypted) fields
— module-local, flagged as future phi-encryption candidates (README).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Groups allowed to drive the review/investigation transitions
# (spec §5.3: head_nurse, ops_manager, manager+).
REVIEW_GROUPS = (
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)
# Fast-close of trivial events (spec §5.3: head_nurse, manager+).
MINOR_CLOSE_GROUPS = (
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)
MANAGER_GROUPS = (
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)

INCIDENT_TYPES = [
    ('fall', 'Fall'),
    ('medication_error', 'Medication Error'),
    ('injury', 'Injury'),
    ('behaviour', 'Behaviour'),
    ('property', 'Property Damage/Loss'),
    ('near_miss', 'Near Miss'),
    ('other', 'Other'),
]

SEVERITIES = [
    ('1', '1 — Negligible'),
    ('2', '2 — Minor'),
    ('3', '3 — Moderate'),
    ('4', '4 — Major'),
    ('5', '5 — Catastrophic'),
]


class HealthIncident(models.Model):
    _name = 'health.incident'
    _description = 'Incident / Adverse Event'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'health.lifecycle.mixin']
    _order = 'incident_datetime desc'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference', readonly=True, copy=False,
        default=lambda self: _('New'),
        help='Reference (sequence health.incident, prefix INC).')
    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    incident_type = fields.Selection(
        INCIDENT_TYPES, string='Type', required=True, tracking=True,
        index=True,
        help='Taxonomy; FHIR AdverseEvent.event '
             '(local CodeSystem health19-incident-types).')
    severity = fields.Selection(
        SEVERITIES, required=True, default='2', tracking=True, index=True,
        help='FHIR AdverseEvent.severity '
             '(1-2 → mild, 3 → moderate, 4-5 → severe).')
    client_id = fields.Many2one(
        'res.partner', string='Client',
        domain=[('is_patient', '=', True)], ondelete='restrict',
        index=True, tracking=True,
        help='FHIR AdverseEvent.subject '
             '(optional — staff-only incidents allowed).')
    order_id = fields.Many2one(
        'health.fieldservice.order', string='Visit',
        ondelete='set null', index=True,
        help='The visit; FHIR AdverseEvent.encounter.')
    facility_id = fields.Many2one(
        'health.facility', string='Facility', tracking=True,
        help='Register slicing (defaults from the visit, else the '
             "client's primary facility).")
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    location = fields.Char(
        help='Where it happened; FHIR AdverseEvent.location.display.')
    incident_datetime = fields.Datetime(
        string='Incident Date/Time', required=True,
        default=fields.Datetime.now, tracking=True,
        help='FHIR AdverseEvent.date')
    reporter_id = fields.Many2one(
        'res.users', string='Reporter',
        default=lambda self: self.env.uid, readonly=True,
        help='FHIR AdverseEvent.recorder')
    reported_datetime = fields.Datetime(
        string='Reported On', default=fields.Datetime.now, readonly=True,
        help='FHIR AdverseEvent.detected / recordedDate')
    description = fields.Text(
        required=True,
        help='Narrative of what happened. Plain field — future '
             'phi-encryption candidate.')
    immediate_actions = fields.Text(
        help='First response taken; FHIR mitigation narrative.')
    witnesses = fields.Char(help='Free-text witness names.')
    state = fields.Selection([
        ('reported', 'Reported'),
        ('under_review', 'Under Review'),
        ('investigation', 'Investigation'),
        ('actions_assigned', 'Actions Assigned'),
        ('closed', 'Closed'),
    ], default='reported', required=True, tracking=True, index=True)
    investigator_id = fields.Many2one(
        'res.users', string='Investigator', tracking=True,
        help='Investigation owner; FHIR AdverseEvent.contributor.')
    investigation_notes = fields.Html(help='Findings.')
    root_cause = fields.Text(help='RCA summary.')
    contributing_factors = fields.Text()
    outcome = fields.Selection([
        ('no_harm', 'No Harm'),
        ('minor_harm', 'Minor Harm'),
        ('moderate_harm', 'Moderate Harm'),
        ('severe_harm', 'Severe Harm'),
        ('death', 'Death'),
    ], tracking=True, help='FHIR AdverseEvent.outcome')
    notifiable = fields.Boolean(
        default=False, tracking=True, index=True,
        help='Regulatory-notifiable flag (no hard constraint ties it '
             'to severity/type — regulator definitions differ).')
    notified_authority = fields.Char(
        help='Which authority (Sở Y tế / MOH / other).')
    notified_date = fields.Date(help='When notified.')
    action_ids = fields.One2many(
        'health.incident.action', 'incident_id',
        string='Corrective Actions')
    action_count = fields.Integer(compute='_compute_action_counts')
    open_action_count = fields.Integer(compute='_compute_action_counts')
    fall_risk_reassessment_triggered = fields.Boolean(
        string='Fall Risk Reassessment Triggered', readonly=True,
        copy=False, help='§5.4 hook fired.')
    closed_date = fields.Datetime(readonly=True, copy=False,
                                  help='Set on close.')
    closed_by_id = fields.Many2one(
        'res.users', string='Closed By', readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'health_incident_attachment_rel',
        'incident_id', 'attachment_id', string='Evidence',
        help='Photos / evidence.')
    client_mutation_id = fields.Char(
        readonly=True, copy=False, index=True,
        help='Idempotency key of the PWA offline queue — a replayed '
             'mutation must not create a duplicate incident.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints — create the
        # unique index explicitly. Partial: NULL mutation ids (backend
        # records) must not collide.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_incident_client_mutation_uidx
            ON health_incident (client_mutation_id)
            WHERE client_mutation_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Computes / onchange
    # ------------------------------------------------------------------
    @api.depends('name', 'incident_type', 'client_id.name')
    def _compute_display_name(self):
        type_labels = dict(
            self._fields['incident_type']._description_selection(self.env))
        for incident in self:
            incident.display_name = '%s — %s (%s)' % (
                incident.name or _('New'),
                type_labels.get(incident.incident_type,
                                incident.incident_type or ''),
                incident.client_id.name or _('no client'))

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id',
                 'facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        # §0.3 with the §5.2.1 fallback: staff-only incidents (no
        # client) take the facility's catchment.
        for incident in self:
            if incident.client_id:
                incident.catchment_province_id = (
                    incident.client_id._get_health_catchment_province())
            elif incident.facility_id:
                incident.catchment_province_id = (
                    incident.facility_id.catchment_province_id)
            else:
                incident.catchment_province_id = False

    @api.depends('action_ids.state')
    def _compute_action_counts(self):
        for incident in self:
            incident.action_count = len(incident.action_ids)
            incident.open_action_count = len(incident.action_ids.filtered(
                lambda action: action.state in ('open', 'in_progress')))

    @api.onchange('order_id', 'client_id')
    def _onchange_default_facility(self):
        if self.order_id and self.order_id.facility_id:
            self.facility_id = self.order_id.facility_id
        elif self.client_id and self.client_id.primary_facility_id:
            self.facility_id = self.client_id.primary_facility_id
        if self.order_id and self.order_id.patient_id and not self.client_id:
            self.client_id = self.order_id.patient_id

    @api.onchange('severity')
    def _onchange_severity_notifiable(self):
        # Onchange only (spec §5.2.1): no hard constraint ties
        # notifiable to severity.
        if self.severity in ('4', '5'):
            self.notifiable = True

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model
    def _notifiable_types(self):
        """Configurable notifiable types (binding design decision):
        comma-separated incident_type codes in the ir.config_parameter
        health_incident.notifiable_types."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'health_incident.notifiable_types') or ''
        return [code.strip() for code in param.split(',') if code.strip()]

    @api.model_create_multi
    def create(self, vals_list):
        notifiable_types = self._notifiable_types()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.incident') or _('New')
            # Server-side counterpart of the onchange defaults — PWA /
            # API creates never run onchanges.
            if not vals.get('facility_id'):
                order = self.env['health.fieldservice.order'].browse(
                    vals.get('order_id')) if vals.get('order_id') else False
                client = self.env['res.partner'].browse(
                    vals.get('client_id')) if vals.get('client_id') else False
                if order and order.facility_id:
                    vals['facility_id'] = order.facility_id.id
                elif client and client.primary_facility_id:
                    vals['facility_id'] = client.primary_facility_id.id
            if (vals.get('severity') in ('4', '5')
                    or vals.get('incident_type') in notifiable_types):
                vals.setdefault('notifiable', True)
        incidents = super().create(vals_list)
        for incident in incidents:
            if incident.severity in ('4', '5'):
                incident._schedule_severe_incident_activity()
            if incident.incident_type == 'fall' and incident.client_id:
                incident._trigger_fall_risk_reassessment()
        return incidents

    def write(self, vals):
        # Binding design decision: severity 4-5 incidents are
        # append-only after closing — no edits below manager.
        self._check_closed_severe_append_only()
        was_fall = {
            incident.id: incident.incident_type == 'fall'
            and bool(incident.client_id) for incident in self}
        result = super().write(vals)
        if 'incident_type' in vals or 'client_id' in vals:
            for incident in self:
                if (incident.incident_type == 'fall' and incident.client_id
                        and not was_fall[incident.id]):
                    incident._trigger_fall_risk_reassessment()
        return result

    def _check_closed_severe_append_only(self):
        if self.env.su:
            return
        user = self.env.user
        if user._is_admin() or any(
                user.has_group(group) for group in MANAGER_GROUPS):
            return
        for incident in self:
            if incident.state == 'closed' and incident.severity in ('4', '5'):
                raise AccessError(_(
                    'Closed severity-%(severity)s incidents are '
                    'append-only: only managers may modify %(name)s. '
                    'Use the chatter to add follow-up notes.',
                    severity=incident.severity, name=incident.name))

    def copy(self, default=None):
        # Odoo 19 gotcha: copy() does not reliably duplicate One2many
        # lines — copy corrective actions explicitly, with a guard.
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('state', 'reported')
        default.setdefault('closed_date', False)
        default.setdefault('closed_by_id', False)
        new_incident = super().copy(default)
        if not new_incident.action_ids:
            for action in self.action_ids:
                action.copy({'incident_id': new_incident.id})
        return new_incident

    # ------------------------------------------------------------------
    # State machine (spec §5.3) — defense in depth: buttons carry
    # groups=..., methods additionally check.
    # ------------------------------------------------------------------
    def _check_groups(self, groups, message):
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        if not any(user.has_group(group) for group in groups):
            raise AccessError(message)

    def action_start_review(self):
        self.ensure_one()
        self._check_groups(REVIEW_GROUPS, _(
            'Only head nurses, operations managers or managers may '
            'start the review of an incident.'))
        if self.state != 'reported':
            raise UserError(_(
                'Only a reported incident can be put under review.'))
        self.write({'state': 'under_review'})
        return True

    def action_start_investigation(self):
        self.ensure_one()
        self._check_groups(REVIEW_GROUPS, _(
            'Only head nurses, operations managers or managers may '
            'start an investigation.'))
        if self.state != 'under_review':
            raise UserError(_(
                'Only an incident under review can move to '
                'investigation.'))
        if not self.investigator_id:
            raise UserError(_(
                'Assign an investigator before starting the '
                'investigation.'))
        self.write({'state': 'investigation'})
        return True

    def action_assign_actions(self):
        self.ensure_one()
        user = self.env.user
        if (not self.env.su and not user._is_admin()
                and user != self.investigator_id
                and not any(user.has_group(group)
                            for group in MANAGER_GROUPS)):
            raise AccessError(_(
                'Only the investigator or a manager may assign '
                'corrective actions.'))
        if self.state != 'investigation':
            raise UserError(_(
                'Only an incident in investigation can move to '
                'actions assigned.'))
        if not self.root_cause:
            raise UserError(_(
                'Record the root cause before assigning corrective '
                'actions.'))
        if not self.action_ids.filtered(
                lambda action: action.state in ('open', 'in_progress')):
            raise UserError(_(
                'Add at least one open corrective action before moving '
                'to actions assigned.'))
        self.write({'state': 'actions_assigned'})
        return True

    def action_close(self):
        self.ensure_one()
        self._check_groups(MANAGER_GROUPS, _(
            'Only managers may close an incident with corrective '
            'actions.'))
        if self.state != 'actions_assigned':
            raise UserError(_(
                'Only an incident with assigned actions can be closed '
                'here.'))
        self._check_close_guards()
        self._do_close()
        return True

    def action_close_minor(self):
        self.ensure_one()
        self._check_groups(MINOR_CLOSE_GROUPS, _(
            'Only head nurses or managers may fast-close a minor '
            'incident.'))
        if self.state not in ('reported', 'under_review'):
            raise UserError(_(
                'Fast-close is only available from Reported or Under '
                'Review.'))
        if self.severity not in ('1', '2'):
            raise UserError(_(
                'Fast-close is only available for severity 1-2 '
                'incidents.'))
        self._check_close_guards()
        self._do_close()
        return True

    def action_reopen(self):
        self.ensure_one()
        self._check_groups(MANAGER_GROUPS, _(
            'Only managers may reopen a closed incident.'))
        if self.state != 'closed':
            raise UserError(_('Only a closed incident can be reopened.'))
        # sudo(): the append-only write guard blocks nobody here
        # (manager check already passed) but keeps the intent explicit.
        self.write({
            'state': 'under_review',
            'closed_date': False,
            'closed_by_id': False,
        })
        return True

    def _check_close_guards(self):
        self.ensure_one()
        open_actions = self.action_ids.filtered(
            lambda action: action.state not in ('done', 'cancelled'))
        if open_actions:
            raise UserError(_(
                'This incident cannot be closed: %(count)s corrective '
                'action(s) are still open.', count=len(open_actions)))
        if self.notifiable and (not self.notified_authority
                                or not self.notified_date):
            raise UserError(_(
                'This incident is notifiable: record the notified '
                'authority and notification date before closing '
                '(compliance evidence).'))

    def _do_close(self):
        self.write({
            'state': 'closed',
            'closed_date': fields.Datetime.now(),
            'closed_by_id': self.env.uid,
        })

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_actions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Corrective Actions'),
            'res_model': 'health.incident.action',
            'view_mode': 'list,form',
            'domain': [('incident_id', '=', self.id)],
            'context': {'default_incident_id': self.id},
        }

    # ------------------------------------------------------------------
    # Business methods (spec §5.4)
    # ------------------------------------------------------------------
    def _get_facility_manager_user(self):
        """Facility-manager fallback (pattern: health_vitals
        _get_facility_manager_user / spec §2.3)."""
        self.ensure_one()
        facility = self.facility_id or (
            self.client_id.primary_facility_id if self.client_id
            else False)
        manager = facility.facility_manager_id if facility else False
        return manager.user_id if manager and manager.user_id else False

    def _schedule_severe_incident_activity(self):
        """Severe (4-5) incident → todo for the facility manager's user
        only, with the missing-manager fallback/logging pattern of
        spec §2.3."""
        self.ensure_one()
        user = self._get_facility_manager_user()
        if not user:
            _logger.warning(
                'Severe incident %s: no facility manager user, cannot '
                'create activity.', self.name)
            return
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        try:
            # sudo(): nurses/receptionists can CREATE incidents but
            # have no write ACL — the capture side effect must not
            # depend on the reporter's write access.
            self.sudo().activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Severe incident reported: %s') % self.name,
                note=_(
                    '<p><strong>Severity %(severity)s incident</strong></p>'
                    '<p>Type: %(type)s</p>'
                    '<p>Client: %(client)s</p>'
                    '<p>When: %(datetime)s</p>',
                    severity=self.severity,
                    type=self.incident_type,
                    client=self.client_id.name or _('no client'),
                    datetime=self.incident_datetime),
                date_deadline=fields.Date.context_today(self),
                user_id=user.id,
            )
        except Exception as exc:  # noqa: BLE001 — alerting must never
            # block incident capture.
            _logger.error(
                'Severe-incident activity scheduling failed for %s: %s',
                self.name, exc)

    def _trigger_fall_risk_reassessment(self):
        """Fall incident with a client → 'Reassess fall risk (Morse)'
        todo for the facility head nurse (fallback facility manager,
        then skip+log). No health.fall.risk record is auto-created —
        assessments need a human (spec §5.4)."""
        for incident in self:
            if incident.fall_risk_reassessment_triggered:
                continue
            if incident.incident_type != 'fall' or not incident.client_id:
                continue
            facility = incident.client_id.primary_facility_id
            user = facility.head_nurse_id if facility else False
            if not user:
                user = incident._get_facility_manager_user()
            # sudo() on the flag write + activity: nurses/receptionists
            # can CREATE incidents but have no write ACL — the capture
            # hook must not depend on the reporter's write access.
            if not user:
                _logger.warning(
                    'Fall incident %s: no head nurse or facility '
                    'manager user for client %s, skipping Morse '
                    'reassessment activity.',
                    incident.name, incident.client_id.name)
                incident.sudo().write(
                    {'fall_risk_reassessment_triggered': True})
                continue
            activity_type = self.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not activity_type:
                _logger.warning('Todo activity type not found')
                incident.sudo().write(
                    {'fall_risk_reassessment_triggered': True})
                continue
            last_assessment = self.env['health.fall.risk'].search(
                [('patient_id', '=', incident.client_id.id)],
                order='assessment_date desc', limit=1)
            try:
                incident.sudo().activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('Reassess fall risk (Morse): %s')
                    % incident.client_id.name,
                    note=_(
                        '<p><strong>Fall incident %(incident)s</strong> '
                        'for %(client)s.</p>'
                        '<p>Latest Morse assessment: %(last)s</p>'
                        '<p>A standing fall-risk Flag is derived for '
                        'FHIR while this incident is open.</p>',
                        incident=incident.name,
                        client=incident.client_id.name,
                        last=last_assessment.assessment_date
                        if last_assessment else _('none on record')),
                    date_deadline=fields.Date.context_today(incident),
                    user_id=user.id,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.error(
                    'Morse reassessment activity scheduling failed for '
                    'incident %s: %s', incident.name, exc)
            incident.sudo().write(
                {'fall_risk_reassessment_triggered': True})

    @api.model
    def get_register(self, date_from, date_to, domain_extra=None):
        """Aggregates for the register dashboards (plain read_group
        wrapper, spec §5.4): counts by type × severity × facility,
        notifiable count, open-actions overdue count."""
        domain = [
            ('incident_datetime', '>=', date_from),
            ('incident_datetime', '<=', date_to),
        ]
        if domain_extra:
            domain += list(domain_extra)
        by_type_severity_facility = self.read_group(
            domain, ['__count'],
            ['incident_type', 'severity', 'facility_id'], lazy=False)
        notifiable_count = self.search_count(
            domain + [('notifiable', '=', True)])
        overdue_action_count = self.env[
            'health.incident.action'].search_count([
                ('incident_id', 'in', self.search(domain).ids),
                ('state', 'in', ('open', 'in_progress')),
                ('due_date', '<', fields.Date.context_today(self)),
            ])
        return {
            'counts': [{
                'incident_type': group.get('incident_type'),
                'severity': group.get('severity'),
                'facility_id': group['facility_id'][0]
                if group.get('facility_id') else False,
                'facility_name': group['facility_id'][1]
                if group.get('facility_id') else False,
                'count': group.get('__count', 0),
            } for group in by_type_severity_facility],
            'notifiable_count': notifiable_count,
            'overdue_action_count': overdue_action_count,
        }
