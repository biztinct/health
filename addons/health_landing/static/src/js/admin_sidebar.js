/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

const TAG_TO_PAGE = {
    admin_dashboard: "dashboard",
    admin_settings: "settings",
    field_requirements_dashboard: "field_req",
};

const XMLID_TO_PAGE = {
    "health_landing.action_admin_users": "users",
    "health_landing.action_admin_facilities": "master_data",
    "health_landing.action_admin_catchments": "master_data",
    "health_landing.action_admin_service_types": "master_data",
    "health_landing.action_admin_symptoms": "master_data",
    "health_landing.action_admin_referral_sources": "master_data",
    "health_landing.action_admin_insurance": "master_data",
    "health_landing.action_admin_urgency": "master_data",
    "health_landing.action_admin_categories": "master_data",
    "health_landing.action_admin_specialties": "master_data",
    "health_landing.action_admin_districts": "master_data",
    "health_landing.action_admin_pricelists": "pricing",
    "health_landing.action_admin_pricing_rules": "pricing",
    "health_landing.action_admin_quick_edit_rules": "pricing",
    "health_landing.action_admin_packages": "pricing",
    "health_landing.action_admin_staff": "staff",
    "health_landing.action_admin_skills": "staff",
    "health_landing.action_admin_areas": "staff",
    "health_landing.action_admin_equipment": "equipment",
    "health_landing.action_admin_holidays": "holidays",
    "health_landing.action_admin_audit": "audit",
};

const NAV_ACTIONS = {
    dashboard: "health_landing.action_admin_dashboard",
    users: "health_landing.action_admin_users",
    master_data: "health_landing.action_admin_facilities",
    pricing: "health_landing.action_admin_pricelists",
    staff: "health_landing.action_admin_staff",
    equipment: "health_landing.action_admin_equipment",
    holidays: "health_landing.action_admin_holidays",
    audit: "health_landing.action_admin_audit",
    field_req: "health_landing.action_admin_field_req",
    settings: "health_landing.action_admin_settings",
};

export class AdminSidebar extends Component {
    static template = "health_landing.AdminSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");

        const sessionName = window.odoo?.session_info?.name || "";
        this.currentUserName = sessionName || "Admin";
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map(p => p[0]).join("").substring(0, 2).toUpperCase() || "AD";

        this.state = useState({ activePage: "" });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this._updateActivePage();
        });

        onMounted(() => {
            this._updateActivePage();
        });
    }

    _updateActivePage() {
        const controller = this.actionService.currentController;
        if (!controller) return;

        const action = controller.action;
        const tag = action.tag;

        if (tag && TAG_TO_PAGE[tag]) {
            this.state.activePage = TAG_TO_PAGE[tag];
            return;
        }

        const xmlId = action.xml_id;
        if (xmlId && XMLID_TO_PAGE[xmlId]) {
            this.state.activePage = XMLID_TO_PAGE[xmlId];
            return;
        }

        if (action.type === "ir.actions.act_window") {
            const model = action.res_model;
            if (model === "health.audit.log.view") {
                this.state.activePage = "audit";
                return;
            }
        }
    }

    navigateTo(page) {
        const action = NAV_ACTIONS[page];
        if (action) {
            this.state.activePage = page;
            this.actionService.doAction(action, { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        window.location.href = "/web";
    }

    isActive(page) {
        return this.state.activePage === page;
    }
}

sidebarRegistry.add("admin_center", {
    actionTags: new Set(Object.keys(TAG_TO_PAGE)),
    windowModels: new Set([
        "health.audit.log.view",
    ]),
    actionXmlIds: new Set(Object.keys(XMLID_TO_PAGE)),
    Component: AdminSidebar,
});
