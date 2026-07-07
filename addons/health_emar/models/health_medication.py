# -*- coding: utf-8 -*-
"""Medication catalog extension (spec §3.2.1).

The catalog itself lives in ``health_base`` (``health.medication``) —
this module only adds the interop coding fields. Existing fields are
reused as-is: ``name``, ``generic_name``, ``brand_name``,
``vietnamese_name`` (the local vi name), ``therapeutic_category``,
``contraindications``. No duplicate vi-name field is added.
"""
from odoo import fields, models


class HealthMedication(models.Model):
    _inherit = 'health.medication'

    rxnorm_code = fields.Char(
        string='RxNorm RXCUI', index=True,
        help='Canonical code (FHIR Medication.code, system '
             'http://www.nlm.nih.gov/research/umls/rxnorm)')
    form = fields.Selection([
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('liquid', 'Liquid/Syrup'),
        ('injection', 'Injection'),
        ('patch', 'Patch'),
        ('cream', 'Cream/Ointment'),
        ('inhaler', 'Inhaler'),
        ('drops', 'Drops'),
        ('suppository', 'Suppository'),
        ('other', 'Other'),
    ], string='Form', help='FHIR Medication.doseForm')
    strength = fields.Char(
        string='Strength',
        help="Display strength, e.g. '500 mg'; "
             'FHIR Medication.ingredient.strength (text)')
    dav_reg_no = fields.Char(
        string='DAV Registration No. (số đăng ký)',
        help='VN drug-registry crosswalk (identifier system '
             'https://dav.gov.vn/so-dang-ky)')
