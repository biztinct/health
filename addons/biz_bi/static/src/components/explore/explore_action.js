/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "./chart_renderer";
import { KpiCard } from "./kpi_card";
import { DataTable } from "./data_table";
import { PivotTable } from "./pivot_table";
import { RecordsTable } from "./records_table";
import { AddToDashboardDialog } from "./add_to_dashboard_dialog";
import {
    checkCompatibility,
    recommendChartType,
} from "../../core/chart_recommender";
import { RELATIVE_RANGES } from "../../core/range_labels";

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
    { type: "sankey", label: _t("Sankey"), icon: "sankey" },
    { type: "radar", label: _t("Radar"), icon: "radar" },
];

const DATE_GRAINS = ["year", "quarter", "month", "week", "day"];
const AGGS = ["sum", "avg", "min", "max", "count", "count_distinct"];

// Records preview cap. The engine clamps to MAX_ROWS anyway; asking for it
// explicitly keeps the "showing X of Y" banner honest about what we asked for.
const RECORDS_PREVIEW_LIMIT = 5000;

export class ExploreAction extends Component {
    static template = "biz_bi.Explore";
    static components = { ChartRenderer, KpiCard, DataTable, PivotTable, RecordsTable };
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
        this.relativeRanges = RELATIVE_RANGES;

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
            // Records mode. recordColumns is kept SEPARATE from the aggregate
            // slots (which are never touched here) so toggling back to
            // Summary restores the previous chart exactly.
            tableMode: "summary",
            recordColumns: [],
            recordsSeeded: false,
            recordSort: null, // {fieldId, dir}
            exporting: false,
        });
        this.labels = {
            records: _t("Records"),
            summary: _t("Summary"),
            excel: _t("Excel"),
            exporting: _t("Exporting…"),
            exportTitle: _t("Download these rows as an Excel file"),
        };
        this._debounce = null;

        onWillStart(async () => {
            this.state.datasets = await this.orm.searchRead(
                "bi.dataset",
                [["state", "=", "published"]],
                ["name", "description", "is_certified", "storage_mode"]
            );
            this.orm.call("bi.ai", "is_available", [])
                .then((available) => {
                    this.state.aiAvailable = available;
                })
                // A fire-and-forget probe in onWillStart has no error path of
                // its own: any rejection reaches the global handler as a modal
                // on a screen that otherwise works (ledger §5.127c). "Can I use
                // AI?" always has an answer, and on failure it is "no".
                .catch(() => {
                    this.state.aiAvailable = false;
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
        this.resetRecordsState();
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
        this.resetRecordsState();
        if ((config.mode || "aggregate") === "detail") {
            this.state.tableMode = "records";
            this.state.recordsSeeded = true;
            this.state.recordColumns = (slots.columns || [])
                .filter((e) => byId[e.field_id])
                .map((e) => ({ ...byId[e.field_id] }));
            const saved = (config.sort || [])[0];
            if (saved && /^d\d+$/.test(saved.ref || "")) {
                const chip = this.state.recordColumns[
                    parseInt(saved.ref.slice(1), 10)];
                if (chip) {
                    this.state.recordSort = {
                        fieldId: chip.id,
                        dir: saved.dir === "desc" ? "desc" : "asc",
                    };
                }
            }
        }
    }

    resetRecordsState() {
        this.state.tableMode = "summary";
        this.state.recordColumns = [];
        this.state.recordsSeeded = false;
        this.state.recordSort = null;
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

    // ------------------------------------------------------------------
    // Records mode
    // ------------------------------------------------------------------

    get isRecords() {
        return this.state.chartType === "table" &&
            this.state.tableMode === "records";
    }

    setTableMode(mode) {
        if (this.state.tableMode === mode) {
            return;
        }
        this.state.tableMode = mode;
        if (mode === "records" && !this.state.recordsSeeded) {
            // first switch: seed the columns from whatever the user already
            // configured, in the order they read on screen
            this.state.recordsSeeded = true;
            const seen = new Set();
            const seeded = [];
            for (const chip of [
                ...this.state.slots.x,
                ...this.state.slots.series,
                ...this.state.slots.values,
            ]) {
                if (seen.has(chip.id)) {
                    continue;
                }
                seen.add(chip.id);
                seeded.push({ ...chip });
            }
            this.state.recordColumns = seeded;
        }
        this.refresh();
    }

    onFieldActivate(field) {
        if (this.isRecords) {
            this.addRecordColumn(field);
            return;
        }
        this.addToSlot(field.role === "measure" ? "values" : "x", field);
    }

    addRecordColumn(field, index = null) {
        const columns = this.state.recordColumns;
        if (columns.some((chip) => chip.id === field.id)) {
            return;
        }
        const at = index === null
            ? columns.length
            : Math.max(0, Math.min(index, columns.length));
        columns.splice(at, 0, { ...field });
        this.refresh();
    }

    moveRecordColumn(from, to) {
        const columns = this.state.recordColumns;
        if (from < 0 || from >= columns.length) {
            return;
        }
        const [chip] = columns.splice(from, 1);
        // `to` was computed against the pre-removal layout
        const target = Math.max(0, Math.min(to > from ? to - 1 : to,
                                            columns.length));
        columns.splice(target, 0, chip);
        this.refresh();
    }

    removeRecordColumn(index) {
        const [removed] = this.state.recordColumns.splice(index, 1);
        if (removed && this.state.recordSort &&
                this.state.recordSort.fieldId === removed.id) {
            this.state.recordSort = null;
        }
        this.refresh();
    }

    toggleRecordSort(index) {
        const chip = this.state.recordColumns[index];
        if (!chip) {
            return;
        }
        const current = this.state.recordSort;
        if (!current || current.fieldId !== chip.id) {
            this.state.recordSort = { fieldId: chip.id, dir: "asc" };
        } else if (current.dir === "asc") {
            this.state.recordSort = { fieldId: chip.id, dir: "desc" };
        } else {
            this.state.recordSort = null;
        }
        this.refresh();
    }

    recordSortSpec() {
        const sort = this.state.recordSort;
        if (!sort) {
            return [];
        }
        const index = this.state.recordColumns.findIndex(
            (chip) => chip.id === sort.fieldId);
        return index === -1 ? [] : [{ ref: "d" + index, dir: sort.dir }];
    }

    get truncation() {
        const meta = this.state.envelope && this.state.envelope.meta;
        if (!meta || !meta.truncated || !meta.total_count) {
            return null;
        }
        const lang = (user.lang || "en_US").replace("_", "-");
        const num = (value) => Number(value).toLocaleString(lang);
        return _t(
            "Showing %(shown)s of %(total)s — refine filters, or export up to %(cap)s rows.",
            {
                shown: num(meta.row_count),
                total: num(meta.total_count),
                cap: num(meta.export_cap || 20000),
            }
        );
    }

    // ------------------------------------------------------------------
    // Excel export (works for a saved OR an unsaved chart, both modes)
    // ------------------------------------------------------------------

    get exportTitle() {
        const name = (this.state.chartName || "").trim();
        if (name) {
            return name;
        }
        const dataset = this.state.datasets.find(
            (entry) => entry.id === this.state.datasetId);
        const prefix = this.isRecords ? _t("Records") : _t("Chart");
        return dataset ? `${prefix} - ${dataset.name}` : String(prefix);
    }

    async exportExcel() {
        if (this.state.exporting) {
            return;
        }
        if (!this.state.envelope || this.state.envelope.error) {
            this.notification.add(_t("Nothing to export yet."),
                { type: "warning" });
            return;
        }
        this.state.exporting = true;
        try {
            const body = new FormData();
            body.append("request_json", JSON.stringify(this.buildRequest()));
            body.append("title", this.exportTitle);
            body.append("csrf_token", odoo.csrf_token);
            const response = await fetch("/bi/export/xlsx", {
                method: "POST",
                body,
            });
            if (!response.ok) {
                throw new Error((await response.text()) || "");
            }
            // a POST cannot window.open — go through a blob + <a download>
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `${this.exportTitle}.xlsx`.replace(/[/\\]/g, "-");
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            this.notification.add(
                (error && error.message) || _t("Export failed."),
                { type: "danger" });
        } finally {
            this.state.exporting = false;
        }
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
        if (!this.state.userPickedType && !this.isRecords) {
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
        if (this.isRecords) {
            // records are rows, not a shape — the gallery collapses to Table
            return {
                ok: type === "table",
                reason: _t("Switch to Summary for charts"),
                recommended: false,
                active: type === "table",
            };
        }
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
        if (type !== "table") {
            this.state.tableMode = "summary";
        }
        this.refresh();
    }

    // ------------------------------------------------------------------
    // Query & preview
    // ------------------------------------------------------------------

    get filterEntries() {
        return this.state.slots.filters
            .filter((chip) => chip.op && chip.value !== "" && chip.value !== undefined)
            .map((chip) => ({
                field_id: chip.id,
                op: chip.op,
                value: chip.value,
            }));
    }

    buildRequest() {
        const slots = this.state.slots;
        if (this.isRecords) {
            return {
                dataset_id: this.state.datasetId,
                dimensions: this.state.recordColumns.map((chip) => ({
                    field_id: chip.id,
                })),
                measures: [],
                filters: this.filterEntries,
                sort: this.recordSortSpec(),
                limit: RECORDS_PREVIEW_LIMIT,
                mode: "detail",
            };
        }
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
            filters: this.filterEntries,
            sort: slots.values.length && this.state.chartType !== "line"
                ? [{ ref: "m0", dir: "desc" }]
                : [],
            limit: 500,
        };
    }

    refresh() {
        clearTimeout(this._debounce);
        if (this.isRecords) {
            if (!this.state.recordColumns.length) {
                this.state.envelope = null;
                return;
            }
        } else if (!this.state.slots.values.length &&
                   this.state.chartType !== "table") {
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
        const config = {
            version: 1,
            chart_type: this.state.chartType,
            slots: {
                x: slots.x.map((c) => ({ field_id: c.id, grain: c.grain })),
                values: slots.values.map((c) => ({ field_id: c.id, agg: c.agg })),
                series: slots.series.map((c) => ({ field_id: c.id, grain: c.grain })),
            },
            filters: this.filterEntries,
            sort: [],
            limit: 500,
            display: {},
        };
        if (this.isRecords) {
            config.mode = "detail";
            config.slots.columns = this.state.recordColumns.map(
                (c) => ({ field_id: c.id }));
            config.sort = this.recordSortSpec();
            config.limit = RECORDS_PREVIEW_LIMIT;
        }
        return config;
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
                [this.state.chartId] = await this.orm.create(
                    "bi.chart", [values]);
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
