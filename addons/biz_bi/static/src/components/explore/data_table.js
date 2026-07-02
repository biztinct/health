/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatFull, formatDimensionValue } from "../../core/formats";
import { user } from "@web/core/user";

/**
 * Flat result table with sticky header. Row cap (5k) is guaranteed by the
 * engine so no virtualization is needed.
 */
export class DataTable extends Component {
    static template = "biz_bi.DataTable";
    static props = {
        envelope: { type: Object },
        config: { type: Object, optional: true },
    };

    get table() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error) {
            return { columns: [], rows: [] };
        }
        const lang = user.lang || "en_US";
        return {
            columns: envelope.columns,
            rows: envelope.rows.map((row) =>
                row.map((value, index) => {
                    const column = envelope.columns[index];
                    return column.role === "measure"
                        ? formatFull(value, column.format, lang)
                        : formatDimensionValue(value, column, lang);
                })
            ),
        };
    }
}
