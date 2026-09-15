# -*- coding: utf-8 -*-
"""GA1-T13 … GA1-T15, GA1-T17 — who may write what, and the two uniqueness
rules that stop an advertising budget being attributed twice.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.health_google_ads.models.google_ads_account import INTERNAL_CTX

from .common import CUSTOMER_A1, GoogleAdsCase


@tagged('post_install', '-at_install')
class TestGoogleAdsSecurity(GoogleAdsCase):

    # ==================================================================
    # GA1-T13 — evidence is internal-write-only (rail R5)
    # ==================================================================
    def test_ga1_t13_evidence_is_stripped_without_the_internal_context(self):
        account = self.account_a2.with_user(self.operator)
        before = {'website_test_at': account.website_test_at,
                  'website_test_kind': account.website_test_kind,
                  'reporting_state': account.reporting_state}

        account.write({'name': 'GADS A2 renamed',
                       'website_test_at': '2026-09-15 01:00:00',
                       'website_test_kind': 'live',
                       'reporting_state': 'connected'})
        account.invalidate_recordset()
        self.assertEqual(account.name, 'GADS A2 renamed',
                         'an ordinary field still writes')
        for field_name, value in before.items():
            self.assertEqual(account[field_name], value,
                             '%s is evidence and may not be typed' % field_name)

    def test_ga1_t13b_the_internal_context_plus_elevation_lands(self):
        account = self.account_a2.sudo().with_context(**{INTERNAL_CTX: True})
        account.write({'reporting_state': 'action_required'})
        self.account_a2.invalidate_recordset()
        self.assertEqual(self.account_a2.reporting_state, 'action_required')

    def test_ga1_t13c_the_context_alone_is_not_enough(self):
        """`su` alone is not enough and neither is the flag — both, or the
        write is stripped. An operator who learns the context key gains
        nothing."""
        account = self.account_a2.with_user(self.operator).with_context(
            **{INTERNAL_CTX: True})
        account.write({'reporting_state': 'connected'})
        self.account_a2.invalidate_recordset()
        self.assertNotEqual(self.account_a2.reporting_state, 'connected')

    def test_ga1_t13d_native_eligibility_is_platform_only(self):
        with self.assertRaises(AccessError):
            self.account_a2.with_user(self.operator).with_context(
                **{INTERNAL_CTX: True}).write(
                    {'native_eligibility': 'eligible'})
        self.account_a2.invalidate_recordset()
        self.assertEqual(self.account_a2.native_eligibility,
                         'healthcare_blocked')

    # ==================================================================
    # GA1-T14 — one advertising customer, one company
    # ==================================================================
    def test_ga1_t14_customer_id_binds_to_one_company(self):
        with self.assertRaises(UserError):
            self.Account.create({'name': 'GADS clash',
                                 'company_id': self.company2.id,
                                 'customer_id': CUSTOMER_A1})

    def test_ga1_t14b_archiving_does_not_free_the_binding(self):
        self.account_a1.write({'active': False})
        with self.assertRaises(UserError):
            self.Account.create({'name': 'GADS clash archived',
                                 'company_id': self.company2.id,
                                 'customer_id': CUSTOMER_A1})

    def test_ga1_t14c_the_display_form_is_normalised_first(self):
        company = self.env['res.company'].create({'name': 'GADS Norm Co'})
        account = self.Account.create({'name': 'GADS norm',
                                       'company_id': company.id,
                                       'customer_id': '555-555-5555'})
        self.assertEqual(account.customer_id, '5555555555')

    # ==================================================================
    # GA1-T15 — one website-only draft per company
    # ==================================================================
    def test_ga1_t15_one_draft_per_company(self):
        company = self.env['res.company'].create({'name': 'GADS Draft Co'})
        draft = self.Account.create({'name': 'GADS draft',
                                     'company_id': company.id})
        with self.assertRaises(UserError):
            self.Account.create({'name': 'GADS second draft',
                                 'company_id': company.id})

        # Giving the draft its customer id upgrades it IN PLACE — and then a
        # new draft is allowed again, because there is no draft any more.
        draft.write({'customer_id': '6666666666'})
        self.assertEqual(draft.customer_id, '6666666666')
        second = self.Account.create({'name': 'GADS new draft',
                                      'company_id': company.id})
        self.assertTrue(second)

    # ==================================================================
    # GA1-T17 — ACLs and record rules
    # ==================================================================
    def test_ga1_t17_plain_crm_user_reads_only_their_company(self):
        visible = self.Account.with_user(self.crm_user).search([])
        self.assertIn(self.account_a1, visible)
        self.assertNotIn(self.account_b1, visible,
                         'the global company rule is not a group privilege '
                         'anyone outranks')

    def test_ga1_t17b_plain_crm_user_cannot_create_or_write(self):
        with self.assertRaises(AccessError):
            self.Account.with_user(self.crm_user).create(
                {'name': 'GADS sneak', 'company_id': self.company.id})
        with self.assertRaises(AccessError):
            self.account_a1.with_user(self.crm_user).write({'name': 'nope'})

    def test_ga1_t17c_operator_can_create_and_write(self):
        account = self.Account.with_user(self.operator).create(
            {'name': 'GADS operator made', 'company_id': self.company.id,
             'customer_id': '7777777777'})
        self.assertTrue(account)
        account.write({'name': 'GADS operator renamed'})
        self.assertEqual(account.name, 'GADS operator renamed')

    def test_ga1_t17d_only_a_platform_admin_deletes(self):
        account = self.Account.with_user(self.operator).create(
            {'name': 'GADS delete me', 'company_id': self.company.id,
             'customer_id': '8888888888'})
        with self.assertRaises(AccessError):
            account.with_user(self.operator).unlink()
        # The record is kept, archivable, and the admin can still remove it.
        account.write({'active': False})
        self.assertFalse(account.active)
        account.sudo().unlink()

    def test_ga1_t17e_campaign_rows_are_operator_only(self):
        with self.assertRaises(AccessError):
            self.Campaign.with_user(self.crm_user).create(
                {'account_id': self.account_a1.id,
                 'external_campaign_id': '1212121212',
                 'name': 'GADS sneak campaign'})
        row = self.Campaign.with_user(self.operator).create(
            {'account_id': self.account_a1.id,
             'external_campaign_id': '1212121212',
             'name': 'GADS operator campaign'})
        self.assertEqual(row.company_id, self.company,
                         'the campaign inherits the account company')

    def test_ga1_t17f_campaign_ids_must_be_digits(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.Campaign.create({'account_id': self.account_a1.id,
                                  'external_campaign_id': 'not-a-number',
                                  'name': 'GADS bad id'})

    def test_ga1_t17g_customer_id_must_be_ten_digits(self):
        from odoo.exceptions import ValidationError
        company = self.env['res.company'].create({'name': 'GADS Digits Co'})
        with self.assertRaises(ValidationError):
            self.Account.create({'name': 'GADS short id',
                                 'company_id': company.id,
                                 'customer_id': '123'})
