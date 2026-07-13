# -*- coding: utf-8 -*-
from odoo import fields, models


class HealthFacility(models.Model):
    _inherit = 'health.facility'

    moh_facility_code = fields.Char(
        string='MOH Facility Code (mã cơ sở KCB)',
        help='Ministry of Health facility registration code (mã cơ sở khám '
             'chữa bệnh) — required for Circular 13/2025 EMR export and future '
             'LGSP submission.')
