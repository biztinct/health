/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "./chart_renderer";
import { KpiCard } from "./kpi_card";
import { DataTable } from "./data_table";
import { PivotTable } from "./pivot_table";
import { AddToDashboardDialog } from "./add_to_dashboard_dialog";
import {
    checkCompatibility,
    recommendChartType,
} from "../../core/chart_recommender";

const CHART_GALLERY = [
    { type: "bar", label: _t("Bar"), icon: "bar" },
    { type: "bar_stacked", label: _t("Stacked"), icon: "bar_stacked" },
    { type: "bar_h", label: _t("H. Bar"), icon: "bar_h" },
    { type: "line", label: _t("Line"), icon: "line" },
    { type: "area", label: _t("Area"), icon: "area" },
    { type: "combo", label: _t("Combo"), icon: "combo" },
    { type: "donut", label: _t("Donut"), icon: "donut" },
    { type: "kpi", label: _t("KPI"), icon: "kpi" },
    { type: "table", label: _t("Table"), icon: "table" },
    { type: "pivot", label: _t("Pivot"), icon: "pivot" },
    { type: "scatter", label: _t("Scatter"), icon: "scatter" },
    { type: "heatmap", label: _t("Heatmap"), icon: "heatmap" },
    { type: "treemap", label: _t("Treemap"), icon: "treemap" },
    { type: "funnel", label: _t("Funnel"), icon: "funnel" },
    { type: "gauge", label: _t("Gauge"), icon: "gauge" },
    { type: "waterfall", label: _t("Waterfall"), icon: "waterfall" },
    { type: "pareto", label: _t("Pareto"), icon: "pareto" },
];

const DATE_GRAINS = ["year", "quarter", "month", "week", "day"];
const AGGS = ["sum", "avg", "min", "max", "count", "count_distinct"];

export class ExploreAction extends Component {
    static template = "biz_bi.Explore";
    static components = { ChartRenderer, KpiCard, DataTable, PivotTable };
    static props = { "*": true };
    static displayName = _t("Explore");

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.biData = useService("bi_data");

        this.gallery = CHART_GALLERY;
        this.grains = DATE_GRAINS;
        this.aggs = AGGS;

        this.state = useState({
            datasets: [],
            datasetId: null,
            metadata: null,
            search: "",
            openFolders: {},
            slots: { x: [], values: [], series: [], filters: [] },
            chartType: "bar",
            userPickedType: false,
            envelope: null,
            loading: false,
            chartId: null,
            chartName: "",
            saving: false,
            dragOverSlot: null,
            aiAvailable: false,
            aiPrompt: "",
            aiBusy: false,
        });
        this._debounce = null;

        onWillStart(async () => {
            this.state.datasets = await this.orm.searchRead(
                "bi.dataset",
                [["state", "=", "published"]],
                ["name", "description", "is_certified", "storage_mode"]
            );
            this.orm.call("bi.ai", "is_available", []).then((available) => {
                this.state.aiAvailable = available;
            });
            const params = this.props.action?.params || {};
            if (params.chart_id) {
                await this.loadChart(params.chart_id);
            } else if (params.dataset_id) {
                await this.selectDataset(params.dataset_id);
            } else if (this.state.datasets.length === 1) {
                await this.selectDataset(this.state.datasets[0].id);
            }
        });
    }

    // ------------------------------------------------------------------
    // Dataset & metadata
    // ------------------------------------------------------------------

    onDatasetSelectChange(ev) {
        const datasetId = parseInt(ev.target.value);
        if (datasetId) {
            this.selectDataset(datasetId);
        }
    }

    filterValueText(chip) {
        return Array.isArray(chip.value) ? chip.value.join(", ") : (chip.value ?? "");
    }

    async selectDataset(datasetId) {
        this.state.datasetId = datasetId;
        this.state.slots = { x: [], values: [], series: [], filters: [] };
        this.state.envelope = null;
        this.state.chartId = null;
        this.state.metadata = await this.orm.call(
            "bi.dataset", "get_builder_metadata", [[datasetId]]);
        // open every folder by default
        for (const field of this.state.metadata.fields) {
            this.state.openFolders[field.folder] = true;
        }
    }

    async loadChart(chartId) {
        const [chart] = await this.orm.read(
            "bi.chart", [chartId],
            ["name", "dataset_id", "chart_type", "config_json"]);
        await this.selectDataset(chart.dataset_id[0]);
        this.materializeConfig(chart.config_json || {}, chart.chart_type);
        this.state.chartId = chartId;
        this.state.chartName = chart.name;
        this.refresh();
    }

    /** Turn a saved/AI chart config into live slot chips. */
    materializeConfig(config, chartType) {
        const slots = config.slots || {};
        const byId = Object.fromEntries(
            this.state.metadata.fields.map((f) => [f.id, f]));
        const materialize = (entries) =>
            (entries || [])
                .filter((e) => byId[e.field_id])
                .map((e) => ({ ...byId[e.field_id], grain: e.grain, agg: e.agg }));
        this.state.slots = {
            x: materialize(slots.x),
            values: materialize(slots.values),
            series: materialize(slots.series),
            filters: (config.filters || []).map((f) => ({
                ...(byId[f.field_id] || { id: f.field_id, name: "?" }),
                op: f.op,
                value: f.value,
            })),
        };
        this.state.chartType = chartType || config.chart_type || "bar";
        this.state.userPickedType = true;
    }

    // ------------------------------------------------------------------
    // AI: natural-language chart + report composer
    // ------------------------------------------------------------------

    async askAi() {
        const prompt = this.state.aiPrompt.trim();
        if (!prompt || this.state.aiBusy) {
            return;
        }
        this.state.aiBusy = true;
        try {
            const result = await this.orm.call(
                "bi.ai", "nlq_chart", [this.state.datasetId, prompt]);
            if (result.error) {
                this.notification.add(result.error, { type: "warning" });
                return;
            }
            this.materializeConfig(result.config, result.config.chart_type);
            if (result.config.name && !this.state.chartName) {
                this.state.chartName = result.config.name;
            }
            this.refresh();
        } finally {
            this.state.aiBusy = false;
        }
    }

    async composeAi() {
        const prompt = this.state.aiPrompt.trim();
        if (!prompt || this.state.aiBusy) {
            return;
        }
        this.state.aiBusy = true;
        try {
            const result = await this.orm.call(
                "bi.ai", "compose_report", [this.state.datasetId, prompt]);
            if (result.error) {
                this.notification.add(result.error, { type: "warning" });
                return;
            }
            if (result.dropped && result.dropped.length) {
                this.notification.add(
                    _t("%s widget(s) could not be built and were skipped.",
                       result.dropped.length),
                    { type: "info" });
            }
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "biz_bi.dashboard",
                params: { dashboard_id: result.dashboard_id },
            });
        } finally {
            this.state.aiBusy = false;
        }
    }

    get folders() {
        const metadata = this.state.metadata;
        if (!metadata) {
            return [];
        }
        const query = this.state.search.trim().toLowerCase();
        const folders = new Map();
        for (const field of metadata.fields) {
            if (field.role === "id") {
                continue;
            }
            if (query && !field.name.toLowerCase().includes(query)) {
                continue;
            }
            if (!folders.has(field.folder)) {
                folders.set(field.folder, []);
            }
            folders.get(field.folder).push(field);
        }
        return [...folders.entries()]
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([name, fields]) => ({ name, fields }));
    }

    toggleFolder(name) {
        this.state.openFolders[name] = !this.state.openFolders[name];
    }

    // ------------------------------------------------------------------
    // Slots: drag & drop + click-to-add
    // ------------------------------------------------------------------

    onFieldDragStart(event, field) {
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("bi/field", JSON.stringify(field));
    }

    slotAccepts(slotName, field) {
        // values: any field (non-measures aggregate as COUNT);
        // x/series: dimensions, dates and geo only — measures make no axis
        if ((slotName === "x" || slotName === "series") && field.role === "measure") {
            return { ok: false, reason: _t("Measures go in Values") };
        }
        return { ok: true };
    }

    onSlotDragOver(event, slotName) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        this.state.dragOverSlot = slotName;
    }

    onSlotDragLeave() {
        this.state.dragOverSlot = null;
    }

    onSlotDrop(event, slotName) {
        event.preventDefault();
        this.state.dragOverSlot = null;
        const raw = event.dataTransfer.getData("bi/field");
        if (!raw) {
            return;
        }
        const field = JSON.parse(raw);
        const verdict = this.slotAccepts(slotName, field);
        if (!verdict.ok) {
            this.notification.add(verdict.reason, { type: "warning" });
            return;
        }
        this.addToSlot(slotName, field);
    }

    addToSlot(slotName, field) {
        const slots = this.state.slots;
        if (slots[slotName].some((f) => f.id === field.id)) {
            return;
        }
        const entry = { ...field };
        if (slotName === "values") {
            entry.agg =
                field.role === "measure" && field.default_agg !== "none"
                    ? field.default_agg
                    : "count";
        }
        if ((slotName === "x" || slotName === "series") &&
                (field.data_type === "date" || field.data_type === "datetime")) {
            entry.grain = entry.grain || "month";
        }
        if (slotName === "filters") {
            entry.op = entry.op || this.defaultOpFor(field);
            entry.value = entry.value !== undefined ? entry.value : "";
        }
        if (slotName === "x" && slots.x.length >= 1 && !slots.series.length &&
                this.state.chartType !== "table") {
            // second category goes to series automatically
            slots.series.push(entry);
        } else {
            slots[slotName].push(entry);
        }
        this.afterSlotChange();
    }

    defaultOpFor(field) {
        if (field.data_type === "date" || field.data_type === "datetime") {
            return "relative";
        }
        if (field.data_type === "selection") {
            return "in";
        }
        if (["integer", "float", "monetary"].includes(field.data_type)) {
            return "gte";
        }
        return "like_i";
    }

    removeFromSlot(slotName, index) {
        this.state.slots[slotName].splice(index, 1);
        this.afterSlotChange();
    }

    setChipAgg(chip, agg) {
        chip.agg = agg;
        this.afterSlotChange();
    }

    setChipGrain(chip, grain) {
        chip.grain = grain;
        this.afterSlotChange();
    }

    setFilterValue(chip, event) {
        const raw = event.target.value;
        chip.value =
            chip.op === "in"
                ? raw.split(",").map((v) => v.trim()).filter(Boolean)
                : raw;
        this.afterSlotChange();
    }

    setFilterOp(chip, event) {
        chip.op = event.target.value;
        this.afterSlotChange();
    }

    afterSlotChange() {
        if (!this.state.userPickedType) {
            this.state.chartType = recommendChartType(
                this.dimChips, this.state.slots.values);
        }
        this.refresh();
    }

    get dimChips() {
        return [...this.state.slots.x, ...this.state.slots.series];
    }

    // ------------------------------------------------------------------
    // Chart type gallery
    // ------------------------------------------------------------------

    galleryEntryState(type) {
        const compat = checkCompatibility(
            type, this.dimChips, this.state.slots.values);
        return {
            ok: compat.ok,
            reason: compat.reason || "",
            recommended:
                recommendChartType(this.dimChips, this.state.slots.values) === type,
            active: this.state.chartType === type,
        };
    }

    pickChartType(type) {
        this.state.chartType = type;
        this.state.userPickedType = true;
        this.refresh();
    }

    // ------------------------------------------------------------------
    // Query & preview
    // ------------------------------------------------------------------

    buildRequest() {
        const slots = this.state.slots;
        return {
            dataset_id: this.state.datasetId,
            dimensions: this.dimChips.map((chip) => ({
                field_id: chip.id,
                grain: chip.grain || undefined,
            })),
            measures: slots.values.map((chip) => ({
                field_id: chip.id,
                agg: chip.agg,
            })),
            filters: slots.filters
                .filter((chip) => chip.op && chip.value !== "" && chip.value !== undefined)
                .map((chip) => ({
                    field_id: chip.id,
                    op: chip.op,
                    value: chip.value,
                })),
            sort: slots.values.length && this.state.chartType !== "line"
                ? [{ ref: "m0", dir: "desc" }]
                : [],
            limit: 500,
        };
    }

    refresh() {
        clearTimeout(this._debounce);
        if (!this.state.slots.values.length && this.state.chartType !== "table") {
            this.state.envelope = null;
            return;
        }
        this._debounce = setTimeout(async () => {
            this.state.loading = true;
            try {
                this.state.envelope = await this.biData.query(
                    this.buildRequest(), { noCache: false });
            } finally {
                this.state.loading = false;
            }
        }, 400);
    }

    get rendererKind() {
        if (this.state.chartType === "kpi") {
            return "kpi";
        }
        if (this.state.chartType === "table") {
            return "table";
        }
        if (this.state.chartType === "pivot") {
            return "pivot";
        }
        return "chart";
    }

    get chartConfig() {
        return { chart_type: this.state.chartType, display: {} };
    }

    // ------------------------------------------------------------------
    // Save
    // ------------------------------------------------------------------

    buildConfigJson() {
        const slots = this.state.slots;
        return {
            version: 1,
            chart_type: this.state.chartType,
            slots: {
                x: slots.x.map((c) => ({ field_id: c.id, grain: c.grain })),
                values: slots.values.map((c) => ({ field_id: c.id, agg: c.agg })),
                series: slots.series.map((c) => ({ field_id: c.id, grain: c.grain })),
            },
            filters: slots.filters
                .filter((c) => c.op && c.value !== "" && c.value !== undefined)
                .map((c) => ({ field_id: c.id, op: c.op, value: c.value })),
            sort: [],
            limit: 500,
            display: {},
        };
    }

    async saveChart() {
        if (!this.state.chartName.trim()) {
            this.notification.add(_t("Give the chart a name first."),
                { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            const values = {
                name: this.state.chartName,
                dataset_id: this.state.datasetId,
                chart_type: this.state.chartType,
                config_json: this.buildConfigJson(),
            };
            if (this.state.chartId) {
                await this.orm.write("bi.chart", [this.state.chartId], values);
            } else {
                this.state.chartId = await this.orm.create("bi.chart", [values]);
            }
            this.notification.add(_t("Chart saved."), { type: "success" });
        } finally {
            this.state.saving = false;
        }
    }

    async addToDashboard() {
        if (!this.state.chartId) {
            await this.saveChart();
            if (!this.state.chartId) {
                return;
            }
        }
        const dashboards = await this.orm.searchRead(
            "bi.dashboard", [], ["name"]);
        this.dialogService.add(AddToDashboardDialog, {
            dashboards,
            onConfirm: async (choice) => {
                let dashboardId = choice.dashboardId;
                if (!dashboardId) {
                    [dashboardId] = await this.orm.create(
                        "bi.dashboard", [{ name: choice.newName }]);
                }
                await this.orm.call("bi.dashboard", "add_chart",
                    [[dashboardId], this.state.chartId]);
                this.actionService.doAction({
                    type: "ir.actions.client",
                    tag: "biz_bi.dashboard",
                    params: { dashboard_id: dashboardId },
                });
            },
        });
    }
}

registry.category("actions").add("biz_bi.explore", ExploreAction);
