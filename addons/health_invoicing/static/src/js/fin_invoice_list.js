/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class FinInvoiceListController extends ListController {
    static template = "health_invoicing.FinInvoiceListView";

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

    get statusTabs() {
        return [
            { id: "all", label: _t("All"), icon: "fa-list" },
            { id: "draft", label: _t("Draft"), icon: "fa-pencil" },
            { id: "posted", label: _t("Posted"), icon: "fa-check" },
            { id: "paid", label: _t("Paid"), icon: "fa-check-circle" },
            { id: "partial", label: _t("Partial"), icon: "fa-adjust" },
            { id: "overdue", label: _t("Overdue"), icon: "fa-exclamation-triangle" },
            { id: "cancelled", label: _t("Cancelled"), icon: "fa-ban" },
        ];
    }

    get dateTabs() {
        return [
            { id: "all_dates", label: _t("All Dates") },
            { id: "today", label: _t("Today") },
            { id: "this_week", label: _t("This Week") },
            { id: "this_month", label: _t("This Month") },
        ];
    }

    _getStatusDomain(tabId) {
        const today = new Date();
        const fmt = (d) => d.toISOString().substring(0, 10);
        switch (tabId) {
            case "draft":
                return [["state", "=", "draft"]];
            case "posted":
                return [["state", "=", "posted"], ["payment_state", "=", "not_paid"]];
            case "paid":
                return [["payment_state", "=", "paid"]];
            case "partial":
                return [["payment_state", "=", "partial"]];
            case "overdue":
                return [["state", "=", "posted"], ["payment_state", "in", ["not_paid", "partial"]], ["invoice_date_due", "<", fmt(today)]];
            case "cancelled":
                return [["state", "=", "cancel"]];
            default:
                return [];
        }
    }

    _getDateDomain(dateId) {
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const todayEnd = new Date(todayStart);
        todayEnd.setDate(todayEnd.getDate() + 1);
        const fmt = (d) => d.toISOString().substring(0, 10);

        switch (dateId) {
            case "today":
                return [
                    ["invoice_date", ">=", fmt(todayStart)],
                    ["invoice_date", "<", fmt(todayEnd)],
                ];
            case "this_week": {
                const weekStart = new Date(todayStart);
                weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1);
                const weekEnd = new Date(weekStart);
                weekEnd.setDate(weekEnd.getDate() + 7);
                return [
                    ["invoice_date", ">=", fmt(weekStart)],
                    ["invoice_date", "<", fmt(weekEnd)],
                ];
            }
            case "this_month": {
                const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
                const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [
                    ["invoice_date", ">=", fmt(monthStart)],
                    ["invoice_date", "<", fmt(monthEnd)],
                ];
            }
            case "custom": {
                const out = [];
                if (this.tabState.customFrom) out.push(["invoice_date", ">=", this.tabState.customFrom]);
                if (this.tabState.customTo) out.push(["invoice_date", "<=", this.tabState.customTo]);
                return out;
            }
            default:
                return [];
        }
    }

    async setTab(tabId) {
        if (this.tabState.activeTab === tabId) return;
        this.tabState.activeTab = tabId;

        if (this._tabFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._tabFilterGroupId);
            this._tabFilterGroupId = null;
        }

        const domain = this._getStatusDomain(tabId);
        if (domain.length) {
            const description = this.statusTabs.find((t) => t.id === tabId)?.label || tabId;
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._tabFilterGroupId = preFilter.groupId;
        }
    }

    async setDateFilter(dateId) {
        // 'custom' may be re-applied while already selected (when the dates change)
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
        if (!domain.length) return; // e.g. custom with no dates entered yet
        const label = dateId === "custom"
            ? _t("Custom (%s → %s)", this.tabState.customFrom || "…", this.tabState.customTo || "…")
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

    openNewInvoice() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("New Invoice"),
            res_model: "account.move",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: { default_move_type: "out_invoice" },
        });
    }
}

export const finInvoiceListView = {
    ...listView,
    Controller: FinInvoiceListController,
};

registry.category("views").add("fin_invoice_list_view", finInvoiceListView);
