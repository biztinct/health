# -*- coding: utf-8 -*-
from odoo import fields, models


class FsLinkTarget(models.Model):
    """The records a "Link to a record" field may point at.

    A curated list, never "any model": an administrator picks from the names
    people use ("Staff member"), and a link to a technical table is a field
    nobody can fill. This module ships none — the product names its own.
    """
    _name = 'fs.link.target'
    _description = 'Record type a Studio link may point at'
    _order = 'sequence, id'

    model = fields.Char(required=True, index=True)
    label = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
