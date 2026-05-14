/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";

const OPS_ACTION_TAGS = new Set([
    "ops_command_center", "ops_booking_queue", "ops_client_list",
    "ops_client_profile", "ops_recurring_booking", "ops_staff_roster",
    "ops_roster_planning", "ops_calendar", "ops_booking_wizard",
    "ops_booking_detail", "ops_payment_collection", "ops_service_in_progress",
    "ops_staff_assignment", "staff_workload_dashboard",
]);

const TAG_TO_PAGE = {
    ops_command_center: "dashboard",
    ops_booking_queue: "bookings",
    ops_booking_wizard: "bookings",
    ops_booking_detail: "bookings",
    ops_client_list: "clients",
    ops_client_profile: "clients",
    ops_recurring_booking: "recurring",
    ops_staff_roster: "staff",
    ops_roster_planning: "roster",
    ops_calendar: "calendar",
    ops_payment_collection: "bookings",
    ops_service_in_progress: "bookings",
    ops_staff_assignment: "bookings",
    staff_workload_dashboard: "workload",
};

const NAV_ACTIONS = {
    dashboard: "health_fieldservice.action_ops_command_center",
    bookings: "health_fieldservice.action_ops_booking_queue",
    clients: "health_fieldservice.action_ops_client_list",
    recurring: "health_fieldservice.action_ops_recurring_booking",
    staff: "health_fieldservice.action_ops_staff_roster",
    roster: "health_fieldservice.action_ops_roster_planning",
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

        this.state = useState({
            opsMode: sessionStorage.getItem("ops_mode") === "1",
            activePage: "",
        });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this._updateOpsState();
        });

        onMounted(() => {
            this._updateOpsState();
        });
    }

    _updateOpsState() {
        const controller = this.actionService.currentController;
        if (!controller) return;

        const action = controller.action;
        const tag = action.tag;

        if (tag && OPS_ACTION_TAGS.has(tag)) {
            sessionStorage.setItem("ops_mode", "1");
            this.state.opsMode = true;
            this.state.activePage = TAG_TO_PAGE[tag] || "";
            return;
        }

        if (action.type === "ir.actions.act_window" && action.res_model === "health.fieldservice.order") {
            this.state.opsMode = true;
            sessionStorage.setItem("ops_mode", "1");
            const viewType = controller.view?.type;
            this.state.activePage = viewType === "calendar" ? "calendar" : "bookings";
            return;
        }

        this.state.opsMode = sessionStorage.getItem("ops_mode") === "1";
        if (!this.state.opsMode) {
            this.state.activePage = "";
        }
    }

    navigateTo(page) {
        const action = NAV_ACTIONS[page];
        if (action) {
            sessionStorage.setItem("ops_mode", "1");
            this.state.opsMode = true;
            this.state.activePage = page;
            this.actionService.doAction(action, { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        sessionStorage.removeItem("ops_mode");
        this.state.opsMode = false;
        this.state.activePage = "";
        window.location.href = "/web";
    }

    isActive(page) {
        return this.state.activePage === page;
    }
}
