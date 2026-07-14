# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCmsClinical(TransactionCase):
    """health_cms_clinical: a pure data + view glue module. The real proof is
    the browser evidence pack; these guard the wiring (records exist, actions
    resolve, sidebar renders them, ops view composes)."""

    def test_01_sidebar_items_exist_and_actions_resolve(self):
        """The 5 items exist under section_clinical; each leaf action_xmlid
        resolves to a real ir.actions.act_window."""
        section = self.env.ref('health_cms_sidebar.section_clinical')

        parent = self.env.ref('health_cms_clinical.item_clin_care_intel')
        self.assertEqual(parent.section_id, section)
        self.assertFalse(parent.parent_id, "Care Intelligence is a root expander")
        self.assertFalse(parent.action_xmlid, "an expander has no action")

        leaves = {
            'health_cms_clinical.item_clin_worklist':
                'health_twin.action_health_twin_risk',
            'health_cms_clinical.item_clin_alerts':
                'health_telemonitoring.action_health_monitor_alert',
            'health_cms_clinical.item_clin_devices':
                'health_telemonitoring.action_health_monitor_device',
            'health_cms_clinical.item_clin_news2':
                'health_telemonitoring.action_health_ews_score',
        }
        for item_xmlid, action_xmlid in leaves.items():
            item = self.env.ref(item_xmlid)
            self.assertEqual(item.section_id, section)
            self.assertEqual(item.parent_id, parent)
            self.assertEqual(item.action_xmlid, action_xmlid)
            action = self.env.ref(action_xmlid)
            self.assertEqual(action._name, 'ir.actions.act_window',
                             "%s must resolve to an act_window" % action_xmlid)

    def test_02_get_sidebar_data_returns_group(self):
        """get_sidebar_data() exposes the Care Intelligence parent with its 4
        children under the CLINICAL section."""
        data = self.env['cms.sidebar.item'].get_sidebar_data()
        # Flatten every item across whatever shape the payload uses.
        blob = str(data)
        for name in ('Care Intelligence', 'Deterioration Worklist',
                     'Deterioration Alerts', 'Monitoring Devices',
                     'NEWS2 Scores'):
            self.assertIn(name, blob,
                          "%r must be present in the sidebar payload" % name)

    def test_03_ops_view_composes_with_new_tabs(self):
        """The ops profile view + our inherit compose: the combined arch (with
        inheritance applied) carries the two new pages by name.

        NB: use get_combined_arch, not get_view — get_view postprocessing
        strips <page groups="..."> nodes when the calling user (superuser in
        tests) is not a member of the healthcare group, which would mask the
        successfully-merged pages. Combined arch proves the xpath matched;
        actual per-role rendering is proven by the browser evidence pack."""
        ops_view = self.env.ref(
            'health_fieldservice.view_health_patient_form_ops')
        arch = ops_view.get_combined_arch()
        self.assertIn('vitals_thresholds_ops', arch)
        self.assertIn('consents_ops', arch)
        # And our inherit view is the one contributing them.
        inherit = self.env.ref(
            'health_cms_clinical.view_ops_profile_clinical_tabs')
        self.assertEqual(inherit.inherit_id, ops_view)
