/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * Sparkline — tiny pure-SVG trend line (no Chart.js cost).
 * Props: values (number[]), width, height, color (optional; defaults by trend).
 */
export class Sparkline extends Component {
    static template = "hr_development_ai.Sparkline";
    static props = {
        values: { type: Array },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
        color: { type: String, optional: true },
    };

    get w() { return this.props.width || 88; }
    get h() { return this.props.height || 28; }
    get color() {
        if (this.props.color) return this.props.color;
        const v = this.props.values || [];
        if (v.length < 2) return "#9CA3AF";
        return v[v.length - 1] >= v[0] ? "#10B981" : "#EF4444";
    }
    get points() {
        const v = (this.props.values || []).map(Number);
        if (!v.length) return "";
        if (v.length === 1) v.push(v[0]);
        const min = Math.min(...v), max = Math.max(...v);
        const span = max - min || 1;
        const pad = 3;
        const stepX = (this.w - pad * 2) / (v.length - 1);
        return v.map((val, i) => {
            const x = pad + i * stepX;
            const y = pad + (this.h - pad * 2) * (1 - (val - min) / span);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }
    get lastPoint() {
        const pts = this.points.split(" ");
        const last = pts[pts.length - 1];
        if (!last) return { x: 0, y: 0 };
        const [x, y] = last.split(",").map(Number);
        return { x, y };
    }
}
