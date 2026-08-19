# -*- coding: utf-8 -*-
"""The Master Data navigator must never expose an unmanaged lookup."""

from odoo.tests import TransactionCase, tagged


MASTER_DATA_MODELS = (
    'health.facility',
    'health.catchment.province',
    'health.province',
    'health.vietnamese.district',
    'health.patient.category',
    'health.contact.reason',
    'health.lead.reason',
    'health.referral.source',
    'health.insurance.provider',
    'crm.lost.reason',
    'health.service.type',
    'product.category',
    'health.urgency.level',
    'health.symptom',
    'health.medical.specialty',
    'health.clinical.protocol',
    'health.medication',
    'health.vitals.type',
    'health.medication.notgiven.reason',
    'health.lookup.value',
    'health.lookup.category',
    'health.fieldservice.stage',
    'health.fieldservice.team',
    'health.booking.cancellation.reason',
    'health.deletion.reason',
)


@tagged('post_install', '-at_install')
class TestMasterDataLifecycle(TransactionCase):

    def test_every_master_data_model_supports_delete_and_archive(self):
        for model_name in MASTER_DATA_MODELS:
            model = self.env[model_name]
            with self.subTest(model=model_name):
                self.assertIn('deleted', model._fields)
                self.assertIn('active', model._fields)
                self.assertTrue(hasattr(model, 'action_soft_delete'))
                self.assertTrue(hasattr(model, 'action_open_archive_wizard'))

    def test_lifecycle_registry_reports_every_master_data_model(self):
        registered = set(
            self.env['health.archive.reason.wizard'].get_lifecycle_models())
        self.assertFalse(set(MASTER_DATA_MODELS) - registered)
