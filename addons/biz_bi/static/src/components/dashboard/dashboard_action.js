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
import { PivotTable } from "../explore/pivot_table";

const MIN_SIZES = {
    kpi: { minW: 2, minH: 2 },
    table: { minW: 4, minH: 3 },
    default: { minW: 3, minH: 3 },
};

// drill ladder: each date-bucket click zooms one level deeper
const GRAIN_LADDER = { year: "quarter", quarter: "month", month: "day", week: "day" };

function bucketEnd(startIso, grain) {
    const date = new Date(startIso);
    switch (grain) {
        case "year": date.setUTCFullYear(date.getUTCFullYear() + 1); break;
        case "quarter": date.setUTCMonth(date.getUTCMonth() + 3); break;
        case "month": date.setUTCMonth(date.getUTCMonth() + 1); break;
        case "week": date.setUTCDate(date.getUTCDate() + 7); break;
        default: date.setUTCDate(date.getUTCDate() + 1);
    }
    return date.toISOString().slice(0, 19).replace("T", " ");
}

export class DashboardAction extends Component {
    static template = "biz_bi.Dashboard";
    static components = { ChartRenderer, KpiCard, DataTable, PivotTable };
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
            compareEnvelopes: {}, // widgetId -> previous-period envelope
            crossFilter: null, // {widgetId, datasetId, fieldId, value, label}
            drillPaths: {}, // widgetId -> [{fieldId, grain, start, end, label}]
            insights: null, // {widgetTitle, findings, narration, loading}
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

    _widgetExtraFilters(widget) {
        const extra = this.biFilter.extraFiltersFor(
            widget.dataset_id, this.state.dashboard.filters);
        const cross = this.state.crossFilter;
        if (cross && cross.datasetId === widget.dataset_id
                && cross.widgetId !== widget.id) {
            extra.push({ field_id: cross.fieldId, op: cross.op || "eq",
                         value: cross.value });
        }
        for (const level of this.state.drillPaths[widget.id] || []) {
            extra.push({ field_id: level.fieldId, op: "date_range",
                         value: [level.start, level.end] });
        }
        return extra;
    }

    _widgetGrainOverrides(widget) {
        const path = this.state.drillPaths[widget.id];
        if (!path || !path.length) {
            return undefined;
        }
        const last = path[path.length - 1];
        return { [last.fieldId]: GRAIN_LADDER[last.grain] || "day" };
    }

    async loadAllWidgetData({ noCache = false } = {}) {
        const dashboard = this.state.dashboard;
        if (!dashboard || !dashboard.widgets.length) {
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        const requests = [];
        const mapping = []; // {widgetId, kind: 'main'|'compare'}
        for (const widget of dashboard.widgets) {
            const extra = this._widgetExtraFilters(widget);
            requests.push({ chart_id: widget.chart_id, extra_filters: extra,
                            grain_overrides: this._widgetGrainOverrides(widget) });
            mapping.push({ widgetId: widget.id, kind: "main" });
            if (widget.chart_type === "kpi") {
                requests.push({ chart_id: widget.chart_id,
                                extra_filters: extra, compare: true });
                mapping.push({ widgetId: widget.id, kind: "compare" });
            }
        }
        try {
            const results = await this.biData.queryBatch(requests, { noCache });
            results.forEach((result, index) => {
                const target = mapping[index];
                if (target.kind === "main") {
                    this.state.envelopes[target.widgetId] = result;
                } else {
                    this.state.compareEnvelopes[target.widgetId] =
                        result && !result.skipped && !result.error
                            ? result : null;
                }
            });
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Cross-filtering: click a datapoint, filter sibling widgets
    // ------------------------------------------------------------------

    onDatapointClick(widget, payload) {
        const column = payload.dimColumn;
        if (!column || payload.rawValue === undefined
                || payload.rawValue === null) {
            return;
        }
        // date buckets: drill the source widget one grain deeper AND focus
        // sibling widgets on the same bucket (pill mirrors the breadcrumb)
        if (column.grain || column.type === "date"
                || column.type === "datetime") {
            const grain = column.grain || "day";
            if (!GRAIN_LADDER[grain]) {
                return; // day level — nothing deeper
            }
            const path = this.state.drillPaths[widget.id] || [];
            path.push({
                fieldId: column.field_id,
                grain,
                start: payload.rawValue,
                end: bucketEnd(payload.rawValue, grain),
                label: payload.category,
            });
            this.state.drillPaths[widget.id] = path;
            this._syncDateCrossFilter(widget);
            this.loadAllWidgetData();
            return;
        }
        const cross = this.state.crossFilter;
        if (cross && cross.widgetId === widget.id
                && cross.value === payload.rawValue) {
            this.state.crossFilter = null; // click again to clear
        } else {
            this.state.crossFilter = {
                widgetId: widget.id,
                datasetId: widget.dataset_id,
                fieldId: column.field_id,
                value: payload.rawValue,
                label: `${column.label}: ${payload.category}`,
            };
        }
        this.loadAllWidgetData();
    }

    clearCrossFilter() {
        this.state.crossFilter = null;
        this.loadAllWidgetData();
    }

    drillTo(widget, levelIndex) {
        // levelIndex -1 = reset to top
        const path = this.state.drillPaths[widget.id] || [];
        this.state.drillPaths[widget.id] = path.slice(0, levelIndex + 1);
        this._syncDateCrossFilter(widget);
        this.loadAllWidgetData();
    }

    /** The date pill mirrors the deepest breadcrumb of the drilled widget. */
    _syncDateCrossFilter(widget) {
        const cross = this.state.crossFilter;
        const ownsCross = cross && cross.widgetId === widget.id
            && cross.op === "date_range";
        const path = this.state.drillPaths[widget.id] || [];
        if (!path.length) {
            if (ownsCross) {
                this.state.crossFilter = null;
            }
            return;
        }
        const deepest = path[path.length - 1];
        if (cross && !ownsCross && cross.op !== "date_range") {
            return; // don't clobber an active category cross-filter
        }
        this.state.crossFilter = {
            widgetId: widget.id,
            datasetId: widget.dataset_id,
            fieldId: deepest.fieldId,
            op: "date_range",
            value: [deepest.start, deepest.end],
            label: deepest.label,
        };
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
        if (widget.chart_type === "pivot") {
            return "pivot";
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

    async showInsights(widget) {
        this.state.openMenu = null;
        this.state.insights = {
            widgetTitle: widget.title, findings: [], narration: null,
            loading: true,
        };
        try {
            const result = await this.orm.call("bi.insights", "analyze_chart",
                [widget.chart_id, this._widgetExtraFilters(widget)]);
            this.state.insights = {
                widgetTitle: widget.title,
                findings: result.findings || [],
                narration: result.narration,
                loading: false,
            };
        } catch (error) {
            this.state.insights = null;
            throw error;
        }
    }

    closeInsights() {
        this.state.insights = null;
    }

    exportWidgetXlsx(widget) {
        const filters = JSON.stringify(this._widgetExtraFilters(widget));
        window.open(`/bi/export/xlsx?chart_id=${widget.chart_id}` +
            `&filters=${encodeURIComponent(filters)}`, "_blank");
    }

    exportWidgetPng(widget) {
        /* global echarts */
        const host = this.gridRef.el?.querySelector(
            `[data-widget-id="${widget.id}"] .bi-chart-host`);
        const instance = host && echarts.getInstanceByDom(host);
        if (!instance) {
            this.notification.add(
                _t("PNG export works for chart widgets."), { type: "info" });
            return;
        }
        const link = document.createElement("a");
        link.href = instance.getDataURL({ pixelRatio: 2,
                                          backgroundColor: "#fff" });
        link.download = `${widget.title}.png`;
        link.click();
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
