# -*- coding: utf-8 -*-
"""Care plan intervention / activity (clinical spec §1.2.3).

FHIR CarePlan.activity.detail. The frequency rule + visit filter drive
the per-visit task compilation (§1.4). ``visit_filter`` is matched
against the Selection-based ``health.fieldservice.order.service_type``
('all' always matches; 'home_visit'/'clinic_visit' must equal).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HealthCareplanActivity(models.Model):
    _name = 'health.careplan.activity'
    _description = 'Care Plan Intervention/Activity'
    _order = 'careplan_id, sequence, id'

    careplan_id = fields.Many2one(
        'health.careplan', string='Care Plan', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Intervention', required=True, translate=True,
        help='Activity label, FHIR Task.code.text')
    service_type_id = fields.Many2one(
        'health.service.type', string='Service Type',
        help='Informational service linkage; FHIR '
             'CarePlan.activity.detail.code')
    goal_ids = fields.Many2many(
        'health.careplan.goal', 'careplan_activity_goal_rel',
        'activity_id', 'goal_id', string='Goals',
        domain="[('careplan_id', '=', careplan_id)]",
        help='FHIR activity.detail.goal')
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='scheduled', required=True,
        help="FHIR activity.detail.status ('not_started' maps to "
             "'not-started').")
    frequency = fields.Selection([
        ('every_visit', 'Every Visit'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('prn', 'PRN / As Needed'),
    ], default='every_visit', required=True,
        help='Task compilation rule (spec §1.4).')
    frequency_interval = fields.Integer(
        default=1,
        help='Every N days/weeks/months (ignored for every_visit / '
             'prn). FHIR Timing.repeat.period')
    times_per_period = fields.Integer(
        default=1, help='FHIR Timing.repeat.frequency')
    visit_filter = fields.Selection([
        ('all', 'All Visits'),
        ('home_visit', 'Home Visits Only'),
        ('clinic_visit', 'Clinic Visits Only'),
    ], default='all',
        help='Which visits receive tasks (matched against the FSO '
             'service_type Selection).')
    instructions = fields.Html(
        translate=True,
        help='Nurse-facing instructions; FHIR '
             'activity.detail.description')
    duration_minutes = fields.Integer(help='Planning aid.')
    start_date = fields.Date(
        help='Activity window start inside the plan period.')
    end_date = fields.Date(
        help='Activity window end inside the plan period.')
    client_id = fields.Many2one(
        related='careplan_id.client_id', store=True, string='Client')

    # ------------------------------------------------------------------
    # Constraints (also enforced from create() — Odoo 19 gotcha).
    # ------------------------------------------------------------------
    @api.constrains('frequency_interval', 'times_per_period')
    def _check_frequency_values(self):
        for activity in self:
            if activity.frequency_interval < 1:
                raise ValidationError(_(
                    'Frequency interval must be at least 1.'))
            if activity.times_per_period < 1:
                raise ValidationError(_(
                    'Times per period must be at least 1.'))

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        activities._check_frequency_values()
        return activities

    # ------------------------------------------------------------------
    # Compilation helpers
    # ------------------------------------------------------------------
    def _matches_visit(self, order, visit_date):
        """Visit filter + activity window check for the compiler
        (spec §1.4). 'all' always matches; 'home_visit'/'clinic_visit'
        must equal the FSO Selection value."""
        self.ensure_one()
        if (self.visit_filter != 'all'
                and order.service_type != self.visit_filter):
            return False
        if self.start_date and visit_date < self.start_date:
            return False
        if self.end_date and visit_date > self.end_date:
            return False
        return True
