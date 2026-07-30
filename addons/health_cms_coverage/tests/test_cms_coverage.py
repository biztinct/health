# -*- coding: utf-8 -*-
"""health_cms_coverage — nineteen sidebar leaves, no python.

The failure mode this module can actually have is a leaf that DRAWS and then
opens nothing: `action_xmlid` is a plain Char with no foreign key, so a typo, a
renamed action or an uninstalled module produces a menu entry that errors on
click and nothing anywhere complains. Every test below exists to make that
impossible to ship silently.

The second failure mode is collateral: a new leaf that steals an existing
leaf's highlight (§5.94) or turns an existing leaf into a non-navigating
expander (§5.69a). Both are asserted structurally, against the live catalogue.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_cms_coverage.hooks import ROLE_GATES

# leaf xml-id -> (section xml-id, action xml-id, every action it must match)
EXPECTED = {
    # --- CRM -----------------------------------------------------------
    'item_crm_channels_setup': (
        'section_crm',
        'health_care_command_channels.action_care_channel_connection',
        ('health_care_command_channels.action_care_channel_connection',
         'health_care_command_channels.action_care_channel_message',
         'health_care_command_channels.action_care_channel_audit')),
    'item_crm_reply_templates': (
        'section_crm',
        'health_care_command.action_care_reply_template',
        ('health_care_command.action_care_reply_template',
         'health_care_command.action_care_watch_phrase')),
    'item_crm_followup_calendar': (
        'section_crm', 'health_crm.action_crm_followup_calendar',
        ('health_crm.action_crm_followup_calendar',)),
    'item_crm_relationships': (
        'section_crm', 'health_crm.action_health_client_relation',
        ('health_crm.action_health_client_relation',)),
    # --- OPERATIONS MANAGER --------------------------------------------
    'item_ops_telehealth': (
        'section_ops', 'health_telehealth.action_telehealth_session',
        ('health_telehealth.action_telehealth_session',)),
    'item_ops_selfbooking': (
        'section_ops', 'health_self_booking.action_selfbook_invite',
        ('health_self_booking.action_selfbook_invite',)),
    'item_ops_family_links': (
        'section_ops', 'health_family_link.action_family_link',
        ('health_family_link.action_family_link',)),
    'item_ops_family_messages': (
        'section_ops', 'health_family_messages.action_family_messages',
        ('health_family_messages.action_family_messages',)),
    'item_ops_route_feasibility': (
        'section_ops', 'health_routes.action_route_transition',
        ('health_routes.action_route_transition',)),
    # --- CLINICAL ------------------------------------------------------
    'item_clin_diagnoses': (
        'section_clinical', 'health_condition.action_health_condition',
        ('health_condition.action_health_condition',)),
    'item_clin_unsigned_notes': (
        'section_clinical', 'health_emr.action_unsigned_clinical_notes',
        ('health_emr.action_unsigned_clinical_notes',)),
    'item_clin_voice_notes': (
        'section_clinical', 'health_scribe.action_scribe_job',
        ('health_scribe.action_scribe_job',)),
    'item_clin_coding_review': (
        'section_clinical', 'health_ai_coding.action_ai_code_suggestion',
        ('health_ai_coding.action_ai_code_suggestion',)),
    'item_clin_visit_tasks': (
        'section_clinical', 'health_careplan.action_health_careplan_task',
        ('health_careplan.action_health_careplan_task',)),
    'item_clin_patient_portal': (
        'section_clinical', 'health_portal.action_portal_access',
        ('health_portal.action_portal_access',
         'health_portal.action_portal_access_log')),
    'item_clin_consent_log': (
        'section_clinical', 'health_consent.action_health_consent_check_log',
        ('health_consent.action_health_consent_check_log',)),
    # --- FINANCE -------------------------------------------------------
    'item_fin_bhyt_claims': (
        'section_finance', 'health_bhyt.action_bhyt_claim',
        ('health_bhyt.action_bhyt_claim',)),
    'item_fin_service_packages': (
        'section_finance', 'health_invoicing.action_fin_package_list',
        ('health_invoicing.action_fin_package_list',)),
    'item_fin_red_invoice_log': (
        'section_finance', 'health_redinvoice.action_redinvoice_requests',
        ('health_redinvoice.action_redinvoice_requests',)),
}

SECTIONS_TOUCHED = {'section_crm', 'section_ops', 'section_clinical',
                    'section_finance'}


@tagged('post_install', '-at_install')
class TestCmsCoverage(TransactionCase):

    def _item(self, key):
        return self.env.ref('health_cms_coverage.%s' % key)

    # ------------------------------------------------------------------
    # T1 — every leaf exists, sits in the right section, and its action
    #      RESOLVES. `action_xmlid` is a Char: nothing else checks this.
    # ------------------------------------------------------------------
    def test_01_every_leaf_resolves_to_a_real_action(self):
        self.assertEqual(len(EXPECTED), 19)
        for key, (section_key, action_xmlid, matches) in EXPECTED.items():
            item = self._item(key)
            self.assertEqual(
                item.section_id,
                self.env.ref('health_cms_sidebar.%s' % section_key), key)
            self.assertTrue(item.active, key)
            self.assertEqual(item.action_xmlid, action_xmlid, key)

            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            self.assertTrue(action, '%s: %s resolves to nothing — the leaf '
                                    'would draw and open an error'
                                    % (key, action_xmlid))
            self.assertIn(action._name, ('ir.actions.act_window',
                                         'ir.actions.client'), key)
            # Every match target must resolve too: an unresolvable one silently
            # stops the leaf highlighting when the user is on that screen.
            declared = {v.strip() for v in (item.match_action_xmlids or '').split(',')
                        if v.strip()}
            self.assertEqual(declared, set(matches), key)
            for xmlid in declared:
                self.assertTrue(
                    self.env.ref(xmlid, raise_if_not_found=False),
                    '%s: match target %s resolves to nothing' % (key, xmlid))

    # ------------------------------------------------------------------
    # T2 — root leaves only (§5.69a) and no model hijack (§5.94)
    # ------------------------------------------------------------------
    def test_02_leaves_are_roots_and_claim_no_models(self):
        Item = self.env['cms.sidebar.item']
        for key in EXPECTED:
            item = self._item(key)
            self.assertFalse(item.parent_id,
                             '%s must be a root leaf — an item with a parent '
                             'turns that parent into a non-navigating '
                             'expander (§5.69a)' % key)
            self.assertFalse(Item.search([('parent_id', '=', item.id)]),
                             '%s must have no children for the same reason' % key)
            self.assertFalse(item.match_models,
                             '%s must not declare match_models: the model '
                             'index is last-wins and this leaf would steal an '
                             'existing one\'s highlight (§5.94)' % key)

    # ------------------------------------------------------------------
    # T3 — nothing pre-existing was disturbed
    # ------------------------------------------------------------------
    def test_03_existing_catalogue_untouched(self):
        """The four sections keep every leaf they had, and ours only append.

        This is the assertion that would catch a sequence collision reordering
        somebody's sidebar, or a leaf accidentally landing in ADMIN — the two
        sections the user explicitly ruled out stay exactly as they were.
        """
        Item = self.env['cms.sidebar.item']
        ours = {self._item(k).id for k in EXPECTED}

        # (a) The excluded sections gained nothing.
        for section_key in ('section_admin', 'section_interop'):
            section = self.env.ref('health_cms_sidebar.%s' % section_key)
            in_section = Item.search([('section_id', '=', section.id)])
            self.assertFalse(
                ours & set(in_section.ids),
                '%s must not have gained a leaf from this module' % section_key)

        # (b) In every section we DID touch, our sequences are strictly above
        #     the pre-existing ones, so no existing item moves.
        for section_key in SECTIONS_TOUCHED:
            section = self.env.ref('health_cms_sidebar.%s' % section_key)
            in_section = Item.search([('section_id', '=', section.id)])
            mine = in_section.filtered(lambda i: i.id in ours)
            theirs = in_section - mine
            self.assertTrue(mine, section_key)
            self.assertTrue(theirs, '%s: fixture guard — the section must '
                                    'still hold its original leaves'
                                    % section_key)
            self.assertGreater(
                min(mine.mapped('sequence')), max(theirs.mapped('sequence')),
                '%s: our sequences must append, never interleave' % section_key)

    # ------------------------------------------------------------------
    # T4 — the shell will actually keep the CMS chrome on these screens
    # ------------------------------------------------------------------
    def test_04_match_keys_reach_the_frontend(self):
        """`get_match_keys()` is what tells the shell "this action is mine".

        Without the action in that payload the screen opens in the bare Odoo
        backend and the user loses the sidebar — the feature would be reachable
        but would kick them out of the CMS to use it.
        """
        keys = self.env['cms.sidebar.item'].get_match_keys()
        xmlids = set(keys['xmlids'])
        for key, (_section, action_xmlid, matches) in EXPECTED.items():
            self.assertIn(action_xmlid, xmlids, key)
            for xmlid in matches:
                self.assertIn(xmlid, xmlids, '%s: %s' % (key, xmlid))

    # ------------------------------------------------------------------
    # T5 — the ungated CLINICAL leaves reach a user with no role at all
    # ------------------------------------------------------------------
    def test_05_ungated_clinical_leaves_are_served(self):
        """Six CLINICAL leaves carry no `role_ids`, like all 24 of their
        siblings, so a user with no `access.role` must still be served them —
        that is the branch `get_sidebar_data` takes for a role-less user."""
        # Returns a LIST of section dicts (not a dict with a 'sections' key).
        data = self.env['cms.sidebar.item'].get_sidebar_data()
        self.assertIsInstance(data, list)
        for expected in ('Diagnoses', 'Unsigned Notes', 'Coding Review',
                         'Visit Tasks', 'Patient Portal', 'Consent Check Log'):
            self.assertIn(expected, self._names(data),
                          '%r is not in the sidebar payload' % expected)

    # ------------------------------------------------------------------
    # T6 — the gating this module writes in python actually landed
    # ------------------------------------------------------------------
    def test_06_role_gates_applied(self):
        """`role_ids` is written by the hook (roles have no xml-id here).

        Asserted against the roles this database really has: a deployment
        missing 'Accountant' must not fail the suite, but where the role exists
        the relation must be exactly the documented set. A gated leaf must also
        never end up gated to NOBODY — that hides a feature from everyone.
        """
        Role = self.env['access.role'].sudo()
        for key, names in ROLE_GATES.items():
            item = self._item(key)
            present = Role.search([('name', 'in', list(names))])
            if not present:
                continue                      # nothing to assert on this DB
            self.assertEqual(
                set(item.role_ids.ids), set(present.ids),
                '%s: expected roles %s' % (key, list(names)))
            self.assertTrue(item.role_ids,
                            '%s must never be gated to no role at all' % key)

        # The six CLINICAL leaves outside the map stay ungated, as their
        # siblings are.
        for key in ('item_clin_diagnoses', 'item_clin_unsigned_notes',
                    'item_clin_coding_review', 'item_clin_visit_tasks',
                    'item_clin_patient_portal', 'item_clin_consent_log'):
            self.assertFalse(self._item(key).role_ids,
                             '%s must stay ungated like every existing '
                             'CLINICAL item' % key)

    # ------------------------------------------------------------------
    # T7 — REGRESSION: the CRM role is not shown what it cannot open
    # ------------------------------------------------------------------
    def test_07_crm_role_is_not_shown_finance_or_scribe(self):
        """The defect this module shipped on its first install.

        Ungated, all nineteen leaves went to every role: a receptionist got a
        FINANCE section their sidebar has never had, and clicking BHYT Claims
        answered "You are not allowed to access 'BHYT Insurance Claim'".
        Measured, not assumed — the CRM role genuinely cannot read
        `bhyt.claim`, `redinvoice.request` or `health.scribe.job`, and can read
        every other model behind these leaves.
        """
        crm_role = self.env['access.role'].sudo().search(
            [('name', '=', 'CRM')], limit=1)
        if not crm_role:
            self.skipTest('this database has no CRM access.role')
        user = self.env['res.users'].create({
            'name': 'cov crm persona', 'login': 'cov_crm_persona',
            'access_role_id': crm_role.id,
        })
        names = self._names(
            self.env['cms.sidebar.item'].with_user(user).get_sidebar_data())

        for hidden in ('BHYT Claims', 'Service Packages', 'Red Invoice Log',
                       'Voice Notes'):
            self.assertNotIn(hidden, names,
                             '%r must not be offered to the CRM role — it '
                             'cannot open it' % hidden)
        for shown in ('Channels (setup)', 'Reply Templates',
                      'Follow-up Calendar', 'Relationships', 'Diagnoses'):
            self.assertIn(shown, names,
                          '%r must still reach the CRM role' % shown)

    # -- helper ---------------------------------------------------------
    @staticmethod
    def _names(data):
        names = set()
        for section in data:
            for item in section.get('items', []):
                names.add(item.get('name'))
                for child in item.get('children', []) or []:
                    names.add(child.get('name'))
        return names
