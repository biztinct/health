/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatFull, formatDimensionValue } from "../../core/formats";
import { user } from "@web/core/user";

/**
 * Flat result table with sticky header.
 *
 * `maxRows` is a RENDER cap for hosts that cannot afford a tall table — a
 * dashboard tile re-lays-out its whole grid as the table grows, and the cost
 * is super-linear (measured on vietuat: 50 rows 1.8s, 500 rows 133s in a
 * gridstack tile, while the same component is instant full-width in Explore).
 * It is never silent: the overflow is stated in a final row.
 */
export class DataTable extends Component {
    static template = "biz_bi.DataTable";
    static props = {
        envelope: { type: Object },
        config: { type: Object, optional: true },
        maxRows: { type: Number, optional: true },
    };

    get table() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error) {
            return { columns: [], rows: [], overflow: null };
        }
        const lang = user.lang || "en_US";
        const cap = this.props.maxRows || 0;
        // the getter runs on every render; a host that re-renders in a loop
        // would otherwise re-format every cell each time
        if (this._memo && this._memo.envelope === envelope &&
                this._memo.lang === lang && this._memo.cap === cap) {
            return this._memo.table;
        }
        const all = envelope.rows || [];
        const shown = cap && all.length > cap ? all.slice(0, cap) : all;
        const table = {
            columns: envelope.columns,
            rows: shown.map((row) =>
                row.map((value, index) => {
                    const column = envelope.columns[index];
                    return column.role === "measure"
                        ? formatFull(value, column.format, lang)
                        : formatDimensionValue(value, column, lang);
                })
            ),
            overflow:
                shown.length < all.length
                    ? _t(
                          "Showing the first %(shown)s of %(total)s rows — open in Explore or export for the full set.",
                          {
                              shown: shown.length.toLocaleString(lang.replace("_", "-")),
                              total: (envelope.meta && envelope.meta.total_count
                                  ? envelope.meta.total_count
                                  : all.length
                              ).toLocaleString(lang.replace("_", "-")),
                          }
                      )
                    : null,
        };
        this._memo = { envelope, lang, cap, table };
        return table;
    }
}
