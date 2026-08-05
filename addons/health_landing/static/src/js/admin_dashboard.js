/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AdminDashboard extends Component {
    static template = "health_landing.AdminDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            isLoading: true,
            kpis: {},
            recentAudit: [],
            cancelPeriod: "month",
            cancelFrom: "",
            cancelTo: "",
            cancelStats: { count: 0, by_reason: [] },
        });

        this.cancelPeriods = [
            { id: "today", label: _t("Today") },
            { id: "week", label: _t("This Week") },
            { id: "month", label: _t("This Month") },
            { id: "all", label: _t("All Dates") },
            { id: "custom", label: _t("Custom") },
        ];

        onWillStart(async () => {
            await this.loadDashboardData();
            await this.loadCancelledStats();
        });
    }

    async loadDashboardData() {
        try {
            const data = await this.orm.call("res.users", "get_admin_dashboard_data", []);
            this.state.kpis = data.kpis || {};
            this.state.recentAudit = data.recent_audit || [];
        } catch {
            this.state.kpis = {};
            this.state.recentAudit = [];
        }
        this.state.isLoading = false;
    }

    async loadCancelledStats() {
        try {
            const data = await this.orm.call("res.users", "get_cancelled_bookings_stats", [
                this.state.cancelPeriod,
                this.state.cancelFrom || false,
                this.state.cancelTo || false,
            ]);
            this.state.cancelStats = { count: data.count || 0, by_reason: data.by_reason || [] };
        } catch {
            this.state.cancelStats = { count: 0, by_reason: [] };
        }
    }

    async onCancelPeriodChange(period) {
        this.state.cancelPeriod = period;
        if (period === "custom" && !(this.state.cancelFrom && this.state.cancelTo)) {
            return;
        }
        await this.loadCancelledStats();
    }

    async onCancelDateChange(which, value) {
        if (which === "from") {
            this.state.cancelFrom = value;
        } else {
            this.state.cancelTo = value;
        }
        this.state.cancelPeriod = "custom";
        if (this.state.cancelFrom && this.state.cancelTo) {
            await this.loadCancelledStats();
        }
    }

    navigateToAction(actionXmlId) {
        this.actionService.doAction(actionXmlId, {
            clearBreadcrumbs: true,
        });
    }

    openAddUser() {
        this.actionService.doAction("health_landing.action_admin_users", {
            clearBreadcrumbs: true,
        });
    }

    openAddFacility() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "health.facility",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPricingRules() {
        this.actionService.doAction("health_landing.action_admin_pricing_rules", {
            clearBreadcrumbs: true,
        });
    }

    openAuditLog() {
        this.actionService.doAction("health_landing.action_admin_audit", {
            clearBreadcrumbs: true,
        });
    }

    openMasterData() {
        this.actionService.doAction("health_landing.action_admin_facilities", {
            clearBreadcrumbs: true,
        });
    }

    openStaff() {
        this.actionService.doAction("health_landing.action_admin_staff", {
            clearBreadcrumbs: true,
        });
    }
}

registry.category("actions").add("admin_dashboard", AdminDashboard);
