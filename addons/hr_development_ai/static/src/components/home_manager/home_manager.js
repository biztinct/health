/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ScoreRing } from "../shared/score_ring";
import { KpiCard } from "../shared/kpi_card";

/**
 * HomeManager — the branch manager's Team Cockpit.
 * One screen answers: how is my team doing, who needs me NOW, and what
 * follow-ups are due — with "Coach now" one click away on every row.
 *
 * Props:
 *   data         workspace_home_data payload (or branch cockpit payload)
 *   cockpitOnly  true when rendered as a regional drill-in
 *   onRefresh, onCoach(bankerId), onOpenDrawer(model, id, kind)
 */
export class HomeManager extends Component {
    static template = "hr_development_ai.HomeManager";
    static components = { ScoreRing, KpiCard };
    static props = {
        data: Object,
        cockpitOnly: { type: Boolean, optional: true },
        onRefresh: Function,
        onCoach: Function,
        onOpenPerson: Function,
        onOpenDrawer: Function,
    };

    get d() { return this.props.data; }
    get strip() { return this.d.kpi_strip || {}; }
    get queue() { return this.d.queue || []; }
    get checkins() { return this.d.checkins_due || []; }
    get needsCoaching() { return this.queue.filter(r => r.needs_coaching); }
    get onTrack() { return this.queue.filter(r => !r.needs_coaching); }

    greeting() {
        const h = new Date().getHours();
        const name = (this.d.user?.name || "").split(" ").pop();
        const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
        return name ? `${part}, ${name}` : part;
    }

    prioChip(p) {
        return { critical: "bfsi-chip-crit", high: "bfsi-chip-warn",
                 medium: "bfsi-chip-info", low: "bfsi-chip-ok" }[p] || "bfsi-chip-muted";
    }
    moveTone(m) { return m > 0 ? "var(--bfsi-ok)" : m < 0 ? "var(--bfsi-danger)" : "var(--bfsi-faint)"; }
}
