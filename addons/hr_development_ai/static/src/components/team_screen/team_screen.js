/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ScoreRing } from "../shared/score_ring";
import { Sparkline } from "../shared/sparkline";

/**
 * TeamScreen — the manager's full roster with filter chips, search and sort.
 * Every card opens the Person 360; Coach now is one click away.
 *
 * Props: branchId (optional override), onCoach, onOpenPerson
 */
export class TeamScreen extends Component {
    static template = "hr_development_ai.TeamScreen";
    static components = { ScoreRing, Sparkline };
    static props = {
        branchId: { type: [Number, Boolean], optional: true },
        onCoach: Function,
        onOpenPerson: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            rows: [],
            branchName: "",
            search: "",
            prio: null,           // null | critical | high | medium | low
            sort: "priority",     // priority | score_asc | score_desc | rank
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "bfsi.coaching.flow", "coaching_queue",
                [this.props.branchId || null]);
            this.state.rows = res.rows || [];
            this.state.branchName = res.branch_name || "";
        } finally {
            this.state.loading = false;
        }
    }

    get filtered() {
        const q = (this.state.search || "").toLowerCase();
        let rows = this.state.rows.filter(r =>
            (!q || r.name.toLowerCase().includes(q) || (r.role || "").toLowerCase().includes(q))
            && (!this.state.prio || r.priority === this.state.prio));
        const prioRank = { critical: 0, high: 1, medium: 2, low: 3 };
        const sorters = {
            priority: (a, b) => (prioRank[a.priority] - prioRank[b.priority]) || (a.score - b.score),
            score_asc: (a, b) => a.score - b.score,
            score_desc: (a, b) => b.score - a.score,
            rank: (a, b) => (a.rank || 99) - (b.rank || 99),
        };
        return [...rows].sort(sorters[this.state.sort] || sorters.priority);
    }

    get prioCounts() {
        const c = { critical: 0, high: 0, medium: 0, low: 0 };
        for (const r of this.state.rows) c[r.priority] = (c[r.priority] || 0) + 1;
        return c;
    }

    togglePrio(p) { this.state.prio = this.state.prio === p ? null : p; }

    prioChip(p) {
        return { critical: "bfsi-chip-crit", high: "bfsi-chip-warn",
                 medium: "bfsi-chip-info", low: "bfsi-chip-ok" }[p] || "bfsi-chip-muted";
    }
    moveTone(m) { return m > 0 ? "var(--bfsi-ok)" : m < 0 ? "var(--bfsi-danger)" : "var(--bfsi-faint)"; }
}
