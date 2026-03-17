# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # MISA Integration toggle (Red Invoice master toggle is in health_redinvoice)
    enable_misa_integration = fields.Boolean(
        'Enable MISA Integration',
        config_parameter='vietnamese_tax.misa_integration_enabled',
        help='Enable synchronization with MISA accounting system. '
             'Requires Red Invoice to be enabled.'
    )

    vat_serial_prefix = fields.Char(
        'VAT Serial Prefix',
        config_parameter='vietnamese_tax.vat_serial_prefix',
        help='Yearly prefix for VAT invoice serial codes (e.g. "C26T" for 2026). '
             'Applied when generating new VAT invoices.',
        default='',
    )
