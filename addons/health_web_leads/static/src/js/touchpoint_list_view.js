/** @odoo-module **/

/**
 * Web Touchpoints list — filter-chip bar.
 *
 * Direct clone of health_fieldservice/static/src/js/ops_client_list_view.js
 * (the Clients list), so the chip bar looks and behaves identically across the
 * CMS. It absorbs the retired "Campaign Review" leaf: that action was the same
 * health.lead.touchpoint model with a different domain
 * ([utm_campaign != False, lead_id.campaign_id = False] grouped by
 * utm_campaign), which is now the "Unmatched Campaigns" chip.
 *
 * NB: each chip owns exactly ONE search-model filter group and deactivates the
 * previous one before creating the next — otherwise the domains stack and the
 * list silently ANDs two chips together.
 */

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class TouchpointListController extends ListController {
    static template = "health_web_leads.TouchpointListView";

    setup() {
        super.setup(...arguments);
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
            { id: "all", label: _t("All Touchpoints"), icon: "fa-globe" },
            {
                id: "unmatched",
                label: _t("Unmatched Campaigns"),
                icon: "fa-bullhorn",
            },
            { id: "converted", label: _t("Converted"), icon: "fa-check-circle" },
            {
                id: "orphan",
                label: _t("Orphan Touches"),
                icon: "fa-question-circle",
            },
        ];
    }

    // Date filter on when the touch occurred.
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
        const todayStart = new Date(
            now.getFullYear(), now.getMonth(), now.getDate()
        );
        const fmt = (d) => d.toISOString().replace("T", " ").substring(0, 19);
        switch (dateId) {
            case "today": {
                const end = new Date(todayStart);
                end.setDate(end.getDate() + 1);
                return [
                    ["occurred_at", ">=", fmt(todayStart)],
                    ["occurred_at", "<", fmt(end)],
                ];
            }
            case "this_week": {
                const ws = new Date(todayStart);
                ws.setDate(ws.getDate() - ((ws.getDay() + 6) % 7));
                const we = new Date(ws);
                we.setDate(we.getDate() + 7);
                return [
                    ["occurred_at", ">=", fmt(ws)],
                    ["occurred_at", "<", fmt(we)],
                ];
            }
            case "this_month": {
                const ms = new Date(now.getFullYear(), now.getMonth(), 1);
                const me = new Date(now.getFullYear(), now.getMonth() + 1, 1);
                return [
                    ["occurred_at", ">=", fmt(ms)],
                    ["occurred_at", "<", fmt(me)],
                ];
            }
            case "custom": {
                const out = [];
                if (this.tabState.customFrom) {
                    out.push([
                        "occurred_at", ">=",
                        this.tabState.customFrom + " 00:00:00",
                    ]);
                }
                if (this.tabState.customTo) {
                    out.push([
                        "occurred_at", "<=",
                        this.tabState.customTo + " 23:59:59",
                    ]);
                }
                return out;
            }
            default:
                return [];
        }
    }

    async setDateFilter(dateId) {
        if (dateId !== "custom" && this.tabState.dateFilter === dateId) {
            return;
        }
        this.tabState.dateFilter = dateId;
        this._applyDateFilter();
    }

    _applyDateFilter() {
        if (this._dateFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._dateFilterGroupId);
            this._dateFilterGroupId = null;
        }
        const dateId = this.tabState.dateFilter;
        if (dateId === "all_dates") {
            return;
        }
        const domain = this._getDateDomain(dateId);
        if (!domain.length) {
            return;
        }
        const label = dateId === "custom"
            ? _t("Occurred %s → %s",
                this.tabState.customFrom || "…",
                this.tabState.customTo || "…")
            : (this.dateTabs.find((t) => t.id === dateId)?.label || dateId);
        const preFilter = { description: label, domain };
        this.env.searchModel.createNewFilters([preFilter]);
        this._dateFilterGroupId = preFilter.groupId;
    }

    onCustomDate(which, ev) {
        this.tabState[which === "from" ? "customFrom" : "customTo"] =
            ev.target.value;
        this.tabState.dateFilter = "custom";
        this._applyDateFilter();
    }

    async setTab(tabId) {
        if (this.tabState.activeTab === tabId) {
            return;
        }
        this.tabState.activeTab = tabId;

        if (this._tabFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._tabFilterGroupId);
            this._tabFilterGroupId = null;
        }

        if (tabId !== "all") {
            let domain;
            let description;
            switch (tabId) {
                case "unmatched":
                    // Was the standalone "Campaign Review" action.
                    domain = [
                        ["utm_campaign", "!=", false],
                        ["lead_id.campaign_id", "=", false],
                    ];
                    description = _t("Unmatched Campaigns");
                    break;
                case "converted":
                    domain = [["lead_id", "!=", false]];
                    description = _t("Converted");
                    break;
                case "orphan":
                    domain = [["lead_id", "=", false]];
                    description = _t("Orphan Touches");
                    break;
            }
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._tabFilterGroupId = preFilter.groupId;
        }
    }
}

export const touchpointListView = {
    ...listView,
    Controller: TouchpointListController,
};

registry.category("views").add("touchpoint_list_view", touchpointListView);
