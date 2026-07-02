# -*- coding: utf-8 -*-
from odoo import fields, models


class BiGlossaryTerm(models.Model):
    """Business glossary: definitions surface as tooltips in the field well
    and ground the AI dataset card."""
    _name = 'bi.glossary.term'
    _description = 'BI Glossary Term'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    definition = fields.Text(required=True, translate=True)
    formula_note = fields.Char(
        help="Human-readable formula, e.g. 'Revenue = sum of posted invoice "
             "totals excluding tax'.")
    owner_id = fields.Many2one('res.users', string='Steward',
                               default=lambda self: self.env.user)
    field_ids = fields.One2many('bi.field', 'glossary_term_id',
                                string='Linked Fields')
