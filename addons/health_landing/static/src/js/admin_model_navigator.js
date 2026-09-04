/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { onWillStart } from "@odoo/owl";
// The one list that says who may change who-can-do-what. Read, never restated:
// a second copy of a gate is a copy that goes out of date, and the copy that is
// wrong is the one that offers somebody a tab they will be refused on.
import { ACCESS_MANAGE_GATE } from "@biz_access/js/access_palette";

// Tabs that open the Access home. Not everybody's: giving out roles is the
// clinic administrators' work and the platform administrator's, which is
// exactly what ACCESS_MANAGE_GATE names.
const ACCESS_TAB_IDS = new Set(["access"]);

// Extension seam. Modules that sit ABOVE health_landing in the dependency
// graph (health_cms_clinical, say) contribute lookup tabs without this file
// having to depend on them:
//
//   registry.category("health_landing.admin_tabs").add("obs_types", {
//       group: "master_data", section: "care", sequence: 70,
//       label: _t("Observation Types"), icon: "fa-thermometer-half",
//       model: "health.vitals.type", action: "some_module.action_x",
//   });
//
// `group` and `section` must name an existing group/section id below;
// contributions pointing at an unknown id are dropped.
const TAB_REGISTRY = registry.category("health_landing.admin_tabs");

// Whole new groups (a fresh tab strip over some other pair of screens) go in
// here, same shape as the TAB_GROUPS entries below:
//
//   registry.category("health_landing.admin_tab_groups").add("cms_config", {
//       tabs: [{ id, label, icon, model, action }, ...],
//   });
const GROUP_REGISTRY = registry.category("health_landing.admin_tab_groups");

// A group is one row of tabs shown above the list. Groups may either declare
// `tabs` flat (People/Pricing/Staff — few enough to read at a glance) or split
// them into labelled `sections` (Master Data — 20+ lookup tables, unreadable
// as a single undifferentiated run of pills).
const TAB_GROUPS = [
    {
        id: "master_data",
        sections: [
            {
                id: "places",
                label: _t("Places"),
                tabs: [
                    { id: "facilities", label: _t("Facilities"), icon: "fa-building",
                      model: "health.facility", action: "health_landing.action_admin_facilities" },
                    { id: "catchments", label: _t("Catchments"), icon: "fa-map-marker",
                      model: "health.catchment.province", action: "health_landing.action_admin_catchments" },
                    { id: "provinces", label: _t("Provinces / Cities"), icon: "fa-flag",
                      model: "health.province", action: "health_landing.action_admin_provinces" },
                    { id: "districts", label: _t("Districts"), icon: "fa-map",
                      model: "health.vietnamese.district", action: "health_landing.action_admin_districts" },
                ],
            },
            {
                id: "clients",
                label: _t("Clients & Contacts"),
                tabs: [
                    { id: "categories", label: _t("Client Categories"), icon: "fa-bookmark",
                      model: "health.patient.category", action: "health_landing.action_admin_categories" },
                    { id: "contact_reasons", label: _t("Contact Reasons"), icon: "fa-comments",
                      model: "health.contact.reason", action: "health_landing.action_admin_contact_reasons" },
                    { id: "lead_reasons", label: _t("Lead Reasons"), icon: "fa-lightbulb-o",
                      model: "health.lead.reason", action: "health_landing.action_admin_lead_reasons" },
                    { id: "referral_sources", label: _t("Referral Sources"), icon: "fa-share-alt",
                      model: "health.referral.source", action: "health_landing.action_admin_referral_sources" },
                    { id: "insurance", label: _t("Insurance"), icon: "fa-shield",
                      model: "health.insurance.provider", action: "health_landing.action_admin_insurance" },
                    { id: "lost_reasons", label: _t("Lost Reasons"), icon: "fa-times-circle",
                      model: "crm.lost.reason", action: "health_landing.action_admin_lost_reasons" },
                ],
            },
            {
                id: "care",
                label: _t("Care & Services"),
                tabs: [
                    { id: "service_types", label: _t("Service Types"), icon: "fa-list-ul",
                      model: "health.service.type", action: "health_landing.action_admin_service_types" },
                    { id: "service_categories", label: _t("Service Categories"), icon: "fa-folder-open",
                      model: "product.category", action: "health_landing.action_admin_service_categories" },
                    { id: "urgency", label: _t("Urgency"), icon: "fa-exclamation-circle",
                      model: "health.urgency.level", action: "health_landing.action_admin_urgency" },
                    { id: "symptoms", label: _t("Symptoms"), icon: "fa-heartbeat",
                      model: "health.symptom", action: "health_landing.action_admin_symptoms" },
                    { id: "specialties", label: _t("Specialties"), icon: "fa-stethoscope",
                      model: "health.medical.specialty", action: "health_landing.action_admin_specialties" },
                    { id: "protocols", label: _t("Clinical Protocols"), icon: "fa-clipboard",
                      model: "health.clinical.protocol", action: "health_landing.action_admin_protocols" },
                    // Medications / Observation Types / Not-Given Reasons are
                    // appended here by health_cms_sidebar via TAB_REGISTRY —
                    // their views live in modules below this one.
                ],
            },
            {
                id: "vocabularies",
                label: _t("Dropdowns"),
                tabs: [
                    // The 24 converted Selection fields all draw from here.
                    // Categories comes second on purpose: values are the daily
                    // job, categories are where you go to import ONE vocabulary.
                    { id: "lookup_values", label: _t("Dropdown Values"), icon: "fa-list-alt",
                      model: "health.lookup.value", action: "health_landing.action_admin_lookup_values" },
                    { id: "lookup_categories", label: _t("Value Categories"), icon: "fa-sitemap",
                      model: "health.lookup.category", action: "health_landing.action_admin_lookup_categories" },
                ],
            },
            {
                id: "operations",
                label: _t("Operations"),
                tabs: [
                    { id: "booking_stages", label: _t("Booking Stages"), icon: "fa-tasks",
                      model: "health.fieldservice.stage", action: "health_landing.action_admin_booking_stages" },
                    { id: "fs_teams", label: _t("Field Service Teams"), icon: "fa-users",
                      model: "health.fieldservice.team", action: "health_landing.action_admin_fs_teams" },
                    { id: "cancel_reasons", label: _t("Cancellation Reasons"), icon: "fa-ban",
                      model: "health.booking.cancellation.reason", action: "health_landing.action_admin_cancel_reasons" },
                    { id: "deletion_reasons", label: _t("Deletion Reasons"), icon: "fa-trash",
                      model: "health.deletion.reason", action: "health_landing.action_admin_deletion_reasons" },
                ],
            },
        ],
    },
    {
        id: "people",
        tabs: [
            { id: "users", label: _t("Users"), icon: "fa-users",
              model: "res.users", action: "health_landing.action_admin_users" },
            // NOT a list of rows: it opens the Access home, which is a screen
            // rather than a table. The tab strip is where somebody looking
            // after people already is, so this is where the door belongs.
            { id: "access", label: _t("Access & roles"), icon: "fa-key",
              model: false, action: "biz_access.action_biz_access_home" },
        ],
    },
    {
        id: "pricing",
        tabs: [
            { id: "services", label: _t("Services"), icon: "fa-list",
              model: "product.template", action: "health_landing.action_admin_services" },
            { id: "rules", label: _t("Pricing Rules"), icon: "fa-list-ul",
              model: "advanced.pricing.rule", action: "health_landing.action_admin_pricing_rules" },
            { id: "quick_edit", label: _t("Quick Edit"), icon: "fa-edit",
              model: "advanced.pricing.rule", action: "health_landing.action_admin_quick_edit_rules" },
            { id: "packages", label: _t("Package Products"), icon: "fa-cube",
              model: "product.template", action: "health_landing.action_admin_packages" },
        ],
    },
    {
        id: "staff",
        tabs: [
            { id: "staff", label: _t("Healthcare Staff"), icon: "fa-user-md",
              model: "hr.employee", action: "health_landing.action_admin_staff" },
            { id: "skills", label: _t("Staff Skills"), icon: "fa-graduation-cap",
              model: "health.staff.skill", action: "health_landing.action_admin_skills" },
            { id: "areas", label: _t("Service Areas"), icon: "fa-map",
              model: "health.service.area", action: "health_landing.action_admin_areas" },
        ],
    },
];

// Normalise both group shapes to `sections`, then fold in registry
// contributions. Recomputed per controller setup so a lazily-loaded module
// that registers after boot is still picked up.
function buildGroups() {
    const declared = [...TAB_GROUPS];
    for (const [id, def] of GROUP_REGISTRY.getEntries()) {
        if (!declared.some((g) => g.id === id)) {
            declared.push({ ...def, id });
        }
    }
    const groups = declared.map((g) => ({
        id: g.id,
        sections: (g.sections || [{ id: "_", label: "", tabs: g.tabs || [] }]).map((s) => ({
            id: s.id,
            label: s.label,
            tabs: [...s.tabs],
        })),
        sectioned: Boolean(g.sections),
    }));
    for (const [id, def] of TAB_REGISTRY.getEntries()) {
        const group = groups.find((g) => g.id === def.group);
        if (!group) {
            continue;
        }
        const section = group.sections.find((s) => s.id === (def.section || "_"));
        if (!section) {
            continue;
        }
        section.tabs.push({ ...def, id });
    }
    for (const group of groups) {
        for (const section of group.sections) {
            section.tabs.sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0));
        }
    }
    return groups;
}

// Intent signal: stores the tab ID clicked by the user before doAction navigates.
// The new controller reads this during setup to know which tab should be active,
// avoiding stale xmlId from actionService.currentController (not yet updated).
let _pendingTabId = null;

export class AdminModelNavigatorController extends ListController {
    static template = "health_landing.AdminModelNavigatorView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.groups = buildGroups();
        this.tabConfig = this._resolveTabConfig();
        this.canManageAccess = false;
        onWillStart(async () => {
            const held = await Promise.all(
                ACCESS_MANAGE_GATE.map((group) => user.hasGroup(group)));
            this.canManageAccess =
                held.some(Boolean) || (await user.hasGroup("base.group_system"));
        });
    }

    _groupTabs(group) {
        return group.sections.flatMap((s) => s.tabs);
    }

    _resolveTabConfig() {
        // 1. Check pending intent from switchTab() — most reliable
        if (_pendingTabId) {
            for (const group of this.groups) {
                const pending = this._groupTabs(group).find((t) => t.id === _pendingTabId);
                if (pending) {
                    _pendingTabId = null;
                    return { group, activeTab: pending.id };
                }
            }
            _pendingTabId = null;
        }

        // 2. Match by model — always correct from props
        for (const group of this.groups) {
            const candidates = this._groupTabs(group).filter(
                (t) => t.model === this.props.resModel);
            if (candidates.length === 0) continue;
            if (candidates.length === 1) return { group, activeTab: candidates[0].id };

            // 3. Same-model disambiguation — try xmlId (best-effort)
            const xmlId = this.actionService.currentController?.action?.xml_id;
            if (xmlId) {
                const exact = candidates.find((t) => t.action === xmlId);
                if (exact) return { group, activeTab: exact.id };
            }
            return { group, activeTab: candidates[0].id };
        }
        return null;
    }

    _visibleTabs(tabs) {
        return this.canManageAccess
            ? tabs
            : tabs.filter((t) => !ACCESS_TAB_IDS.has(t.id));
    }

    // Sections that still have at least one visible tab, in declaration order.
    get navigationSections() {
        const group = this.tabConfig?.group;
        if (!group) {
            return [];
        }
        return group.sections
            .map((s) => ({ ...s, tabs: this._visibleTabs(s.tabs) }))
            .filter((s) => s.tabs.length);
    }

    get isSectioned() {
        return Boolean(this.tabConfig?.group.sectioned);
    }

    get navigationTabs() {
        return this._visibleTabs(
            this.tabConfig ? this._groupTabs(this.tabConfig.group) : []);
    }

    get activeTabId() {
        return this.tabConfig?.activeTab || "";
    }

    get hasNavigationTabs() {
        return this.navigationTabs.length > 0;
    }

    switchTab(tabId) {
        const tab = this.navigationTabs.find((t) => t.id === tabId);
        if (tab && tab.id !== this.activeTabId) {
            _pendingTabId = tabId;
            this.actionService.doAction(tab.action, { clearBreadcrumbs: true });
        }
    }
}

export const adminModelNavigatorView = {
    ...listView,
    Controller: AdminModelNavigatorController,
};

registry.category("views").add("admin_model_navigator_view", adminModelNavigatorView);
