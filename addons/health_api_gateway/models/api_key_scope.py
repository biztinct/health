# -*- coding: utf-8 -*-
from odoo import fields, models


class ApiKeyScope(models.Model):
    """One namespace for both REST scopes (booking.read) and FHIR scopes
    (system/Patient.read) — spec B.2.1."""
    _name = 'api.key.scope'
    _description = 'API Key Scope'
    _order = 'code'

    code = fields.Char(required=True, index=True,
                       help="e.g. pwa.read, booking.write, system/Patient.read")
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Scope code must be unique.'),
    ]
