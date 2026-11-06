# -*- coding: utf-8 -*-
"""An empty contact screen speaks the product's words (UAT round 10, item 4)."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEmptyContactsHelp(TransactionCase):

    def test_contacts_list_empty_text(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'health_crm.action_crm_contact_list_native')
        help_html = self.env['crm.lead'].with_context(
            default_type='opportunity').get_empty_list_help(action.get('help') or '')
        self.assertIn('No contacts yet.', str(help_html))
        self.assertIn('Press New Contact', str(help_html))
        for stock in ('playing with your pipeline', 'email gateway', 'Odoo'):
            self.assertNotIn(stock, str(help_html))

    def test_lead_type_and_own_help(self):
        out = self.env['crm.lead'].with_context(default_type='lead').get_empty_list_help('')
        self.assertIn('No contacts yet.', str(out))
        own = '<p>Already said</p>'
        self.assertIn('Already said', str(self.env['crm.lead'].get_empty_list_help(own)))

    def test_activities_screen_has_its_own_help(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'health_crm.action_crm_activity_list')
        self.assertIn('No follow-ups to do.', action.get('help') or '')
