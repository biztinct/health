# -*- coding: utf-8 -*-
"""Per-visit checklist item (clinical spec §1.2.4) — FHIR Task.

Compiled from care-plan activities onto field-service orders
(health.careplan._compile_tasks_for_orders). Name + instructions are
snapshots taken at compile time. Nurses tick tasks done / not-done
(with a coded reason) from the backend or the PWA.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# The not-done reasons are client-maintained now — see the
# 'task_not_done_reason' vocabulary in health.lookup.value. The PWA keeps a
# hardcoded copy in careplan-components.js for offline rendering; it falls
# back to the code, so an added reason degrades to its key rather than
# breaking the picker.


class HealthCareplanTask(models.Model):
    _name = 'health.careplan.task'
    _description = 'Care Plan Visit Task'
    _order = 'fso_id, sequence, id'
    _rec_name = 'name'

    careplan_id = fields.Many2one(
        'health.careplan', string='Care Plan', required=True,
        ondelete='cascade', index=True)
    activity_id = fields.Many2one(
        'health.careplan.activity', string='Intervention',
        required=True, ondelete='cascade', index=True)
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', required=True,
        ondelete='cascade', index=True,
        help='FHIR Task.encounter')
    client_id = fields.Many2one(
        related='careplan_id.client_id', store=True, string='Client')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Task', required=True,
        help='Snapshot of the activity name at compile time.')
    instructions = fields.Html(
        help='Snapshot of the activity instructions at compile time '
             '(immutable per-visit instructions).')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('not_done', 'Not Done'),
    ], default='pending', required=True, index=True,
        help='FHIR Task.status (pending → requested, done → '
             'completed, not_done → failed with statusReason).')
    not_done_reason_id = fields.Many2one(
        'health.lookup.value',
        string='Not Done Reason',
        domain="[('category_code', '=', 'task_not_done_reason'), ('active', '=', True)]",
        ondelete='restrict',
        help='FHIR Task.statusReason')
    not_done_note = fields.Char(
        string='Reason Detail', help='Free-text reason detail.')
    completed_by_id = fields.Many2one(
        'res.users', string='Completed By', readonly=True, copy=False)
    completed_datetime = fields.Datetime(
        string='Completed At', readonly=True, copy=False)
    is_prn = fields.Boolean(
        string='PRN', default=False, readonly=True,
        help='Added ad-hoc from the PWA.')

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints — enforce the
        # one-task-per-activity-per-visit rule with a partial unique
        # index (PRN duplicates exempt, spec §1.2.4).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_careplan_task_activity_fso_uidx
            ON health_careplan_task (activity_id, fso_id)
            WHERE is_prn IS NOT TRUE
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for task in self:
            task.catchment_province_id = (
                task.client_id._get_health_catchment_province()
                if task.client_id else False)

    # ------------------------------------------------------------------
    # Constraints (Python side of the partial-unique rule — skips
    # is_prn records; also enforced from create(), Odoo 19 gotcha).
    # ------------------------------------------------------------------
    @api.constrains('activity_id', 'fso_id', 'is_prn')
    def _check_uniq_activity_per_fso(self):
        for task in self:
            if task.is_prn:
                continue
            duplicate = self.search([
                ('id', '!=', task.id),
                ('activity_id', '=', task.activity_id.id),
                ('fso_id', '=', task.fso_id.id),
                ('is_prn', '=', False),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'This activity already has a task on this visit.'))

    @api.model_create_multi
    def create(self, vals_list):
        # Pre-check BEFORE the insert so callers get a ValidationError
        # rather than the partial unique index's IntegrityError (Odoo
        # 19 create gotcha: constraints alone are not enough).
        seen = set()
        for vals in vals_list:
            if vals.get('is_prn'):
                continue
            key = (vals.get('activity_id'), vals.get('fso_id'))
            if key in seen or (
                    key[0] and key[1] and self.search_count([
                        ('activity_id', '=', key[0]),
                        ('fso_id', '=', key[1]),
                        ('is_prn', '=', False),
                    ])):
                raise ValidationError(_(
                    'This activity already has a task on this visit.'))
            seen.add(key)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Tick actions (PWA + backend; any healthcare nurse+ may call)
    # ------------------------------------------------------------------
    def action_mark_done(self):
        for task in self:
            if task.state not in ('pending', 'not_done'):
                raise UserError(_(
                    'Task "%s" is already done.') % task.name)
            task.write({
                'state': 'done',
                'not_done_reason_id': False,
                'not_done_note': False,
                'completed_by_id': self.env.uid,
                'completed_datetime': fields.Datetime.now(),
            })
        return True

    def action_mark_not_done(self, reason=None, note=None):
        for task in self:
            vals = {
                'state': 'not_done',
                'completed_by_id': self.env.uid,
                'completed_datetime': fields.Datetime.now(),
            }
            if reason:
                # The PWA and the JSON API pass a CODE, not an id — that
                # contract is unchanged by the lookup conversion.
                vals['not_done_reason_id'] = reason if isinstance(reason, int) else \
                    self.env['health.lookup.value']._default_for(
                        'task_not_done_reason', reason)
            if note:
                vals['not_done_note'] = note
            if not vals.get('not_done_reason_id') and not task.not_done_reason_id:
                raise ValidationError(_(
                    'A reason is required to mark a task not done.'))
            task.write(vals)
        return True

    def action_reset_pending(self):
        for task in self:
            task.write({
                'state': 'pending',
                'not_done_reason_id': False,
                'not_done_note': False,
                'completed_by_id': False,
                'completed_datetime': False,
            })
        return True

    # ------------------------------------------------------------------
    # PRN (spec §1.4)
    # ------------------------------------------------------------------
    @api.model
    def add_prn_task(self, fso, activity):
        """Create an is_prn task for a PRN activity on the given
        visit (PWA add_prn endpoint)."""
        if activity.careplan_id.client_id != fso.patient_id:
            raise UserError(_(
                'This intervention belongs to a different client.'))
        if activity.careplan_id.state not in ('active', 'under_review'):
            raise UserError(_(
                'The care plan of this intervention is not active.'))
        return self.create({
            'careplan_id': activity.careplan_id.id,
            'activity_id': activity.id,
            'fso_id': fso.id,
            'sequence': activity.sequence,
            'name': activity.name,
            'instructions': activity.instructions,
            'is_prn': True,
        })

    # ------------------------------------------------------------------
    # Ops booking tab (lazy fetch — booking_visit_tasks_widget.js)
    #
    # The FSO already carries careplan_task_ids, but the ops booking arch is
    # loaded whole in one web_read, so exposing it as a <field> would tax every
    # booking open. The widget calls this only when the tab is clicked.
    # ------------------------------------------------------------------
    @api.model
    def get_booking_tasks(self, fso_id):
        """Return the care-plan visit tasks for one booking, as plain dicts."""
        if not fso_id:
            return {'tasks': []}
        tasks = self.search([('fso_id', '=', fso_id)])
        state_sel = dict(
            self._fields['state']._description_selection(self.env))
        rows = []
        for task in tasks:
            rows.append({
                'id': task.id,
                'name': task.name or '',
                'state': task.state,
                'state_label': state_sel.get(task.state, task.state),
                'is_prn': bool(task.is_prn),
                'careplan_id': task.careplan_id.id or False,
                'careplan_name': task.careplan_id.display_name or '',
                'not_done_reason': task.not_done_reason_id.code or '',
                'not_done_note': task.not_done_note or '',
                'completed_by': task.completed_by_id.display_name or '',
                'completed_datetime': _tab_dt(task, task.completed_datetime),
            })
        return {'tasks': rows}


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
