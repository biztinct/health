# -*- coding: utf-8 -*-
"""Lifecycle opt-in for clinical lookups contributed to Master Data here."""

from odoo import models


class HealthMedication(models.Model):
    _name = 'health.medication'
    _inherit = ['health.medication', 'health.lifecycle.mixin']


class HealthVitalsType(models.Model):
    _name = 'health.vitals.type'
    _inherit = ['health.vitals.type', 'health.lifecycle.mixin']


class HealthMedicationNotgivenReason(models.Model):
    _name = 'health.medication.notgiven.reason'
    _inherit = ['health.medication.notgiven.reason', 'health.lifecycle.mixin']
