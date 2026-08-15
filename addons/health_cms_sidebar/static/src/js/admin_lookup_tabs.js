/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// Clinical lookup tables joining the Admin Center's MASTER DATA strip.
//
// health_landing owns the strip but sits below the clinical modules, so these
// two are contributed through its extension registry instead. `sequence`
// places them after the tabs health_landing declares in the same section
// (those carry no sequence, i.e. 0). Actions/views: views/admin_lookup_tabs.xml.
const adminTabs = registry.category("health_landing.admin_tabs");

// The sidebar's own config screens get a tab strip of their own, so the
// section-level role gating is one click from the item list instead of buried
// under a backend menu the CMS shell never shows.
registry.category("health_landing.admin_tab_groups").add("cms_config", {
    tabs: [
        { id: "cms_items", label: _t("Menu Items"), icon: "fa-bars",
          model: "cms.sidebar.item", action: "health_cms_sidebar.action_cms_sidebar_item" },
        { id: "cms_sections", label: _t("Sections & Role Access"), icon: "fa-shield",
          model: "cms.sidebar.section", action: "health_cms_sidebar.action_cms_sidebar_section" },
    ],
});

adminTabs.add("medications", {
    group: "master_data",
    section: "care",
    sequence: 5,
    label: _t("Medications"),
    icon: "fa-medkit",
    model: "health.medication",
    action: "health_cms_sidebar.action_admin_medications",
});

adminTabs.add("observation_types", {
    group: "master_data",
    section: "care",
    sequence: 10,
    label: _t("Observation Types"),
    icon: "fa-thermometer-half",
    model: "health.vitals.type",
    action: "health_cms_sidebar.action_admin_observation_types",
});

adminTabs.add("notgiven_reasons", {
    group: "master_data",
    section: "care",
    sequence: 20,
    label: _t("Not-Given Reasons"),
    icon: "fa-times",
    model: "health.medication.notgiven.reason",
    action: "health_cms_sidebar.action_admin_notgiven_reasons",
});
