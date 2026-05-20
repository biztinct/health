/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart, onMounted } from "@odoo/owl";

export class CrmContactListController extends ListController {
    static template = "health_crm.CrmContactListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.tabState = useState({
            activeTab: "all",
            dateFilter: "today",
            followupCount: 0,
        });
        this._tabFilterGroupId = null;
        this._dateFilterGroupId = null;
        this._initialFilterApplied = false;

        onWillStart(async () => {
            await this._loadFollowupCount();
        });

        onMounted(() => {
            if (!this._initialFilterApplied) {
                this._initialFilterApplied = true;
                this._applyInitialDateFilter();
            }
        });
    }

    async _loadFollowupCount() {
        try {
            const count = await this.orm.searchCount("crm.lead", [
                ["contact_status", "=", "lead"],
            ]);
            this.tabState.followupCount = count;
        } catch (_e) { /* ignore */ }
    }

    get statusTabs() {
        return [
            { id: "all", label: "All", icon: "fa-list" },
            { id: "active", label: "Active", icon: "fa-phone" },
            { id: "leads", label: "Leads", icon: "fa-bullseye", count: this.tabState.followupCount },
            { id: "bookings", label: "Bookings", icon: "fa-calendar-check-o" },
            { id: "lost", label: "Lost", icon: "fa-times-circle" },
            { id: "spam", label: "Spam", icon: "fa-ban" },
        ];
    }

    get dateTabs() {
        return [
            { id: "all_dates", label: "All Dates" },
            { id: "today", label: "Today" },
            { id: "this_week", label: "This Week" },
            { id: "this_month", label: "This Month" },
            { id: "overdue", label: "Overdue" },
        ];
    }

    _getStatusDomain(tabId) {
        switch (tabId) {
            case "active":
                return [["contact_status", "=", "active"]];
            case "leads":
                return [["contact_status", "=", "lead"]];
            case "bookings":
                return [["contact_status", "=", "booking"]];
            case "lost":
                return [["contact_status", "=", "lost_booking"]];
            case "spam":
                return [["contact_status", "=", "spam"]];
            default:
                return [];
        }
    }

    _getDateDomain(dateId) {
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const todayEnd = new Date(todayStart);
        todayEnd.setDate(todayEnd.getDate() + 1);
        const fmt = (d) => d.toISOString().replace("T", " ").substring(0, 19);

        switch (dateId) {
            case "today":
                return [
                    ["create_date", ">=", fmt(todayStart)],
                    ["create_date", "<", fmt(todayEnd)],
                ];
            case "this_week": {
                const weekStart = new Date(todayStart);
                weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1);
                const weekEnd = new Date(weekStart);
                weekEnd.setDate(weekEnd.getDate() + 7);
                return [
                    ["create_date", ">=", fmt(weekStart)],
                    ["create_date", "<", fmt(weekEnd)],
                ];
            }
            case "this_month": {
                const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
                const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [
                    ["create_date", ">=", fmt(monthStart)],
                    ["create_date", "<", fmt(monthEnd)],
                ];
            }
            case "overdue":
                return [
                    ["next_follow_up_date", "<", fmt(now)],
                    ["contact_status", "=", "lead"],
                ];
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
        if (this.tabState.dateFilter === dateId) return;
        this.tabState.dateFilter = dateId;

        if (this._dateFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._dateFilterGroupId);
            this._dateFilterGroupId = null;
        }

        if (dateId !== "all_dates") {
            const domain = this._getDateDomain(dateId);
            const description = this.dateTabs.find((t) => t.id === dateId)?.label || dateId;
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._dateFilterGroupId = preFilter.groupId;
        }
    }

    _applyInitialDateFilter() {
        if (this.env.searchModel.query && this.env.searchModel.query.length > 0) return;
        const domain = this._getDateDomain("today");
        const preFilter = { description: "Today", domain };
        this.env.searchModel.createNewFilters([preFilter]);
        this._dateFilterGroupId = preFilter.groupId;
    }

    openNewContact() {
        this.actionService.doAction("health_crm.action_crm_new_contact", {
            clearBreadcrumbs: true,
        });
    }
}

export const crmContactListView = {
    ...listView,
    Controller: CrmContactListController,
};

registry.category("views").add("crm_contact_list_view", crmContactListView);
