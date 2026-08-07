/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatFull, formatDimensionValue } from "../../core/formats";
import { user } from "@web/core/user";

/**
 * The Records view of the Table chart: one row per underlying record, and the
 * table ITSELF is the drop target.
 *
 * Drop rules, in the order a user discovers them:
 *  - over the header row  -> insert at the caret (nearest gap by midpoint);
 *  - anywhere else        -> append AFTER the last column;
 *  - dragging a header    -> reorder, same caret.
 * There is no slot-compatibility test: any visible field is a valid column,
 * measures included (they are shown raw, not aggregated).
 */
export class RecordsTable extends Component {
    static template = "biz_bi.RecordsTable";
    static props = {
        envelope: { type: [Object, { value: null }], optional: true },
        columns: { type: Array },
        sort: { type: [Object, { value: null }], optional: true },
        onDropField: Function,
        onMoveColumn: Function,
        onRemoveColumn: Function,
        onToggleSort: Function,
    };

    setup() {
        this.state = useState({ caret: null, over: false });
        this.labels = {
            empty: _t("Drag any fields here — one row per record"),
            emptySub: _t(
                "Every row is one underlying record. The filters you set still apply."
            ),
            remove: _t("Remove column"),
            sortHint: _t("Click to sort"),
            policy: _t("Emptied by a data policy"),
            noRows: _t("No records match the current filters."),
        };
    }

    // ------------------------------------------------------------------
    // Rendering
    // ------------------------------------------------------------------

    get envelopeColumns() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error) {
            return [];
        }
        return envelope.columns || [];
    }

    get rows() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error || !envelope.rows) {
            return [];
        }
        const lang = user.lang || "en_US";
        const columns = envelope.columns || [];
        return envelope.rows.map((row) =>
            row.map((value, index) => {
                const column = columns[index] || {};
                return column.role === "measure"
                    ? formatFull(value, column.format, lang)
                    : formatDimensionValue(value, column, lang);
            })
        );
    }

    /** columns_meta entry matching a header chip, when the preview is fresh */
    metaFor(index) {
        return this.envelopeColumns[index] || {};
    }

    sortDirFor(chip) {
        const sort = this.props.sort;
        return sort && sort.fieldId === chip.id ? sort.dir : null;
    }

    // ------------------------------------------------------------------
    // Drag & drop
    // ------------------------------------------------------------------

    onColumnDragStart(event, index) {
        // copyMove, not move: the drop is rejected outright when dropEffect
        // and effectAllowed disagree, and a field dragged from the well is a
        // "copy" — one drop target, two gestures, so allow both.
        event.dataTransfer.effectAllowed = "copyMove";
        event.dataTransfer.setData("bi/column", String(index));
    }

    /** move when a header is being reordered, copy for a new field */
    _dropEffect(event) {
        const types = event.dataTransfer.types || [];
        return [...types].includes("bi/column") ? "move" : "copy";
    }

    onHeaderDragOver(event) {
        event.preventDefault();
        // the wrapper's handler would otherwise overwrite the caret with
        // "append at the end" the instant the pointer entered a header
        event.stopPropagation();
        event.dataTransfer.dropEffect = this._dropEffect(event);
        this.state.over = true;
        const cells = [...event.currentTarget.children];
        let index = cells.length;
        for (let i = 0; i < cells.length; i++) {
            const rect = cells[i].getBoundingClientRect();
            if (event.clientX < rect.left + rect.width / 2) {
                index = i;
                break;
            }
        }
        this.state.caret = index;
    }

    onBodyDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = this._dropEffect(event);
        this.state.over = true;
        // the user's literal ask: dropping on the table appends at the end
        this.state.caret = this.props.columns.length;
    }

    onDragLeave(event) {
        if (event.currentTarget.contains(event.relatedTarget)) {
            return;
        }
        this.state.caret = null;
        this.state.over = false;
    }

    onDrop(event) {
        event.preventDefault();
        const index =
            this.state.caret === null ? this.props.columns.length : this.state.caret;
        this.state.caret = null;
        this.state.over = false;
        const moved = event.dataTransfer.getData("bi/column");
        if (moved !== "" && moved !== null && moved !== undefined) {
            this.props.onMoveColumn(parseInt(moved, 10), index);
            return;
        }
        const raw = event.dataTransfer.getData("bi/field");
        if (!raw) {
            return;
        }
        this.props.onDropField(JSON.parse(raw), index);
    }

    caretClass(index) {
        if (this.state.caret === null) {
            return "";
        }
        if (this.state.caret === index) {
            return "bi-caret-before";
        }
        if (index === this.props.columns.length - 1 &&
                this.state.caret >= this.props.columns.length) {
            return "bi-caret-after";
        }
        return "";
    }
}
