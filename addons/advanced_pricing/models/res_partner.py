# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Read by the price list's "Foreign customer" conditions (Hanoi: ×1.5,
    # HCMC: +100,000 on the on-demand injection fee). A flag rather than a
    # nationality: the price list asks only "foreign or not".
    is_foreign_client = fields.Boolean(
        'Foreign Client',
        help='Foreign clients are charged the foreign-client rates in the price list.')
