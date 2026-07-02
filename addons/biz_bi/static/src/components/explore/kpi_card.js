/** @odoo-module **/

import { Component } from "@odoo/owl";
import { formatNumber, formatFull } from "../../core/formats";
import { user } from "@web/core/user";

/**
 * KPI card renderer (OWL, not ECharts): big number + optional comparison
 * delta versus a previous-period envelope.
 */
export class KpiCard extends Component {
    static template = "biz_bi.KpiCard";
    static props = {
        envelope: { type: Object },
        config: { type: Object },
        compareEnvelope: { type: Object, optional: true },
        showLabel: { type: Boolean, optional: true },
    };

    get metric() {
        const envelope = this.props.envelope;
        if (!envelope || envelope.error || !envelope.rows.length) {
            return { value: "–", full: "", label: "" };
        }
        const column = envelope.columns.find((c) => c.ref === "m0");
        const raw = envelope.rows[0][envelope.columns.indexOf(column)];
        const lang = user.lang || "en_US";
        return {
            value: formatNumber(raw, column.format, lang),
            full: formatFull(raw, column.format, lang),
            label: column.label,
            raw,
        };
    }

    get delta() {
        const compare = this.props.compareEnvelope;
        if (!compare || compare.error || !compare.rows.length) {
            return null;
        }
        const current = this.metric.raw;
        const previous = compare.rows[0][0];
        if (typeof current !== "number" || typeof previous !== "number" || previous === 0) {
            return null;
        }
        const pct = ((current - previous) / Math.abs(previous)) * 100;
        return {
            pct: Math.abs(pct).toFixed(1),
            direction: pct >= 0 ? "up" : "down",
        };
    }
}
