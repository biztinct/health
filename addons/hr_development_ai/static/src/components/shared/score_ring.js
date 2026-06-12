/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * ScoreRing — SVG circular score gauge used on every screen.
 * Props: value (0-100), size (px, default 64), label (optional sub-label).
 */
export class ScoreRing extends Component {
    static template = "hr_development_ai.ScoreRing";
    static props = {
        value: { type: Number },
        size: { type: Number, optional: true },
        label: { type: String, optional: true },
        thickness: { type: Number, optional: true },
    };

    get size() { return this.props.size || 64; }
    get thickness() { return this.props.thickness || Math.max(4, this.size / 12); }
    get radius() { return (this.size - this.thickness) / 2; }
    get circumference() { return 2 * Math.PI * this.radius; }
    get offset() {
        const v = Math.max(0, Math.min(100, this.props.value || 0));
        return this.circumference * (1 - v / 100);
    }
    get color() {
        const v = this.props.value || 0;
        return v >= 50 ? "#10B981" : v >= 25 ? "#F59E0B" : "#EF4444";
    }
    get fontSize() { return Math.round(this.size / 3.4); }
}
