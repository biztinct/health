/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ScoreRing } from "../shared/score_ring";
import { Sparkline } from "../shared/sparkline";

/**
 * Person360 — THE hub for one banker. Everything about the person in one
 * place: canonical score, KPI gaps + root cause, plans with an interactive
 * checklist, session timeline, strategies — with "Coach now" and
 * "Log check-in" one click away. Every list in the app links here.
 *
 * Props: employeeId, onCoach(bankerId), onOpenDrawer(model, id, kind)
 */
export class Person360 extends Component {
    static template = "hr_development_ai.Person360";
    static components = { ScoreRing, Sparkline };
    static props = {
        employeeId: Number,
        onCoach: Function,
        onOpenDrawer: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            d: null,
            tab: "plans",          // plans | sessions | strategies
            // lazy AI insight
            aiBusy: false,
            aiText: "",
            // quick check-in dialog
            checkinOpen: false,
            checkinOutcome: "",
            checkinNotes: "",
            checkinBusy: false,
        });
        onWillStart(() => this.load());
        onWillUpdateProps((next) => {
            if (next.employeeId !== this.props.employeeId) {
                return this.load(next.employeeId);
            }
        });
    }

    async load(empId) {
        this.state.loading = true;
        this.state.aiText = "";
        try {
            const d = await this.orm.call(
                "bfsi.coaching.flow", "person_360_data",
                [empId || this.props.employeeId]);
            if (d.error) {
                this.state.error = d.error;
                this.state.d = null;
            } else {
                this.state.d = d;
                this.state.error = null;
            }
        } catch (e) {
            console.error("person_360_data failed", e);
            this.state.error = "Could not load this person.";
        } finally {
            this.state.loading = false;
        }
    }

    get d() { return this.state.d || {}; }
    get snap() { return this.d.snapshot || {}; }
    get activePlans() {
        return (this.d.plans || []).filter(p =>
            ["committed", "in_progress", "overdue"].includes(p.state));
    }
    get pastPlans() {
        return (this.d.plans || []).filter(p =>
            !["committed", "in_progress", "overdue"].includes(p.state));
    }

    prioChip(p) {
        return { critical: "bfsi-chip-crit", high: "bfsi-chip-warn",
                 medium: "bfsi-chip-info", low: "bfsi-chip-ok" }[p] || "bfsi-chip-muted";
    }
    prioLabel(p) {
        return { critical: "Critical", high: "High", medium: "Medium",
                 low: "On track" }[p] || p;
    }
    outcomeChip(o) {
        return { excellent: "bfsi-chip-ok", good: "bfsi-chip-ok",
                 moderate: "bfsi-chip-info",
                 needs_improvement: "bfsi-chip-warn" }[o] || "bfsi-chip-muted";
    }
    stateChip(st) {
        return { committed: "bfsi-chip-info", in_progress: "bfsi-chip-warn",
                 completed: "bfsi-chip-ok", overdue: "bfsi-chip-crit",
                 in_use: "bfsi-chip-warn", generated: "bfsi-chip-info",
                 cancelled: "bfsi-chip-muted" }[st] || "bfsi-chip-muted";
    }
    stateLabel(st) {
        return (st || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
    barColor(cat) {
        return { input: "var(--bfsi-cat-input)", beh: "var(--bfsi-cat-behavior)",
                 out: "var(--bfsi-cat-output)" }[cat] || "var(--bfsi-primary)";
    }
    barPct(bar) {
        if (!bar.target) return 0;
        return Math.min(100, Math.round((bar.value / bar.target) * 100));
    }
    moveTone(m) { return m > 0 ? "var(--bfsi-ok)" : m < 0 ? "var(--bfsi-danger)" : "var(--bfsi-faint)"; }

    async toggleItem(item) {
        if (item.state === "completed") return;
        try {
            await this.orm.call("bfsi.action.plan.item", "action_mark_complete", [[item.id]]);
            await this.load();
        } catch (e) {
            console.error(e);
            this.notification.add("Could not update the item.", { type: "danger" });
        }
    }

    /* ── lazy AI deep insight ── */
    async aiInsight() {
        if (this.state.aiBusy) return;
        this.state.aiBusy = true;
        try {
            const res = await this.orm.call(
                "bfsi.coaching.flow", "coaching_ai_enhance",
                [this.props.employeeId, "performance deep-dive insight"]);
            this.state.aiText = (res && res.ok && res.text) ? res.text
                : "AI is not available right now — the data-driven root cause above still applies.";
        } finally {
            this.state.aiBusy = false;
        }
    }

    /* ── quick check-in ── */
    openCheckin() {
        this.state.checkinOpen = true;
        this.state.checkinOutcome = "";
        this.state.checkinNotes = "";
    }
    async saveCheckin() {
        if (!this.state.checkinOutcome || this.state.checkinBusy) return;
        this.state.checkinBusy = true;
        try {
            const plan = this.activePlans[0];
            await this.orm.call("bfsi.coaching.flow", "workspace_quick_session", [
                this.props.employeeId, {
                    outcome: this.state.checkinOutcome,
                    notes: this.state.checkinNotes,
                    plan_id: plan ? plan.id : false,
                },
            ]);
            this.notification.add("Check-in logged.", { type: "success" });
            this.state.checkinOpen = false;
            await this.load();
        } catch (e) {
            console.error(e);
            this.notification.add(
                e.data?.message || "Could not log the check-in.", { type: "danger" });
        } finally {
            this.state.checkinBusy = false;
        }
    }
}
