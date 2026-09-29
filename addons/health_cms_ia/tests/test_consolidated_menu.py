# -*- coding: utf-8 -*-
"""MENU M2 — the consolidated left menu.

Numbered as the handover numbers them (MENU_M2_CONSOLIDATION.md §4):

  T1  the hook is idempotent: a second run changes nothing
  T2  every screen the live menu drew on 2026-09-29 is on exactly one entry;
      no heading opens onto nothing; no two tabs share a number; no child in
      another area than its tab
  T3  an upgrade of every updatable seed leaves every moved row where the
      hook put it — asserted by re-loading each seed file in update mode
  T5  the Clinical area: a Doctor sees its seven tabs, a Nurse does not see
      it at all; a Nurse's whole menu is Home, Operations (Bookings, Clients,
      Schedule) and Learn
  T6  with Care Command switched off, its tabs and set-up screens are absent
      for everybody; with the phone switched off, Phone and its set-up
  T7  the Access home's picture of a person's menu is the menu itself
  T8  the highlight: every screen lights its own entry, its tab and its area
      (the M1 resolver's rules, run over the real payload)
  +   no drawn entry is open to everybody except Home and the Training journey

T4 (the per-person before/after) runs on a copy of the live system, not here:
it needs the real seventy-two people.
"""
import json

from odoo.tests import TransactionCase, tagged
from odoo.tools.convert import convert_file

from odoo.addons.health_cms_ia import hooks

#: Every screen the live left menu drew on 2026-09-29 (carejiox, 107 actions
#: on 115 active entries). Pinned, never re-derived at test time: the point is
#: that none of these can quietly leave the menu.
LIVE_ACTIONS = (
    'biz_access.action_biz_access_home',
    'biz_bi.action_bi_dashboard_backend',
    'biz_bi.action_bi_dataset',
    'biz_bi.action_bi_explore',
    'biz_bi.action_bi_glossary',
    'biz_bi.action_bi_modeler',
    'biz_bi.action_bi_pipeline_editor',
    'biz_bi.action_bi_refresh_job',
    'biz_bi.action_bi_source',
    'biz_bi_cms.action_bi_hub',
    'biz_tenancy.action_biz_tenancy_about',
    'biz_tenants.action_biz_tenants',
    'health_ai_coding.action_ai_code_suggestion',
    'health_base.action_health_archive_log',
    'health_bhyt.action_bhyt_claim',
    'health_care_command.action_care_command',
    'health_care_command.action_care_reply_template',
    'health_care_command.action_care_watch_phrase',
    'health_care_command_channels.action_care_channel_audit',
    'health_care_command_channels.action_care_channel_connection',
    'health_care_command_channels.action_care_channel_message',
    'health_care_command_channels.action_care_contact_capture',
    'health_care_command_channels.action_channel_center',
    'health_care_command_channels.action_channel_golive_studio',
    'health_cms_sidebar.action_cms_sidebar_item',
    'health_consent.action_health_consent_check_log',
    'health_consent.action_health_consent_expiring',
    'health_crm.action_crm_activity_list',
    'health_crm.action_crm_contact_list_native',
    'health_crm.action_crm_dashboard',
    'health_crm.action_health_client_relation',
    'health_emar.action_health_medication_administration',
    'health_emar.action_health_medication_emar',
    'health_emar.action_health_medication_order',
    'health_emr.action_unsigned_clinical_notes',
    'health_evv.action_health_evv_event',
    'health_family_messages.action_family_messages',
    'health_fhir_adapter_base.action_fhir_submission_log',
    'health_fhir_adapter_vn.action_vn_emr_readiness',
    'health_fhir_terminology.action_medical_code',
    'health_fhir_terminology.action_medical_code_import',
    'health_fhir_terminology.action_medical_coding_system',
    'health_fieldservice.action_health_staff_timeoff',
    'health_fieldservice.action_ops_booking_list_native',
    'health_fieldservice.action_ops_client_list_native',
    'health_fieldservice.action_ops_command_center',
    'health_fieldservice.action_staff_schedule',
    'health_fieldservice.action_staff_workload_dashboard',
    'health_forms.action_health_form_instance',
    'health_forms.action_health_form_template',
    'health_google_ads.action_google_ads_accounts',
    'health_google_ads.action_google_ads_platform_config',
    'health_incident.action_health_incident',
    'health_incident.action_health_incident_action',
    'health_incident.action_health_incident_analysis',
    'health_invoicing.action_fin_account_payment',
    'health_invoicing.action_fin_ar_dashboard',
    'health_invoicing.action_fin_ar_management',
    'health_invoicing.action_fin_ar_transactions',
    'health_invoicing.action_fin_cash_collections',
    'health_invoicing.action_fin_dashboard',
    'health_invoicing.action_fin_invoice_list',
    'health_invoicing.action_fin_overdue',
    'health_invoicing.action_fin_package_list',
    'health_invoicing.action_fin_payment_list',
    'health_invoicing.action_fin_refund_credit',
    'health_invoicing.action_fin_vat_log',
    'health_invoicing.action_ops_cash_collections',
    'health_landing.action_admin_audit',
    'health_landing.action_admin_dashboard',
    'health_landing.action_admin_equipment',
    'health_landing.action_admin_facilities',
    'health_landing.action_admin_field_req',
    'health_landing.action_admin_holidays',
    'health_landing.action_admin_services',
    'health_landing.action_admin_settings',
    'health_landing.action_admin_staff',
    'health_landing.action_admin_users',
    'health_learn.action_learn_event',
    'health_learn.action_learn_journey',
    'health_learn.action_learn_lesson',
    'health_learn.action_learn_override',
    'health_learn.action_learn_progress',
    'health_learn.action_learn_station',
    'health_messaging.action_outbound_message',
    'health_redinvoice.action_redinvoice_requests',
    'health_routes.action_route_transition',
    'health_scribe.action_scribe_job',
    'health_telemonitoring.action_health_ews_score',
    'health_telemonitoring.action_health_monitor_alert',
    'health_telemonitoring.action_health_monitor_device',
    'health_twin.action_health_twin_risk',
    'health_vitals.action_health_observation',
    'health_vitals.action_health_vitals_type',
    'health_voip24h.action_voip_call_log',
    'health_voip24h.action_voip_call_recording',
    'health_voip24h.action_voip_call_session',
    'health_voip24h.action_voip_callbacks',
    'health_voip24h.action_voip_config',
    'health_voip24h.action_voip_extension',
    'health_web_leads.action_health_lead_touchpoint',
    'health_web_leads.action_web_leads_connector',
    'health_web_leads.action_web_leads_funnel',
    'health_workflow_auto.action_timecard_mismatch',
    'health_workflow_auto.action_visit_offer',
    'hr_development_ai.action_bfsi_coaching_workspace',
    'hr_development_ai.action_hr_development_dashboard',
)

#: The updatable seeds — every upgrade of their module re-writes what they
#: name (program §1.1).
UPDATABLE_SEEDS = (
    ('biz_bi_cms', 'data/cms_sidebar_analytics.xml'),
    ('health_care_command', 'data/cms_sidebar_items_care_command.xml'),
    ('health_care_command_channels',
     'data/cms_sidebar_items_channel_center.xml'),
    ('health_care_command_channels',
     'data/cms_sidebar_items_contact_capture.xml'),
    ('health_care_command_channels', 'data/cms_sidebar_items_golive.xml'),
    ('health_care_command_voip', 'data/cms_sidebar_items_phone.xml'),
    ('health_web_leads', 'data/cms_sidebar_items_web_leads.xml'),
    ('health_google_ads', 'data/cms_sidebar_items_google_ads.xml'),
    ('health_learn', 'data/learn_sidebar_item.xml'),
    ('health_cms_sidebar', 'data/cms_sidebar_items_ops_schedule.xml'),
)

CLINICAL_TABS = ('Observations', 'Care Intelligence', 'Medications',
                 'Assessments', 'Incidents', 'Consents', 'Notes')

#: Mutating parts of the move log. The informational ones (what the door
#: check narrowed, rows this database does not have) are not "changes".
MUTATIONS = ('section_renames', 'renames', 'moves', 'retired', 'matches',
             'released', 'headings', 'gates', 'features', 'phone_roles',
             'phone_people')


def _split(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


@tagged('post_install', '-at_install')
class TestConsolidatedMenu(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Item = cls.env['cms.sidebar.item']
        cls.All = cls.Item.sudo().with_context(active_test=False)

    # ------------------------------------------------------------ helpers
    def _person(self, login, *role_xmlids):
        groups = self.env.ref('base.group_user')
        for xmlid in role_xmlids:
            role = self.env.ref(xmlid, raise_if_not_found=False)
            if not role:
                self.skipTest('%s is not on this database' % xmlid)
            groups |= role.group_ids
        return self.env['res.users'].create({
            'name': login, 'login': '%s@m2.example.test' % login,
            'group_ids': [(6, 0, groups.ids)]})

    def _menu(self, user):
        return self.Item.with_user(user).sudo().get_sidebar_data()

    @staticmethod
    def _tabs(data, key):
        for section in data:
            if section['key'] == key:
                return {i['name']: [k['name'] for k in i['children']]
                        for i in section['items']}
        return None

    def _set_features(self, off):
        value = json.dumps({k: {'on': False, 'name': k} for k in off}) if off else ''
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_tenancy.features', value)
        self.env.registry.clear_cache()

    # ================================================================ T1
    def test_01_a_second_run_changes_nothing(self):
        log = hooks.consolidate_ia(self.env)
        changed = {k: log[k] for k in MUTATIONS if log.get(k)}
        self.assertFalse(changed, 'the hook is not idempotent: %s' % changed)

    # ================================================================ T2
    def test_02_every_live_screen_is_on_exactly_one_entry(self):
        active = self.Item.sudo().search([])
        own = {}
        for item in active:
            if item.action_xmlid:
                own.setdefault(item.action_xmlid, []).append(item)
        lost = []
        for xmlid in LIVE_ACTIONS:
            owners = own.get(xmlid, [])
            if xmlid in ('health_invoicing.action_fin_ar_management',):
                # Retired as ruled; the heading that holds its three cards
                # answers for it.
                self.assertFalse(owners)
                claim = active.filtered(
                    lambda i, x=xmlid: x in _split(i.match_action_xmlids))
                self.assertEqual(
                    claim, self.env.ref(hooks.P_PAYMENTS),
                    'the AR Management screen must light Finance › Payments')
                continue
            if not self.env.ref(xmlid, raise_if_not_found=False):
                continue                         # module not on this database
            if len(owners) != 1:
                lost.append('%s on %s entries' % (xmlid, len(owners)))
        self.assertFalse(lost, 'screens not on exactly one entry: %s' % lost)

    def test_02b_no_heading_opens_onto_nothing(self):
        for item in self.Item.sudo().search([]):
            if item.action_xmlid or item.action_tag:
                continue
            kids = self.Item.sudo().search([('parent_id', '=', item.id)])
            self.assertTrue(kids, '%r is a heading with nothing inside it'
                            % item.name)

    def test_02c_numbers_are_unique_and_children_stay_in_their_area(self):
        clashes = []
        seen = {}
        for item in self.Item.sudo().search([]):
            key = (item.section_id.id, item.parent_id.id or 0, item.sequence)
            if key in seen:
                clashes.append('%s / %s both at %s' % (
                    seen[key], item.name, item.sequence))
            seen[key] = item.name
            if item.parent_id:
                self.assertEqual(item.parent_id.section_id, item.section_id,
                                 '%s sits in another area than its tab'
                                 % item.name)
                self.assertFalse(item.parent_id.parent_id,
                                 '%s is three levels deep' % item.name)
        self.assertFalse(clashes, clashes)

    def test_02d_the_catalogue_is_the_approved_table(self):
        """Spot checks of §2, by fixed name — the whole table is the hook's."""
        for xmlid, (section, parent, sequence) in hooks.MOVE.items():
            item = self.env.ref(xmlid, raise_if_not_found=False)
            if not item:
                continue
            self.assertEqual(item.section_id, self.env.ref(section), xmlid)
            self.assertEqual(item.parent_id,
                             self.env.ref(parent) if parent else self.Item,
                             xmlid)
            self.assertEqual(item.sequence, sequence, xmlid)
        for xmlid, name in hooks.RENAME.items():
            item = self.env.ref(xmlid, raise_if_not_found=False)
            if item:
                self.assertEqual(
                    item.with_context(lang='en_US').name.casefold(),
                    name.casefold(), xmlid)
        self.assertFalse(self.env.ref(
            'health_cms_sidebar.item_fin_ar_management').active)

    # ================================================================ T3
    def test_03_an_upgrade_of_every_updatable_seed_moves_nothing(self):
        def snapshot():
            rows = {}
            for item in self.All.search([]):
                rows[item.id] = (item.section_id.id, item.parent_id.id,
                                 item.sequence,
                                 item.with_context(lang='en_US').name,
                                 item.active, tuple(sorted(item.biz_role_ids.ids)))
            sections = {s.id: s.with_context(lang='en_US').name for s in
                        self.env['cms.sidebar.section'].sudo().with_context(
                            active_test=False).search([])}
            return rows, sections

        before = snapshot()
        for module, path in UPDATABLE_SEEDS:
            if not self.env['ir.module.module'].search_count(
                    [('name', '=', module), ('state', '=', 'installed')]):
                continue
            convert_file(self.env, module, path, {}, mode='update',
                         noupdate=False)
        self.env.invalidate_all()
        after = snapshot()
        moved = [iid for iid in before[0] if before[0][iid] != after[0].get(iid)]
        self.assertFalse(
            moved, 'an upgrade of a seed pulled these rows back: %s' % [
                (self.All.browse(i).get_external_id().get(i), before[0][i],
                 after[0].get(i)) for i in moved])
        self.assertEqual(before[1], after[1], 'a seed renamed an area back')

    # ================================================================ T5
    def test_05_the_clinical_area_opens_for_doctors_not_nurses(self):
        doctor = self._person('m2doc', hooks.DOCTOR)
        nurse = self._person('m2nurse', hooks.NURSE)
        tabs = self._tabs(self._menu(doctor), 'clinical')
        self.assertIsNotNone(tabs, 'a Doctor must see the Clinical area')
        self.assertEqual(list(tabs), list(CLINICAL_TABS))
        self.assertIsNone(self._tabs(self._menu(nurse), 'clinical'),
                          'a Nurse must not see the Clinical area (Q6)')

    def test_05b_a_nurses_whole_menu(self):
        nurse = self._person('m2nurse2', hooks.NURSE)
        data = self._menu(nurse)
        self.assertEqual([s['key'] for s in data], ['home', 'ops', 'learn'])
        ops = self._tabs(data, 'ops')
        self.assertEqual(list(ops), ['Bookings', 'Clients', 'Schedule'])
        self.assertEqual(ops['Schedule'],
                         ['Staff Schedule', 'Time Off', 'Workload'])
        self.assertEqual(list(self._tabs(data, 'learn')), ['Training'])

    def test_05c_a_doctors_whole_menu(self):
        from odoo.addons.health_access.hooks import role_can_read
        doctor = self._person('m2doc2', hooks.DOCTOR)
        role = self.env.ref(hooks.DOCTOR)
        data = self._menu(doctor)
        keys = [s['key'] for s in data]
        self.assertEqual(keys[0], 'home')
        self.assertIn('clinical', keys)
        self.assertIn('learn', keys)
        for forbidden in ('crm', 'finance', 'admin', 'analytics'):
            self.assertNotIn(forbidden, keys)
        ops = self._tabs(data, 'ops')
        self.assertIn('Clients', ops)
        # The door check: a doctor is given Bookings only where the Doctor
        # role can open the bookings list at all.
        self.assertEqual(
            'Bookings' in ops,
            role_can_read(self.env, role, 'health.fieldservice.order'))
        self.assertEqual(self._tabs(data, 'clinical')['Notes'],
                         ['Unsigned Notes', 'Coding Review'],
                         'Voice Notes is not a doctor\'s: they cannot open it')

    def test_05d_nothing_drawn_is_open_to_everybody_by_accident(self):
        """Home and the Training journey are the two open doors (docstring);
        every other active entry carries a gate, its own or inherited."""
        allowed = {self.env.ref('health_cms_sidebar.item_home').id}
        journey = self.env.ref('health_learn.item_learn_journey',
                               raise_if_not_found=False)
        if journey:
            allowed.add(journey.id)
        open_ = [i.name for i in self.Item.sudo().search([])
                 if i.id not in allowed and not i.effective_biz_role_ids]
        self.assertFalse(open_, 'open to everybody: %s' % open_)

    # ================================================================ T6
    def test_06_a_switched_off_part_takes_its_tabs_with_it(self):
        if 'biz.tenancy' not in self.env:
            self.skipTest('no product switches here')
        names = lambda data: {i['name'] for s in data for i in s['items']} | {
            k['name'] for s in data for i in s['items'] for k in i['children']}
        self._set_features(['care_command'])
        try:
            drawn = names(self.Item.sudo().get_sidebar_data())
            for gone in ('Channels', 'Care Command', 'Channel Go-Live',
                         'Reply Templates', 'Channels (setup)'):
                self.assertNotIn(gone, drawn, gone)
            self.assertIn('Phone', drawn)
        finally:
            self._set_features([])
        self._set_features(['voice'])
        try:
            data = self.Item.sudo().get_sidebar_data()
            drawn = names(data)
            for gone in ('Phone', 'Phone system', 'Extensions'):
                self.assertNotIn(gone, drawn, gone)
            settings = self._tabs(data, 'admin')
            self.assertIn('Connections', settings,
                          'the rest of Connections stays')
            from odoo.addons.health_tenancy.models.cms_sidebar import menu_preview
            preview = menu_preview(self.env, ['voice'])
            states = {}
            for section in preview:
                for row in section['items']:
                    states[row['label']] = row['state']
                    for kid in row['children']:
                        states[kid['label']] = kid['state']
            self.assertEqual(states.get('Phone'), 'hidden')
            self.assertEqual(states.get('Phone system'), 'hidden')
            self.assertEqual(states.get('Extensions'), 'hidden')
        finally:
            self._set_features([])

    # ================================================================ T7
    def test_07_the_access_home_draws_exactly_the_menu(self):
        for label, role in (('owner', hooks.OWNER), ('doctor', hooks.DOCTOR),
                            ('nurse', hooks.NURSE),
                            ('accountant', hooks.ACCOUNTANT),
                            ('crm', hooks.CRM)):
            person = self._person('m2vis_%s' % label, role)
            data = self._menu(person)
            drawn = {i['id'] for s in data for i in s['items']} | {
                k['id'] for s in data for i in s['items'] for k in i['children']}
            items, sections = self.Item._biz_visible_map(person)
            self.assertEqual(drawn, {i for i, st in items.items() if st == 'on'},
                             label)
            self.assertEqual({s['id'] for s in data},
                             {i for i, st in sections.items() if st == 'on'},
                             label)

    def test_07b_a_tab_holding_screens_for_different_people(self):
        """Settings › Connections: the front desk sees its channel set-up,
        not the owner's phone set-up — and the heading is gated by what is
        inside it, not open to everybody."""
        crm = self._person('m2crmconn', hooks.CRM)
        tabs = self._tabs(self._menu(crm), 'admin')
        self.assertIsNotNone(tabs, 'the front desk keeps its set-up screens')
        self.assertEqual(tabs.get('Connections'),
                         ['Channels (setup)', 'Reply Templates'])
        heading = self.env.ref(hooks.P_CONNECTIONS)
        self.assertFalse(heading.biz_role_ids)
        self.assertTrue(heading.effective_biz_role_ids)
        nurse = self._person('m2nurseconn', hooks.NURSE)
        self.assertIsNone(self._tabs(self._menu(nurse), 'admin'))

    # ================================================================ T8
    def test_08_every_screen_lights_its_own_entry_tab_and_area(self):
        """The M1 resolver (`cms_sidebar.js` `_matchAction`), run over the
        payload a platform administrator is drawn: own tag, own xml-id, then
        the match lists, then the model."""
        data = self.Item.sudo().get_sidebar_data()
        own_tag, own_xml, tag_idx, xml_idx = {}, {}, {}, {}
        where = {}
        for section in data:
            for item in section['items']:
                for node in [item] + item['children']:
                    where[node['id']] = (section['key'], item['id'])
                    if node['action_tag']:
                        own_tag[node['action_tag']] = node['id']
                    if node['action_xmlid']:
                        own_xml[node['action_xmlid']] = node['id']
                    for t in node['match_action_tags']:
                        tag_idx[t] = node['id']
                    for x in node['match_action_xmlids']:
                        xml_idx[x] = node['id']

        def resolve(xmlid, tag=None):
            for index, key in ((own_tag, tag), (own_xml, xmlid),
                               (tag_idx, tag), (xml_idx, xmlid)):
                if key and key in index:
                    return index[key]
            return None

        wrong = []
        for section in data:
            for item in section['items']:
                for node in [item] + item['children']:
                    if not (node['action_xmlid'] or node['action_tag']):
                        continue
                    got = resolve(node['action_xmlid'], node['action_tag'])
                    if got != node['id']:
                        wrong.append(node['name'])
                    elif where[got] != (section['key'], item['id']):
                        wrong.append('%s (tab)' % node['name'])
        self.assertFalse(wrong, 'these do not light themselves: %s' % wrong)
        # The formerly borrowed and the retired.
        for xmlid, expect in (
                ('health_crm.action_health_client_relation',
                 'health_cms_coverage.item_crm_relationships'),
                ('health_care_command_channels.action_care_channel_audit',
                 'health_access.item_crm_channel_audit'),
                ('health_care_command_channels.action_care_channel_message',
                 'health_access.item_crm_channel_messages'),
                ('health_care_command.action_care_watch_phrase',
                 'health_access.item_crm_watch_phrases'),
                ('health_invoicing.action_fin_ar_management', hooks.P_PAYMENTS)):
            target = self.env.ref(expect, raise_if_not_found=False)
            if not target or not self.env.ref(xmlid, raise_if_not_found=False):
                continue
            self.assertEqual(resolve(xmlid), target.id, xmlid)
        # Data Lifecycle keeps the deletion reasons by model (§5.94 owner).
        lifecycle = self.env.ref('health_cms_sidebar.item_admin_data_lifecycle')
        self.assertIn('health.deletion.reason', _split(lifecycle.match_models))

    # ============================================================ markers
    def test_09_override_keeps_its_model_marker(self):
        method = type(self.Item)._sidebar_visible_items
        self.assertTrue(getattr(method, '_api_model', False)
                        or getattr(method, '_api', None) == 'model')
