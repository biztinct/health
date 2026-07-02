/** @odoo-module **/

import { registry } from "@web/core/registry";
import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "../explore/chart_renderer";
import { KpiCard } from "../explore/kpi_card";
import { DataTable } from "../explore/data_table";

const MIN_SIZES = {
    kpi: { minW: 2, minH: 2 },
    table: { minW: 4, minH: 3 },
    default: { minW: 3, minH: 3 },
};

export class DashboardAction extends Component {
    static template = "biz_bi.Dashboard";
    static components = { ChartRenderer, KpiCard, DataTable };
    static props = { "*": true };
    static displayName = _t("Dashboard");

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.biData = useService("bi_data");
        this.biFilter = useService("bi_filter");

        this.gridRef = useRef("grid");
        this.grid = null;
        this._refreshTimer = null;

        this.state = useState({
            dashboard: null,
            envelopes: {}, // widgetId -> envelope
            editMode: false,
            tvMode: false,
            loading: true,
            openMenu: null,
        });

        onWillStart(async () => {
            const params = this.props.action?.params || {};
            this.dashboardId =
                params.dashboard_id || params.active_id || null;
            if (!this.dashboardId) {
                const [first] = await this.orm.search("bi.dashboard", [], { limit: 1 });
                this.dashboardId = first;
            }
            if (this.dashboardId) {
                await this.loadDashboard();
            }
            if (params.mode === "tv") {
                this.state.tvMode = true;
            }
        });

        onMounted(() => {
            this.initGrid();
            this.loadAllWidgetData();
            this.setupTvRefresh();
        });

        onWillUnmount(() => {
            clearInterval(this._refreshTimer);
            if (this.grid) {
                this.grid.destroy(false);
            }
        });
    }

    async loadDashboard() {
        this.state.dashboard = await this.orm.call(
            "bi.dashboard", "get_dashboard_data", [[this.dashboardId]]);
        // apply filter defaults
        for (const filter of this.state.dashboard.filters) {
            if (filter.default && filter.default.op) {
                this.biFilter.setGlobalFilter(filter.id, {
                    op: filter.default.op,
                    value: filter.default.value,
                });
            }
        }
    }

    // ------------------------------------------------------------------
    // GridStack: flexible canvas — dashed placeholder + live auto-reflow
    // ------------------------------------------------------------------

    initGrid() {
        if (!this.gridRef.el || !this.state.dashboard) {
            return;
        }
        /* global GridStack */
        this.grid = GridStack.init(
            {
                column: 12,
                cellHeight: 76,
                margin: 8,
                float: false, // auto-compact: neighbors slide to make room
                animate: true,
                resizable: { handles: "all" },
                disableDrag: !this.state.editMode,
                disableResize: !this.state.editMode,
            },
            this.gridRef.el
        );
        this.grid.on("change", () => this.persistLayout());
        this.grid.on("resizestop", (event, el) => {
            // charts re-render crisply at the new size via ResizeObserver;
            // nothing else to do — observer lives in ChartRenderer
        });
    }

    toggleEdit() {
        this.state.editMode = !this.state.editMode;
        if (this.grid) {
            this.grid.enableMove(this.state.editMode);
            this.grid.enableResize(this.state.editMode);
        }
    }

    async persistLayout() {
        if (!this.grid || !this.state.editMode) {
            return;
        }
        const layout = this.grid.engine.nodes.map((node) => ({
            widget_id: parseInt(node.el.dataset.widgetId),
            x: node.x,
            y: node.y,
            w: node.w,
            h: node.h,
        }));
        await this.orm.call("bi.dashboard", "save_layout",
            [[this.dashboardId], layout]);
    }

    minSize(widget) {
        return MIN_SIZES[widget.chart_type] || MIN_SIZES.default;
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------

    async loadAllWidgetData({ noCache = false } = {}) {
        const dashboard = this.state.dashboard;
        if (!dashboard || !dashboard.widgets.length) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        const requests = dashboard.widgets.map((widget) => ({
            chart_id: widget.chart_id,
            extra_filters: this.biFilter.extraFiltersFor(
                widget.dataset_id, dashboard.filters),
        }));
        try {
            const results = await this.biData.queryBatch(requests, { noCache });
            dashboard.widgets.forEach((widget, index) => {
                this.state.envelopes[widget.id] = results[index];
            });
        } finally {
            this.state.loading = false;
        }
    }

    setupTvRefresh() {
        const dashboard = this.state.dashboard;
        if (dashboard && dashboard.refresh_seconds >= 30) {
            this._refreshTimer = setInterval(() => {
                if (this.state.tvMode) {
                    this.loadAllWidgetData({ noCache: true });
                }
            }, dashboard.refresh_seconds * 1000);
        }
    }

    // ------------------------------------------------------------------
    // Global filters
    // ------------------------------------------------------------------

    onListFilterChange(filter, ev) {
        const raw = ev.target.value;
        const values = raw ? raw.split(",").map((v) => v.trim()).filter(Boolean) : "";
        this.onFilterChange(filter, "in", values);
    }

    onFilterChange(filter, op, value) {
        if (value === "" || value === null || value === undefined) {
            this.biFilter.setGlobalFilter(filter.id, null);
        } else {
            this.biFilter.setGlobalFilter(filter.id, { op, value });
        }
        this.loadAllWidgetData();
    }

    activeFilterValue(filter) {
        const active = this.biFilter.state.globalFilters[filter.id];
        return active ? active.value : "";
    }

    clearFilters() {
        this.biFilter.clearAll();
        this.loadAllWidgetData();
    }

    // ------------------------------------------------------------------
    // Widget actions
    // ------------------------------------------------------------------

    rendererFor(widget) {
        if (widget.chart_type === "kpi") {
            return "kpi";
        }
        if (widget.chart_type === "table") {
            return "table";
        }
        return "chart";
    }

    widgetConfig(widget) {
        return {
            chart_type: widget.chart_type,
            display: (widget.config && widget.config.display) || {},
        };
    }

    freshness(widget) {
        const envelope = this.state.envelopes[widget.id];
        if (!envelope || envelope.error || !envelope.meta) {
            return null;
        }
        const at = new Date(envelope.meta.freshness_at + "Z");
        const minutes = Math.max(0, Math.round((Date.now() - at) / 60000));
        return {
            label: minutes < 1 ? _t("just now") : _t("%s min ago", minutes),
            stale: minutes > 120,
            source: envelope.meta.source,
        };
    }

    toggleMenu(widgetId) {
        this.state.openMenu = this.state.openMenu === widgetId ? null : widgetId;
    }

    editWidget(widget) {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_bi.explore",
            params: { chart_id: widget.chart_id },
        });
    }

    async removeWidget(widget) {
        await this.orm.unlink("bi.dashboard.widget", [widget.id]);
        await this.reloadFull();
    }

    async duplicateWidget(widget) {
        const chartId = await this.orm.call(
            "bi.chart", "action_duplicate", [[widget.chart_id]]);
        await this.orm.call("bi.dashboard", "add_chart",
            [[this.dashboardId], chartId.id || chartId]);
        await this.reloadFull();
    }

    exportWidgetCsv(widget) {
        const envelope = this.state.envelopes[widget.id];
        if (!envelope || envelope.error) {
            return;
        }
        const header = envelope.columns.map((c) => `"${c.label}"`).join(",");
        const body = envelope.rows
            .map((row) => row.map((v) => (v === null ? "" : `"${v}"`)).join(","))
            .join("\n");
        const blob = new Blob([header + "\n" + body], { type: "text/csv" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `${widget.title}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    async reloadFull() {
        // structural change: rebuild the grid DOM cleanly
        if (this.grid) {
            this.grid.destroy(false);
            this.grid = null;
        }
        await this.loadDashboard();
        // let OWL re-render the item list before re-initializing
        await new Promise((resolve) => setTimeout(resolve));
        this.initGrid();
        await this.loadAllWidgetData();
    }

    // ------------------------------------------------------------------
    // TV mode
    // ------------------------------------------------------------------

    enterTv() {
        this.state.tvMode = true;
        this.state.editMode = false;
        if (this.grid) {
            this.grid.enableMove(false);
            this.grid.enableResize(false);
        }
        document.documentElement.requestFullscreen?.();
    }

    exitTv() {
        this.state.tvMode = false;
        document.exitFullscreen?.();
    }
}

registry.category("actions").add("biz_bi.dashboard", DashboardAction);
