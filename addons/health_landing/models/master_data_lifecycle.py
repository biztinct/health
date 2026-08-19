# -*- coding: utf-8 -*-
"""Govern every lookup exposed by the Admin Center's Master Data screen.

The web lifecycle policy discovers models through ``health.lifecycle.mixin``.
Keeping the opt-in here, beside the navigator which defines the Master Data
catalogue, prevents a new lookup screen from silently falling back to hard
delete.
"""

from odoo import fields, models


class HealthCatchmentProvince(models.Model):
    _name = 'health.catchment.province'
    _inherit = ['health.catchment.province', 'health.lifecycle.mixin']


class HealthProvince(models.Model):
    _name = 'health.province'
    _inherit = ['health.province', 'health.lifecycle.mixin']


class HealthVietnameseDistrict(models.Model):
    _name = 'health.vietnamese.district'
    _inherit = ['health.vietnamese.district', 'health.lifecycle.mixin']


class HealthPatientCategory(models.Model):
    _name = 'health.patient.category'
    _inherit = ['health.patient.category', 'health.lifecycle.mixin']


class HealthContactReason(models.Model):
    _name = 'health.contact.reason'
    _inherit = ['health.contact.reason', 'health.lifecycle.mixin']


class HealthLeadReason(models.Model):
    _name = 'health.lead.reason'
    _inherit = ['health.lead.reason', 'health.lifecycle.mixin']


class HealthReferralSource(models.Model):
    _name = 'health.referral.source'
    _inherit = ['health.referral.source', 'health.lifecycle.mixin']


class HealthInsuranceProvider(models.Model):
    _name = 'health.insurance.provider'
    _inherit = ['health.insurance.provider', 'health.lifecycle.mixin']


class CrmLostReason(models.Model):
    _name = 'crm.lost.reason'
    _inherit = ['crm.lost.reason', 'health.lifecycle.mixin']


class HealthServiceType(models.Model):
    _name = 'health.service.type'
    _inherit = ['health.service.type', 'health.lifecycle.mixin']


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'health.lifecycle.mixin']

    # Core product categories are not archivable. Master Data categories need
    # the standard active flag so the shared Archive action can deactivate
    # them without destroying categories referenced by services.
    active = fields.Boolean(default=True)


class HealthUrgencyLevel(models.Model):
    _name = 'health.urgency.level'
    _inherit = ['health.urgency.level', 'health.lifecycle.mixin']


class HealthSymptom(models.Model):
    _name = 'health.symptom'
    _inherit = ['health.symptom', 'health.lifecycle.mixin']


class HealthMedicalSpecialty(models.Model):
    _name = 'health.medical.specialty'
    _inherit = ['health.medical.specialty', 'health.lifecycle.mixin']


class HealthClinicalProtocol(models.Model):
    _name = 'health.clinical.protocol'
    _inherit = ['health.clinical.protocol', 'health.lifecycle.mixin']


class HealthLookupValue(models.Model):
    _name = 'health.lookup.value'
    _inherit = ['health.lookup.value', 'health.lifecycle.mixin']


class HealthLookupCategory(models.Model):
    _name = 'health.lookup.category'
    _inherit = ['health.lookup.category', 'health.lifecycle.mixin']


class HealthFieldserviceStage(models.Model):
    _name = 'health.fieldservice.stage'
    _inherit = ['health.fieldservice.stage', 'health.lifecycle.mixin']


class HealthFieldserviceTeam(models.Model):
    _name = 'health.fieldservice.team'
    _inherit = ['health.fieldservice.team', 'health.lifecycle.mixin']


class HealthBookingCancellationReason(models.Model):
    _name = 'health.booking.cancellation.reason'
    _inherit = ['health.booking.cancellation.reason', 'health.lifecycle.mixin']


class HealthDeletionReason(models.Model):
    _name = 'health.deletion.reason'
    _inherit = ['health.deletion.reason', 'health.lifecycle.mixin']
