/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * VisualDesigner — Power BI/Tableau-style chart builder.
 * 
 * Left:   Field list from the selected dataset
 * Center: Live chart preview (ECharts)
 * Right:  Chart slots (X-axis, Y-axis, Color) + chart type selector
 */
export class VisualDesigner extends Component {
    static template = "bi_studio.VisualDesigner";
    static components = { ChartRenderer };
    static props = {
        action: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action_service = useService("action");

        const params = this.props.action?.params || {};
        this.state = useState({
            loading: true,

            // Visual
            visualId: params.visual_id || null,
            visualName: params.visual_name || "New Visual",

            // Dataset
            datasetId: params.dataset_id || null,
            datasetName: "",

            // Available fields from dataset
            dimensions: [],
            measures: [],
            dates: [],

            // Chart config
            chartType: "column",
            xAxis: null,       // { field_id, field_path, label }
            yAxis: [],         // [{ field_id, field_path, label, aggregation }]
            colorField: null,  // { field_id, field_path, label }
            chartFilters: [],

            // Chart data
            chartData: { labels: [], datasets: [] },
            chartLoading: false,

            // Styling
            colorPalette: "default",
            showLegend: true,
            showLabels: false,

            // Field search
            fieldSearch: "",
        });

        onMounted(() => this._loadData());
    }

    // =========================================================================
    // Data Loading
    // =========================================================================

    async _loadData() {
        try {
            // Load dataset fields
            if (this.state.datasetId) {
                const ds = await this.orm.read("bi.dataset", [this.state.datasetId],
                    ["name"]);
                if (ds.length) {
                    this.state.datasetName = ds[0].name;
                }

                const fields = await this.orm.searchRead("bi.dataset.field", [
                    ["dataset_id", "=", this.state.datasetId],
                    ["is_selected", "=", true],
                ], [
                    "id", "field_name", "field_path", "field_label", "display_label",
                    "odoo_field_type", "field_role", "default_aggregation",
                ], { order: "sequence" });

                this.state.dimensions = fields.filter(f => f.field_role === "dimension");
                this.state.measures = fields.filter(f => f.field_role === "measure");
                this.state.dates = fields.filter(f => f.field_role === "date");
            }

            // Load existing visual config
            if (this.state.visualId) {
                const vis = await this.orm.read("bi.visual", [this.state.visualId], [
                    "name", "visual_type", "config_json", "color_palette",
                    "show_legend", "show_labels", "dataset_id",
                ]);
                if (vis.length) {
                    const v = vis[0];
                    this.state.visualName = v.name;
                    this.state.chartType = v.visual_type;
                    this.state.colorPalette = v.color_palette || "default";
                    this.state.showLegend = v.show_legend;
                    this.state.showLabels = v.show_labels;
                    
                    if (!this.state.datasetId && v.dataset_id) {
                        this.state.datasetId = v.dataset_id[0];
                    }

                    // Parse config
                    try {
                        const config = JSON.parse(v.config_json || "{}");
                        if (config.x_axis) this.state.xAxis = config.x_axis;
                        if (config.y_axis) this.state.yAxis = config.y_axis;
                        if (config.color) this.state.colorField = config.color;
                    } catch (e) {
                        // ignore parse errors
                    }
                }
            }

            // If we have config, load chart data
            if (this.state.xAxis && this.state.yAxis.length) {
                await this._refreshChart();
            }
        } catch (e) {
            console.error("VisualDesigner load error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    // =========================================================================
    // Chart Slot Management
    // =========================================================================

    setXAxis(field) {
        this.state.xAxis = {
            field_id: field.id,
            field_path: field.field_path,
            label: field.display_label || field.field_label,
        };
        this._autoRefresh();
    }

    addYAxis(field) {
        // Prevent duplicates
        if (this.state.yAxis.some(y => y.field_path === field.field_path)) return;
        
        this.state.yAxis.push({
            field_id: field.id,
            field_path: field.field_path,
            label: field.display_label || field.field_label,
            aggregation: field.default_aggregation || "sum",
        });
        this._autoRefresh();
    }

    removeYAxis(index) {
        this.state.yAxis.splice(index, 1);
        this._autoRefresh();
    }

    setColorField(field) {
        this.state.colorField = {
            field_id: field.id,
            field_path: field.field_path,
            label: field.display_label || field.field_label,
        };
        this._autoRefresh();
    }

    clearXAxis() {
        this.state.xAxis = null;
        this._autoRefresh();
    }

    clearColorField() {
        this.state.colorField = null;
        this._autoRefresh();
    }

    onChartTypeChange(ev) {
        this.state.chartType = ev.target.value;
        this._autoRefresh();
    }

    selectChartType(type) {
        this.state.chartType = type;
        this._autoRefresh();
    }

    // =========================================================================
    // Chart Data
    // =========================================================================

    async _autoRefresh() {
        if (this.state.xAxis && this.state.yAxis.length) {
            await this._refreshChart();
        }
    }

    async _refreshChart() {
        if (!this.state.datasetId) return;

        this.state.chartLoading = true;
        try {
            // Save config to visual first
            const config = {
                x_axis: this.state.xAxis,
                y_axis: this.state.yAxis,
                color: this.state.colorField,
                filters: this.state.chartFilters,
                limit: 50,
            };

            if (this.state.visualId) {
                await this.orm.call("bi.visual", "save_visual_config",
                    [this.state.visualId], { config });
                
                // Get computed chart data
                const data = await this.orm.call("bi.visual", "get_visual_chart_data",
                    [], { visual_id: this.state.visualId });
                this.state.chartData = data || { labels: [], datasets: [] };
            } else {
                // Get data directly from dataset for preview
                const result = await this.orm.call("bi.dataset", "action_preview_data",
                    [this.state.datasetId], { limit: 50 });

                // Process into chart format
                this.state.chartData = this._processPreviewToChart(result);
            }
        } catch (e) {
            console.error("Chart refresh error:", e);
        } finally {
            this.state.chartLoading = false;
        }
    }

    _processPreviewToChart(previewData) {
        if (!previewData || !previewData.columns || !previewData.rows) {
            return { labels: [], datasets: [] };
        }

        const colIndex = {};
        previewData.columns.forEach((col, i) => { colIndex[col.name] = i; });

        const xPath = this.state.xAxis?.field_path;
        const xIdx = colIndex[xPath];
        if (xIdx === undefined) return { labels: [], datasets: [] };

        // Aggregate
        const grouped = {};
        for (const row of previewData.rows) {
            const xVal = row[xIdx] != null ? String(row[xIdx]) : "N/A";
            if (!grouped[xVal]) grouped[xVal] = {};
            for (const yf of this.state.yAxis) {
                const yIdx = colIndex[yf.field_path];
                if (yIdx === undefined) continue;
                if (!grouped[xVal][yf.field_path]) grouped[xVal][yf.field_path] = [];
                const val = row[yIdx];
                grouped[xVal][yf.field_path].push(typeof val === "number" ? val : 0);
            }
        }

        const labels = Object.keys(grouped);
        const datasets = this.state.yAxis.map(yf => {
            const data = labels.map(label => {
                const vals = grouped[label]?.[yf.field_path] || [0];
                switch (yf.aggregation) {
                    case "sum": return vals.reduce((a, b) => a + b, 0);
                    case "avg": return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
                    case "min": return Math.min(...vals);
                    case "max": return Math.max(...vals);
                    case "count": return vals.length;
                    default: return vals.reduce((a, b) => a + b, 0);
                }
            });
            return { name: yf.label, data, type: this.state.chartType };
        });

        return { labels, datasets };
    }

    // =========================================================================
    // Chart Types
    // =========================================================================

    get chartTypes() {
        return [
            { value: "column", label: _t("Column"), icon: "fa-bar-chart" },
            { value: "bar", label: _t("Bar"), icon: "fa-bar-chart fa-rotate-90" },
            { value: "line", label: _t("Line"), icon: "fa-line-chart" },
            { value: "area", label: _t("Area"), icon: "fa-area-chart" },
            { value: "pie", label: _t("Pie"), icon: "fa-pie-chart" },
            { value: "doughnut", label: _t("Donut"), icon: "fa-circle-o" },
            { value: "scatter", label: _t("Scatter"), icon: "fa-braille" },
            { value: "radar", label: _t("Radar"), icon: "fa-star-o" },
            { value: "funnel", label: _t("Funnel"), icon: "fa-filter" },
            { value: "treemap", label: _t("Treemap"), icon: "fa-th" },
            { value: "gauge", label: _t("Gauge"), icon: "fa-tachometer" },
            { value: "heatmap", label: _t("Heatmap"), icon: "fa-th-large" },
        ];
    }

    // =========================================================================
    // Field search
    // =========================================================================

    onFieldSearch(ev) {
        this.state.fieldSearch = ev.target.value.toLowerCase();
    }

    get filteredDimensions() {
        return this._filterFields(this.state.dimensions);
    }

    get filteredMeasures() {
        return this._filterFields(this.state.measures);
    }

    get filteredDates() {
        return this._filterFields(this.state.dates);
    }

    _filterFields(fields) {
        if (!this.state.fieldSearch) return fields;
        const q = this.state.fieldSearch;
        return fields.filter(f =>
            (f.field_label || "").toLowerCase().includes(q) ||
            (f.field_path || "").toLowerCase().includes(q)
        );
    }

    // =========================================================================
    // Save
    // =========================================================================

    async saveVisual() {
        const config = {
            x_axis: this.state.xAxis,
            y_axis: this.state.yAxis,
            color: this.state.colorField,
            filters: this.state.chartFilters,
        };

        const vals = {
            name: this.state.visualName,
            visual_type: this.state.chartType,
            config_json: JSON.stringify(config),
            color_palette: this.state.colorPalette,
            show_legend: this.state.showLegend,
            show_labels: this.state.showLabels,
        };

        try {
            if (this.state.visualId) {
                await this.orm.write("bi.visual", [this.state.visualId], vals);
            } else {
                vals.dataset_id = this.state.datasetId;
                const newId = await this.orm.create("bi.visual", [vals]);
                this.state.visualId = newId[0];
            }
            this.notification.add(_t("Visual saved successfully"), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Error saving visual"), { type: "danger" });
        }
    }

    goBack() {
        this.action_service.doAction({
            type: "ir.actions.act_window",
            res_model: "bi.visual",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
        });
    }

    get hasChartConfig() {
        return this.state.xAxis && this.state.yAxis.length > 0;
    }
}

registry.category("actions").add("bi_studio.visual_designer", VisualDesigner);
