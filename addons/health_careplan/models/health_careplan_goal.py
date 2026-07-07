# -*- coding: utf-8 -*-
"""Care plan goal (clinical spec §1.2.2) — FHIR Goal.

Targets an observation type from the health_vitals catalog; progress is
computed direction-aware from the latest final observation of that type
for the client (design decision: goal progress from latest observation
vs target).
"""
from odoo import _, api, fields, models


class HealthCareplanGoal(models.Model):
    _name = 'health.careplan.goal'
    _description = 'Care Plan Goal'
    _order = 'careplan_id, sequence, id'

    careplan_id = fields.Many2one(
        'health.careplan', string='Care Plan', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Goal', required=True, translate=True,
        help='FHIR Goal.description.text')
    client_id = fields.Many2one(
        related='careplan_id.client_id', store=True,
        string='Client', help='FHIR Goal.subject')
    lifecycle_status = fields.Selection([
        ('proposed', 'Proposed'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='proposed', required=True,
        help="FHIR Goal.lifecycleStatus (codes verbatim, 'on_hold' "
             "maps to 'on-hold').")
    achievement_status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('improving', 'Improving'),
        ('worsening', 'Worsening'),
        ('achieved', 'Achieved'),
        ('not_achieved', 'Not Achieved'),
    ], help='FHIR Goal.achievementStatus')
    vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Target Observation',
        help='FHIR Goal.target.measure (LOINC via the type).')
    loinc_code = fields.Char(
        related='vitals_type_id.loinc_code', readonly=True,
        string='LOINC Code')
    baseline_value = fields.Float(
        help='Baseline measure at plan start.')
    baseline_date = fields.Date(help='When the baseline was taken.')
    target_value_min = fields.Float(
        string='Target Min',
        help='FHIR Goal.target.detailRange.low')
    target_value_max = fields.Float(
        string='Target Max',
        help='FHIR Goal.target.detailRange.high')
    target_unit = fields.Char(
        related='vitals_type_id.ucum_unit', readonly=True,
        string='Unit (UCUM)')
    due_date = fields.Date(help='FHIR Goal.target.dueDate')
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], default='medium', help='FHIR Goal.priority')
    latest_value = fields.Float(
        compute='_compute_latest_value',
        help="Most recent final observation of the goal's type for "
             'the client.')
    latest_value_date = fields.Datetime(
        compute='_compute_latest_value')
    is_on_target = fields.Boolean(
        compute='_compute_latest_value', string='On Target',
        help='Latest value inside [target min, target max] '
             '(open bounds allowed — direction-aware).')
    notes = fields.Text()

    # ------------------------------------------------------------------
    # Progress from health_vitals observations
    # ------------------------------------------------------------------
    @api.depends('client_id', 'vitals_type_id',
                 'target_value_min', 'target_value_max')
    def _compute_latest_value(self):
        Observation = self.env['health.observation']
        # One search per distinct (client, type) pair in the batch —
        # goals of the same plan sharing a measure reuse the lookup.
        latest_cache = {}
        for goal in self:
            goal.latest_value = 0.0
            goal.latest_value_date = False
            goal.is_on_target = False
            if not goal.client_id or not goal.vitals_type_id:
                continue
            key = (goal.client_id.id, goal.vitals_type_id.id)
            if key not in latest_cache:
                latest_cache[key] = Observation.search([
                    ('client_id', '=', key[0]),
                    ('vitals_type_id', '=', key[1]),
                    ('state', '=', 'final'),
                ], order='effective_datetime desc, id desc', limit=1)
            observation = latest_cache[key]
            if not observation:
                continue
            value = observation.value_quantity
            goal.latest_value = value
            goal.latest_value_date = observation.effective_datetime
            # Direction-aware: only the bounds that are set constrain
            # the goal (min-only = "raise above", max-only = "lower
            # below", both = "keep inside the range").
            on_target = True
            if goal.target_value_min and value < goal.target_value_min:
                on_target = False
            if goal.target_value_max and value > goal.target_value_max:
                on_target = False
            if not goal.target_value_min and not goal.target_value_max:
                on_target = False
            goal.is_on_target = on_target
