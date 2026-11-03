# -*- coding: utf-8 -*-
"""A CRM user can book for a client through a representative caller.

The New Contact wizard offers representative, guardian and emergency-contact
callers, and converting such a contact creates the caller's res.partner. The
CRM partner rule allowed creating only client/caregiver/payer/referrer
partners, so the booking failed with an AccessError (UAT CT-05, 2026-11-04);
the representative also had no catchment area.

  1  conversion as a CRM user creates the representative without an error
  2  the representative carries the client's area and the user can read it
  3  another area's CRM user still cannot read that representative
"""
from odoo.tests import TransactionCase, new_test_user, tagged

# every CRM login on carejiox holds both CRM groups (checked 2026-11-04)
CRM_GROUPS = ('sales_team.group_sale_salesman,health_crm.group_health_crm_user,'
              'health_crm.group_health_crm_manager,health_base.group_healthcare_base')


@tagged('post_install', '-at_install')
class TestRepresentativeBookingAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Area = cls.env['health.catchment.province']
        cls.area_a = Area.create({'name': 'UAT rep A'})
        cls.area_b = Area.create({'name': 'UAT rep B'})
        cls.client = cls.env['res.partner'].create({
            'name': 'UAT rep client', 'is_patient': True, 'catchment_province_id': cls.area_a.id,
        })
        cls.user_a = new_test_user(cls.env, login='uat_rep_crm_a', groups=CRM_GROUPS)
        cls.user_a.catchment_province_id = cls.area_a
        cls.user_b = new_test_user(cls.env, login='uat_rep_crm_b', groups=CRM_GROUPS)
        cls.user_b.catchment_province_id = cls.area_b

    def test_representative_booking_as_crm_user(self):
        Lead = self.env['crm.lead'].with_user(self.user_a)
        lead = Lead.create({
            'name': 'UAT rep caller', 'phone': '0901234560', 'type': 'opportunity',
            'contact_relationship_type': 'client_representative',
            'client_name': self.client.name, 'patient_id': self.client.id,
            'catchment_province_id': self.area_a.id,
        })
        lead.write({'contact_outcome': 'service_booked'})          # 1: no AccessError
        rep = self.env['res.partner'].search([('name', '=', 'UAT rep caller'),
                                              ('is_representative', '=', True)])
        self.assertEqual(len(rep), 1)
        self.assertEqual(rep.catchment_province_id, self.area_a)    # 2
        self.assertTrue(rep.with_user(self.user_a).has_access('read'))
        self.assertFalse(rep.with_user(self.user_b).has_access('read'))  # 3
