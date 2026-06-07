/** @odoo-module **/

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
        });

        onWillStart(async () => {
            await this.loadDashboardData();
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
