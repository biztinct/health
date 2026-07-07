# -*- coding: utf-8 -*-
"""Incident corrective action (clinical spec §5.2.2).

FHIR: local extension / Task (owner = assignee,
restriction.period.end = due_date; open → requested,
in_progress → in-progress, done → completed, cancelled → cancelled).

NB (Odoo 19 gotcha): the One2many on health.incident is `action_ids`
per the spec — never `activity_ids`, which would shadow the
mail.activity.mixin field and break registry load.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HealthIncidentAction(models.Model):
    _name = 'health.incident.action'
    _description = 'Incident Corrective Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date, id'

    incident_id = fields.Many2one(
        'health.incident', string='Incident', required=True,
        ondelete='cascade', index=True)
    name = fields.Char(string='Action', required=True,
                       help='Action summary.')
    description = fields.Text(help='Detail.')
    assignee_id = fields.Many2one(
        'res.users', string='Assignee', required=True, tracking=True,
        help='Owner — gets a to-do activity on create with the due '
             'date as deadline.')
    due_date = fields.Date(required=True, tracking=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='open', required=True, tracking=True)
    completed_date = fields.Date(readonly=True, copy=False,
                                 help='Set by Mark Done.')
    effectiveness_review = fields.Text(
        help='Post-completion review.')
    catchment_province_id = fields.Many2one(
        related='incident_id.catchment_province_id', store=True,
        string='Catchment Area',
        help='Catchment area used for filtering and access control')

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        actions = super().create(vals_list)
        for action in actions:
            action._schedule_assignee_activity()
        return actions

    def _schedule_assignee_activity(self):
        self.ensure_one()
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        try:
            # sudo(): the creator (e.g. the investigator) may lack
            # write access on the action under the catchment write
            # rules — the deadline activity must be scheduled anyway.
            self.sudo().activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Corrective action due: %s') % self.name,
                note=_(
                    '<p>Incident: %(incident)s</p><p>%(detail)s</p>',
                    incident=self.incident_id.display_name,
                    detail=self.description or self.name),
                date_deadline=self.due_date,
                user_id=self.assignee_id.id,
            )
        except Exception as exc:  # noqa: BLE001 — activity scheduling
            # must never block corrective-action capture.
            _logger.error(
                'Corrective-action activity scheduling failed for '
                'action %s: %s', self.id, exc)

    # ------------------------------------------------------------------
    # Buttons (spec §5.2.2)
    # ------------------------------------------------------------------
    def action_start(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Only an open action can be started.'))
        self.write({'state': 'in_progress'})
        return True

    def action_done(self):
        self.ensure_one()
        if self.state not in ('open', 'in_progress'):
            raise UserError(_(
                'Only an open or in-progress action can be marked '
                'done.'))
        self.write({
            'state': 'done',
            'completed_date': fields.Date.context_today(self),
        })
        self._feedback_todo_activities()
        return True

    def action_cancel_action(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('A completed action cannot be cancelled.'))
        self.write({'state': 'cancelled'})
        self._feedback_todo_activities()
        return True

    def _feedback_todo_activities(self):
        """Mark the assignee's deadline activity done (spec: action_done
        marks the mail activity done)."""
        self.ensure_one()
        try:
            self.activity_feedback(
                ['mail.mail_activity_data_todo'],
                feedback=_('Corrective action %s.') % dict(
                    self._fields['state']._description_selection(
                        self.env)).get(self.state, self.state))
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                'Activity feedback failed for corrective action %s: %s',
                self.id, exc)
