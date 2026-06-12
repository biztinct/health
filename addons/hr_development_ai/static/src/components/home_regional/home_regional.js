/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ScoreRing } from "../shared/score_ring";

/**
 * HomeRegional — region rollup: one card per branch with the canonical
 * branch score + coverage; click drills into that branch's cockpit.
 *
 * Props: data (workspace_home_data payload with .branch_rollup),
 *        onOpenBranch(branchId)
 */
export class HomeRegional extends Component {
    static template = "hr_development_ai.HomeRegional";
    static components = { ScoreRing };
    static props = {
        data: Object,
        onOpenBranch: Function,
    };

    get d() { return this.props.data; }
    get branches() { return this.d.branch_rollup || []; }

    greeting() {
        const h = new Date().getHours();
        const name = (this.d.user?.name || "").split(" ").pop();
        const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
        return name ? `${part}, ${name}` : part;
    }
}
