/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

const TAG_TO_PAGE = {
    ops_command_center: "dashboard",
    ops_booking_queue: "bookings",
    ops_booking_wizard: "bookings",
    ops_booking_detail: "bookings",
    ops_client_list: "clients",
    ops_client_profile: "clients",
    ops_quick_booking: "bookings",
    ops_recurring_booking: "recurring",
    ops_staff_roster: "staff",
    ops_roster_planning: "roster",
    ops_calendar: "calendar",
    ops_payment_collection: "bookings",
    ops_service_in_progress: "bookings",
    ops_staff_assignment: "bookings",
    staff_workload_dashboard: "workload",
};

const XMLID_TO_PAGE = {
    "health_fieldservice.action_ops_client_list_native": "clients",
    "health_fieldservice.action_ops_booking_list_native": "bookings",
    "health_fieldservice.action_ops_booking_form": "bookings",
    "health_fieldservice.action_ops_calendar": "calendar",
    "health_fieldservice.action_staff_workload_dashboard": "workload",
    "health_fieldservice.action_assignment_web_timeline_view": "roster",
};

const NAV_ACTIONS = {
    dashboard: "health_fieldservice.action_ops_command_center",
    bookings: "health_fieldservice.action_ops_booking_list_native",
    clients: "health_fieldservice.action_ops_client_list_native",
    recurring: "health_fieldservice.action_ops_recurring_booking",
    staff: "health_fieldservice.action_ops_staff_roster",
    roster: "health_fieldservice.action_assignment_web_timeline_view",
    calendar: "health_fieldservice.action_health_fieldservice_order",
    workload: "health_fieldservice.action_staff_workload_dashboard",
    analytics: "health_fieldservice.action_staff_workload_dashboard",
};

export class OpsSidebar extends Component {
    static template = "health_fieldservice.OpsSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");

        const sessionName = window.odoo?.session_info?.name || "";
        this.currentUserName = sessionName || "Operations Manager";
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map(p => p[0]).join("").substring(0, 2).toUpperCase() || "OM";

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

        if (action.type === "ir.actions.act_window" && action.res_model === "health.fieldservice.order") {
            const viewType = controller.view?.type;
            this.state.activePage = viewType === "calendar" ? "calendar" : "bookings";
            return;
        }

        const xmlId = action.xml_id;
        if (xmlId && XMLID_TO_PAGE[xmlId]) {
            this.state.activePage = XMLID_TO_PAGE[xmlId];
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

sidebarRegistry.add("ops_center", {
    actionTags: new Set(Object.keys(TAG_TO_PAGE)),
    windowModels: new Set(["health.fieldservice.order", "health.staff.assignment", "res.partner"]),
    actionXmlIds: new Set([
        "health_fieldservice.action_ops_client_list_native",
        "health_fieldservice.action_ops_booking_list_native",
        "health_fieldservice.action_ops_booking_form",
        "health_fieldservice.action_ops_calendar",
        "health_fieldservice.action_staff_workload_dashboard",
        "health_fieldservice.action_assignment_web_timeline_view",
        "health_fieldservice.action_ops_client_profile_form",
    ]),
    Component: OpsSidebar,
});
