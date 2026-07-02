/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STEP_TYPES = [
    { type: "rename", label: _t("Rename Columns") },
    { type: "cast", label: _t("Change Type") },
    { type: "filter", label: _t("Filter Rows") },
    { type: "calc", label: _t("Calculated Column") },
    { type: "dedupe", label: _t("Remove Duplicates") },
];

const FILTER_OPS = ["eq", "neq", "gt", "gte", "lt", "lte", "like_i",
                    "is_set", "is_null"];
const CAST_TARGETS = ["numeric", "integer", "date", "timestamp",
                      "boolean", "text"];

function defaultParams(type) {
    switch (type) {
        case "rename": return { map: {} };
        case "cast": return { col: "", to: "numeric" };
        case "filter": return { conditions: [["", "eq", ""]] };
        case "calc": return { as: "", expression: "" };
        case "dedupe": return { keys: [], order_by: [] };
        default: return {};
    }
}

export class PipelineAction extends Component {
    static template = "biz_bi.Pipeline";
    static props = { "*": true };
    static displayName = _t("Pipeline Editor");

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.stepTypes = STEP_TYPES;
        this.filterOps = FILTER_OPS;
        this.castTargets = CAST_TARGETS;

        this.state = useState({
            sources: [],
            sourceId: null,
            editor: null, // get_editor_data payload
            steps: [],
            addMenuOpen: false,
            dirty: false,
            busy: false,
        });

        onWillStart(async () => {
            this.state.sources = await this.orm.searchRead(
                "bi.source", [], ["name", "type"], { order: "name" });
            const params = this.props.action?.params || {};
            const initial = params.source_id
                || (this.state.sources[0] && this.state.sources[0].id);
            if (initial) {
                await this.loadSource(initial);
            }
        });
    }

    onSourceSelectChange(ev) {
        const sourceId = parseInt(ev.target.value);
        if (sourceId) {
            this.loadSource(sourceId);
        }
    }

    async loadSource(sourceId) {
        this.state.sourceId = sourceId;
        this.state.editor = await this.orm.call(
            "bi.pipeline", "get_editor_data", [sourceId]);
        this.state.steps = JSON.parse(
            JSON.stringify(this.state.editor.steps || []));
        this.state.dirty = false;
    }

    /** Columns available BEFORE the given step index. */
    schemaBefore(index) {
        const schemas = this.state.editor?.schemas || [];
        // schemas are index-aligned with SAVED steps; for locally edited
        // steps past the last valid schema, fall back to the deepest known
        const schema = schemas[Math.min(index, schemas.length - 1)] || [];
        return schema.map(([name, type]) => ({ name, type }));
    }

    stepError(index) {
        const editor = this.state.editor;
        return editor && !this.state.dirty && editor.invalid_step === index
            ? editor.error : null;
    }

    // ------------------------------------------------------------------
    // Step list edits (local until Apply)
    // ------------------------------------------------------------------

    markDirty() {
        this.state.dirty = true;
    }

    addStep(type) {
        this.state.steps.push({
            id: "s" + (this.state.steps.length + 1),
            type,
            params: defaultParams(type),
        });
        this.state.addMenuOpen = false;
        this.markDirty();
    }

    removeStep(index) {
        this.state.steps.splice(index, 1);
        this.markDirty();
    }

    moveStep(index, delta) {
        const target = index + delta;
        if (target < 0 || target >= this.state.steps.length) {
            return;
        }
        const [step] = this.state.steps.splice(index, 1);
        this.state.steps.splice(target, 0, step);
        this.markDirty();
    }

    // rename helpers
    renameEntries(step) {
        return Object.entries(step.params.map || {});
    }

    addRename(step) {
        step.params.map = { ...(step.params.map || {}), "": "" };
        this.markDirty();
    }

    setRename(step, oldKey, newOld, newName) {
        const map = { ...(step.params.map || {}) };
        delete map[oldKey];
        if (newOld) {
            map[newOld] = newName;
        }
        step.params.map = map;
        this.markDirty();
    }

    // filter helpers
    addCondition(step) {
        step.params.conditions.push(["", "eq", ""]);
        this.markDirty();
    }

    removeCondition(step, index) {
        step.params.conditions.splice(index, 1);
        this.markDirty();
    }

    setCondition(step, index, position, value) {
        step.params.conditions[index][position] = value;
        this.markDirty();
    }

    // dedupe helpers
    toggleKey(step, column) {
        const keys = step.params.keys || [];
        const at = keys.indexOf(column);
        if (at === -1) {
            keys.push(column);
        } else {
            keys.splice(at, 1);
        }
        step.params.keys = keys;
        this.markDirty();
    }

    setDedupeOrder(step, column, direction) {
        step.params.order_by = column
            ? [{ col: column, dir: direction || "desc" }] : [];
        this.markDirty();
    }

    // ------------------------------------------------------------------
    // Apply
    // ------------------------------------------------------------------

    async apply() {
        this.state.busy = true;
        try {
            const steps = this.state.steps.map((step, index) => ({
                ...step, id: "s" + (index + 1),
            }));
            this.state.editor = await this.orm.call(
                "bi.pipeline", "save_steps",
                [this.state.sourceId, steps, true]);
            this.state.steps = JSON.parse(
                JSON.stringify(this.state.editor.steps || []));
            this.state.dirty = false;
            if (this.state.editor.error) {
                this.notification.add(this.state.editor.error,
                    { type: "warning" });
            } else {
                this.notification.add(_t("Pipeline applied."),
                    { type: "success" });
            }
        } finally {
            this.state.busy = false;
        }
    }

    stepTypeLabel(type) {
        const entry = STEP_TYPES.find((s) => s.type === type);
        return entry ? entry.label : type;
    }
}

registry.category("actions").add("biz_bi.pipeline", PipelineAction);
