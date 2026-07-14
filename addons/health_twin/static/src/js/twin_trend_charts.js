/** @odoo-module **/

import {
    Component, useState, useRef, useEffect, onWillStart, onMounted,
    onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/* global echarts */

// Read a --vu-* CSS var off :root (follows the active light/dark theme).
function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement)
        .getPropertyValue(name).trim();
    return v || fallback;
}

// #rrggbb (or rgb()/named) → rgba(...,alpha) for faint band fills.
function withAlpha(color, alpha) {
    const c = (color || "").trim();
    const m = c.match(/^#([0-9a-f]{6})$/i);
    if (m) {
        const n = parseInt(m[1], 16);
        return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
    }
    const rgb = c.match(/^rgb\(([^)]+)\)$/i);
    if (rgb) {
        return `rgba(${rgb[1]},${alpha})`;
    }
    return c;
}

export class TwinTrendCharts extends Component {
    static template = "health_twin.TwinTrendCharts";
    static props = {
        record: { type: Object },
        name: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
        class: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.containerRef = useRef("container");
        this.charts = [];          // live echarts instances (per non-empty panel)
        this.resizeObserver = null;
        this.state = useState({ days: 30, loading: true, panels: [] });

        onWillStart(async () => {
            await this._load();
        });

        onMounted(() => {
            // Resize every live chart when the container resizes (biz_bi
            // ChartRenderer discipline). rAF-coalesced to dodge layout thrash.
            this.resizeObserver = new ResizeObserver(() => {
                if (this._rafPending) {
                    return;
                }
                this._rafPending = true;
                window.requestAnimationFrame(() => {
                    this._rafPending = false;
                    if (this.state.loading) {
                        return;
                    }
                    // Charts skipped at first render because the tab was
                    // hidden (zero-size host) get initialised now that the
                    // container has real size; otherwise just resize.
                    if (!this.charts.length) {
                        this._renderCharts();
                    } else {
                        for (const ch of this.charts) {
                            ch.resize();
                        }
                    }
                });
            });
            if (this.containerRef.el) {
                this.resizeObserver.observe(this.containerRef.el);
            }
        });

        // Render (or re-render) the canvases after every load / range switch,
        // once the DOM for the panels is patched in and the tab is visible.
        useEffect(
            () => {
                if (this.state.loading) {
                    return;
                }
                this._renderCharts();
                return () => this._disposeCharts();
            },
            () => [this.state.loading, this.state.days]
        );

        onWillUnmount(() => {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
                this.resizeObserver = null;
            }
            this._disposeCharts();
        });
    }

    get patientId() {
        return this.props.record.resId;
    }

    async _load() {
        if (!this.patientId) {
            this.state.loading = false;
            this.state.panels = [];
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "health.twin.risk", "chart_series",
                [this.patientId, this.state.days]);
            this.state.panels = (data && data.panels) || [];
        } catch (e) {
            console.error("twin_trend_charts load error:", e);
            this.state.panels = [];
        }
        this.state.loading = false;
    }

    async setDays(days) {
        if (days === this.state.days) {
            return;
        }
        this.state.days = days;
        await this._load();
    }

    isEmptyPanel(panel) {
        return !panel.series
            || panel.series.every((s) => !s.points || !s.points.length);
    }

    // --- theme-aware palette (read at render so a theme switch is honoured) --
    _palette() {
        return {
            line: [
                cssVar("--vu-brand-primary", "#1565c0"),
                cssVar("--vu-brand-primary-dark", "#0d47a1"),
            ],
            success: cssVar("--vu-status-success", "#176B47"),
            warning: cssVar("--vu-status-warning", "#946200"),
            danger: cssVar("--vu-status-danger", "#C0332A"),
            axis: cssVar("--vu-text-secondary", "#6b7280"),
            split: cssVar("--vu-border-soft", "#e0e0e0"),
            surface: cssVar("--vu-surface-card", "#ffffff"),
        };
    }

    _sevColor(pal, severity) {
        if (severity === "critical" || severity === "danger") {
            return pal.danger;
        }
        if (severity === "warning") {
            return pal.warning;
        }
        return pal.success;
    }

    _buildOption(panel, pal) {
        const series = panel.series.map((s, i) => {
            const color = pal.line[i % pal.line.length];
            const spec = {
                name: s.name,
                type: "line",
                showSymbol: true,
                symbolSize: 5,
                connectNulls: true,
                lineStyle: { color, width: 2 },
                itemStyle: { color },
                data: s.points,
            };
            // Threshold lines + NEWS2 zones ride on the first series only.
            if (i === 0 && panel.bands && panel.bands.length) {
                const lines = [];
                for (const b of panel.bands) {
                    const col = this._sevColor(pal, b.severity);
                    if (b.min) {
                        lines.push({
                            yAxis: b.min,
                            lineStyle: { color: col, type: "dashed" },
                            label: { formatter: `${b.severity} min`,
                                     color: col, position: "insideEndTop" },
                        });
                    }
                    if (b.max) {
                        lines.push({
                            yAxis: b.max,
                            lineStyle: { color: col, type: "dashed" },
                            label: { formatter: `${b.severity} max`,
                                     color: col, position: "insideEndBottom" },
                        });
                    }
                }
                if (lines.length) {
                    spec.markLine = { silent: true, symbol: "none", data: lines };
                }
            }
            if (i === 0 && panel.band_zones && panel.band_zones.length) {
                spec.markArea = {
                    silent: true,
                    data: panel.band_zones.map(([lo, hi, sev]) => [
                        { yAxis: lo,
                          itemStyle: {
                              color: withAlpha(this._sevColor(pal, sev), 0.1) } },
                        { yAxis: hi },
                    ]),
                };
            }
            return spec;
        });

        return {
            grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
            tooltip: { trigger: "axis" },
            legend: panel.series.length > 1
                ? { top: 0, textStyle: { color: pal.axis } } : undefined,
            xAxis: {
                type: "time",
                axisLine: { lineStyle: { color: pal.split } },
                axisLabel: { color: pal.axis, hideOverlap: true },
            },
            yAxis: {
                type: "value",
                scale: true,
                name: panel.unit || "",
                nameTextStyle: { color: pal.axis },
                axisLabel: { color: pal.axis },
                splitLine: { lineStyle: { color: pal.split } },
            },
            series,
        };
    }

    _disposeCharts() {
        for (const ch of this.charts) {
            ch.dispose();
        }
        this.charts = [];
    }

    _renderCharts() {
        this._disposeCharts();
        const root = this.containerRef.el;
        if (!root || typeof echarts === "undefined") {
            return;
        }
        const pal = this._palette();
        for (const host of root.querySelectorAll(".twin-chart-host")) {
            const key = host.dataset.key;
            const panel = this.state.panels.find((p) => p.key === key);
            if (!panel || this.isEmptyPanel(panel)) {
                continue;
            }
            // A hidden tab has zero height; only init once the host has size.
            if (!host.clientWidth || !host.clientHeight) {
                continue;
            }
            const chart = echarts.init(host, null, { renderer: "canvas" });
            chart.setOption(this._buildOption(panel, pal), { notMerge: true });
            this.charts.push(chart);
        }
    }
}

TwinTrendCharts.emptyLabel = _t("No readings yet");

export const twinTrendChartsWidget = { component: TwinTrendCharts };
registry.category("view_widgets").add("twin_trend_charts", twinTrendChartsWidget);
