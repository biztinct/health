/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatFull, formatDimensionValue } from "../../core/formats";
import { user } from "@web/core/user";

/**
 * Matrix pivot: rows = d0 members, columns = d1 members, cells = m0,
 * with row and column totals. Row cap (5k) guaranteed by the engine, so
 * no virtualization. Sticky header + sticky first column via CSS.
 */
export class PivotTable extends Component {
    static template = "biz_bi.PivotTable";
    static props = {
        envelope: { type: Object },
        config: { type: Object, optional: true },
    };

    get matrix() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error) {
            return { cols: [], rows: [], colTotals: [], grandTotal: "" };
        }
        const lang = user.lang || "en_US";
        const columns = envelope.columns;
        const d0 = columns.find((c) => c.ref === "d0");
        const d1 = columns.find((c) => c.ref === "d1");
        const m0 = columns.find((c) => c.ref === "m0");
        const d0i = columns.indexOf(d0);
        const d1i = columns.indexOf(d1);
        const m0i = columns.indexOf(m0);
        const format = (v) => (v === null || v === undefined ? "–" : formatFull(v, m0.format, lang));

        const colKeys = [];
        const colPos = new Map();
        const rowKeys = [];
        const rowPos = new Map();
        const cells = new Map(); // "r|c" -> number

        for (const row of envelope.rows) {
            const rk = formatDimensionValue(row[d0i], d0, lang);
            const ck = d1 ? formatDimensionValue(row[d1i], d1, lang) : "";
            if (!rowPos.has(rk)) { rowPos.set(rk, rowKeys.length); rowKeys.push(rk); }
            if (!colPos.has(ck)) { colPos.set(ck, colKeys.length); colKeys.push(ck); }
            const key = rowPos.get(rk) + "|" + colPos.get(ck);
            cells.set(key, (cells.get(key) || 0) + (row[m0i] || 0));
        }

        const colTotals = new Array(colKeys.length).fill(0);
        let grandTotal = 0;
        const rows = rowKeys.map((rk, ri) => {
            let rowTotal = 0;
            const values = colKeys.map((ck, ci) => {
                const value = cells.get(ri + "|" + ci);
                if (value !== undefined) {
                    rowTotal += value;
                    colTotals[ci] += value;
                }
                return value === undefined ? "–" : format(value);
            });
            grandTotal += rowTotal;
            return { label: rk, values, total: format(rowTotal) };
        });

        return {
            cornerLabel: d0 ? d0.label : "",
            measureLabel: m0 ? m0.label : "",
            cols: colKeys,
            rows,
            colTotals: colTotals.map(format),
            grandTotal: format(grandTotal),
        };
    }
}
