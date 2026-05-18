/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class FinPaymentListController extends ListController {
    static template = "health_invoicing.FinPaymentListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabState = useState({
            activeTab: "all",
            typeFilter: "all_types",
        });
        this._tabFilterGroupId = null;
        this._typeFilterGroupId = null;
    }

    get statusTabs() {
        return [
            { id: "all", label: "All", icon: "fa-list" },
            { id: "collected", label: "Collected", icon: "fa-check" },
            { id: "pending_delivery", label: "Pending Delivery", icon: "fa-truck" },
            { id: "delivered", label: "Delivered", icon: "fa-inbox" },
            { id: "reconciled", label: "Reconciled", icon: "fa-check-circle" },
            { id: "failed", label: "Failed", icon: "fa-times-circle" },
        ];
    }

    get typeTabs() {
        return [
            { id: "all_types", label: "All Types" },
            { id: "cash", label: "Cash" },
            { id: "bank_transfer", label: "Bank Transfer" },
            { id: "credit_card", label: "Card" },
            { id: "qr_code", label: "QR Code" },
            { id: "prepaid", label: "Prepaid" },
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
