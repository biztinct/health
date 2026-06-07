/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class FinPaymentListController extends ListController {
    static template = "health_invoicing.FinPaymentListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabState = useState({
            activeTab: "all",
            typeFilter: "all_types",
            dateFilter: "all_dates",
            customFrom: "",
            customTo: "",
        });
        this._tabFilterGroupId = null;
        this._typeFilterGroupId = null;
        this._dateFilterGroupId = null;
    }

    get dateTabs() {
        return [
            { id: "all_dates", label: _t("All Dates") },
            { id: "today", label: _t("Today") },
            { id: "this_week", label: _t("This Week") },
            { id: "this_month", label: _t("This Month") },
        ];
    }

    _getDateDomain(dateId) {
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const fmt = (d) => d.toISOString().replace("T", " ").substring(0, 19);
        switch (dateId) {
            case "today": {
                const end = new Date(todayStart); end.setDate(end.getDate() + 1);
                return [["transaction_date", ">=", fmt(todayStart)], ["transaction_date", "<", fmt(end)]];
            }
            case "this_week": {
                const ws = new Date(todayStart); ws.setDate(ws.getDate() - ((ws.getDay() + 6) % 7));
                const we = new Date(ws); we.setDate(we.getDate() + 7);
                return [["transaction_date", ">=", fmt(ws)], ["transaction_date", "<", fmt(we)]];
            }
            case "this_month": {
                const ms = new Date(now.getFullYear(), now.getMonth(), 1);
                const me = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [["transaction_date", ">=", fmt(ms)], ["transaction_date", "<", fmt(me)]];
            }
            case "custom": {
                const out = [];
                if (this.tabState.customFrom) out.push(["transaction_date", ">=", this.tabState.customFrom + " 00:00:00"]);
                if (this.tabState.customTo) out.push(["transaction_date", "<=", this.tabState.customTo + " 23:59:59"]);
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

    get statusTabs() {
        return [
            { id: "all", label: _t("All"), icon: "fa-list" },
            { id: "collected", label: _t("Collected"), icon: "fa-check" },
            { id: "pending_delivery", label: _t("Pending Delivery"), icon: "fa-truck" },
            { id: "delivered", label: _t("Delivered"), icon: "fa-inbox" },
            { id: "reconciled", label: _t("Reconciled"), icon: "fa-check-circle" },
            { id: "failed", label: _t("Failed"), icon: "fa-times-circle" },
        ];
    }

    get typeTabs() {
        return [
            { id: "all_types", label: _t("All Types") },
            { id: "cash", label: _t("Cash") },
            { id: "bank_transfer", label: _t("Bank Transfer") },
            { id: "credit_card", label: _t("Card") },
            { id: "qr_code", label: _t("QR Code") },
            { id: "prepaid", label: _t("Prepaid") },
        ];
    }

    _getStatusDomain(tabId) {
        if (tabId === "all") return [];
        return [["status", "=", tabId]];
    }

    _getTypeDomain(typeId) {
        if (typeId === "all_types") return [];
        return [["payment_method", "=", typeId]];
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

    async setTypeFilter(typeId) {
        if (this.tabState.typeFilter === typeId) return;
        this.tabState.typeFilter = typeId;

        if (this._typeFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._typeFilterGroupId);
            this._typeFilterGroupId = null;
        }

        const domain = this._getTypeDomain(typeId);
        if (domain.length) {
            const description = this.typeTabs.find((t) => t.id === typeId)?.label || typeId;
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._typeFilterGroupId = preFilter.groupId;
        }
    }
}

export const finPaymentListView = {
    ...listView,
    Controller: FinPaymentListController,
};

registry.category("views").add("fin_payment_list_view", finPaymentListView);
