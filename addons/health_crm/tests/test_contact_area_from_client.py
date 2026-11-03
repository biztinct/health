# -*- coding: utf-8 -*-
"""An area-less contact takes its client's area (crm.lead._catchment_from_client).

  1  created with a client and no area -> the client's area
  2  an area already on the contact is never overwritten
  3  an area-less contact linked to a client later -> the client's area
  4  clearing the area on a contact with a client puts the client's area back
  5  the patient link (Quick Booking conversion) also gives the area
  6  a staff user of another area reads the contact list without an
     AccessError; the other area's client cells are blank, not leaked
"""
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestContactAreaFromClient(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Area = cls.env['health.catchment.province']
        cls.area_a = Area.create({'name': 'UAT Area A'})
        cls.area_b = Area.create({'name': 'UAT Area B'})
        cls.client = cls.env['res.partner'].create({
            'name': 'UAT area client', 'catchment_province_id': cls.area_a.id,
        })
        cls.Lead = cls.env['crm.lead']

    def test_1_create_with_client(self):
        lead = self.Lead.create({'name': 'UAT area 1', 'partner_id': self.client.id})
        self.assertEqual(lead.catchment_province_id, self.area_a)

    def test_2_own_area_kept(self):
        lead = self.Lead.create({'name': 'UAT area 2', 'partner_id': self.client.id,
                                 'catchment_province_id': self.area_b.id})
        self.assertEqual(lead.catchment_province_id, self.area_b)

    def test_3_client_linked_later(self):
        lead = self.Lead.create({'name': 'UAT area 3'})
        self.assertFalse(lead.catchment_province_id)
        lead.write({'partner_id': self.client.id})
        self.assertEqual(lead.catchment_province_id, self.area_a)

    def test_4_cleared_area_refilled(self):
        lead = self.Lead.create({'name': 'UAT area 4', 'partner_id': self.client.id})
        lead.write({'catchment_province_id': False})
        self.assertEqual(lead.catchment_province_id, self.area_a)

    def test_5_patient_link(self):
        patient = self.env['res.partner'].create({
            'name': 'UAT area patient', 'is_patient': True,
            'catchment_province_id': self.area_a.id,
        })
        lead = self.Lead.create({'name': 'UAT area 5', 'contact_relationship_type': 'client'})
        lead.write({'patient_id': patient.id})
        self.assertEqual(lead.catchment_province_id, self.area_a)

    def test_6_other_area_user_reads_list(self):
        patient = self.env['res.partner'].create({
            'name': 'UAT area A patient', 'is_patient': True,
            'catchment_province_id': self.area_a.id, 'patient_code': 'UATAREA6',
        })
        # A contact set to area B whose client sits in area A (live: "Client Jun25").
        lead = self.Lead.create({'name': 'UAT area 6', 'contact_relationship_type': 'client',
                                 'patient_id': patient.id,
                                 'catchment_province_id': self.area_b.id})
        user = new_test_user(self.env, login='uat_area_b_staff',
                             groups='sales_team.group_sale_salesman_all_leads,'
                                    'health_base.group_healthcare_base')
        user.catchment_province_id = self.area_b
        self.assertTrue(user.catchment_enforced)
        rows = self.Lead.with_user(user).search_read(
            [('id', '=', lead.id)], ['related_client_name', 'client_patient_code', 'patient_display_id'])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['related_client_name'])
        self.assertFalse(rows[0]['client_patient_code'])
        self.assertFalse(rows[0]['patient_display_id'])
        # ...while a user who may read area A still sees the client.
        lead.invalidate_recordset()
        self.assertEqual(lead.related_client_name, 'UAT area A patient')
