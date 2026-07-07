# -*- coding: utf-8 -*-
"""Coding-sidecar extension: link extracted observations back to the
clinical form instance they were derived from (FHIR Observation.derivedFrom
→ QuestionnaireResponse). Nothing else about health.observation changes."""
from odoo import fields, models


class HealthObservation(models.Model):
    _inherit = 'health.observation'

    form_instance_id = fields.Many2one(
        'health.form.instance', string='Form Instance',
        ondelete='set null', index=True,
        help='Clinical form instance this observation was extracted from.')
