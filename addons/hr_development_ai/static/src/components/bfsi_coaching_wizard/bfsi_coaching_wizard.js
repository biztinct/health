/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * BfsiCoachingWizard — the guided, OWL-native coaching flow.
 *
 * Replaces the dense 6-tab coaching-session form with one continuous journey:
 *   1. Diagnose   2. Strategy   3. Session   4. Action Plan -> Done
 *
 * Rendered as a full-screen overlay by the manager dashboard. All data comes
 * from the bfsi.coaching.flow orchestration model; commit creates the strategy,
 * session and action plan atomically.
 */
export class BfsiCoachingWizard extends Component {
    static template = "hr_development_ai.BfsiCoachingWizard";
    static props = {
        bankerId: { type: Number },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.STEPS = ["Diagnose", "Strategy", "Session", "Action Plan"];
        this.state = useState({
            loading: true,
            error: null,
            step: 0,            // 0..3, then 4 = done
            ctx: null,          // payload from coaching_get_context
            // session step
            checklist: [],      // [{text, done}]
            notes: "",
            chat: [],           // [{role, text}]
            chatInput: "",
            chatBusy: false,
            // action plan step
            items: [],          // editable action items
            checkIn: "weekly",
            committing: false,
            result: null,       // commit result
        });

        onWillStart(async () => {
            try {
                const ctx = await this.orm.call(
                    "bfsi.coaching.flow", "coaching_get_context", [this.props.bankerId]
                );
                if (ctx.error) { this.state.error = ctx.error; }
                else {
                    this.state.ctx = ctx;
                    this.state.checklist = this._buildChecklist(ctx);
                    this.state.items = (ctx.suggested_items || []).map(it => ({ ...it, _on: true }));
                    this.state.chat = [{
                        role: "ai",
                        text: `Ready when you are. ${ctx.banker.name.split(" ")[0]}'s biggest lever is ` +
                              `${(ctx.gaps[0] || "consistency").toLowerCase()}. Ask me anything mid-session.`,
                    }];
                }
            } catch (e) {
                console.error("coaching_get_context failed", e);
                this.state.error = "Could not load coaching data for this banker.";
            } finally {
                this.state.loading = false;
            }
        });
    }

    _buildChecklist(ctx) {
        const first = ctx.banker.name.split(" ")[0];
        const topGap = (ctx.gaps[0] || "the key gap").split(" — ")[0].toLowerCase();
        return [
            { text: `Open: ask how ${first}'s week felt vs the goal`, done: false },
            { text: `Surface the real blocker (${topGap})`, done: false },
            { text: "Review a recent lost opportunity together", done: false },
            { text: "Agree ONE technique to try next week", done: false },
            { text: "Set a measurable commitment + number", done: false },
            { text: "Agree how you'll check in", done: false },
        ];
    }

    /* ── step nav ── */
    get banker() { return this.state.ctx ? this.state.ctx.banker : {}; }
    goto(n) { this.state.step = n; const b = document.querySelector(".bcw-body"); if (b) b.scrollTop = 0; }
    next() { this.goto(this.state.step + 1); }
    back() { this.goto(this.state.step - 1); }
    close() { this.props.onClose(this.state.result); }
    goHome() { this.action.doAction("hr_development_ai.action_bfsi_manager_dashboard"); }

    stepClass(i) {
        if (i < this.state.step) return "done";
        if (i === this.state.step) return "on";
        return "";
    }

    /* ── visual helpers ── */
    ringColor(s) { return s >= 50 ? "#10B981" : s >= 25 ? "#F59E0B" : "#EF4444"; }
    barColor(cat) { return cat === "input" ? "#3B82F6" : cat === "beh" ? "#F59E0B" : "#10B981"; }
    barPct(v, t) { return Math.min(100, t ? (v / t) * 100 : 0); }
    trendH(v) { const mx = Math.max(...(this.state.ctx?.trend || [1]), 1); return Math.max(6, (v / mx) * 100); }
    moveLabel(m) { return m > 0 ? "+" + m : m === 0 ? "—" : "" + m; }
    kpiTagClass(cat) {
        return cat === "input" ? "in" : cat === "behavior" || cat === "beh" ? "beh" : "out";
    }

    /* ── session interactions ── */
    toggleCheck(i) { this.state.checklist[i].done = !this.state.checklist[i].done; }
    onNotes(ev) { this.state.notes = ev.target.value; }
    onChatInput(ev) { this.state.chatInput = ev.target.value; }
    onChatKey(ev) { if (ev.key === "Enter") this.sendChat(); }

    async sendChat() {
        const msg = (this.state.chatInput || "").trim();
        if (!msg || this.state.chatBusy) return;
        this.state.chat.push({ role: "me", text: msg });
        this.state.chatInput = "";
        this.state.chatBusy = true;
        try {
            const res = await this.orm.call(
                "bfsi.coaching.flow", "coaching_ai_enhance",
                [this.props.bankerId, "coaching reply to: " + msg]
            );
            this.state.chat.push({
                role: "ai",
                text: (res && res.ok && res.text) ? res.text :
                    "Anchor it to a number he controls today, and have him say the commitment out loud — verbal commitments stick far better.",
            });
        } catch (e) {
            this.state.chat.push({ role: "ai", text: "Keep it specific and measurable — one behaviour, one number, one date." });
        } finally {
            this.state.chatBusy = false;
        }
    }

    /* ── action plan editing ── */
    onItemTitle(i, ev) { this.state.items[i].title = ev.target.value; }
    toggleItem(i) { this.state.items[i]._on = !this.state.items[i]._on; }
    addItem() {
        this.state.items.push({
            title: "", kpi_category: "behavior", specific_kpi: "other",
            kpi_label: "Custom", from_val: "", to_val: "", target_value: 0, _on: true,
        });
    }
    onCheckIn(ev) { this.state.checkIn = ev.target.value; }

    async commit() {
        if (this.state.committing) return;
        const items = this.state.items.filter(it => it._on && (it.title || "").trim());
        this.state.committing = true;
        try {
            const res = await this.orm.call("bfsi.coaching.flow", "coaching_commit", [
                this.props.bankerId,
                {
                    notes: this.state.notes,
                    themes: this.state.ctx.themes,
                    opening: this.state.ctx.opening,
                    probing: this.state.ctx.probing,
                    closing: this.state.ctx.closing,
                    check_in: this.state.checkIn,
                    action_items: items.map(it => ({
                        title: it.title, kpi_category: it.kpi_category,
                        specific_kpi: it.specific_kpi, target_value: it.target_value,
                        priority: "high",
                    })),
                },
            ]);
            this.state.result = res;
            this.goto(4);
        } catch (e) {
            console.error("coaching_commit failed", e);
            this.notification.add("Could not save the coaching plan. Please try again.", { type: "danger" });
        } finally {
            this.state.committing = false;
        }
    }
}
