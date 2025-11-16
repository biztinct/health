# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    red_supplier_tax_code = fields.Char(related='company_id.red_supplier_tax_code', readonly=False)
    red_invoice_api_base = fields.Char(related='company_id.red_invoice_api_base', readonly=False)
    red_invoice_username = fields.Char(related='company_id.red_invoice_username', readonly=False)
    red_invoice_password = fields.Char(related='company_id.red_invoice_password', readonly=False)
    red_invoice_signing_mode = fields.Selection(related='company_id.red_invoice_signing_mode', readonly=False)
    red_invoice_type = fields.Selection(related='company_id.red_invoice_type', readonly=False)
    red_invoice_template_code = fields.Char(related='company_id.red_invoice_template_code', readonly=False)
    red_invoice_series = fields.Char(related='company_id.red_invoice_series', readonly=False)
    red_invoice_exchange_user = fields.Char(related='company_id.red_invoice_exchange_user', readonly=False)
    red_invoice_merchant_code = fields.Char(related='company_id.red_invoice_merchant_code', readonly=False)
    red_invoice_merchant_name = fields.Char(related='company_id.red_invoice_merchant_name', readonly=False)
    red_invoice_merchant_city = fields.Char(related='company_id.red_invoice_merchant_city', readonly=False)
    red_invoice_bank_name = fields.Char(related='company_id.red_invoice_bank_name', readonly=False)
    red_invoice_bank_account = fields.Char(related='company_id.red_invoice_bank_account', readonly=False)
    red_invoice_country_code = fields.Char(related='company_id.red_invoice_country_code', readonly=False)
    red_invoice_district_name = fields.Char(related='company_id.red_invoice_district_name', readonly=False)
    red_invoice_auto_issue = fields.Boolean(string='Auto-create Red Invoice on Post', config_parameter='health_redinvoice.auto_issue', default=True)
    red_invoice_allow_download_pdf = fields.Boolean(string='Download Converted PDF', config_parameter='health_redinvoice.download_pdf', default=True)
