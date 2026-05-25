/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

const TAG_TO_PAGE = {
    crm_dashboard: "dashboard",
    crm_new_contact: "new_contact",
    crm_booking_wizard: "new_contact",
    crm_settings: "settings",
};

const XMLID_TO_PAGE = {
    "health_crm.action_crm_contact_list_native": "contacts",
    "health_crm.action_crm_contact_form_native": "contacts",
    "health_crm.action_crm_client_list": "clients",
    "health_crm.action_crm_bookings_calendar": "bookings",
    "health_crm.action_crm_followup_calendar": "calendar",
    "health_crm.action_crm_activity_list": "activities",
};

const NAV_ACTIONS = {
    dashboard: "health_crm.action_crm_dashboard",
    new_contact: "health_crm.action_crm_new_contact",
    contacts: "health_crm.action_crm_contact_list_native",
    clients: "health_crm.action_crm_client_list",
    bookings: "health_fieldservice.action_ops_booking_list_native",
    calendar: "health_crm.action_crm_followup_calendar",
    activities: "health_crm.action_crm_activity_list",
    settings: "health_crm.action_crm_settings",
};

export class CrmSidebar extends Component {
    static template = "health_crm.CrmSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");

        const sessionName = window.odoo?.session_info?.name || "";
        this.currentUserName = sessionName || "CRM Agent";
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map(p => p[0]).join("").substring(0, 2).toUpperCase() || "CA";

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

        if (action.type === "ir.actions.act_window" && action.res_model === "crm.lead") {
            const viewType = controller.view?.type;
            this.state.activePage = viewType === "calendar" ? "calendar" : "contacts";
            return;
        }

        if (action.type === "ir.actions.act_window" && action.res_model === "res.partner") {
            this.state.activePage = "clients";
            return;
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

sidebarRegistry.add("crm_center", {
    actionTags: new Set(Object.keys(TAG_TO_PAGE)),
    windowModels: new Set(["crm.lead", "res.partner", "health.fieldservice.order"]),
    actionXmlIds: new Set(Object.keys(XMLID_TO_PAGE)),
    Component: CrmSidebar,
});
