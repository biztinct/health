/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * KpiCard — strip metric card: icon, value, label, optional delta/sub line.
 * Props: icon, value, label, sub (optional), tone (ok/warn/danger/info/brand).
 */
export class KpiCard extends Component {
    static template = "hr_development_ai.KpiCard";
    static props = {
        icon: { type: String },
        value: { type: [String, Number] },
        label: { type: String },
        sub: { type: String, optional: true },
        tone: { type: String, optional: true },
        onClick: { type: Function, optional: true },
    };

    get toneClass() {
        return `bfsi-kpi-${this.props.tone || "brand"}`;
    }
}
