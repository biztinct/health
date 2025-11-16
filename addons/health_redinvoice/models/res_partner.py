# -*- coding: utf-8 -*-

from odoo import fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    buyer_legal_name = fields.Char(string='Buyer Legal Name')
    buyer_postal_code = fields.Char(string='Buyer Postal Code')
    buyer_district_name = fields.Char(string='Buyer District')
    buyer_country_code = fields.Char(string='Buyer Country Code')
    buyer_bank_name = fields.Char(string='Buyer Bank Name')
    buyer_bank_account = fields.Char(string='Buyer Bank Account')
    buyer_id_type = fields.Selection([
        ('1', 'ID Card'),
        ('2', 'Passport'),
        ('3', 'Business License'),
    ], string='Buyer Document Type')
    buyer_not_get_invoice = fields.Boolean(string='Buyer Opt-out of Invoice Delivery')
