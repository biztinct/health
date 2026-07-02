/** @odoo-module **/

import { formatNumber, formatFull, formatDimensionValue } from "./formats";

/**
 * Pure function: (result envelope, chart config, theme tokens, lang)
 * -> ECharts option. All chart cosmetics live client-side; the server only
 * returns data. Mono flat palette, no gradients.
 */

export const MONO_PALETTE = [
    "#1565C0", "#00897B", "#F57C00", "#6A1B9A", "#C62828",
    "#2E7D32", "#4527A0", "#00838F", "#EF6C00", "#283593",
];

function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return value ? value.trim() : fallback;
}

/**
 * Pivot the flat envelope (d0 [, d1], m0..mn) into ECharts-shaped data.
 * - one dimension: categories = d0 values, one series per measure
 * - two dimensions: categories = d0 values, one series per distinct d1 value
 *   (first measure only)
 */
export function pivotEnvelope(envelope, lang) {
    const columns = envelope.columns || [];
    const dims = columns.filter((c) => c.ref.startsWith("d"));
    const measures = columns.filter((c) => c.ref.startsWith("m"));
    const rows = envelope.rows || [];
    const dimIndex = (ref) => columns.findIndex((c) => c.ref === ref);

    if (dims.length <= 1) {
        const categories = [];
        const rawCategories = [];
        const seriesData = measures.map(() => []);
        for (const row of rows) {
            const raw = dims.length ? row[dimIndex("d0")] : null;
            rawCategories.push(raw);
            categories.push(dims.length ? formatDimensionValue(raw, dims[0], lang) : "");
            measures.forEach((m, mi) => {
                seriesData[mi].push(row[dimIndex(m.ref)]);
            });
        }
        return {
            categories,
            rawCategories,
            dimColumn: dims[0] || null,
            series: measures.map((m, mi) => ({
                name: m.label,
                column: m,
                data: seriesData[mi],
            })),
        };
    }

    // 2 dims: d0 = axis, d1 = series
    const d0i = dimIndex("d0");
    const d1i = dimIndex("d1");
    const m0i = dimIndex(measures[0].ref);
    const categories = [];
    const rawCategories = [];
    const catPos = new Map();
    const seriesMap = new Map();
    for (const row of rows) {
        const cat = formatDimensionValue(row[d0i], dims[0], lang);
        if (!catPos.has(cat)) {
            catPos.set(cat, categories.length);
            categories.push(cat);
            rawCategories.push(row[d0i]);
        }
    }
    for (const row of rows) {
        const cat = formatDimensionValue(row[d0i], dims[0], lang);
        const ser = formatDimensionValue(row[d1i], dims[1], lang);
        if (!seriesMap.has(ser)) {
            seriesMap.set(ser, new Array(categories.length).fill(null));
        }
        seriesMap.get(ser)[catPos.get(cat)] = row[m0i];
    }
    for (const data of seriesMap.values()) {
        while (data.length < categories.length) {
            data.push(null);
        }
    }
    return {
        categories,
        rawCategories,
        dimColumn: dims[0] || null,
        series: [...seriesMap.entries()].map(([name, data]) => ({
            name,
            column: measures[0],
            data,
        })),
    };
}

export function buildChartOption(envelope, config, lang = "en_US") {
    const chartType = config.chart_type || "bar";
    const display = config.display || {};
    const { categories, series } = pivotEnvelope(envelope, lang);
    const textColor = cssVar("--vu-text-secondary", "#6B7280");
    const gridLine = cssVar("--vu-border-color", "#E8EBF0");

    const base = {
        color: MONO_PALETTE,
        animationDuration: 400,
        textStyle: { fontFamily: "inherit" },
        tooltip: {
            trigger: chartType === "donut" ? "item" : "axis",
            backgroundColor: "#1F2937",
            borderWidth: 0,
            borderRadius: 8,
            textStyle: { color: "#F9FAFB", fontSize: 12 },
            valueFormatter: (value) => formatFull(value, seriesFormat(series), lang),
        },
        legend: {
            show: display.show_legend !== false && series.length > 1,
            bottom: 0,
            type: "scroll",
            icon: "circle",
            textStyle: { color: textColor, fontSize: 11 },
        },
    };

    if (chartType === "donut") {
        return {
            ...base,
            series: [
                {
                    type: "pie",
                    radius: ["48%", "72%"],
                    padAngle: 1,
                    itemStyle: { borderRadius: 4 },
                    label: {
                        show: display.show_labels !== false,
                        formatter: (p) => `${p.name}\n${p.percent}%`,
                        color: textColor,
                        fontSize: 11,
                    },
                    data: categories.map((name, i) => ({
                        name,
                        value: series[0] ? series[0].data[i] : 0,
                    })),
                },
            ],
        };
    }

    if (chartType === "treemap") {
        return {
            ...base,
            tooltip: { ...base.tooltip, trigger: "item" },
            legend: { show: false },
            series: [{
                type: "treemap",
                roam: false,
                nodeClick: false,
                breadcrumb: { show: false },
                label: { fontSize: 11 },
                itemStyle: { borderColor: "#fff", borderWidth: 1, gapWidth: 1 },
                data: categories.map((name, i) => ({
                    name,
                    value: series[0] ? series[0].data[i] : 0,
                })),
            }],
        };
    }

    if (chartType === "funnel") {
        return {
            ...base,
            tooltip: { ...base.tooltip, trigger: "item" },
            series: [{
                type: "funnel",
                sort: "descending",
                gap: 3,
                left: "10%",
                width: "80%",
                label: { show: true, position: "inside", fontSize: 11 },
                itemStyle: { borderRadius: 2 },
                data: categories.map((name, i) => ({
                    name,
                    value: series[0] ? series[0].data[i] : 0,
                })),
            }],
        };
    }

    if (chartType === "gauge") {
        const value = series[0] && series[0].data.length ? series[0].data[0] : 0;
        const goal = display.goal_line;
        const max = goal || Math.max(Math.abs(value) * 1.4, 1);
        return {
            ...base,
            tooltip: { show: false },
            legend: { show: false },
            series: [{
                type: "gauge",
                startAngle: 210,
                endAngle: -30,
                min: 0,
                max,
                progress: { show: true, width: 14, roundCap: true },
                axisLine: { lineStyle: { width: 14, color: [[1, gridLine]] } },
                pointer: { show: false },
                axisTick: { show: false },
                splitLine: { show: false },
                axisLabel: { show: false },
                anchor: { show: false },
                detail: {
                    valueAnimation: true,
                    fontSize: 26,
                    fontWeight: 700,
                    color: MONO_PALETTE[0],
                    offsetCenter: [0, "10%"],
                    formatter: (v) => formatNumber(v, seriesFormat(series), lang),
                },
                data: [{ value }],
            }],
        };
    }

    if (chartType === "scatter") {
        // 2 measures: x = m0, y = m1, one point per dimension member
        const envelopeColumns = envelope.columns || [];
        const measureCols = envelopeColumns.filter((c) => c.ref.startsWith("m"));
        const dimCols = envelopeColumns.filter((c) => c.ref.startsWith("d"));
        const points = (envelope.rows || []).map((row) => {
            const name = dimCols.length
                ? formatDimensionValue(row[envelopeColumns.indexOf(dimCols[0])], dimCols[0], lang)
                : "";
            return {
                name,
                value: measureCols.map((mc) => row[envelopeColumns.indexOf(mc)]),
            };
        });
        const axisStyle = {
            splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
            axisLabel: {
                color: textColor,
                fontSize: 11,
                formatter: (v) => formatNumber(v, {}, lang),
            },
        };
        return {
            ...base,
            tooltip: {
                ...base.tooltip,
                trigger: "item",
                formatter: (p) =>
                    `${p.name || ""}<br/>${measureCols[0]?.label}: ${formatFull(p.value[0], measureCols[0]?.format || {}, lang)}` +
                    (measureCols[1] ? `<br/>${measureCols[1].label}: ${formatFull(p.value[1], measureCols[1].format || {}, lang)}` : ""),
            },
            legend: { show: false },
            grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
            xAxis: { type: "value", name: measureCols[0]?.label, ...axisStyle },
            yAxis: { type: "value", name: measureCols[1]?.label, ...axisStyle },
            series: [{ type: "scatter", symbolSize: 12, data: points }],
        };
    }

    if (chartType === "heatmap") {
        // 2 dims + 1 measure
        const envelopeColumns = envelope.columns || [];
        const dimCols = envelopeColumns.filter((c) => c.ref.startsWith("d"));
        const measureCol = envelopeColumns.find((c) => c.ref === "m0");
        const xSet = [], ySet = [];
        const xPos = new Map(), yPos = new Map();
        const cells = [];
        let maxValue = 0;
        for (const row of envelope.rows || []) {
            const xv = formatDimensionValue(row[envelopeColumns.indexOf(dimCols[0])], dimCols[0], lang);
            const yv = dimCols[1]
                ? formatDimensionValue(row[envelopeColumns.indexOf(dimCols[1])], dimCols[1], lang)
                : "";
            if (!xPos.has(xv)) { xPos.set(xv, xSet.length); xSet.push(xv); }
            if (!yPos.has(yv)) { yPos.set(yv, ySet.length); ySet.push(yv); }
            const value = row[envelopeColumns.indexOf(measureCol)] || 0;
            maxValue = Math.max(maxValue, Math.abs(value));
            cells.push([xPos.get(xv), yPos.get(yv), value]);
        }
        return {
            ...base,
            tooltip: { ...base.tooltip, trigger: "item" },
            legend: { show: false },
            grid: { left: 8, right: 16, top: 8, bottom: 40, containLabel: true },
            xAxis: { type: "category", data: xSet, axisLabel: { color: textColor, fontSize: 11, rotate: xSet.length > 10 ? 30 : 0 } },
            yAxis: { type: "category", data: ySet, axisLabel: { color: textColor, fontSize: 11 } },
            visualMap: {
                min: 0,
                max: maxValue || 1,
                calculable: false,
                orient: "horizontal",
                left: "center",
                bottom: 0,
                inRange: { color: ["#E8F1FB", MONO_PALETTE[0]] },
                textStyle: { color: textColor, fontSize: 10 },
            },
            series: [{
                type: "heatmap",
                data: cells,
                label: { show: cells.length <= 120, fontSize: 10, formatter: (p) => formatNumber(p.value[2], measureCol?.format || {}, lang) },
                itemStyle: { borderColor: "#fff", borderWidth: 1 },
            }],
        };
    }

    if (chartType === "sankey") {
        // flows: d0 (source) -> d1 (target), weight = m0
        const envelopeColumns = envelope.columns || [];
        const dimCols = envelopeColumns.filter((c) => c.ref.startsWith("d"));
        const measureCol = envelopeColumns.find((c) => c.ref === "m0");
        const nodeSet = new Set();
        const links = [];
        for (const row of envelope.rows || []) {
            const source = "▸ " + formatDimensionValue(
                row[envelopeColumns.indexOf(dimCols[0])], dimCols[0], lang);
            const target = formatDimensionValue(
                row[envelopeColumns.indexOf(dimCols[1])], dimCols[1], lang);
            const value = row[envelopeColumns.indexOf(measureCol)];
            if (!value || value < 0) {
                continue;
            }
            nodeSet.add(source);
            nodeSet.add(target);
            links.push({ source, target, value });
        }
        return {
            ...base,
            tooltip: { ...base.tooltip, trigger: "item",
                       valueFormatter: (v) => formatFull(v, measureCol?.format || {}, lang) },
            legend: { show: false },
            series: [{
                type: "sankey",
                left: 20, right: 90, top: 10, bottom: 10,
                nodeGap: 10,
                lineStyle: { color: "source", opacity: 0.25, curveness: 0.55 },
                itemStyle: { borderRadius: 3 },
                label: { fontSize: 11, color: textColor },
                emphasis: { focus: "adjacency" },
                data: [...nodeSet].map((name) => ({ name })),
                links,
            }],
        };
    }

    if (chartType === "radar") {
        // indicators = d0 members, one polygon per measure
        const maxValue = Math.max(
            1, ...series.flatMap((s) => s.data.map((v) => Math.abs(v || 0))));
        return {
            ...base,
            tooltip: { ...base.tooltip, trigger: "item" },
            radar: {
                indicator: categories.map((name) => ({
                    name, max: maxValue * 1.15,
                })),
                splitLine: { lineStyle: { color: gridLine } },
                splitArea: { show: false },
                axisLine: { lineStyle: { color: gridLine } },
                axisName: { color: textColor, fontSize: 11 },
            },
            series: [{
                type: "radar",
                symbolSize: 4,
                data: series.map((s) => ({
                    name: s.name,
                    value: s.data.map((v) => v || 0),
                    areaStyle: { opacity: 0.12 },
                    lineStyle: { width: 2 },
                })),
            }],
        };
    }

    if (chartType === "waterfall") {
        // cumulative bridge: transparent base + positive/negative deltas
        const data = series[0] ? series[0].data : [];
        const bases = [], rises = [], falls = [];
        let running = 0;
        for (const value of data) {
            const v = value || 0;
            if (v >= 0) {
                bases.push(running);
                rises.push(v);
                falls.push(null);
            } else {
                bases.push(running + v);
                rises.push(null);
                falls.push(-v);
            }
            running += v;
        }
        const categoryAxisW = {
            type: "category",
            data: categories,
            axisTick: { show: false },
            axisLabel: { color: textColor, fontSize: 11, rotate: categories.length > 12 ? 30 : 0 },
        };
        return {
            ...base,
            legend: { show: false },
            grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
            xAxis: categoryAxisW,
            yAxis: {
                type: "value",
                splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
                axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatNumber(v, seriesFormat(series), lang) },
            },
            series: [
                { type: "bar", stack: "wf", itemStyle: { color: "transparent" }, emphasis: { itemStyle: { color: "transparent" } }, tooltip: { show: false }, data: bases },
                { name: series[0]?.name, type: "bar", stack: "wf", itemStyle: { color: MONO_PALETTE[1], borderRadius: [3, 3, 0, 0] }, data: rises },
                { name: series[0]?.name, type: "bar", stack: "wf", itemStyle: { color: MONO_PALETTE[4], borderRadius: [3, 3, 0, 0] }, data: falls },
            ],
        };
    }

    if (chartType === "pareto") {
        const data = (series[0] ? series[0].data : []).map((v) => v || 0);
        const total = data.reduce((a, b) => a + b, 0) || 1;
        let running = 0;
        const cumulative = data.map((v) => {
            running += v;
            return Math.round((running / total) * 1000) / 10;
        });
        return {
            ...base,
            grid: { left: 8, right: 40, top: 24, bottom: base.legend.show ? 32 : 8, containLabel: true },
            xAxis: {
                type: "category",
                data: categories,
                axisTick: { show: false },
                axisLabel: { color: textColor, fontSize: 11, rotate: categories.length > 12 ? 30 : 0 },
            },
            yAxis: [
                {
                    type: "value",
                    splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
                    axisLabel: { color: textColor, fontSize: 11, formatter: (v) => formatNumber(v, seriesFormat(series), lang) },
                },
                {
                    type: "value",
                    min: 0,
                    max: 100,
                    splitLine: { show: false },
                    axisLabel: { color: textColor, fontSize: 11, formatter: "{value}%" },
                },
            ],
            series: [
                { name: series[0]?.name, type: "bar", barMaxWidth: 36, itemStyle: { borderRadius: [3, 3, 0, 0] }, data },
                { name: "%", type: "line", yAxisIndex: 1, smooth: 0.25, symbolSize: 5, lineStyle: { width: 2, color: MONO_PALETTE[2] }, itemStyle: { color: MONO_PALETTE[2] }, data: cumulative },
            ],
        };
    }

    const horizontal = chartType === "bar_h" || display.horizontal;
    const categoryAxis = {
        type: "category",
        data: categories,
        axisLine: { lineStyle: { color: gridLine } },
        axisTick: { show: false },
        axisLabel: {
            color: textColor,
            fontSize: 11,
            hideOverlap: true,
            ...(horizontal ? {} : { rotate: categories.length > 12 ? 30 : 0 }),
        },
    };
    const valueAxis = {
        type: "value",
        splitLine: { lineStyle: { color: gridLine, type: "dashed" } },
        axisLabel: {
            color: textColor,
            fontSize: 11,
            formatter: (value) => formatNumber(value, seriesFormat(series), lang),
        },
    };

    const option = {
        ...base,
        grid: {
            left: 8,
            right: 16,
            top: 24,
            bottom: base.legend.show ? 32 : 8,
            containLabel: true,
        },
        xAxis: horizontal ? valueAxis : categoryAxis,
        yAxis: horizontal ? categoryAxis : valueAxis,
        series: series.map((ser, index) => buildSeries(ser, index, chartType, display)),
    };

    if (display.goal_line != null && option.series.length) {
        option.series[0].markLine = {
            silent: true,
            symbol: "none",
            lineStyle: { color: cssVar("--vu-danger", "#C62828"), type: "dashed", width: 1.5 },
            data: [{ yAxis: display.goal_line }],
        };
    }
    return option;
}

function seriesFormat(series) {
    return (series[0] && series[0].column && series[0].column.format) || {};
}

function buildSeries(ser, index, chartType, display) {
    const stacked = chartType === "bar_stacked" || display.stacked;
    switch (chartType) {
        case "line":
            return {
                name: ser.name,
                type: "line",
                data: ser.data,
                smooth: 0.25,
                symbolSize: 6,
                lineStyle: { width: 2.5 },
                emphasis: { focus: "series" },
            };
        case "area":
            return {
                name: ser.name,
                type: "line",
                data: ser.data,
                smooth: 0.25,
                symbol: "none",
                lineStyle: { width: 2 },
                areaStyle: { opacity: 0.18 }, // flat mono fill, no gradient
                emphasis: { focus: "series" },
            };
        case "combo":
            return {
                name: ser.name,
                type: index === 0 ? "bar" : "line",
                data: ser.data,
                smooth: 0.25,
                barMaxWidth: 36,
                itemStyle: index === 0 ? { borderRadius: [3, 3, 0, 0] } : undefined,
                yAxisIndex: 0,
            };
        default: // bar, bar_stacked, bar_h
            return {
                name: ser.name,
                type: "bar",
                data: ser.data,
                stack: stacked ? "total" : undefined,
                barMaxWidth: 36,
                itemStyle: {
                    borderRadius: stacked
                        ? 0
                        : chartType === "bar_h"
                          ? [0, 3, 3, 0]
                          : [3, 3, 0, 0],
                },
                emphasis: { focus: "series" },
            };
    }
}
