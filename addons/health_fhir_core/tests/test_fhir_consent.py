# -*- coding: utf-8 -*-
"""Consent-gated FHIR facade (Phase 2, architecture §6.6).

The facade must not release a patient's PHI to an external system without an
active `data_sharing` consent. Default is LOG-ONLY (audited, nothing withheld);
`health_fhir_core.consent_enforced` flips it to deny-by-default.
"""
import uuid

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_fhir_core.serializers import REGISTRY
from odoo.addons.health_fhir_core.serializers.base import (
    consent_allowed_records, consent_enforced,
)


@tagged('post_install', '-at_install')
class TestFhirConsentGate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'CG Prov %s' % uuid.uuid4().hex[:5],
            'code': 'CG%s' % uuid.uuid4().hex[:3]})
        cls.facility = cls.env['health.facility'].create({
            'name': 'CG Facility', 'code': 'CGF%s' % uuid.uuid4().hex[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': cls.province.id})
        def mk_patient(name):
            return cls.env['res.partner'].create({
                'name': name, 'is_patient': True,
                'catchment_province_id': cls.province.id,
                'primary_facility_id': cls.facility.id,
                'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        cls.consented = mk_patient('CG Consented')
        cls.unconsented = mk_patient('CG Unconsented')
        # Active data_sharing consent for the consented patient only.
        consent = cls.env['health.consent'].create({
            'client_id': cls.consented.id,
            'consent_type_id': cls.env['health.lookup.value']._default_for('consent_type', 'data_sharing'),
            'method': 'verbal',
        })
        consent.action_grant()
        cls.both = cls.consented | cls.unconsented

    def _logs_for(self, partner):
        return self.env['health.consent.check.log'].sudo().search([
            ('client_id', '=', partner.id),
            ('consent_type_code', '=', 'data_sharing'),
            ('source', '=', 'fhir_facade')])

    # -- log-only (default) --------------------------------------------------
    def test_log_only_returns_all_but_audits(self):
        ser = REGISTRY['Patient']
        result = consent_allowed_records(self.env, ser, self.both, enforced=False)
        self.assertEqual(result, self.both)  # nothing withheld
        # Both patients' checks were logged (the audit trail).
        con = self._logs_for(self.consented)
        unc = self._logs_for(self.unconsented)
        self.assertTrue(con and all(con.mapped('result')))
        self.assertTrue(unc and not any(unc.mapped('result')))

    # -- enforced ------------------------------------------------------------
    def test_enforced_filters_unconsented(self):
        ser = REGISTRY['Patient']
        result = consent_allowed_records(self.env, ser, self.both, enforced=True)
        self.assertEqual(result, self.consented)
        self.assertNotIn(self.unconsented, result)

    def test_enforced_denies_single_unconsented(self):
        # The read-path shape: a single un-consented record -> empty -> 404.
        ser = REGISTRY['Patient']
        self.assertFalse(
            consent_allowed_records(self.env, ser, self.unconsented, enforced=True))
        self.assertEqual(
            consent_allowed_records(self.env, ser, self.consented, enforced=True),
            self.consented)

    # -- non-PHI resources are never gated -----------------------------------
    def test_non_phi_resource_passes_through(self):
        ser = REGISTRY['Organization']  # patient_ids_of == []
        result = consent_allowed_records(
            self.env, ser, self.facility, enforced=True)
        self.assertEqual(result, self.facility)

    # -- config flag ---------------------------------------------------------
    def test_consent_enforced_flag(self):
        ICP = self.env['ir.config_parameter'].sudo()
        self.addCleanup(ICP.set_param, 'health_fhir_core.consent_enforced',
                        ICP.get_param('health_fhir_core.consent_enforced'))
        ICP.set_param('health_fhir_core.consent_enforced', 'False')
        self.assertFalse(consent_enforced(self.env))
        ICP.set_param('health_fhir_core.consent_enforced', 'True')
        self.assertTrue(consent_enforced(self.env))
