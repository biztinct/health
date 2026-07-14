# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    news2_spo2_scale2 = fields.Boolean(
        string='NEWS2 SpO₂ Scale 2 (hypercapnic)',
        default=False, tracking=True,
        help='Use NEWS2 SpO₂ Scale 2 for this patient — for hypercapnic '
             'respiratory failure (e.g. COPD) with a target saturation '
             'range of 88–92%. Leave off for the default Scale 1.')
