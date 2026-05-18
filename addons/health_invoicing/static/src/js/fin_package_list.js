/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useState } from "@odoo/owl";

export class FinPackageListController extends ListController {
    static template = "health_invoicing.FinPackageListView";

    setup() {
        super.setup(...arguments);
        this.tabState = useState({ activeTab: "all" });
        this._tabFilterGroupId = null;
    }

    get statusTabs() {
        return [
            { id: "all", label: "All", icon: "fa-list" },
            { id: "active", label: "Active", icon: "fa-check-circle" },
            { id: "exhausted", label: "Exhausted", icon: "fa-battery-empty" },
            { id: "expired", label: "Expired", icon: "fa-clock-o" },
            { id: "cancelled", label: "Cancelled", icon: "fa-ban" },
        ];
    }

    _getStatusDomain(tabId) {
        if (tabId === "all") return [];
        return [["state", "=", tabId]];
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
}

export const finPackageListView = {
    ...listView,
    Controller: FinPackageListController,
};

registry.category("views").add("fin_package_list_view", finPackageListView);
