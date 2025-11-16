# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    red_supplier_tax_code = fields.Char(string='Red Invoice Tax Code')
    red_invoice_api_base = fields.Char(string='Red Invoice API Base URL')
    red_invoice_username = fields.Char(string='Red Invoice Username')
    red_invoice_password = fields.Char(string='Red Invoice Password', password=True)
    red_invoice_signing_mode = fields.Selection([
        ('server', 'Server Signature (HSM)'),
        ('usb_token', 'USB Token'),
        ('cloud_ca', 'Cloud CA'),
    ], string='Red Invoice Signing Mode', default='server')
    red_invoice_type = fields.Selection([
        ('1', 'Invoice Type 1 (TT78)'),
        ('2', 'Invoice Type 2'),
        ('3', 'Invoice Type 3'),
        ('4', 'Invoice Type 4'),
    ], string='Red Invoice Type', default='1')
    red_invoice_template_code = fields.Char(string='Default Template Code')
    red_invoice_series = fields.Char(string='Default Invoice Series')
    red_invoice_exchange_user = fields.Char(string='Default Exchange User')
    red_invoice_merchant_code = fields.Char(string='Merchant Code (QR78)')
    red_invoice_merchant_name = fields.Char(string='Merchant Name (QR78)')
    red_invoice_merchant_city = fields.Char(string='Merchant City (QR78)')
    red_invoice_bank_name = fields.Char(string='Seller Bank Name')
    red_invoice_bank_account = fields.Char(string='Seller Bank Account')
    red_invoice_country_code = fields.Char(string='Seller Country Code')
    red_invoice_district_name = fields.Char(string='Seller District')
