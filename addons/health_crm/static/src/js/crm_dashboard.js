/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STATUS_LABELS = {
    active: _t("Initial Contact"),
    booking: _t("Booking"),
    lead: _t("Lead"),
    lost_booking: _t("Lost Booking"),
    spam: _t("Spam"),
};

const STATUS_COLORS = {
    active: "#1565C0",
    booking: "#2E7D32",
    lead: "#F57F17",
    lost_booking: "#C62828",
    spam: "#757575",
};

class CrmDashboard extends Component {
    static template = "health_crm.CrmDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isLoading: true,
            kpis: {},
            recentContacts: [],
            statusBreakdown: [],
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "crm.lead",
                "get_crm_dashboard_data",
                []
            );
            this.state.kpis = data.kpis || {};
            this.state.recentContacts = data.recent_contacts || [];
            this.state.statusBreakdown = data.status_breakdown || [];
        } catch (e) {
            console.error("Failed to load CRM dashboard:", e);
            this.notification.add(_t("Error loading dashboard"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    getStatusLabel(status) {
        return STATUS_LABELS[status] || status;
    }

    getStatusColor(status) {
        return STATUS_COLORS[status] || "#9E9E9E";
    }

    getStatusClass(status) {
        return "crm-status-" + (status || "active");
    }

    getOutcomeClass(outcome) {
        const map = {
            service_booked: "crm-outcome-booked",
            pending_follow_up: "crm-outcome-followup",
            rejected: "crm-outcome-rejected",
            no_response: "crm-outcome-noresp",
            booking_lost: "crm-outcome-lost",
        };
        return map[outcome] || "";
    }

    formatPercent(val) {
        if (!val && val !== 0) return "0%";
        return val.toFixed(1) + "%";
    }

    // Quick Actions
    openNewContact() {
        this.action.doAction("health_crm.action_crm_new_contact", { clearBreadcrumbs: true });
    }

    openContacts() {
        this.action.doAction("health_crm.action_crm_contact_list_native", { clearBreadcrumbs: true });
    }

    openCalendar() {
        this.action.doAction("health_crm.action_crm_followup_calendar", { clearBreadcrumbs: true });
    }

    openActivities() {
        this.action.doAction("health_crm.action_crm_activity_list", { clearBreadcrumbs: true });
    }

    openContact(leadId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: leadId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onRefresh() {
        await this.loadDashboardData();
        this.notification.add(_t("Dashboard refreshed"), { type: "success" });
    }
}

registry.category("actions").add("crm_dashboard", CrmDashboard);

export default CrmDashboard;
