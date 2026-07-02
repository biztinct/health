/** @odoo-module **/

/**
 * Pure ranking function: given the current slot configuration, order chart
 * types best-first. The Explore gallery highlights the winner and dims
 * incompatible types with a reason.
 */

export const CHART_REQUIREMENTS = {
    bar: { minDims: 1, maxDims: 2, minMeasures: 1 },
    bar_stacked: { minDims: 2, maxDims: 2, minMeasures: 1 },
    bar_h: { minDims: 1, maxDims: 2, minMeasures: 1 },
    line: { minDims: 1, maxDims: 2, minMeasures: 1 },
    area: { minDims: 1, maxDims: 2, minMeasures: 1 },
    combo: { minDims: 1, maxDims: 1, minMeasures: 2 },
    donut: { minDims: 1, maxDims: 1, minMeasures: 1 },
    kpi: { minDims: 0, maxDims: 0, minMeasures: 1 },
    table: { minDims: 0, maxDims: 8, minMeasures: 0 },
    scatter: { minDims: 0, maxDims: 1, minMeasures: 2 },
    heatmap: { minDims: 2, maxDims: 2, minMeasures: 1 },
    treemap: { minDims: 1, maxDims: 1, minMeasures: 1 },
    funnel: { minDims: 1, maxDims: 1, minMeasures: 1 },
    gauge: { minDims: 0, maxDims: 0, minMeasures: 1 },
    waterfall: { minDims: 1, maxDims: 1, minMeasures: 1 },
    pareto: { minDims: 1, maxDims: 1, minMeasures: 1 },
    pivot: { minDims: 2, maxDims: 2, minMeasures: 1 },
};

export function checkCompatibility(chartType, dims, measures) {
    const req = CHART_REQUIREMENTS[chartType];
    if (!req) {
        return { ok: false, reason: "Unknown chart type" };
    }
    if (dims.length < req.minDims) {
        return { ok: false, reason: `Needs at least ${req.minDims} dimension(s)` };
    }
    if (dims.length > req.maxDims) {
        return { ok: false, reason: `Supports at most ${req.maxDims} dimension(s)` };
    }
    if (measures.length < req.minMeasures) {
        return { ok: false, reason: `Needs at least ${req.minMeasures} measure(s)` };
    }
    return { ok: true };
}

export function recommendChartType(dims, measures) {
    const hasDate = dims.some((d) => d.role === "date" || d.grain);
    if (!dims.length && measures.length) {
        return "kpi";
    }
    if (hasDate && measures.length === 1 && dims.length === 1) {
        return "line";
    }
    if (hasDate && measures.length >= 2) {
        return "combo";
    }
    if (dims.length === 2) {
        return "bar_stacked";
    }
    if (dims.length === 1 && measures.length === 1) {
        // small category counts read best as donut
        return "bar";
    }
    if (dims.length === 1 && measures.length >= 2) {
        return "bar";
    }
    return "table";
}
