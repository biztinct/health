# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestClientRelationshipExperience(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catchment = cls.env['health.catchment.province'].create({
            'name': 'Relationship UX Catchment',
            'code': 'RUX',
        })
        cls.client = cls.env['res.partner'].create({
            'name': 'Relationship UX Client',
            'is_patient': True,
            'phone': '0900000001',
            'catchment_province_id': cls.catchment.id,
        })
        cls.representative = cls.env['res.partner'].create({
            'name': 'Relationship UX Representative',
            'is_representative': True,
            'email': 'representative@example.test',
        })
        cls.relation = cls.env['health.client.relation'].create({
            'client_id': cls.client.id,
            'representative_id': cls.representative.id,
            'role': 'caregiver',
            'can_receive_medical_info': True,
            'can_schedule_appointments': True,
        })

    def test_status_tracks_the_relationship_lifecycle(self):
        self.assertEqual(self.relation.relationship_status, 'active')

        self.relation.start_date = fields.Date.today() + timedelta(days=1)
        self.assertEqual(self.relation.relationship_status, 'scheduled')

        self.relation.start_date = fields.Date.today() - timedelta(days=10)
        self.relation.end_date = fields.Date.today() - timedelta(days=1)
        self.assertEqual(self.relation.relationship_status, 'ended')

        self.relation.active = False
        self.assertEqual(self.relation.relationship_status, 'archived')

    def test_authority_summary_and_contact_context_are_readable(self):
        self.assertEqual(self.relation.client_phone, '0900000001')
        self.assertEqual(
            self.relation.representative_email,
            'representative@example.test')
        self.assertIn('Medical information', self.relation.authority_summary)
        self.assertIn('Scheduling', self.relation.authority_summary)
