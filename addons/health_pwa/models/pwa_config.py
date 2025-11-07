# -*- coding: utf-8 -*-
from odoo import models, fields


class HealthPWAConfig(models.Model):
    """Health PWA Configuration Model"""
    _name = 'health.pwa.config'
    _description = 'Health PWA Configuration'

    name = fields.Char('Name', required=True, default='Health PWA Configuration')
    clinic_phone_number = fields.Char('Clinic Phone Number', required=True)
    clinic_name = fields.Char('Clinic Name', required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, required=True)
    active = fields.Boolean('Active', default=True)
    notes = fields.Text('Notes')

    def get_clinic_phone(self):
        """Get clinic phone number for API calls"""
        self.ensure_one()
        return self.clinic_phone_number

    def get_clinic_name(self):
        """Get clinic name for API calls"""
        self.ensure_one()
        return self.clinic_name
