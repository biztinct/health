# -*- coding: utf-8 -*-
"""CarePlan ← health.careplan, Goal ← health.careplan.goal,
Task ← health.careplan.task (health_careplan)."""

from .base import (
    FHIRSerializer, FHIRBadRequest, fhir_date, fhir_instant, strip_html,
    date_param_domain, LOINC_SYSTEM, UCUM_SYSTEM,
)
from . import fso_common

CAREPLAN_CATEGORY_SYSTEM = 'urn:health19:careplan-category'
NOT_DONE_REASON_SYSTEM = 'urn:health19:not-done-reason'
GOAL_ACHIEVEMENT_SYSTEM = (
    'http://terminology.hl7.org/CodeSystem/goal-achievement')
GOAL_PRIORITY_SYSTEM = 'http://terminology.hl7.org/CodeSystem/goal-priority'


def _loinc_concept(vtype):
    """LOINC CodeableConcept for a vitals type (Goal.target.measure)."""
    coding = {'system': LOINC_SYSTEM}
    if vtype.loinc_code:
        coding['code'] = vtype.loinc_code
    if vtype.name:
        coding['display'] = vtype.name
    return {'coding': [coding], 'text': vtype.name or ''}


def _reverse_token_domain(fhir_to_states, field='state'):
    """Build a token search callable from a {fhir_status: [states]} map."""
    def _domain(value):
        states = fhir_to_states.get(value)
        if not states:
            raise FHIRBadRequest("Unknown status token: %r" % value)
        return [(field, 'in', states)]
    return _domain


# ---------------------------------------------------------------------------
# CarePlan
# ---------------------------------------------------------------------------

_CAREPLAN_STATUS = {
    'draft': 'draft',
    'active': 'active',
    'under_review': 'active',
    'completed': 'completed',
    'cancelled': 'revoked',
}
_CAREPLAN_STATUS_SEARCH = {
    'draft': ['draft'],
    'active': ['active', 'under_review'],
    'completed': ['completed'],
    'revoked': ['cancelled'],
}
_ACTIVITY_STATUS = {
    'not_started': 'not-started',
    'scheduled': 'scheduled',
    'in_progress': 'in-progress',
    'completed': 'completed',
    'cancelled': 'cancelled',
}


class CarePlanSerializer(FHIRSerializer):
    resource_type = 'CarePlan'
    odoo_model = 'health.careplan'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'status': {'type': 'token',
                   'domain': _reverse_token_domain(_CAREPLAN_STATUS_SEARCH)},
        'date': {'type': 'date', 'domain': date_param_domain('period_start')},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, plan):
        resource = {
            'resourceType': 'CarePlan',
            'id': str(plan.id),
            'meta': self.meta(plan),
            'status': _CAREPLAN_STATUS.get(plan.state, 'active'),
            'intent': 'plan',
            'subject': self.reference('Patient', plan.client_id.id,
                                      display=plan.client_id.name),
        }
        if plan.title:
            resource['title'] = plan.title
        if plan.description:
            description = strip_html(plan.description)
            if description:
                resource['description'] = description
        if plan.category:
            resource['category'] = [{
                'coding': [{
                    'system': CAREPLAN_CATEGORY_SYSTEM,
                    'code': plan.category,
                }],
            }]
        period = {}
        if plan.period_start:
            period['start'] = fhir_date(plan.period_start)
        if plan.period_end:
            period['end'] = fhir_date(plan.period_end)
        if period:
            resource['period'] = period
        if plan.author_id:
            resource['author'] = {'display': plan.author_id.name}
        if plan.goal_ids:
            resource['goal'] = [
                self.reference('Goal', goal.id) for goal in plan.goal_ids]
        activities = []
        for activity in plan.careplan_activity_ids:
            detail = {
                'status': _ACTIVITY_STATUS.get(activity.status, 'scheduled'),
                'code': {'text': activity.name or ''},
            }
            description = strip_html(activity.instructions)
            if description:
                detail['description'] = description
            activities.append({'detail': detail})
        if activities:
            resource['activity'] = activities
        return resource


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------

_GOAL_LIFECYCLE = {
    'proposed': 'proposed',
    'active': 'active',
    'on_hold': 'on-hold',
    'completed': 'completed',
    'cancelled': 'cancelled',
}
_GOAL_LIFECYCLE_SEARCH = {v: [k] for k, v in _GOAL_LIFECYCLE.items()}
_GOAL_ACHIEVEMENT = {
    'in_progress': 'in-progress',
    'improving': 'improving',
    'worsening': 'worsening',
    'achieved': 'achieved',
    'not_achieved': 'not-achieved',
}
_GOAL_PRIORITY = {
    'high': 'high-priority',
    'medium': 'medium-priority',
    'low': 'low-priority',
}


class GoalSerializer(FHIRSerializer):
    resource_type = 'Goal'
    odoo_model = 'health.careplan.goal'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain(
                        'careplan_id.client_id')},
        'lifecycle-status': {'type': 'token',
                             'domain': _reverse_token_domain(
                                 _GOAL_LIFECYCLE_SEARCH,
                                 field='lifecycle_status')},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('careplan_id.client_id').ids

    def _bound(self, value, vtype):
        quantity = {'value': value}
        if vtype.unit_display:
            quantity['unit'] = vtype.unit_display
        if vtype.ucum_unit:
            quantity['system'] = UCUM_SYSTEM
            quantity['code'] = vtype.ucum_unit
        return quantity

    def to_fhir(self, goal):
        resource = {
            'resourceType': 'Goal',
            'id': str(goal.id),
            'meta': self.meta(goal),
            'lifecycleStatus': _GOAL_LIFECYCLE.get(
                goal.lifecycle_status, 'proposed'),
            'description': {'text': goal.name or ''},
        }
        if goal.client_id:
            resource['subject'] = self.reference(
                'Patient', goal.client_id.id, display=goal.client_id.name)
        if goal.achievement_status:
            resource['achievementStatus'] = {
                'coding': [{
                    'system': GOAL_ACHIEVEMENT_SYSTEM,
                    'code': _GOAL_ACHIEVEMENT.get(goal.achievement_status),
                }],
            }
        if goal.priority and goal.priority in _GOAL_PRIORITY:
            resource['priority'] = {
                'coding': [{
                    'system': GOAL_PRIORITY_SYSTEM,
                    'code': _GOAL_PRIORITY[goal.priority],
                }],
            }
        if goal.vitals_type_id:
            target = {'measure': _loinc_concept(goal.vitals_type_id)}
            detail_range = {}
            if goal.target_value_min:
                detail_range['low'] = self._bound(
                    goal.target_value_min, goal.vitals_type_id)
            if goal.target_value_max:
                detail_range['high'] = self._bound(
                    goal.target_value_max, goal.vitals_type_id)
            if detail_range:
                target['detailRange'] = detail_range
            if goal.due_date:
                target['dueDate'] = fhir_date(goal.due_date)
            resource['target'] = [target]
        return resource


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

_TASK_STATUS = {
    'pending': 'requested',
    'done': 'completed',
    'not_done': 'failed',
}
_TASK_STATUS_SEARCH = {v: [k] for k, v in _TASK_STATUS.items()}


class TaskSerializer(FHIRSerializer):
    resource_type = 'Task'
    odoo_model = 'health.careplan.task'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain(
                        'careplan_id.client_id')},
        'status': {'type': 'token',
                   'domain': _reverse_token_domain(_TASK_STATUS_SEARCH)},
        'encounter': {'type': 'reference',
                      'domain': lambda v: [(
                          'fso_id', '=',
                          fso_common.parse_reference_value(v, 'Encounter'))]},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('careplan_id.client_id').ids

    def to_fhir(self, task):
        resource = {
            'resourceType': 'Task',
            'id': str(task.id),
            'meta': self.meta(task),
            'status': _TASK_STATUS.get(task.state, 'requested'),
            'intent': 'order',
            'code': {'text': task.name or ''},
        }
        if task.state == 'not_done' and task.not_done_reason:
            label = dict(task._fields['not_done_reason']
                         ._description_selection(task.env)).get(
                             task.not_done_reason)
            resource['statusReason'] = {
                'coding': [{
                    'system': NOT_DONE_REASON_SYSTEM,
                    'code': task.not_done_reason,
                }],
                'text': task.not_done_note or label or '',
            }
        description = strip_html(task.instructions)
        if description:
            resource['description'] = description
        if task.client_id:
            resource['for'] = self.reference(
                'Patient', task.client_id.id, display=task.client_id.name)
        encounter = fso_common.encounter_ref_if_qualifies(self, task.fso_id)
        if encounter:
            resource['encounter'] = encounter
        if task.completed_datetime:
            resource['executionPeriod'] = {
                'end': fhir_instant(task.completed_datetime)}
        if task.completed_by_id:
            resource['owner'] = {'display': task.completed_by_id.name}
        if task.careplan_id:
            resource['basedOn'] = [
                self.reference('CarePlan', task.careplan_id.id)]
        return resource
