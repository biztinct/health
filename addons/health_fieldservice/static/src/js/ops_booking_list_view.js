/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";

export class OpsBookingListController extends ListController {
    static template = "health_fieldservice.OpsBookingListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.tabState = useState({
            activeTab: "all",
            dateFilter: "all_dates",
            needsStaffCount: 0,
        });
        this._tabFilterGroupId = null;
        this._dateFilterGroupId = null;

        onWillStart(async () => {
            await this._loadNeedsStaffCount();
        });
    }

    async _loadNeedsStaffCount() {
        try {
            const count = await this.orm.searchCount("health.fieldservice.order", [
                ['has_staff_assigned', '=', false],
                ['state', 'in', ['draft', 'confirmed']],
            ]);
            this.tabState.needsStaffCount = count;
        } catch (e) { /* ignore */ }
    }

    get statusTabs() {
        return [
            { id: "all", label: "All", icon: "fa-list" },
            { id: "needs_staff", label: "Needs Staff", icon: "fa-user-plus", count: this.tabState.needsStaffCount },
            { id: "active", label: "Active", icon: "fa-play-circle" },
            { id: "completed", label: "Completed", icon: "fa-check-circle" },
            { id: "issues", label: "Issues", icon: "fa-exclamation-triangle" },
        ];
    }

    get dateTabs() {
        return [
            { id: "all_dates", label: "All Dates" },
            { id: "today", label: "Today" },
            { id: "tomorrow", label: "Tomorrow" },
            { id: "this_week", label: "This Week" },
            { id: "overdue", label: "Overdue" },
        ];
    }

    _getStatusDomain(tabId) {
        switch (tabId) {
            case "needs_staff":
                return [['has_staff_assigned', '=', false], ['state', 'in', ['draft', 'confirmed']]];
            case "active":
                return [['state', '=', 'in_progress']];
            case "completed":
                return [['state', 'in', ['completed', 'completed_pending_invoice']]];
            case "issues":
                return ['|', ['state', '=', 'cancelled'], ['priority', '>=', '3']];
            default:
                return [['state', '!=', 'cancelled']];
        }
    }

    _getDateDomain(dateId) {
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const todayEnd = new Date(todayStart);
        todayEnd.setDate(todayEnd.getDate() + 1);

        const fmt = (d) => d.toISOString().replace('T', ' ').substring(0, 19);

        switch (dateId) {
            case "today":
                return [
                    ['scheduled_datetime', '>=', fmt(todayStart)],
                    ['scheduled_datetime', '<', fmt(todayEnd)],
                ];
            case "tomorrow": {
                const tmrStart = new Date(todayStart);
                tmrStart.setDate(tmrStart.getDate() + 1);
                const tmrEnd = new Date(tmrStart);
                tmrEnd.setDate(tmrEnd.getDate() + 1);
                return [
                    ['scheduled_datetime', '>=', fmt(tmrStart)],
                    ['scheduled_datetime', '<', fmt(tmrEnd)],
                ];
            }
            case "this_week": {
                const weekEnd = new Date(todayStart);
                weekEnd.setDate(weekEnd.getDate() + 7);
                return [
                    ['scheduled_datetime', '>=', fmt(todayStart)],
                    ['scheduled_datetime', '<', fmt(weekEnd)],
                ];
            }
            case "overdue":
                return [
                    ['scheduled_datetime', '<', fmt(now)],
                    ['state', 'not in', ['completed', 'completed_pending_invoice', 'cancelled']],
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
        const description = this.statusTabs.find(t => t.id === tabId)?.label || tabId;
        const preFilter = { description, domain };
        this.env.searchModel.createNewFilters([preFilter]);
        this._tabFilterGroupId = preFilter.groupId;
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
            const description = this.dateTabs.find(t => t.id === dateId)?.label || dateId;
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._dateFilterGroupId = preFilter.groupId;
        }
    }

    _getPatientIdFromAction() {
        const ctx = this.props.context || {};
        if (ctx.default_patient_id) return ctx.default_patient_id;
        const domain = this.props.domain || [];
        for (const leaf of domain) {
            if (Array.isArray(leaf) && leaf[0] === 'patient_id' && leaf[1] === '=' && leaf[2]) {
                return leaf[2];
            }
        }
        return false;
    }

    async onClickCreate() {
        const patientId = this._getPatientIdFromAction();
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'ops_quick_booking',
            name: 'Create Booking',
            target: 'current',
            context: { default_patient_id: patientId },
            params: { default_patient_id: patientId },
        });
    }

    openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "health.fieldservice.order",
            res_id: record.resId,
            views: [[false, "form"]],
            target: "current",
            context: { form_view_ref: "health_fieldservice.view_health_fso_form_ops" },
        });
    }
}

export const opsBookingListView = {
    ...listView,
    Controller: OpsBookingListController,
};

registry.category("views").add("ops_booking_list_view", opsBookingListView);
