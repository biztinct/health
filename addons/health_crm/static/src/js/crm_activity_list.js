/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class CrmActivityListController extends ListController {
    static template = "health_crm.CrmActivityListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabState = useState({
            activeType: "all",
            dateFilter: "all_dates",
        });
        this._typeFilterGroupId = null;
        this._dateFilterGroupId = null;
    }

    get typeTabs() {
        return [
            { id: "all", label: "All Activities", icon: "fa-list" },
            { id: "call", label: "Call", icon: "fa-phone" },
            { id: "meeting", label: "Meeting", icon: "fa-users" },
            { id: "todo", label: "To-Do", icon: "fa-check-circle" },
            { id: "email", label: "Email", icon: "fa-envelope" },
            { id: "escalated", label: "Escalated", icon: "fa-exclamation-triangle" },
        ];
    }

    get dateTabs() {
        return [
            { id: "all_dates", label: "All Dates" },
            { id: "overdue", label: "Overdue" },
            { id: "today", label: "Today" },
            { id: "this_week", label: "This Week" },
            { id: "this_month", label: "This Month" },
        ];
    }

    _getTypeDomain(typeId) {
        switch (typeId) {
            case "call":
                return [["calendar_display_name", "ilike", "Call"]];
            case "meeting":
                return [["calendar_display_name", "ilike", "Meeting"]];
            case "todo":
                return [
                    ["calendar_display_name", "ilike", "To-Do"],
                    "!", ["activity_ids.summary", "ilike", "Escalated"],
                ];
            case "email":
                return [["calendar_display_name", "ilike", "Email"]];
            case "escalated":
                return [["activity_ids.summary", "ilike", "Escalated"]];
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
            case "overdue":
                return [["calendar_date", "<", fmt(todayStart)]];
            case "today":
                return [
                    ["calendar_date", ">=", fmt(todayStart)],
                    ["calendar_date", "<", fmt(todayEnd)],
                ];
            case "this_week": {
                const weekStart = new Date(todayStart);
                weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1);
                const weekEnd = new Date(weekStart);
                weekEnd.setDate(weekEnd.getDate() + 7);
                return [
                    ["calendar_date", ">=", fmt(weekStart)],
                    ["calendar_date", "<", fmt(weekEnd)],
                ];
            }
            case "this_month": {
                const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
                const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [
                    ["calendar_date", ">=", fmt(monthStart)],
                    ["calendar_date", "<", fmt(monthEnd)],
                ];
            }
            default:
                return [];
        }
    }

    async setTypeTab(typeId) {
        if (this.tabState.activeType === typeId) return;
        this.tabState.activeType = typeId;

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

    switchToActivityView() {
        this.actionService.doAction("health_crm.action_crm_activity_list", {
            clearBreadcrumbs: true,
            viewType: "activity",
        });
    }
}

export const crmActivityListView = {
    ...listView,
    Controller: CrmActivityListController,
};

registry.category("views").add("crm_activity_list_view", crmActivityListView);
