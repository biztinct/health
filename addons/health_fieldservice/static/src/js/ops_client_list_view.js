/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class OpsClientListController extends ListController {
    static template = "health_fieldservice.OpsClientListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabState = useState({
            activeTab: "all",
            dateFilter: "all_dates",
            customFrom: "",
            customTo: "",
        });
        this._tabFilterGroupId = null;
        this._dateFilterGroupId = null;
    }

    get tabs() {
        return [
            { id: "all", label: "All Clients", icon: "fa-users" },
            { id: "active", label: "Active", icon: "fa-check-circle" },
            { id: "inactive", label: "Inactive", icon: "fa-pause-circle" },
            { id: "recent", label: "Recent Visits", icon: "fa-clock-o" },
        ];
    }

    // Date filter on the last visit date
    get dateTabs() {
        return [
            { id: "all_dates", label: "All Dates" },
            { id: "today", label: "Today" },
            { id: "this_week", label: "This Week" },
            { id: "this_month", label: "This Month" },
        ];
    }

    _getDateDomain(dateId) {
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const fmt = (d) => d.toISOString().replace("T", " ").substring(0, 19);
        switch (dateId) {
            case "today": {
                const end = new Date(todayStart); end.setDate(end.getDate() + 1);
                return [["last_visit_date", ">=", fmt(todayStart)], ["last_visit_date", "<", fmt(end)]];
            }
            case "this_week": {
                const ws = new Date(todayStart); ws.setDate(ws.getDate() - ((ws.getDay() + 6) % 7));
                const we = new Date(ws); we.setDate(we.getDate() + 7);
                return [["last_visit_date", ">=", fmt(ws)], ["last_visit_date", "<", fmt(we)]];
            }
            case "this_month": {
                const ms = new Date(now.getFullYear(), now.getMonth(), 1);
                const me = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [["last_visit_date", ">=", fmt(ms)], ["last_visit_date", "<", fmt(me)]];
            }
            case "custom": {
                const out = [];
                if (this.tabState.customFrom) out.push(["last_visit_date", ">=", this.tabState.customFrom + " 00:00:00"]);
                if (this.tabState.customTo) out.push(["last_visit_date", "<=", this.tabState.customTo + " 23:59:59"]);
                return out;
            }
            default:
                return [];
        }
    }

    async setDateFilter(dateId) {
        if (dateId !== "custom" && this.tabState.dateFilter === dateId) return;
        this.tabState.dateFilter = dateId;
        this._applyDateFilter();
    }

    _applyDateFilter() {
        if (this._dateFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._dateFilterGroupId);
            this._dateFilterGroupId = null;
        }
        const dateId = this.tabState.dateFilter;
        if (dateId === "all_dates") return;
        const domain = this._getDateDomain(dateId);
        if (!domain.length) return;
        const label = dateId === "custom"
            ? `Last visit ${this.tabState.customFrom || "…"} → ${this.tabState.customTo || "…"}`
            : (this.dateTabs.find((t) => t.id === dateId)?.label || dateId);
        const preFilter = { description: label, domain };
        this.env.searchModel.createNewFilters([preFilter]);
        this._dateFilterGroupId = preFilter.groupId;
    }

    onCustomDate(which, ev) {
        this.tabState[which === "from" ? "customFrom" : "customTo"] = ev.target.value;
        this.tabState.dateFilter = "custom";
        this._applyDateFilter();
    }

    async setTab(tabId) {
        if (this.tabState.activeTab === tabId) return;
        this.tabState.activeTab = tabId;

        if (this._tabFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._tabFilterGroupId);
            this._tabFilterGroupId = null;
        }

        if (tabId !== "all") {
            let domain;
            let description;
            switch (tabId) {
                case "active":
                    domain = [["patient_status", "=", "active"]];
                    description = "Active";
                    break;
                case "inactive":
                    domain = [["patient_status", "=", "inactive"]];
                    description = "Inactive";
                    break;
                case "recent":
                    domain = [["last_visit_date", "!=", false]];
                    description = "Recent Visits";
                    break;
            }
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._tabFilterGroupId = preFilter.groupId;
        }
    }

    openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: record.resId,
            views: [[false, "form"]],
            target: "current",
            context: { form_view_ref: "health_fieldservice.view_health_patient_form_ops" },
        });
    }
}

export const opsClientListView = {
    ...listView,
    Controller: OpsClientListController,
};

registry.category("views").add("ops_client_list_view", opsClientListView);
