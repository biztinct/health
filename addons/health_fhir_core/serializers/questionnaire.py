# -*- coding: utf-8 -*-
"""Questionnaire ← health.form.template,
QuestionnaireResponse ← health.form.instance (health_forms).

QuestionnaireResponse ``item.linkId`` values are the schema question keys,
kept byte-identical to the Questionnaire ``item.linkId`` so responses
correlate with their questionnaire. Responses render from the pinned
``schema_snapshot`` (never the live template)."""

from .base import (
    FHIRSerializer, FHIRBadRequest, fhir_date, fhir_instant, strip_html,
    date_param_domain, parse_reference_value, token_domain,
    token_status_domain,
)
from . import fso_common

# health.form.question.question_type → FHIR Questionnaire.item.type.
# 'number' has no integer/decimal discriminator on the question model, so it
# maps to 'decimal' (which validates integer values too).
_ITEM_TYPE = {
    'number': 'decimal',
    'selection': 'choice',
    'multiselect': 'choice',
    'text': 'string',
    'boolean': 'boolean',
    'date': 'date',
    'photo': 'attachment',
    'signature': 'attachment',
    'computed_score': 'decimal',
}


# ---------------------------------------------------------------------------
# Questionnaire
# ---------------------------------------------------------------------------

_TEMPLATE_STATUS = {'published': 'active', 'retired': 'retired'}
_TEMPLATE_STATUS_SEARCH = {'active': ['published'], 'retired': ['retired']}


def _template_status_domain(value):
    states = _TEMPLATE_STATUS_SEARCH.get(value)
    if not states:
        raise FHIRBadRequest("Unknown status token: %r" % value)
    return [('state', 'in', states)]


class QuestionnaireSerializer(FHIRSerializer):
    resource_type = 'Questionnaire'
    odoo_model = 'health.form.template'

    search_params = {
        # `name` is the template's stable code, matched exactly — a token,
        # not the base spec's string param (see the GC-2 report, D3).
        'name': {'type': 'token', 'domain': token_domain('code')},
        'status': {'type': 'token',
                   'domain': token_status_domain(_template_status_domain)},
    }

    def base_domain(self, env):
        # Drafts are not public contract.
        return [('state', 'in', ['published', 'retired'])]

    def patient_ids_of(self, records):
        return []

    def to_fhir(self, template):
        resource = {
            'resourceType': 'Questionnaire',
            'id': str(template.id),
            'meta': self.meta(template),
            'status': _TEMPLATE_STATUS.get(template.state, 'active'),
        }
        if template.code:
            resource['name'] = template.code
        if template.name:
            resource['title'] = template.name
        if template.version is not None:
            resource['version'] = str(template.version)
        if template.description:
            description = strip_html(template.description)
            if description:
                resource['description'] = description
        if template.published_date:
            resource['date'] = fhir_date(template.published_date)
        items = []
        for question in template.question_ids.sorted(
                key=lambda q: (q.sequence, q.id or 0)):
            item = {
                'linkId': question.key or str(question.id),
                'text': question.label or '',
                'type': _ITEM_TYPE.get(question.question_type, 'string'),
            }
            if question.question_type in ('selection', 'multiselect'):
                options = question.options_json or []
                answer_option = []
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    coding = {'code': str(option.get('value', ''))}
                    if option.get('label'):
                        coding['display'] = option['label']
                    answer_option.append({'valueCoding': coding})
                if answer_option:
                    item['answerOption'] = answer_option
            items.append(item)
        if items:
            resource['item'] = items
        return resource


# ---------------------------------------------------------------------------
# QuestionnaireResponse
# ---------------------------------------------------------------------------

_INSTANCE_STATUS = {
    'draft': 'in-progress',
    'completed': 'completed',
    'amended': 'amended',
    'cancelled': 'stopped',
}
_INSTANCE_STATUS_SEARCH = {v: [k] for k, v in _INSTANCE_STATUS.items()}


def _instance_status_domain(value):
    states = _INSTANCE_STATUS_SEARCH.get(value)
    if not states:
        raise FHIRBadRequest("Unknown status token: %r" % value)
    return [('state', 'in', states)]


def _answer_objects(qtype, value):
    """One (or more) FHIR answer objects for a stored answer value, or None
    when the question should be omitted (empty / attachment / malformed)."""
    if value is None or value == '':
        return None
    # Attachment answers ({"attachment_id": ...}) are PHI binary — skipped.
    if qtype in ('photo', 'signature') or isinstance(value, dict):
        return None
    try:
        if qtype == 'boolean':
            return [{'valueBoolean': bool(value)}]
        if qtype in ('number', 'computed_score'):
            return [{'valueDecimal': float(value)}]
        if qtype == 'multiselect' and isinstance(value, (list, tuple)):
            objects = [{'valueString': str(item)} for item in value if item]
            return objects or None
        return [{'valueString': str(value)}]
    except (TypeError, ValueError):
        return None


class QuestionnaireResponseSerializer(FHIRSerializer):
    resource_type = 'QuestionnaireResponse'
    odoo_model = 'health.form.instance'

    search_params = {
        'patient': {'type': 'reference',
                    'domain': fso_common.patient_ref_domain('client_id')},
        'status': {'type': 'token',
                   'domain': token_status_domain(_instance_status_domain)},
        'authored': {'type': 'date',
                     'domain': date_param_domain('completed_datetime')},
        'questionnaire': {'type': 'reference',
                          'domain': lambda v: [(
                              'template_id', '=',
                              parse_reference_value(v, 'Questionnaire'))]},
    }

    def base_domain(self, env):
        return []

    def patient_ids_of(self, records):
        return records.mapped('client_id').ids

    def to_fhir(self, instance):
        resource = {
            'resourceType': 'QuestionnaireResponse',
            'id': str(instance.id),
            'meta': self.meta(instance),
            'status': _INSTANCE_STATUS.get(instance.state, 'in-progress'),
            # R4 QuestionnaireResponse.questionnaire is a canonical (a plain
            # string), not a Reference object.
            'questionnaire': 'Questionnaire/%s' % instance.template_id.id,
            'subject': self.reference('Patient', instance.client_id.id,
                                      display=instance.client_id.name),
        }
        encounter = fso_common.encounter_ref_if_qualifies(
            self, instance.order_id)
        if encounter:
            resource['encounter'] = encounter
        if instance.completed_datetime:
            resource['authored'] = fhir_instant(instance.completed_datetime)
        if instance.performer_id:
            resource['author'] = {'display': instance.performer_id.name}
        items = self._items(instance)
        if items:
            resource['item'] = items
        return resource

    def _items(self, instance):
        schema = instance.schema_snapshot or {}
        answers = instance.answers_json or {}
        items = []
        for question in schema.get('questions', []):
            if not isinstance(question, dict):
                continue
            key = question.get('key')
            if not key or key not in answers:
                continue
            try:
                answer_objects = _answer_objects(
                    question.get('type'), answers.get(key))
            except Exception:  # noqa: BLE001 — a bad answer omits its item
                answer_objects = None
            if not answer_objects:
                continue
            items.append({
                'linkId': key,
                'text': question.get('label') or '',
                'answer': answer_objects,
            })
        return items
