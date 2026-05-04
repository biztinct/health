/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * ReportCanvas — Dashboard layout with GridStack.
 * 
 * Displays multiple chart widgets in a drag-resize grid.
 * Supports global filters, auto-refresh, and export.
 */
export class ReportCanvas extends Component {
    static template = "bi_studio.ReportCanvas";
    static components = { ChartRenderer };
    static props = {
        action: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action_service = useService("action");

        const params = this.props.action?.params || {};
        this.gridRef = useRef("grid");
        this.gridInstance = null;
        this._refreshTimer = null;

        this.state = useState({
            loading: true,
            reportId: params.report_id || null,
            reportName: "",
            theme: "light",
            visuals: [],
            autoRefresh: false,
            refreshInterval: 300,
            allowExport: true,
            isEditMode: false,
        });

        onMounted(() => this._loadReport());
        onWillUnmount(() => this._cleanup());
    }

    // =========================================================================
    // Load Report
    // =========================================================================

    async _loadReport() {
        if (!this.state.reportId) {
            this.state.loading = false;
            return;
        }

        try {
            const data = await this.orm.call("bi.report.page", "get_report_data",
                [this.state.reportId]);

            if (data.error) {
                this.notification.add(data.error, { type: "danger" });
                this.state.loading = false;
                return;
            }

            this.state.reportName = data.name || "";
            this.state.theme = data.theme || "light";
            this.state.visuals = data.visuals || [];
            this.state.autoRefresh = data.auto_refresh || false;
            this.state.refreshInterval = data.refresh_interval || 300;
            this.state.allowExport = data.allow_export !== false;

            // Wait for DOM to render
            await new Promise(r => setTimeout(r, 100));
            this._initGridStack();

            // Auto refresh
            if (this.state.autoRefresh) {
                this._startAutoRefresh();
            }
        } catch (e) {
            console.error("Report load error:", e);
            this.notification.add(_t("Error loading dashboard"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // =========================================================================
    // GridStack
    // =========================================================================

    _initGridStack() {
        if (!this.gridRef.el || typeof GridStack === "undefined") return;

        this.gridInstance = GridStack.init({
            column: 12,
            cellHeight: 80,
            margin: 8,
            animate: true,
            float: false,
            disableResize: !this.state.isEditMode,
            disableDrag: !this.state.isEditMode,
        }, this.gridRef.el);

        // Save on change
        this.gridInstance.on("change", () => {
            if (this.state.isEditMode) {
                this._saveLayout();
            }
        });
    }

    _updateGridEditMode() {
        if (!this.gridInstance) return;
        if (this.state.isEditMode) {
            this.gridInstance.enable();
        } else {
            this.gridInstance.disable();
        }
    }

    async _saveLayout() {
        if (!this.gridInstance || !this.state.reportId) return;

        const items = this.gridInstance.getGridItems().map(el => {
            const node = el.gridstackNode;
            return {
                id: el.getAttribute("gs-id"),
                x: node.x,
                y: node.y,
                w: node.w,
                h: node.h,
            };
        });

        try {
            await this.orm.call("bi.report.page", "save_grid_layout",
                [this.state.reportId], { layout: items });
        } catch (e) {
            console.error("Layout save error:", e);
        }
    }

    // =========================================================================
    // Auto Refresh
    // =========================================================================

    _startAutoRefresh() {
        this._stopAutoRefresh();
        this._refreshTimer = setInterval(async () => {
            await this._refreshAllVisuals();
        }, this.state.refreshInterval * 1000);
    }

    _stopAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
            this._refreshTimer = null;
        }
    }

    async _refreshAllVisuals() {
        try {
            const data = await this.orm.call("bi.report.page", "get_report_data",
                [this.state.reportId]);
            if (data.visuals) {
                this.state.visuals = data.visuals;
            }
        } catch (e) {
            console.error("Refresh error:", e);
        }
    }

    // =========================================================================
    // Actions
    // =========================================================================

    toggleEditMode() {
        this.state.isEditMode = !this.state.isEditMode;
        this._updateGridEditMode();
    }

    async addVisual() {
        // Open visual designer to create a new visual
        if (!this.state.reportId) return;

        // Get available datasets
        const report = await this.orm.read("bi.report.page", [this.state.reportId],
            ["dataset_ids"]);
        const datasetIds = report[0]?.dataset_ids || [];

        if (!datasetIds.length) {
            this.notification.add(_t("Add datasets to this report first"), {
                type: "warning",
            });
            return;
        }

        this.action_service.doAction({
            type: "ir.actions.client",
            tag: "bi_studio.visual_designer",
            params: {
                dataset_id: datasetIds[0],
                report_id: this.state.reportId,
            },
        });
    }

    async refreshDashboard() {
        this.state.loading = true;
        await this._refreshAllVisuals();
        this.state.loading = false;
        this.notification.add(_t("Dashboard refreshed"), { type: "info" });
    }

    goBack() {
        this.action_service.doAction({
            type: "ir.actions.act_window",
            res_model: "bi.report.page",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openVisualSettings(visualId) {
        this.action_service.doAction({
            type: "ir.actions.client",
            tag: "bi_studio.visual_designer",
            params: {
                visual_id: visualId,
            },
        });
    }

    _cleanup() {
        this._stopAutoRefresh();
        if (this.gridInstance) {
            this.gridInstance.destroy(false);
            this.gridInstance = null;
        }
    }
}

registry.category("actions").add("bi_studio.report_canvas", ReportCanvas);
