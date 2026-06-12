/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ScoreRing } from "../shared/score_ring";
import { Sparkline } from "../shared/sparkline";

/**
 * HomeBanker — the coachee's own 360°: score + trend, KPI bars vs target,
 * an interactive plan checklist, recent sessions and AI nudges.
 *
 * Props: data (workspace_home_data payload with .me), onRefresh,
 *        onOpenDrawer(model, id, kind)
 */
export class HomeBanker extends Component {
    static template = "hr_development_ai.HomeBanker";
    static components = { ScoreRing, Sparkline };
    static props = {
        data: Object,
        onRefresh: Function,
        onOpenDrawer: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    get d() { return this.props.data; }
    get me() { return this.d.me || {}; }
    get snap() { return this.me.snapshot || {}; }
    get plans() { return this.me.plans || []; }
    get sessions() { return this.me.sessions || []; }

    greeting() {
        const h = new Date().getHours();
        const name = (this.d.user?.name || "").split(" ").pop();
        const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
        return name ? `${part}, ${name}` : part;
    }

    barColor(cat) {
        return { input: "var(--bfsi-cat-input)", beh: "var(--bfsi-cat-behavior)",
                 out: "var(--bfsi-cat-output)" }[cat] || "var(--bfsi-primary)";
    }
    barPct(bar) {
        if (!bar.target) return 0;
        return Math.min(100, Math.round((bar.value / bar.target) * 100));
    }

    async toggleItem(item) {
        if (item.state === "completed") return;
        try {
            await this.orm.call("bfsi.action.plan.item", "action_mark_complete", [[item.id]]);
            this.notification.add("Nice — action completed.", { type: "success" });
            await this.props.onRefresh();
        } catch (e) {
            console.error(e);
            this.notification.add("Could not update the item.", { type: "danger" });
        }
    }

    outcomeChip(outcome) {
        return { excellent: "bfsi-chip-ok", good: "bfsi-chip-ok",
                 moderate: "bfsi-chip-info",
                 needs_improvement: "bfsi-chip-warn" }[outcome] || "bfsi-chip-muted";
    }
}
