/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * DatasetBuilder — 3-panel Power BI-style dataset creation interface.
 * 
 * Left panel:  Field tree (browse model fields, toggle selection)
 * Center:      Data preview table (live query results)
 * Right:       Configuration (grain, filters, sort, save)
 */
export class DatasetBuilder extends Component {
    static template = "bi_studio.DatasetBuilder";
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action_service = useService("action");

        this.state = useState({
            // Loading
            loading: true,
            previewLoading: false,

            // Dataset
            datasetId: this.props.action?.params?.dataset_id || null,
            datasetName: "",
            modelName: "",
            modelLabel: "",

            // Fields
            fieldGroups: {},     // { "Source Model": { dimensions: [], measures: [], dates: [] } }
            selectedFields: {},  // { field_path: true }
            expandedGroups: {},  // { "Source Model": true }
            fieldSearch: "",

            // Preview
            previewColumns: [],
            previewRows: [],
            previewTotal: 0,

            // Config
            grainLevel: "root",
            domainFilter: "[]",
            recordLimit: 1000,
            sortField: "",
            sortOrder: "desc",
        });

        onMounted(() => this._loadDataset());
    }

    // =========================================================================
    // Data Loading
    // =========================================================================

    async _loadDataset() {
        if (!this.state.datasetId) {
            this.state.loading = false;
            return;
        }

        try {
            const ds = await this.orm.read("bi.dataset", [this.state.datasetId], [
                "name", "model_name", "model_label", "grain_level",
                "domain_filter", "record_limit", "sort_field", "sort_order",
            ]);

            if (ds.length) {
                const d = ds[0];
                this.state.datasetName = d.name;
                this.state.modelName = d.model_name;
                this.state.modelLabel = d.model_label;
                this.state.grainLevel = d.grain_level;
                this.state.domainFilter = d.domain_filter || "[]";
                this.state.recordLimit = d.record_limit || 1000;
                this.state.sortField = d.sort_field || "";
                this.state.sortOrder = d.sort_order || "desc";
            }

            // Load fields
            const fields = await this.orm.searchRead("bi.dataset.field", [
                ["dataset_id", "=", this.state.datasetId],
            ], [
                "field_name", "field_path", "field_label", "display_label",
                "odoo_field_type", "field_role", "field_group",
                "default_aggregation", "source_model_label",
                "is_from_relation", "is_selected", "sequence",
            ], { order: "sequence" });

            // Build field groups
            const groups = {};
            const selected = {};
            for (const f of fields) {
                const groupName = f.source_model_label || "Other";
                if (!groups[groupName]) {
                    groups[groupName] = { dimensions: [], measures: [], dates: [] };
                }
                const category = f.field_role === "measure" ? "measures" :
                    f.field_role === "date" ? "dates" : "dimensions";
                groups[groupName][category].push(f);
                if (f.is_selected) {
                    selected[f.field_path] = true;
                }
            }

            this.state.fieldGroups = groups;
            this.state.selectedFields = selected;

            // Expand first group
            const firstGroup = Object.keys(groups)[0];
            if (firstGroup) {
                this.state.expandedGroups[firstGroup] = true;
            }

            // Load preview
            await this._refreshPreview();
        } catch (e) {
            console.error("Dataset load error:", e);
            this.notification.add(_t("Error loading dataset"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async _refreshPreview() {
        if (!this.state.datasetId) return;

        this.state.previewLoading = true;
        try {
            const result = await this.orm.call("bi.dataset", "action_preview_data",
                [this.state.datasetId], { limit: 50 });

            this.state.previewColumns = result.columns || [];
            this.state.previewRows = result.rows || [];
            this.state.previewTotal = result.total_count || 0;
        } catch (e) {
            console.error("Preview error:", e);
        } finally {
            this.state.previewLoading = false;
        }
    }

    // =========================================================================
    // Field Selection
    // =========================================================================

    async toggleField(fieldPath) {
        const newVal = !this.state.selectedFields[fieldPath];
        this.state.selectedFields[fieldPath] = newVal;

        // Update in backend
        if (this.state.datasetId) {
            try {
                const fieldRecs = await this.orm.searchRead("bi.dataset.field", [
                    ["dataset_id", "=", this.state.datasetId],
                    ["field_path", "=", fieldPath],
                ], ["id"], { limit: 1 });

                if (fieldRecs.length) {
                    await this.orm.write("bi.dataset.field", [fieldRecs[0].id], {
                        is_selected: newVal,
                    });
                }

                // Refresh preview
                await this._refreshPreview();
            } catch (e) {
                console.error("Toggle field error:", e);
            }
        }
    }

    isFieldSelected(fieldPath) {
        return !!this.state.selectedFields[fieldPath];
    }

    // =========================================================================
    // Group Expansion
    // =========================================================================

    toggleGroup(groupName) {
        this.state.expandedGroups[groupName] = !this.state.expandedGroups[groupName];
    }

    isGroupExpanded(groupName) {
        return !!this.state.expandedGroups[groupName];
    }

    // =========================================================================
    // Field Filtering
    // =========================================================================

    onFieldSearch(ev) {
        this.state.fieldSearch = ev.target.value.toLowerCase();
    }

    getFilteredFields(fields) {
        if (!this.state.fieldSearch) return fields;
        const q = this.state.fieldSearch;
        return fields.filter(f =>
            (f.field_label || "").toLowerCase().includes(q) ||
            (f.field_path || "").toLowerCase().includes(q)
        );
    }

    get groupNames() {
        return Object.keys(this.state.fieldGroups);
    }

    getGroupFields(groupName) {
        const g = this.state.fieldGroups[groupName];
        if (!g) return [];
        const all = [...(g.dimensions || []), ...(g.measures || []), ...(g.dates || [])];
        return this.getFilteredFields(all);
    }

    getGroupFieldCount(groupName) {
        const g = this.state.fieldGroups[groupName];
        if (!g) return 0;
        return (g.dimensions || []).length + (g.measures || []).length + (g.dates || []).length;
    }

    // =========================================================================
    // UI Helpers
    // =========================================================================

    getFieldIcon(role) {
        switch (role) {
            case "measure": return "fa-calculator";
            case "date": return "fa-calendar";
            default: return "fa-tag";
        }
    }

    formatCellValue(value) {
        if (value === null || value === undefined) return "—";
        if (value === true) return "✓";
        if (value === false) return "✗";
        if (typeof value === "number") {
            return value.toLocaleString();
        }
        const str = String(value);
        return str.length > 50 ? str.substring(0, 50) + "…" : str;
    }

    get selectedFieldCount() {
        return Object.values(this.state.selectedFields).filter(Boolean).length;
    }

    // =========================================================================
    // Save
    // =========================================================================

    async saveDataset() {
        if (!this.state.datasetId) return;

        try {
            await this.orm.write("bi.dataset", [this.state.datasetId], {
                grain_level: this.state.grainLevel,
                domain_filter: this.state.domainFilter,
                record_limit: this.state.recordLimit,
                sort_field: this.state.sortField,
                sort_order: this.state.sortOrder,
            });

            this.notification.add(_t("Dataset saved"), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Error saving dataset"), { type: "danger" });
        }
    }

    goBack() {
        this.action_service.doAction({
            type: "ir.actions.act_window",
            res_model: "bi.dataset",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
        });
    }
}

// Register as client action
registry.category("actions").add("bi_studio.dataset_builder", DatasetBuilder);
