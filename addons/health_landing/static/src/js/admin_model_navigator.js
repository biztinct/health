/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TAB_GROUPS = [
    {
        id: "master_data",
        tabs: [
            { id: "facilities", label: "Facilities", icon: "fa-building",
              model: "health.facility", action: "health_landing.action_admin_facilities" },
            { id: "catchments", label: "Catchments", icon: "fa-map-marker",
              model: "health.catchment.province", action: "health_landing.action_admin_catchments" },
            { id: "service_types", label: "Service Types", icon: "fa-list-ul",
              model: "health.service.type", action: "health_landing.action_admin_service_types" },
            { id: "symptoms", label: "Symptoms", icon: "fa-heartbeat",
              model: "health.symptom", action: "health_landing.action_admin_symptoms" },
            { id: "referral_sources", label: "Referral Sources", icon: "fa-share-alt",
              model: "health.referral.source", action: "health_landing.action_admin_referral_sources" },
            { id: "insurance", label: "Insurance", icon: "fa-shield",
              model: "health.insurance.provider", action: "health_landing.action_admin_insurance" },
            { id: "urgency", label: "Urgency", icon: "fa-exclamation-circle",
              model: "health.urgency.level", action: "health_landing.action_admin_urgency" },
            { id: "categories", label: "Categories", icon: "fa-bookmark",
              model: "health.patient.category", action: "health_landing.action_admin_categories" },
            { id: "specialties", label: "Specialties", icon: "fa-stethoscope",
              model: "health.medical.specialty", action: "health_landing.action_admin_specialties" },
            { id: "districts", label: "Districts", icon: "fa-map",
              model: "health.vietnamese.district", action: "health_landing.action_admin_districts" },
        ],
    },
    {
        id: "people",
        tabs: [
            { id: "users", label: "Users", icon: "fa-users",
              model: "res.users", action: "health_landing.action_admin_users" },
            { id: "roles", label: "Access Roles", icon: "fa-key",
              model: "access.role", action: "health_landing.action_admin_roles" },
            { id: "role_mgmt", label: "Role Management", icon: "fa-shield",
              model: "role.management", action: "health_landing.action_admin_role_mgmt" },
        ],
    },
    {
        id: "pricing",
        tabs: [
            { id: "pricelists", label: "Pricing Engines", icon: "fa-cogs",
              model: "advanced.pricing.engine", action: "health_landing.action_admin_pricelists" },
            { id: "rules", label: "Pricing Rules", icon: "fa-list-ul",
              model: "advanced.pricing.rule", action: "health_landing.action_admin_pricing_rules" },
            { id: "quick_edit", label: "Quick Edit", icon: "fa-edit",
              model: "advanced.pricing.rule", action: "health_landing.action_admin_quick_edit_rules" },
            { id: "packages", label: "Package Products", icon: "fa-cube",
              model: "product.template", action: "health_landing.action_admin_packages" },
        ],
    },
    {
        id: "staff",
        tabs: [
            { id: "staff", label: "Healthcare Staff", icon: "fa-user-md",
              model: "hr.employee", action: "health_landing.action_admin_staff" },
            { id: "skills", label: "Staff Skills", icon: "fa-graduation-cap",
              model: "health.staff.skill", action: "health_landing.action_admin_skills" },
            { id: "areas", label: "Service Areas", icon: "fa-map",
              model: "health.service.area", action: "health_landing.action_admin_areas" },
        ],
    },
];

// Intent signal: stores the tab ID clicked by the user before doAction navigates.
// The new controller reads this during setup to know which tab should be active,
// avoiding stale xmlId from actionService.currentController (not yet updated).
let _pendingTabId = null;

export class AdminModelNavigatorController extends ListController {
    static template = "health_landing.AdminModelNavigatorView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabConfig = this._resolveTabConfig();
    }

    _resolveTabConfig() {
        // 1. Check pending intent from switchTab() — most reliable
        if (_pendingTabId) {
            for (const group of TAB_GROUPS) {
                const pending = group.tabs.find((t) => t.id === _pendingTabId);
                if (pending) {
                    _pendingTabId = null;
                    return { group, activeTab: pending.id };
                }
            }
            _pendingTabId = null;
        }

        // 2. Match by model — always correct from props
        for (const group of TAB_GROUPS) {
            const candidates = group.tabs.filter((t) => t.model === this.props.resModel);
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

    get navigationTabs() {
        return this.tabConfig?.group.tabs || [];
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
