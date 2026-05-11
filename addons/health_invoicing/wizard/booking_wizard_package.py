# -*- coding: utf-8 -*-

from odoo import models, fields


class BookingServicesWizardPackage(models.TransientModel):
    _inherit = 'health.booking.services.wizard'

    package_id = fields.Many2one(
        'health.service.package', string='Select Prepaid Package',
        domain="[('patient_id', '=', client_id), ('state', '=', 'active'), ('remaining_services', '>', 0)]",
    )
