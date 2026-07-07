# -*- coding: utf-8 -*-
"""Per-client vitals alert thresholds (clinical spec §2.2.3).

min/max band per (client, observation type, severity) with an
escalation action executed on breach (chatter note or mail.activity for
the facility manager / care-plan author).

Blockly visual authoring of threshold rules is explicitly OUT of scope
for v1 (deferred) — thresholds are maintained through the editable list
views on the client form and the Vitals Thresholds menu.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HealthVitalsThreshold(models.Model):
    _name = 'health.vitals.threshold'
    _description = 'Per-Client Vitals Alert Threshold'
    _order = 'client_id, vitals_type_id, severity'

    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('is_patient', '=', True)], ondelete='cascade',
        index=True)
    vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Observation Type', required=True,
        domain=[('value_type', '=', 'quantity')])
    severity = fields.Selection([
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], default='warning', required=True, help='Alert band.')
    min_value = fields.Float(
        string='Min', help='Breach when the value falls below this.')
    max_value = fields.Float(
        string='Max', help='Breach when the value rises above this.')
    escalation_action = fields.Selection([
        ('none', 'Record Only'),
        ('chatter', 'Post on Client Chatter'),
        ('activity', 'Create Activity for Facility Manager'),
        ('activity_author', 'Create Activity for Care Plan Author'),
    ], default='activity', required=True,
        help='What happens when an observation breaches this band.')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    active = fields.Boolean(default=True)
    notes = fields.Char(help='Rationale.')

    _sql_constraints = [
        ('uniq_threshold', 'UNIQUE(client_id, vitals_type_id, severity)',
         'One threshold per client, type and severity.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_vitals_threshold_uniq_uidx
            ON health_vitals_threshold (client_id, vitals_type_id, severity)
        """)

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    @api.model_create_multi
    def create(self, vals_list):
        # @api.constrains only fires for fields present in vals — a create
        # without either bound would slip through; enforce explicitly.
        records = super().create(vals_list)
        records._check_bounds()
        return records

    @api.constrains('min_value', 'max_value')
    def _check_bounds(self):
        for rec in self:
            if not rec.min_value and not rec.max_value:
                raise ValidationError(_(
                    'A threshold needs at least a minimum or a maximum '
                    'value.'))
            if (rec.min_value and rec.max_value
                    and rec.min_value > rec.max_value):
                raise ValidationError(_(
                    'Threshold minimum cannot exceed its maximum.'))
