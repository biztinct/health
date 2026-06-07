/** @odoo-module **/

import { ActivityController } from "@mail/views/web/activity/activity_controller";
import { activityView } from "@mail/views/web/activity/activity_view";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";

export class CrmActivityController extends ActivityController {
    static template = "health_crm.CrmActivityView";

    setup() {
        super.setup(...arguments);
        this.filterState = useState({
            activeType: "all",
            activeDateFilter: "all",
            showDatePicker: false,
        });
        this._dateFilterGroupId = null;
    }

    get typeFilters() {
        return [
            { id: "all", label: _t("All"), icon: "fa-th-large" },
            { id: "todo", label: _t("To-Do"), icon: "fa-check-square-o" },
            { id: "email", label: _t("Email"), icon: "fa-envelope-o" },
            { id: "call", label: _t("Call"), icon: "fa-phone" },
            { id: "meeting", label: _t("Meeting"), icon: "fa-users" },
        ];
    }

    get dateFilters() {
        return [
            { id: "all", label: _t("All Dates") },
            { id: "today", label: _t("Today") },
            { id: "week", label: _t("This Week") },
            { id: "month", label: _t("This Month") },
        ];
    }

    get rendererProps() {
        const props = super.rendererProps;
        if (this.filterState.activeType === "all") {
            return props;
        }
        const typeNameMap = {
            todo: "To-Do",
            email: "Email",
            call: "Call",
            meeting: "Meeting",
        };
        const filterName = typeNameMap[this.filterState.activeType];
        if (!filterName) {
            return props;
        }

        props.activityTypes = props.activityTypes.filter(
            (t) => t.name === filterName
        );
        const allowedTypeIds = new Set(props.activityTypes.map((t) => t.id));

        const filteredGrouped = {};
        for (const resId in props.groupedActivities) {
            const byType = props.groupedActivities[resId];
            const filtered = {};
            for (const typeId in byType) {
                if (allowedTypeIds.has(parseInt(typeId))) {
                    filtered[typeId] = byType[typeId];
                }
            }
            if (Object.keys(filtered).length > 0) {
                filteredGrouped[resId] = filtered;
            }
        }
        props.groupedActivities = filteredGrouped;

        const validResIds = new Set(
            Object.keys(filteredGrouped).map(Number)
        );
        props.activityResIds = props.activityResIds.filter((id) =>
            validResIds.has(id)
        );
        props.records = props.records.filter((r) =>
            validResIds.has(r.resId)
        );

        return props;
    }

    setTypeFilter(typeId) {
        this.filterState.activeType = typeId;
    }

    async setDateFilter(dateId) {
        if (this.filterState.activeDateFilter === dateId) return;
        this.filterState.activeDateFilter = dateId;
        this.filterState.showDatePicker = false;

        if (this._dateFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._dateFilterGroupId);
            this._dateFilterGroupId = null;
        }

        if (dateId === "all") return;

        const today = new Date();
        let domain;
        let description;

        if (dateId === "today") {
            const todayStr = today.toISOString().slice(0, 10);
            domain = [["activity_date_deadline", "=", todayStr]];
            description = _t("Today");
        } else if (dateId === "week") {
            const dow = today.getDay();
            const weekStart = new Date(today);
            weekStart.setDate(today.getDate() - (dow === 0 ? 6 : dow - 1));
            const weekEnd = new Date(weekStart);
            weekEnd.setDate(weekStart.getDate() + 6);
            domain = [
                ["activity_date_deadline", ">=", weekStart.toISOString().slice(0, 10)],
                ["activity_date_deadline", "<=", weekEnd.toISOString().slice(0, 10)],
            ];
            description = _t("This Week");
        } else if (dateId === "month") {
            const monthStart = today.toISOString().slice(0, 8) + "01";
            domain = [["activity_date_deadline", ">=", monthStart]];
            description = _t("This Month");
        }

        if (domain) {
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._dateFilterGroupId = preFilter.groupId;
        }
    }

    toggleDatePicker() {
        this.filterState.showDatePicker = !this.filterState.showDatePicker;
    }

    onDateSelected(ev) {
        const selectedDate = ev.target.value;
        if (!selectedDate) return;

        this.filterState.activeDateFilter = "custom";
        this.filterState.showDatePicker = false;

        if (this._dateFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._dateFilterGroupId);
            this._dateFilterGroupId = null;
        }

        const preFilter = {
            description: selectedDate,
            domain: [["activity_date_deadline", "=", selectedDate]],
        };
        this.env.searchModel.createNewFilters([preFilter]);
        this._dateFilterGroupId = preFilter.groupId;
    }
}

export const crmActivityView = {
    ...activityView,
    Controller: CrmActivityController,
};

registry.category("views").add("crm_activity_view", crmActivityView);
