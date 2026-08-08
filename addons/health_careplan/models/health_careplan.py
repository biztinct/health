# -*- coding: utf-8 -*-
"""Care plan header (clinical spec §1.2.1).

FHIR CarePlan: status draft/active/completed/revoked ('under_review' is
a local sub-state of active). Holds the goals (FHIR Goal) and the
interventions (FHIR CarePlan.activity.detail) that compile into
per-visit task checklists (FHIR Task) on field-service orders.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Frequency → rolling-window unit length in days (spec §1.4).
FREQUENCY_PERIOD_DAYS = {
    'daily': 1,
    'weekly': 7,
    'monthly': 30,
}

# Groups allowed to drive the plan state machine (spec §1.3).
CLINICAL_GROUPS = (
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_doctor',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)
MANAGER_GROUPS = (
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)


class HealthCareplan(models.Model):
    _name = 'health.careplan'
    _description = 'Care Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'health.lifecycle.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference', required=True, readonly=True, copy=False,
        default=lambda self: _('New'),
        help='Plan reference (sequence health.careplan, prefix CP).')
    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('is_patient', '=', True)], ondelete='restrict',
        index=True, tracking=True,
        help='FHIR CarePlan.subject')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('under_review', 'Under Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True,
        help="FHIR CarePlan.status (draft/active/completed/revoked; "
             "'under_review' is a local sub-state of active).")
    category = fields.Selection([
        ('home_care', 'Home Care'),
        ('post_acute', 'Post-Acute'),
        ('chronic', 'Chronic Disease'),
        ('palliative', 'Palliative'),
        ('rehabilitation', 'Rehabilitation'),
        ('other', 'Other'),
    ], default='home_care', tracking=True,
        help='FHIR CarePlan.category')
    title = fields.Char(
        translate=True, help='Human title, FHIR CarePlan.title')
    description = fields.Html(
        translate=True, help='FHIR CarePlan.description')
    author_id = fields.Many2one(
        'res.users', string='Author',
        default=lambda self: self.env.uid, readonly=True, tracking=True,
        help='FHIR CarePlan.author')
    facility_id = fields.Many2one(
        'health.facility', string='Facility', tracking=True,
        help='Managing facility (defaults from the client'
             "'s primary facility).")
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    protocol_id = fields.Many2one(
        'health.clinical.protocol', string='Based on Protocol',
        help='FHIR CarePlan.instantiatesCanonical → PlanDefinition')
    period_start = fields.Date(
        string='Start Date', required=True,
        default=fields.Date.context_today, tracking=True,
        help='FHIR CarePlan.period.start')
    period_end = fields.Date(
        string='End Date', tracking=True,
        help='FHIR CarePlan.period.end')
    review_cycle_days = fields.Integer(
        string='Review Cycle (days)', default=90, required=True,
        help='Review cadence.')
    next_review_date = fields.Date(
        compute='_compute_next_review_date', store=True, readonly=True,
        help='Drives the review cron.')
    last_review_date = fields.Date(
        readonly=True, copy=False,
        help='Set by Confirm Review.')
    version = fields.Integer(
        default=1, readonly=True, copy=False,
        help='Bumped on each confirmed review.')
    goal_ids = fields.One2many(
        'health.careplan.goal', 'careplan_id', string='Goals')
    careplan_activity_ids = fields.One2many(
        'health.careplan.activity', 'careplan_id',
        string='Interventions')
    task_ids = fields.One2many(
        'health.careplan.task', 'careplan_id', string='Visit Tasks',
        copy=False)
    goal_count = fields.Integer(compute='_compute_counts')
    activity_count = fields.Integer(compute='_compute_counts')
    task_count = fields.Integer(compute='_compute_counts')
    adherence_rate = fields.Float(
        readonly=True, copy=False, aggregator='avg',
        help='Done tasks / expected tasks, trailing 30 days '
             '(written by the drift cron, not a @depends compute).')
    drift_flag = fields.Boolean(
        string='Drift', readonly=True, tracking=True, copy=False,
        help='Set by the drift-detection cron when adherence falls '
             'below the configured threshold.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # Kept for documentation parity with the spec — Odoo 19 no longer
    # materializes _sql_constraints; both checks are enforced by the
    # Python constraints below (also called from create()).
    _sql_constraints = [
        ('period_check',
         'CHECK (period_end IS NULL OR period_end >= period_start)',
         'End date must be after start date.'),
        ('review_cycle_positive',
         'CHECK (review_cycle_days > 0)',
         'Review cycle must be positive.'),
    ]

    # ------------------------------------------------------------------
    # Computes / onchange
    # ------------------------------------------------------------------
    @api.depends('name', 'client_id.name')
    def _compute_display_name(self):
        for plan in self:
            if plan.client_id:
                plan.display_name = '%s (%s)' % (
                    plan.client_id.name, plan.name or _('New'))
            else:
                plan.display_name = plan.name or _('New')

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for plan in self:
            plan.catchment_province_id = (
                plan.client_id._get_health_catchment_province()
                if plan.client_id else False)

    @api.depends('period_start', 'last_review_date', 'review_cycle_days')
    def _compute_next_review_date(self):
        for plan in self:
            base = plan.last_review_date or plan.period_start
            plan.next_review_date = (
                base + timedelta(days=plan.review_cycle_days)
                if base and plan.review_cycle_days else False)

    @api.depends('goal_ids', 'careplan_activity_ids', 'task_ids')
    def _compute_counts(self):
        for plan in self:
            plan.goal_count = len(plan.goal_ids)
            plan.activity_count = len(plan.careplan_activity_ids)
            plan.task_count = len(plan.task_ids)

    @api.onchange('client_id')
    def _onchange_client_id(self):
        if self.client_id and self.client_id.primary_facility_id:
            self.facility_id = self.client_id.primary_facility_id

    # ------------------------------------------------------------------
    # Constraints (also enforced from create() — Odoo 19 gotcha:
    # @api.constrains does not fire on create when none of the
    # constrained fields are in vals).
    # ------------------------------------------------------------------
    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        for plan in self:
            if (plan.period_end and plan.period_start
                    and plan.period_end < plan.period_start):
                raise ValidationError(
                    _('End date must be after start date.'))

    @api.constrains('review_cycle_days')
    def _check_review_cycle(self):
        for plan in self:
            if plan.review_cycle_days <= 0:
                raise ValidationError(
                    _('Review cycle must be positive.'))

    @api.constrains('state', 'client_id', 'category')
    def _check_one_active_per_category(self):
        for plan in self:
            if plan.state not in ('active', 'under_review'):
                continue
            duplicate = self.search([
                ('id', '!=', plan.id),
                ('client_id', '=', plan.client_id.id),
                ('category', '=', plan.category),
                ('state', 'in', ('active', 'under_review')),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Client %(client)s already has an active '
                    '%(category)s care plan (%(plan)s). Complete or '
                    'cancel it first.',
                    client=plan.client_id.name,
                    category=dict(plan._fields['category']
                                  ._description_selection(plan.env)
                                  ).get(plan.category, plan.category),
                    plan=duplicate.name))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.careplan') or _('New')
        plans = super().create(vals_list)
        # Constraints re-run explicitly (Odoo 19 create gotcha).
        plans._check_period()
        plans._check_review_cycle()
        plans._check_one_active_per_category()
        return plans

    def copy(self, default=None):
        # Odoo 19 gotcha: copy() does not reliably duplicate One2many
        # lines — copy goals and activities explicitly, with a guard.
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('state', 'draft')
        new_plan = super().copy(default)
        goal_map = {}
        if not new_plan.goal_ids:
            for goal in self.goal_ids:
                goal_map[goal.id] = goal.copy(
                    {'careplan_id': new_plan.id})
        if not new_plan.careplan_activity_ids:
            for activity in self.careplan_activity_ids:
                new_activity = activity.copy(
                    {'careplan_id': new_plan.id, 'goal_ids': False})
                if goal_map:
                    new_activity.goal_ids = [
                        (6, 0, [goal_map[goal.id].id
                                for goal in activity.goal_ids
                                if goal.id in goal_map])]
        return new_plan

    # ------------------------------------------------------------------
    # State machine (spec §1.3) — defense in depth: buttons carry
    # groups=..., methods additionally check.
    # ------------------------------------------------------------------
    def _check_state_change_allowed(self, manager_only=False):
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        groups = MANAGER_GROUPS if manager_only else CLINICAL_GROUPS
        if not any(user.has_group(group) for group in groups):
            raise AccessError(_(
                'Only head nurses, doctors or managers may change the '
                'state of a care plan.') if not manager_only else _(
                'Only managers may reset a cancelled care plan.'))

    def action_activate(self):
        self.ensure_one()
        self._check_state_change_allowed()
        if self.state != 'draft':
            raise UserError(_(
                'Only a draft care plan can be activated.'))
        if not self.goal_ids:
            raise UserError(_(
                'Add at least one goal before activating the plan.'))
        if not self.careplan_activity_ids:
            raise UserError(_(
                'Add at least one intervention before activating the '
                'plan.'))
        if not self.period_start:
            raise UserError(_(
                'Set the plan start date before activating.'))
        self.write({'state': 'active'})
        return True

    def action_start_review(self):
        self.ensure_one()
        self._check_state_change_allowed()
        if self.state != 'active':
            raise UserError(_(
                'Only an active care plan can be put under review.'))
        self.write({'state': 'under_review'})
        return True

    def action_confirm_review(self):
        self.ensure_one()
        self._check_state_change_allowed()
        if self.state != 'under_review':
            raise UserError(_(
                'Only a care plan under review can be confirmed.'))
        self.write({
            'state': 'active',
            'version': self.version + 1,
            'last_review_date': fields.Date.context_today(self),
        })
        return True

    def action_complete(self):
        self.ensure_one()
        self._check_state_change_allowed()
        if self.state not in ('active', 'under_review'):
            raise UserError(_(
                'Only an active care plan can be completed.'))
        vals = {'state': 'completed'}
        if not self.period_end:
            vals['period_end'] = fields.Date.context_today(self)
        self.write(vals)
        return True

    def action_cancel(self):
        self.ensure_one()
        self._check_state_change_allowed()
        if self.state not in ('draft', 'active', 'under_review'):
            raise UserError(_(
                'This care plan cannot be cancelled from its current '
                'state.'))
        # Pending tasks on future / not-yet-delivered visits go away.
        # sudo(): the access matrix grants unlink to owner only, but
        # removing system-compiled pending snapshots is part of the
        # cancel transition (never touches ticked tasks).
        stale = self.task_ids.filtered(
            lambda task: task.state == 'pending'
            and task.fso_id.state in ('draft', 'confirmed', 'assigned'))
        stale.sudo().unlink()
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self.ensure_one()
        self._check_state_change_allowed(manager_only=True)
        if self.state != 'cancelled':
            raise UserError(_(
                'Only a cancelled care plan can be reset to draft.'))
        self.write({'state': 'draft'})
        return True

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visit Tasks'),
            'res_model': 'health.careplan.task',
            'view_mode': 'list,form',
            'domain': [('careplan_id', '=', self.id)],
            'context': {'default_careplan_id': self.id},
        }

    def action_view_goals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goals'),
            'res_model': 'health.careplan.goal',
            'view_mode': 'list',
            'domain': [('careplan_id', '=', self.id)],
            'context': {'default_careplan_id': self.id},
        }

    def action_view_activities(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Interventions'),
            'res_model': 'health.careplan.activity',
            'view_mode': 'list',
            'domain': [('careplan_id', '=', self.id)],
            'context': {'default_careplan_id': self.id},
        }

    def action_view_client(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client'),
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': self.client_id.id,
        }

    # ------------------------------------------------------------------
    # Task compilation (spec §1.4 + binding design decision: wrapped in
    # try/except — compilation must NEVER block a booking; idempotent).
    # ------------------------------------------------------------------
    @api.model
    def _compile_tasks_for_orders(self, orders):
        for order in orders:
            try:
                self._compile_tasks_for_order(order)
            except Exception:  # noqa: BLE001 — never block the booking
                _logger.exception(
                    'Care plan task compilation failed for order %s — '
                    'booking not blocked.', order.id)
        return True

    @api.model
    def _compile_tasks_for_order(self, order):
        Task = self.env['health.careplan.task']
        if (order.state not in ('confirmed', 'assigned')
                or not order.patient_id):
            return
        visit_date = order.scheduled_date or (
            order.scheduled_datetime and order.scheduled_datetime.date())
        if not visit_date:
            return
        plans = self.search([
            ('state', '=', 'active'),
            ('client_id', '=', order.patient_id.id),
            ('period_start', '<=', visit_date),
            '|', ('period_end', '=', False),
            ('period_end', '>=', visit_date),
        ])
        valid_activities = self.env['health.careplan.activity']
        for plan in plans:
            for activity in plan.careplan_activity_ids:
                if activity.status not in ('scheduled', 'in_progress'):
                    continue
                if not activity._matches_visit(order, visit_date):
                    continue
                valid_activities |= activity
                if activity.frequency == 'prn':
                    continue  # never auto-compiled
                existing = Task.search([
                    ('activity_id', '=', activity.id),
                    ('fso_id', '=', order.id),
                    ('is_prn', '=', False),
                ], limit=1)
                if existing:
                    continue  # idempotent re-run
                if activity.frequency in FREQUENCY_PERIOD_DAYS:
                    period_days = (
                        max(activity.frequency_interval, 1)
                        * FREQUENCY_PERIOD_DAYS[activity.frequency])
                    window_start = visit_date - timedelta(
                        days=period_days - 1)
                    already = Task.search_count([
                        ('activity_id', '=', activity.id),
                        ('is_prn', '=', False),
                        ('state', '!=', 'not_done'),
                        ('fso_id.scheduled_date', '>=', window_start),
                        ('fso_id.scheduled_date', '<=', visit_date),
                    ])
                    if already >= max(activity.times_per_period, 1):
                        continue
                Task.create({
                    'careplan_id': plan.id,
                    'activity_id': activity.id,
                    'fso_id': order.id,
                    'sequence': activity.sequence,
                    # Snapshot at compile time (immutable per-visit).
                    'name': activity.name,
                    'instructions': activity.instructions,
                })
        # Cleanup: pending auto-compiled tasks whose FSO moved out of
        # the plan window or whose activity was cancelled/filtered out.
        # sudo(): unlink is owner-only in the access matrix, but this
        # only removes system-compiled pending snapshots (never ticked
        # tasks) and runs inside the guarded compile hook.
        stale_domain = [
            ('fso_id', '=', order.id),
            ('state', '=', 'pending'),
            ('is_prn', '=', False),
        ]
        if valid_activities:
            # NB: ('activity_id', 'not in', [0]) silently matches NOTHING
            # in Odoo 19 (falsy sentinel mis-optimized) — only add the
            # criterion when there are activities to exclude.
            stale_domain.append(
                ('activity_id', 'not in', valid_activities.ids))
        stale = Task.search(stale_domain)
        if stale:
            stale.sudo().unlink()

    # ------------------------------------------------------------------
    # Crons (spec §1.4)
    # ------------------------------------------------------------------
    @api.model
    def _cron_careplan_reviews(self):
        """Daily: plans whose review is due flip to 'under_review' and
        the author gets a to-do activity."""
        today = fields.Date.context_today(self)
        plans = self.search([
            ('state', '=', 'active'),
            ('next_review_date', '!=', False),
            ('next_review_date', '<=', today),
        ])
        for plan in plans:
            plan.action_start_review()
            plan._schedule_author_activity(_(
                'Care plan review due: %s') % plan.client_id.name)
        return True

    @api.model
    def _cron_careplan_drift(self):
        """Weekly: trailing-30-day adherence per plan; below threshold
        → drift flag + author activity (the drift-detection hook)."""
        threshold = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'health_careplan.drift_threshold') or 0.8)
        window_end = fields.Date.context_today(self)
        window_start = window_end - timedelta(days=30)
        plans = self.search([
            ('state', 'in', ('active', 'under_review')),
        ])
        for plan in plans:
            rate = self._compute_drift(plan, window_start, window_end)
            drifted = rate < threshold
            plan.write({
                'adherence_rate': rate,
                'drift_flag': drifted,
            })
            if drifted:
                plan._schedule_author_activity(_(
                    'Care plan drift detected (%(rate).0f%%): '
                    '%(client)s',
                    rate=rate * 100.0,
                    client=plan.client_id.name))
        return True

    @api.model
    def _compute_drift(self, plan, window_start, window_end):
        """Overridable drift computation: done / expected tasks on
        delivered visits inside the window (1.0 when nothing was
        expected)."""
        expected = plan.task_ids.filtered(
            lambda task: task.fso_id.state in (
                'completed', 'completed_pending_invoice', 'closed')
            and task.fso_id.scheduled_date
            and window_start <= task.fso_id.scheduled_date <= window_end)
        if not expected:
            return 1.0
        done = expected.filtered(lambda task: task.state == 'done')
        return len(done) / len(expected)

    def _schedule_author_activity(self, summary):
        self.ensure_one()
        if not self.author_id:
            return
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        try:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                summary=summary,
                date_deadline=fields.Date.context_today(self)
                + timedelta(days=1),
                user_id=self.author_id.id,
            )
        except Exception as exc:  # noqa: BLE001 — alerting must never
            # break the cron loop for the remaining plans.
            _logger.error(
                'Care plan activity scheduling failed for plan %s: %s',
                self.id, exc)

    # ------------------------------------------------------------------
    # Ops client-profile tab (lazy fetch — client_careplans_widget.js)
    #
    # Not an x2many on the ops arch: that arch is loaded whole by the single
    # web_read on client-page open, so a <field> list would cost every open.
    # ------------------------------------------------------------------
    @api.model
    def get_client_careplans(self, patient_id):
        """Return this patient's care plans as plain dicts for the tab."""
        if not patient_id:
            return {'careplans': []}
        plans = self.search([('client_id', '=', patient_id)], limit=50)
        state_sel = dict(
            self._fields['state']._description_selection(self.env))
        cat_sel = dict(
            self._fields['category']._description_selection(self.env))
        rows = []
        for plan in plans:
            rows.append({
                'id': plan.id,
                'title': plan.title or plan.name or '',
                'state': plan.state,
                'state_label': state_sel.get(plan.state, plan.state),
                'category_label': cat_sel.get(plan.category, plan.category or ''),
                'period_start': _tab_date(plan.period_start),
                'period_end': _tab_date(plan.period_end),
                'next_review_date': _tab_date(plan.next_review_date),
                'goal_count': plan.goal_count,
                'task_count': plan.task_count,
                'adherence_rate': round(plan.adherence_rate or 0.0, 1),
                'drift_flag': bool(plan.drift_flag),
            })
        return {'careplans': rows}


# ---------------------------------------------------------------------------
# Display formatting for the ops record tabs.
#
# Stored datetimes are naive UTC; context_timestamp converts to the user's
# timezone (Asia/Ho_Chi_Minh here) so a tab does not show a visit as 7 hours
# earlier than every other surface. Raw ``to_string`` output ("2026-07-08
# 09:17:30") was also the only place in the ops forms not using the
# "Aug 21, 4:30 PM" house format.
# ---------------------------------------------------------------------------
def _tab_dt(record, value):
    """Naive-UTC datetime -> user-timezone display string."""
    if not value:
        return ''
    return fields.Datetime.context_timestamp(record, value).strftime(
        '%b %d, %Y %I:%M %p')


def _tab_date(value):
    """Date -> display string (dates carry no timezone)."""
    return value.strftime('%b %d, %Y') if value else ''
