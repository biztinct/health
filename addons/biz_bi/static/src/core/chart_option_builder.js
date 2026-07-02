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
        const seriesData = measures.map(() => []);
        for (const row of rows) {
            categories.push(dims.length ? formatDimensionValue(row[dimIndex("d0")], dims[0], lang) : "");
            measures.forEach((m, mi) => {
                seriesData[mi].push(row[dimIndex(m.ref)]);
            });
        }
        return {
            categories,
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
    const catPos = new Map();
    const seriesMap = new Map();
    for (const row of rows) {
        const cat = formatDimensionValue(row[d0i], dims[0], lang);
        if (!catPos.has(cat)) {
            catPos.set(cat, categories.length);
            categories.push(cat);
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
