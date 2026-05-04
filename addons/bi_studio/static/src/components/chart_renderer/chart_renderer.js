/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, onPatched } from "@odoo/owl";

/**
 * ChartRenderer — Apache ECharts wrapper for OWL.
 * 
 * Renders any ECharts chart from a { labels, datasets } data structure.
 * Handles resize, theme changes, and disposal.
 */
export class ChartRenderer extends Component {
    static template = "bi_studio.ChartRenderer";
    static props = {
        chartData: { type: Object, optional: true },
        chartType: { type: String, optional: true },
        colorPalette: { type: String, optional: true },
        showLegend: { type: Boolean, optional: true },
        showLabels: { type: Boolean, optional: true },
        showGrid: { type: Boolean, optional: true },
        enableAnimation: { type: Boolean, optional: true },
        height: { type: String, optional: true },
        onChartClick: { type: Function, optional: true },
    };

    setup() {
        this.chartRef = useRef("chart");
        this.chartInstance = null;
        this._resizeObserver = null;

        onMounted(() => this._initChart());
        onPatched(() => this._updateChart());
        onWillUnmount(() => this._dispose());
    }

    _initChart() {
        if (!this.chartRef.el) return;
        if (typeof echarts === "undefined") {
            console.warn("BI Studio: ECharts library not loaded");
            return;
        }

        this.chartInstance = echarts.init(this.chartRef.el);
        this._updateChart();

        // Resize observer
        this._resizeObserver = new ResizeObserver(() => {
            if (this.chartInstance) {
                this.chartInstance.resize();
            }
        });
        this._resizeObserver.observe(this.chartRef.el);

        // Click handler
        if (this.props.onChartClick) {
            this.chartInstance.on("click", (params) => {
                this.props.onChartClick(params);
            });
        }
    }

    _updateChart() {
        if (!this.chartInstance) return;
        const option = this._buildOption();
        this.chartInstance.setOption(option, true);
    }

    _buildOption() {
        const data = this.props.chartData || { labels: [], datasets: [] };
        const type = this.props.chartType || "bar";
        const colors = this._getColorPalette();

        // Base option
        const option = {
            color: colors,
            tooltip: {
                trigger: type === "pie" || type === "doughnut" ? "item" : "axis",
                backgroundColor: "rgba(30, 41, 59, 0.95)",
                borderColor: "transparent",
                textStyle: { color: "#f8fafc", fontSize: 12 },
                borderRadius: 8,
                padding: [8, 12],
            },
            grid: {
                left: "3%",
                right: "4%",
                bottom: "3%",
                top: this.props.showLegend !== false ? "15%" : "8%",
                containLabel: true,
            },
            animationDuration: this.props.enableAnimation !== false ? 800 : 0,
            animationEasing: "cubicInOut",
        };

        // Legend
        if (this.props.showLegend !== false && data.datasets && data.datasets.length > 1) {
            option.legend = {
                top: 0,
                textStyle: { color: "#64748b", fontSize: 12 },
                icon: "roundRect",
                itemWidth: 14,
                itemHeight: 8,
            };
        }

        // Build based on chart type
        switch (type) {
            case "pie":
            case "doughnut":
                return this._buildPieOption(option, data, type === "doughnut");
            case "radar":
                return this._buildRadarOption(option, data);
            case "scatter":
                return this._buildScatterOption(option, data);
            case "gauge":
                return this._buildGaugeOption(option, data);
            case "funnel":
                return this._buildFunnelOption(option, data);
            case "treemap":
                return this._buildTreemapOption(option, data);
            case "heatmap":
                return this._buildHeatmapOption(option, data);
            default:
                return this._buildCartesianOption(option, data, type);
        }
    }

    _buildCartesianOption(option, data, type) {
        option.xAxis = {
            type: "category",
            data: data.labels || [],
            axisLabel: {
                color: "#94a3b8",
                fontSize: 11,
                rotate: data.labels && data.labels.length > 8 ? 30 : 0,
            },
            axisLine: { lineStyle: { color: "#e2e8f0" } },
            splitLine: { show: false },
        };

        option.yAxis = {
            type: "value",
            axisLabel: { color: "#94a3b8", fontSize: 11 },
            axisLine: { show: false },
            splitLine: {
                show: this.props.showGrid !== false,
                lineStyle: { color: "#f1f5f9", type: "dashed" },
            },
        };

        // Horizontal bar
        if (type === "bar") {
            [option.xAxis, option.yAxis] = [option.yAxis, option.xAxis];
            option.yAxis.type = "category";
            option.xAxis.type = "value";
        }

        option.series = (data.datasets || []).map((ds, i) => {
            const seriesType = type === "area" ? "line" : (type === "column" ? "bar" : type);
            const series = {
                name: ds.name || `Series ${i + 1}`,
                type: seriesType === "bar" && type !== "bar" ? "bar" : seriesType,
                data: ds.data || [],
                emphasis: { focus: "series" },
                label: {
                    show: this.props.showLabels === true,
                    position: "top",
                    fontSize: 11,
                    color: "#64748b",
                },
            };

            if (type === "area" || type === "line") {
                series.type = "line";
                series.smooth = true;
                series.symbol = "circle";
                series.symbolSize = 6;
                if (type === "area") {
                    series.areaStyle = {
                        opacity: 0.15,
                    };
                }
            }

            if (type === "column" || (type !== "bar" && type !== "line" && type !== "area")) {
                series.type = "bar";
                series.barMaxWidth = 40;
                series.itemStyle = {
                    borderRadius: [4, 4, 0, 0],
                };
            }

            return series;
        });

        return option;
    }

    _buildPieOption(option, data, isDoughnut) {
        delete option.grid;
        const pieData = (data.labels || []).map((label, i) => ({
            name: label,
            value: data.datasets && data.datasets[0] ? data.datasets[0].data[i] : 0,
        }));

        option.series = [{
            type: "pie",
            radius: isDoughnut ? ["45%", "70%"] : ["0%", "70%"],
            center: ["50%", "55%"],
            data: pieData,
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: "rgba(0, 0, 0, 0.2)",
                },
            },
            label: {
                show: this.props.showLabels !== false,
                fontSize: 12,
                color: "#64748b",
            },
            itemStyle: {
                borderRadius: isDoughnut ? 6 : 4,
                borderColor: "#fff",
                borderWidth: 2,
            },
        }];

        return option;
    }

    _buildRadarOption(option, data) {
        delete option.grid;
        const indicators = (data.labels || []).map((name) => ({
            name,
            max: Math.max(...(data.datasets || []).flatMap(ds => ds.data || []), 100),
        }));

        option.radar = {
            indicator: indicators,
            shape: "polygon",
            axisName: { color: "#94a3b8", fontSize: 11 },
        };

        option.series = [{
            type: "radar",
            data: (data.datasets || []).map((ds) => ({
                name: ds.name,
                value: ds.data || [],
                areaStyle: { opacity: 0.15 },
            })),
        }];

        return option;
    }

    _buildScatterOption(option, data) {
        option.xAxis = {
            type: "value",
            axisLabel: { color: "#94a3b8", fontSize: 11 },
            splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
        };
        option.yAxis = {
            type: "value",
            axisLabel: { color: "#94a3b8", fontSize: 11 },
            splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
        };

        option.series = (data.datasets || []).map((ds) => ({
            name: ds.name,
            type: "scatter",
            data: ds.data || [],
            symbolSize: 10,
        }));

        return option;
    }

    _buildGaugeOption(option, data) {
        delete option.grid;
        const value = data.datasets && data.datasets[0] && data.datasets[0].data
            ? data.datasets[0].data[0] : 0;

        option.series = [{
            type: "gauge",
            progress: { show: true, width: 18 },
            axisLine: { lineStyle: { width: 18 } },
            axisTick: { show: false },
            splitLine: { length: 15, lineStyle: { width: 2, color: "#999" } },
            axisLabel: { distance: 25, color: "#999", fontSize: 12 },
            anchor: { show: true, showAbove: true, size: 20, itemStyle: { borderWidth: 8 } },
            detail: { valueAnimation: true, fontSize: 26, offsetCenter: [0, "70%"], color: "#1e293b" },
            data: [{ value, name: data.labels ? data.labels[0] : "" }],
        }];

        return option;
    }

    _buildFunnelOption(option, data) {
        delete option.grid;
        const funnelData = (data.labels || []).map((label, i) => ({
            name: label,
            value: data.datasets && data.datasets[0] ? data.datasets[0].data[i] : 0,
        })).sort((a, b) => b.value - a.value);

        option.series = [{
            type: "funnel",
            left: "10%",
            top: 60,
            bottom: 60,
            width: "80%",
            gap: 2,
            label: { show: true, position: "inside", fontSize: 12 },
            data: funnelData,
        }];

        return option;
    }

    _buildTreemapOption(option, data) {
        delete option.grid;
        const treemapData = (data.labels || []).map((label, i) => ({
            name: label,
            value: data.datasets && data.datasets[0] ? data.datasets[0].data[i] : 0,
        }));

        option.series = [{
            type: "treemap",
            data: treemapData,
            label: { show: true, fontSize: 12 },
            breadcrumb: { show: false },
            itemStyle: { borderColor: "#fff", borderWidth: 2, gapWidth: 2 },
        }];

        return option;
    }

    _buildHeatmapOption(option, data) {
        // Simplified heatmap
        option.xAxis = {
            type: "category",
            data: data.labels || [],
            axisLabel: { color: "#94a3b8", fontSize: 11 },
        };
        option.yAxis = {
            type: "category",
            data: data.datasets ? data.datasets.map(ds => ds.name) : [],
            axisLabel: { color: "#94a3b8", fontSize: 11 },
        };

        const heatData = [];
        (data.datasets || []).forEach((ds, yi) => {
            (ds.data || []).forEach((val, xi) => {
                heatData.push([xi, yi, val]);
            });
        });

        const allValues = heatData.map(d => d[2]);
        option.visualMap = {
            min: Math.min(...allValues, 0),
            max: Math.max(...allValues, 100),
            calculable: true,
            orient: "horizontal",
            left: "center",
            bottom: "0%",
            inRange: { color: ["#e0f2fe", "#3b82f6", "#1e3a5f"] },
        };

        option.series = [{
            type: "heatmap",
            data: heatData,
            label: { show: true, fontSize: 11 },
        }];

        return option;
    }

    _getColorPalette() {
        const palettes = {
            default: ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"],
            blue: ["#3b82f6", "#60a5fa", "#93c5fd", "#2563eb", "#1d4ed8", "#1e40af", "#bfdbfe", "#dbeafe"],
            green: ["#10b981", "#34d399", "#6ee7b7", "#059669", "#047857", "#065f46", "#a7f3d0", "#d1fae5"],
            sunset: ["#f59e0b", "#f97316", "#ef4444", "#eab308", "#d97706", "#dc2626", "#fbbf24", "#fca5a5"],
            purple: ["#8b5cf6", "#a78bfa", "#c4b5fd", "#7c3aed", "#6d28d9", "#5b21b6", "#ddd6fe", "#ede9fe"],
            mono: ["#1e293b", "#334155", "#475569", "#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0", "#f1f5f9"],
            pastel: ["#93c5fd", "#86efac", "#fde68a", "#fca5a5", "#c4b5fd", "#fbcfe8", "#99f6e4", "#fcd34d"],
            vivid: ["#7c3aed", "#06b6d4", "#f97316", "#10b981", "#f43f5e", "#0ea5e9", "#eab308", "#8b5cf6"],
        };
        return palettes[this.props.colorPalette] || palettes.default;
    }

    _dispose() {
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        if (this.chartInstance) {
            this.chartInstance.dispose();
            this.chartInstance = null;
        }
    }
}
