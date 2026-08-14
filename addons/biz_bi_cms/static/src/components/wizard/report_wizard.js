/** @odoo-module **/

import {
    Component,
    markup,
    onWillStart,
    onWillUnmount,
    useEffect,
    useRef,
    useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

import { ChartRenderer } from "@biz_bi/components/explore/chart_renderer";
import { KpiCard } from "@biz_bi/components/explore/kpi_card";
import { DataTable } from "@biz_bi/components/explore/data_table";
import { PivotTable } from "@biz_bi/components/explore/pivot_table";
import {
    checkCompatibility,
    recommendChartType,
} from "@biz_bi/core/chart_recommender";
import { RELATIVE_RANGES } from "@biz_bi/core/range_labels";

// ---------------------------------------------------------------------------
// Inline SVG icons — repo convention (never emoji, never font-awesome inside
// our own body markup). Same helper shape as the hub's, kept local so the two
// components stay independently editable.
// ---------------------------------------------------------------------------

function svgIcon(body, size) {
    return markup(
        `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" ` +
            `stroke="currentColor" stroke-width="2" stroke-linecap="round" ` +
            `stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`
    );
}

const UI_ICONS = {
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    next: '<path d="m9 18 6-6-6-6"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    spark: '<path d="M12 3v4"/><path d="M12 17v4"/><path d="M3 12h4"/>' +
        '<path d="M17 12h4"/><path d="m5.6 5.6 2.8 2.8"/>' +
        '<path d="m15.6 15.6 2.8 2.8"/><path d="m18.4 5.6-2.8 2.8"/>' +
        '<path d="m8.4 15.6-2.8 2.8"/>',
    data: '<ellipse cx="12" cy="6" rx="8" ry="3"/>' +
        '<path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/>' +
        '<path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    certified: '<path d="m9 12 2 2 4-4"/><circle cx="12" cy="12" r="9"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/>' +
        '<path d="M3 10h18"/><path d="M8 3v4"/><path d="M16 3v4"/>',
    empty: '<path d="M3 3v18h18"/><path d="M7 16h.01"/><path d="M12 16h.01"/>' +
        '<path d="M17 16h.01"/>',
    external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>' +
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    chart: '<path d="M3 21h18"/><rect x="5" y="10" width="4" height="8"/>' +
        '<rect x="10" y="6" width="4" height="12"/>' +
        '<rect x="15" y="13" width="4" height="5"/>',
    rows: '<rect x="3" y="4" width="18" height="16" rx="2"/>' +
        '<path d="M3 9h18"/><path d="M3 14h18"/>',
    caret: '<path d="m6 9 6 6 6-6"/>',
    // The picked-columns row runs left→right, so the reorder affordances are
    // left/right chevrons — an up/down pair would contradict its own tooltip.
    left: '<path d="m15 18-6-6 6-6"/>',
    right: '<path d="m9 18 6-6-6-6"/>',
    xlsx: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
        '<path d="M14 2v6h6"/><path d="m9 13 6 6"/><path d="m15 13-6 6"/>',
};

// A deliberately approachable subset of biz_bi's nineteen chart types. The
// full gallery stays in the advanced builder, one click away.
const CHART_GALLERY = [
    {
        type: "bar",
        label: _t("Bar"),
        icon: '<path d="M3 21h18"/><rect x="5" y="10" width="4" height="8"/>' +
            '<rect x="10" y="6" width="4" height="12"/>' +
            '<rect x="15" y="13" width="4" height="5"/>',
    },
    {
        type: "bar_stacked",
        label: _t("Stacked"),
        icon: '<path d="M3 21h18"/><rect x="6" y="12" width="5" height="6"/>' +
            '<rect x="6" y="6" width="5" height="6"/>' +
            '<rect x="14" y="14" width="5" height="4"/>' +
            '<rect x="14" y="9" width="5" height="5"/>',
    },
    {
        type: "line",
        label: _t("Line"),
        icon: '<path d="M3 21h18"/><polyline points="4,16 9,10 13,13 20,5"/>',
    },
    {
        type: "area",
        label: _t("Area"),
        icon: '<path d="M3 21h18"/><path d="M4 18v-3l5-5 4 3 7-7v12z"/>',
    },
    {
        type: "donut",
        label: _t("Donut"),
        icon: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    },
    {
        type: "kpi",
        label: _t("Big number"),
        icon: '<rect x="3" y="5" width="18" height="14" rx="2"/>' +
            '<path d="M7 10h6"/><path d="M7 14h10"/>',
    },
    {
        type: "table",
        label: _t("Table"),
        icon: '<rect x="3" y="4" width="18" height="16" rx="2"/>' +
            '<path d="M3 10h18"/><path d="M9 4v16"/>',
    },
    {
        type: "pivot",
        label: _t("Matrix"),
        icon: '<rect x="3" y="4" width="18" height="16" rx="2"/>' +
            '<path d="M3 9h18"/><path d="M3 14h18"/><path d="M9 4v16"/>' +
            '<path d="M15 4v16"/>',
    },
];

const DATE_GRAINS = ["year", "quarter", "month", "week", "day"];
const DATE_TYPES = ["date", "datetime"];

// --- Records path ----------------------------------------------------------
// Three different numbers, deliberately:
//   * RECORDS_PREVIEW_LIMIT is what the PREVIEW asks the engine for. The
//     envelope still carries the honest `meta.total_count`, so a small number
//     here costs nothing in honesty and keeps the wizard snappy.
//   * RECORDS_PREVIEW_MAX_ROWS is what the preview RENDERS (ledger §5.139 —
//     bound the node count, never silently).
//   * RECORDS_SAVED_LIMIT is what the SAVED chart carries, matching the limit
//     Explore writes for a Records chart (`explore_action.js`'s
//     RECORDS_PREVIEW_LIMIT), so a wizard-made and an Explore-made records
//     chart are the same row on the dashboard.
// The Excel export is bounded by neither: the server re-runs the request at
// `biz_bi.export_row_cap`.
const RECORDS_PREVIEW_LIMIT = 1000;
const RECORDS_PREVIEW_MAX_ROWS = 100;
const RECORDS_SAVED_LIMIT = 5000;

/**
 * The guided three-step report builder.
 *
 * It is a consolidation of `biz_bi`'s Explore builder for people who do not
 * think in measures and dimensions: pick a dataset, answer two questions,
 * look at the result, save it onto a dashboard. Everything it produces is an
 * ordinary `bi.chart` with an ordinary `config_json`, byte-compatible with
 * what Explore writes (`explore_action.js:466`) — so "Open in advanced
 * builder" is a lossless hand-off in both directions and nothing downstream
 * has to know a wizard exists.
 */
export class ReportWizard extends Component {
    static template = "biz_bi_cms.ReportWizard";
    static components = { ChartRenderer, KpiCard, DataTable, PivotTable };
    static props = { onClose: Function };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.biData = useService("bi_data");

        this.gallery = CHART_GALLERY;
        this.grains = DATE_GRAINS;
        this.relativeRanges = RELATIVE_RANGES;

        // Keyboard: the pane takes focus every time the step changes, so Tab
        // starts at the top of the content the user just advanced to instead
        // of at the browser chrome, and Escape (handled on the root) is live
        // from the moment the overlay opens.
        this.paneRef = useRef("pane");

        this.state = useState({
            step: 1,
            datasets: [],
            datasetId: null,
            metadata: null,
            measure: null,
            agg: "sum",
            groupBy: null,
            grain: "month",
            splitBy: null,
            dateField: null,
            dateRange: "",
            chartType: "bar",
            userPickedType: false,
            envelope: null,
            loading: false,
            chartName: "",
            aiPrompt: "",
            aiBusy: false,
            dashboards: [],
            targetDashboardId: 0, // 0 == the "New dashboard" option
            newDashboardName: "",
            saving: false,
            // --- bookkeeping beyond the handover's state list ---------------
            aiAvailable: false,
            chartId: null, // survives a failed add_chart so a retry cannot
            // create a second chart
            nameTouched: false,
            // --- RT-2: the Records list path -------------------------------
            buildMode: "chart", // "chart" | "records"
            recordColumns: [], // ORDERED — the column order is the report
            closedFolders: {}, // folders open by default, closed by exception
            exporting: false,
        });
        this._debounce = null;

        onWillStart(async () => {
            this.state.newDashboardName = _t("My dashboard").toString();
            this.state.datasets = await this.orm.searchRead(
                "bi.dataset",
                [["state", "=", "published"]],
                ["name", "description", "is_certified", "storage_mode"]
            );
            // AWAITED, and safe to call unguarded: biz_bi_cms/models/bi_ai.py
            // makes the probe answer False instead of raising for a user who
            // cannot read bi.ai.provider (ledger §5.127b).
            this.state.aiAvailable = !!(await this.orm.call(
                "bi.ai", "is_available", []));
            if (this.state.datasets.length === 1) {
                await this.selectDataset(this.state.datasets[0].id);
            }
        });

        useEffect(
            () => {
                if (this.paneRef.el) {
                    this.paneRef.el.focus({ preventScroll: true });
                }
            },
            () => [this.state.step]
        );

        onWillUnmount(() => clearTimeout(this._debounce));
    }

    // ------------------------------------------------------------------
    // Keyboard
    // ------------------------------------------------------------------

    /** Escape closes the overlay. Nothing else is trapped: the pane holds
     *  focus, every control is a real focusable element, and Tab / Enter are
     *  the browser's own. */
    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.close();
        }
    }

    /** Enter in the name field saves, the way it would in a one-field form. */
    onNameKeydown(ev) {
        this.onNameTouched();
        if (ev.key === "Enter" && !this.state.saving) {
            ev.preventDefault();
            this.saveReport();
        }
    }

    // ------------------------------------------------------------------
    // Icons & labels
    // ------------------------------------------------------------------

    uiIcon(name, size = 16) {
        return svgIcon(UI_ICONS[name] || UI_ICONS.empty, size);
    }

    galleryIcon(entry) {
        return svgIcon(entry.icon, 20);
    }

    get bigEmptyIcon() {
        return svgIcon(UI_ICONS.empty, 40);
    }

    get steps() {
        return [
            { index: 1, label: _t("Choose data") },
            { index: 2, label: _t("Build") },
            { index: 3, label: _t("Preview & save") },
        ];
    }

    /** The engine's grain keys are technical; the wizard shows words. */
    grainLabel(grain) {
        return {
            year: _t("Year"),
            quarter: _t("Quarter"),
            month: _t("Month"),
            week: _t("Week"),
            day: _t("Day"),
        }[grain] || grain;
    }

    get closeLabel() {
        return _t("Close");
    }

    get modeGroupLabel() {
        return _t("What kind of report?");
    }

    get moveLeftLabel() {
        return _t("Move left");
    }

    get moveRightLabel() {
        return _t("Move right");
    }

    get removeColumnLabel() {
        return _t("Remove column");
    }

    get namePlaceholder() {
        return _t("Report name");
    }

    get aiPlaceholder() {
        return _t("e.g. monthly revenue by facility");
    }

    get newDashboardPlaceholder() {
        return _t("New dashboard name");
    }

    // ------------------------------------------------------------------
    // Field groups
    // ------------------------------------------------------------------

    get fields() {
        return (this.state.metadata && this.state.metadata.fields) || [];
    }

    isDate(field) {
        return !!field && DATE_TYPES.includes(field.data_type);
    }

    /** Measures aggregate; `role === "id"` join keys are never offered
     *  (Explore skips them too — explore_action.js:228). */
    get measureFields() {
        return this.fields.filter((f) => f.role === "measure");
    }

    get dimensionFields() {
        return this.fields.filter((f) => f.role !== "measure" && f.role !== "id");
    }

    get dateFields() {
        return this.fields.filter((f) => this.isDate(f) && f.role !== "id");
    }

    // ------------------------------------------------------------------
    // Step 2 — the path choice (Chart | Records list)
    // ------------------------------------------------------------------

    get isRecords() {
        return this.state.buildMode === "records";
    }

    get modeEntries() {
        return [
            { key: "chart", label: _t("Chart"), icon: "chart" },
            { key: "records", label: _t("Records list"), icon: "rows" },
        ];
    }

    /** Switching path throws away the preview, never the pickers: going
     *  Records → Chart → Records must not lose the columns somebody ticked,
     *  and the date range is shared by both paths on purpose. */
    setBuildMode(mode) {
        if (this.state.buildMode === mode) {
            return;
        }
        this.state.buildMode = mode;
        this.state.envelope = null;
        this.state.chartId = null; // a saved chart is one shape or the other
        this.state.userPickedType = false;
        if (mode === "records") {
            this.state.chartType = "table";
        }
        this.afterChange();
    }

    // ------------------------------------------------------------------
    // Records: the column checklist
    // ------------------------------------------------------------------

    /** Everything a record can show. `role === "id"` join keys are skipped
     *  exactly as Explore's field well skips them
     *  (explore_action.js:284). */
    get columnFolders() {
        const folders = new Map();
        for (const field of this.fields) {
            if (field.role === "id") {
                continue;
            }
            const name = field.folder || _t("General").toString();
            if (!folders.has(name)) {
                folders.set(name, []);
            }
            folders.get(name).push(field);
        }
        return [...folders.entries()]
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([name, fields]) => ({ name, fields }));
    }

    isFolderOpen(name) {
        return !this.state.closedFolders[name];
    }

    toggleFolder(name) {
        this.state.closedFolders[name] = this.isFolderOpen(name);
    }

    isColumnPicked(field) {
        return this.state.recordColumns.some((chip) => chip.id === field.id);
    }

    toggleColumn(field) {
        const columns = this.state.recordColumns;
        const index = columns.findIndex((chip) => chip.id === field.id);
        if (index === -1) {
            columns.push({ id: field.id, name: field.name });
        } else {
            columns.splice(index, 1);
        }
        this.afterChange();
    }

    removeColumn(index) {
        this.state.recordColumns.splice(index, 1);
        this.afterChange();
    }

    /** ‹/› in the picked-columns row. `delta` is -1 (earlier) or +1 (later);
     *  the ends are no-ops rather than wraps. */
    moveColumn(index, delta) {
        const columns = this.state.recordColumns;
        const target = index + delta;
        if (index < 0 || index >= columns.length ||
                target < 0 || target >= columns.length) {
            return;
        }
        const [chip] = columns.splice(index, 1);
        columns.splice(target, 0, chip);
        this.afterChange();
    }

    // ------------------------------------------------------------------
    // Step 1 — dataset
    // ------------------------------------------------------------------

    async selectDataset(datasetId) {
        this.state.metadata = await this.orm.call(
            "bi.dataset", "get_builder_metadata", [[datasetId]]);
        this.state.datasetId = datasetId;
        this.state.measure = null;
        this.state.agg = "sum";
        this.state.groupBy = null;
        this.state.grain = "month";
        this.state.splitBy = null;
        this.state.dateRange = "";
        this.state.envelope = null;
        this.state.chartId = null;
        this.state.chartName = "";
        this.state.nameTouched = false;
        this.state.userPickedType = false;
        this.state.chartType = "bar";
        // A new dataset means new field ids: a column picked against the
        // previous one would be a foreign key into another dataset.
        this.state.buildMode = "chart";
        this.state.recordColumns = [];
        this.state.closedFolders = {};
        const dates = this.dateFields;
        this.state.dateField = dates.length ? dates[0] : null;
        this.state.step = 2;
        // Seed the recommendation so the gallery never opens with a
        // highlighted-but-impossible type.
        this.afterChange();
    }

    datasetSubtitle(dataset) {
        return dataset.description || "";
    }

    // ------------------------------------------------------------------
    // Step 2 — pickers
    // ------------------------------------------------------------------

    _fieldById(rawId) {
        const id = parseInt(rawId, 10);
        return this.fields.find((f) => f.id === id) || null;
    }

    onMeasureChange(ev) {
        const field = this._fieldById(ev.target.value);
        this.state.measure = field;
        // "picking sets agg = default_agg || sum" — `none` is biz_bi's way of
        // saying "no opinion", so it falls through to sum as well.
        this.state.agg =
            field && field.default_agg && field.default_agg !== "none"
                ? field.default_agg
                : "sum";
        this.afterChange();
    }

    onGroupByChange(ev) {
        this.state.groupBy = this._fieldById(ev.target.value);
        if (this.isDate(this.state.groupBy) && !this.state.grain) {
            this.state.grain = "month";
        }
        this.afterChange();
    }

    onSplitByChange(ev) {
        this.state.splitBy = this._fieldById(ev.target.value);
        this.afterChange();
    }

    onDateFieldChange(ev) {
        this.state.dateField = this._fieldById(ev.target.value);
        this.afterChange();
    }

    setGrain(grain) {
        this.state.grain = grain;
        this.afterChange();
    }

    /** Chips toggle: clicking the active range clears it back to All time. */
    setDateRange(value) {
        this.state.dateRange = this.state.dateRange === value ? "" : value;
        this.afterChange();
    }

    /** Once the user has touched the name, `afterChange` stops re-deriving
     *  it from the pickers — going Back and changing the breakdown must not
     *  silently overwrite a title somebody typed. */
    onNameTouched() {
        this.state.nameTouched = true;
    }

    afterChange() {
        if (this.isRecords) {
            // A records report IS a table — the gallery is hidden on this
            // path, so nothing may re-recommend a chart type underneath it.
            this.state.chartType = "table";
        } else if (!this.state.userPickedType) {
            this.state.chartType = recommendChartType(
                this.dimChips, this.measureChips);
        }
        if (!this.state.nameTouched) {
            this.state.chartName = this.defaultName;
        }
        if (this.state.step === 3) {
            this.state.envelope = null;
            this.schedulePreview();
        }
    }

    // Explore's chip shapes, exactly: dims [{id, grain?, ...field}],
    // measures [{id, agg, ...field}].
    get dimChips() {
        const chips = [];
        if (this.state.groupBy) {
            chips.push({
                ...this.state.groupBy,
                grain: this.isDate(this.state.groupBy)
                    ? this.state.grain : undefined,
            });
        }
        if (this.state.splitBy) {
            chips.push({
                ...this.state.splitBy,
                grain: this.isDate(this.state.splitBy) ? "month" : undefined,
            });
        }
        return chips;
    }

    get measureChips() {
        return this.state.measure
            ? [{ ...this.state.measure, agg: this.state.agg }]
            : [];
    }

    get defaultName() {
        if (this.isRecords) {
            const dataset =
                (this.state.metadata && this.state.metadata.name) || "";
            return dataset
                ? _t("%(dataset)s records", { dataset }).toString()
                : _t("Records").toString();
        }
        const measure = this.state.measure ? this.state.measure.name : "";
        const group = this.state.groupBy ? this.state.groupBy.name : "";
        if (measure && group) {
            return _t("%(measure)s by %(group)s",
                      { measure: measure, group: group }).toString();
        }
        return measure || _t("New report").toString();
    }

    // ------------------------------------------------------------------
    // Chart type gallery
    // ------------------------------------------------------------------

    galleryEntryState(type) {
        const compat = checkCompatibility(type, this.dimChips, this.measureChips);
        return {
            ok: compat.ok,
            reason: compat.reason || "",
            recommended:
                recommendChartType(this.dimChips, this.measureChips) === type,
            active: this.state.chartType === type,
        };
    }

    pickChartType(type) {
        this.state.chartType = type;
        this.state.userPickedType = true;
        if (this.state.step === 3) {
            this.state.envelope = null;
            this.schedulePreview();
        }
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    /** Step dots are clickable BACKWARDS only — going forward has
     *  preconditions and belongs to the explicit buttons. */
    goToStep(index) {
        if (index < this.state.step) {
            this.state.step = index;
        }
    }

    get canPreview() {
        if (this.isRecords) {
            // "require ≥1 column to continue" — nothing else is mandatory:
            // a records list with no date range is every record, honestly.
            return this.state.recordColumns.length > 0;
        }
        if (!this.state.measure) {
            return false;
        }
        // A big number needs a measure and nothing else.
        return this.state.chartType === "kpi" || !!this.state.groupBy;
    }

    async goToPreview() {
        if (!this.canPreview) {
            return;
        }
        this.state.step = 3;
        if (!this.state.chartName) {
            this.state.chartName = this.defaultName;
        }
        await this.loadDashboards();
        this.schedulePreview();
    }

    async loadDashboards() {
        // AH-3: the list is now what the user may WRITE, not merely what they
        // may see — `get_wizard_targets` applies the same predicate the
        // dashboard screen publishes as `can_edit`. Offering a dashboard the
        // save would refuse was the last "discovered at Save time" surprise
        // left in the wizard.
        //
        // The save path KEEPS its AccessError branch: ownership can change
        // between this call and the click, and a viewer legitimately gets an
        // empty list here.
        try {
            this.state.dashboards = await this.orm.call(
                "bi.dashboard", "get_wizard_targets", []);
        } catch {
            this.state.dashboards = [];
        }
        if (!this.state.dashboards.some(
            (dash) => dash.id === this.state.targetDashboardId)) {
            // Nothing writable (or the preselection went away): "New
            // dashboard" is the only honest default.
            this.state.targetDashboardId = 0;
        }
    }

    /** Step 3 says so out loud when there is nothing to add to. */
    get hasNoTargets() {
        return !this.state.dashboards.length;
    }

    close() {
        this.props.onClose();
    }

    /** The escape hatch: hand the exact same state to the full builder.
     *
     *  A SAVED report travels as `chart_id` and Explore rebuilds everything
     *  from its `config_json`. An unsaved one used to travel as a bare
     *  `dataset_id`, which opened the builder in Summary with an empty
     *  canvas — the columns somebody had just ticked were simply gone.
     *  `records_config` is the Records path's state in the shape
     *  `explore_action.js::applyRecordsConfig` reads (field ids + the same
     *  filter entries `buildRequest` sends); the chart path is unchanged. */
    openAdvanced() {
        let params;
        if (this.state.chartId) {
            params = { chart_id: this.state.chartId };
        } else {
            params = { dataset_id: this.state.datasetId };
            if (this.isRecords && this.state.recordColumns.length) {
                params.records_config = {
                    columns: this.state.recordColumns.map((chip) => chip.id),
                    filters: this.filterEntries,
                };
            }
        }
        this.props.onClose();
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_bi.explore",
            params,
        });
    }

    // ------------------------------------------------------------------
    // AI
    // ------------------------------------------------------------------

    async askAi() {
        const prompt = String(this.state.aiPrompt || "").trim();
        if (!prompt || this.state.aiBusy) {
            return;
        }
        this.state.aiBusy = true;
        let materialized = false;
        try {
            const result = await this.orm.call(
                "bi.ai", "nlq_chart", [this.state.datasetId, prompt]);
            if (result.error) {
                this.notification.add(result.error, { type: "warning" });
                return;
            }
            materialized = this.materializeConfig(result.config || {});
        } catch (error) {
            // Never blocking: the pickers below are always a complete answer.
            this.notification.add(
                _t("The assistant could not build that chart. Use the pickers below."),
                { type: "warning" });
        } finally {
            this.state.aiBusy = false;
        }
        if (materialized) {
            await this.goToPreview();
        }
    }

    /**
     * Turn an AI chart config into wizard state, the way Explore's
     * `materializeConfig` turns it into chips: every `field_id` is resolved
     * back through this dataset's metadata, and anything that does not
     * resolve is DROPPED with a warning rather than sent to the engine.
     */
    materializeConfig(config) {
        const byId = Object.fromEntries(this.fields.map((f) => [f.id, f]));
        const dropped = [];
        const resolve = (entry) => {
            if (!entry || !entry.field_id) {
                return null;
            }
            if (!byId[entry.field_id]) {
                dropped.push(entry.field_id);
                return null;
            }
            return byId[entry.field_id];
        };
        const slots = config.slots || {};
        const valueEntry = (slots.values || [])[0];
        const xEntry = (slots.x || [])[0];
        const seriesEntry = (slots.series || [])[0];

        const measure = resolve(valueEntry);
        if (measure) {
            this.state.measure = measure;
            this.state.agg =
                valueEntry.agg ||
                (measure.default_agg !== "none" && measure.default_agg) ||
                "sum";
        }
        const groupBy = resolve(xEntry);
        this.state.groupBy = groupBy;
        if (groupBy && xEntry.grain) {
            this.state.grain = xEntry.grain;
        }
        this.state.splitBy = resolve(seriesEntry);

        // The wizard offers exactly one filter row, so the first resolvable
        // relative date filter is the one it can represent.
        this.state.dateRange = "";
        for (const filter of config.filters || []) {
            const field = byId[filter.field_id];
            if (field && filter.op === "relative" && filter.value) {
                this.state.dateField = field;
                this.state.dateRange = filter.value;
                break;
            }
            if (!field && filter.field_id) {
                dropped.push(filter.field_id);
            }
        }
        if (config.chart_type) {
            this.state.chartType = config.chart_type;
            this.state.userPickedType = true;
        }
        if (config.name) {
            this.state.chartName = config.name;
            this.state.nameTouched = true;
        }
        if (dropped.length) {
            this.notification.add(
                _t("%s suggested field(s) are not in this dataset and were dropped.",
                   dropped.length),
                { type: "info" });
        }
        if (!this.state.measure) {
            this.notification.add(
                _t("The assistant did not choose a measure — pick one below."),
                { type: "warning" });
            return false;
        }
        return true;
    }

    // ------------------------------------------------------------------
    // Preview
    // ------------------------------------------------------------------

    get filterEntries() {
        if (!this.state.dateField || !this.state.dateRange) {
            return [];
        }
        // The engine's relative-range contract: op "relative", value one of
        // RELATIVE_RANGES' keys (bi_query_engine.py:46-74).
        return [{
            field_id: this.state.dateField.id,
            op: "relative",
            value: this.state.dateRange,
        }];
    }

    buildRequest() {
        if (this.isRecords) {
            // The RT-1 detail contract: ordered dimensions, no measures, no
            // grain, `mode: 'detail'`. The envelope comes back with
            // `meta.total_count` + `meta.truncated`, which is what makes the
            // banner honest.
            return {
                dataset_id: this.state.datasetId,
                dimensions: this.state.recordColumns.map((chip) => ({
                    field_id: chip.id,
                })),
                measures: [],
                filters: this.filterEntries,
                sort: [],
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
            measures: this.measureChips.map((chip) => ({
                field_id: chip.id,
                agg: chip.agg,
            })),
            filters: this.filterEntries,
            sort: this.measureChips.length && this.state.chartType !== "line"
                ? [{ ref: "m0", dir: "desc" }]
                : [],
            limit: 500,
        };
    }

    schedulePreview() {
        clearTimeout(this._debounce);
        // Synchronously, not inside the timeout: otherwise the 400 ms of
        // debounce render as the "no data" empty state before the skeleton
        // ever appears.
        this.state.loading = true;
        this._debounce = setTimeout(async () => {
            try {
                this.state.envelope = await this.biData.query(
                    this.buildRequest(), { noCache: false });
            } finally {
                this.state.loading = false;
            }
        }, 400);
    }

    get rendererKind() {
        if (this.isRecords) {
            return "table";
        }
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

    get hasRows() {
        const envelope = this.state.envelope;
        return !!(envelope && !envelope.error && (envelope.rows || []).length);
    }

    /** The dashboard tile and the wizard preview both bound what they draw
     *  (§5.139). 0 means "no cap", which is exactly today's chart path. */
    get previewMaxRows() {
        return this.isRecords ? RECORDS_PREVIEW_MAX_ROWS : 0;
    }

    /**
     * The honest headline above a records preview.
     *
     * Two different truncations can be in play and the user must not have to
     * tell them apart: the ENGINE may have cut the result at
     * `RECORDS_PREVIEW_LIMIT` (`meta.truncated`), and the TABLE renders at
     * most `RECORDS_PREVIEW_MAX_ROWS` of whatever came back. Either one means
     * the same thing to the person reading it — what is on screen is not all
     * of it, and the saved report and the export are wider.
     */
    get recordsTruncation() {
        if (!this.isRecords || !this.hasRows) {
            return null;
        }
        const envelope = this.state.envelope;
        const meta = envelope.meta || {};
        const fetched = (envelope.rows || []).length;
        const shown = Math.min(fetched, RECORDS_PREVIEW_MAX_ROWS);
        const total = meta.total_count || fetched;
        if (!meta.truncated && total <= shown) {
            return null;
        }
        const locale = (user.lang || "en_US").replace("_", "-");
        const num = (value) => Number(value).toLocaleString(locale);
        return _t(
            "Showing first %(shown)s of %(total)s records — the saved report and Excel export include more.",
            { shown: num(shown), total: num(total) }
        );
    }

    // ------------------------------------------------------------------
    // Excel export (records path) — the RT-1 POST route, verbatim pattern
    // ------------------------------------------------------------------

    get exportTitle() {
        return String(this.state.chartName || "").trim() || this.defaultName;
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
            // The server decides the row ceiling itself
            // (`biz_bi.export_row_cap`) and strips anything the client sends,
            // so the preview's small limit does not shrink the workbook.
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

    // ------------------------------------------------------------------
    // Save
    // ------------------------------------------------------------------

    /** Byte-for-byte the shape Explore writes (explore_action.js:466-483). */
    buildConfigJson() {
        if (this.isRecords) {
            // The RT-1 saved shape, verbatim: `chart_type: 'table'`,
            // `mode: 'detail'`, an ORDERED `slots.columns`, the empty
            // aggregate slots so nothing downstream has to test for their
            // absence, and the same 5 000-row limit Explore writes.
            return {
                version: 1,
                chart_type: "table",
                mode: "detail",
                slots: {
                    x: [],
                    values: [],
                    series: [],
                    columns: this.state.recordColumns.map((chip) => ({
                        field_id: chip.id,
                    })),
                },
                filters: this.filterEntries,
                sort: [],
                limit: RECORDS_SAVED_LIMIT,
                display: {},
            };
        }
        const groupBy = this.state.groupBy;
        const splitBy = this.state.splitBy;
        return {
            version: 1,
            chart_type: this.state.chartType,
            slots: {
                x: groupBy
                    ? [{
                        field_id: groupBy.id,
                        grain: this.isDate(groupBy) ? this.state.grain : undefined,
                    }]
                    : [],
                values: this.state.measure
                    ? [{ field_id: this.state.measure.id, agg: this.state.agg }]
                    : [],
                series: splitBy
                    ? [{
                        field_id: splitBy.id,
                        grain: this.isDate(splitBy) ? "month" : undefined,
                    }]
                    : [],
            },
            filters: this.filterEntries,
            sort: [],
            limit: 500,
            display: {},
        };
    }

    selectDashboard(dashboardId) {
        this.state.targetDashboardId = dashboardId;
    }

    async saveReport() {
        const name = String(this.state.chartName || "").trim();
        if (!name) {
            this.notification.add(_t("Give the report a name first."),
                                  { type: "warning" });
            return;
        }
        if (this.isRecords) {
            if (!this.state.recordColumns.length) {
                this.notification.add(_t("Pick at least one column first."),
                                      { type: "warning" });
                return;
            }
        } else if (!this.state.measure) {
            this.notification.add(_t("Pick a measure first."),
                                  { type: "warning" });
            return;
        }
        this.state.saving = true;
        let landedOn = null;
        try {
            if (!this.state.chartId) {
                // orm.create returns a LIST of ids — destructure it. Handing
                // the list on to add_chart is the 5e91455e bug.
                const [chartId] = await this.orm.create("bi.chart", [{
                    name,
                    dataset_id: this.state.datasetId,
                    chart_type: this.state.chartType,
                    config_json: this.buildConfigJson(),
                }]);
                this.state.chartId = chartId;
            }
            let dashboardId = this.state.targetDashboardId;
            if (!dashboardId) {
                const dashboardName =
                    String(this.state.newDashboardName || "").trim() ||
                    _t("My dashboard").toString();
                const [createdId] = await this.orm.create(
                    "bi.dashboard", [{ name: dashboardName }]);
                dashboardId = createdId;
                // A retry after a later failure must not create a second one.
                this.state.targetDashboardId = dashboardId;
            }
            await this.orm.call("bi.dashboard", "add_chart",
                                [[dashboardId], this.state.chartId]);
            landedOn = dashboardId;
        } catch (error) {
            const kind = (error && error.data && error.data.name) || "";
            if (kind.includes("AccessError")) {
                this.notification.add(
                    _t("You can't add a report to that dashboard. Pick another one, or create your own."),
                    { type: "warning" });
            } else {
                const message =
                    (error && error.data && error.data.message) ||
                    (error && error.message) || "";
                this.notification.add(
                    message || _t("The report could not be saved."),
                    { type: "danger" });
            }
        } finally {
            this.state.saving = false;
        }
        // Navigate only on success, and only AFTER the last state write —
        // unmounting the component first and then touching `this.state`
        // is a write to a destroyed reactive.
        if (landedOn) {
            this.notification.add(_t("Report saved."), { type: "success" });
            this.props.onClose();
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "biz_bi.dashboard",
                params: { dashboard_id: landedOn },
            });
        }
    }
}
