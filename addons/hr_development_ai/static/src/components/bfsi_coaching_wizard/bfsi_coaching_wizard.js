/** @odoo-module **/

import { Component, useState, onWillStart, onPatched, useRef, markup } from "@odoo/owl";
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

        // keep the AI chat pinned to the latest message after each render
        this.chatScroll = useRef("chatScroll");
        this._pendingScroll = false;
        onPatched(() => {
            if (this._pendingScroll && this.chatScroll.el) {
                this.chatScroll.el.scrollTop = this.chatScroll.el.scrollHeight;
                this._pendingScroll = false;
            }
        });

        this.STEPS = ["Diagnose", "Strategy", "Session", "Action Plan"];
        this.state = useState({
            loading: true,
            error: null,
            step: 0,            // 0..3, then 4 = done
            maxStep: 0,         // furthest step reached → drives "review" labels
            ctx: null,          // payload from coaching_get_context
            // session step
            checklist: [],      // [{text, done}]
            notes: "",
            outcome: "",        // required before building the plan
            satisfaction: "",
            perfOpen: null,     // expanded performance-reference row
            chat: [],           // [{role, text}]
            chatInput: "",
            chatBusy: false,
            // action plan step
            items: [],          // editable action items
            checkIn: "weekly",
            committing: false,
            result: null,       // commit result
            // strategy reuse: true = continue with the banker's active
            // strategy; false = build (and supersede) a fresh one
            useExisting: false,
        });

        onWillStart(async () => {
            try {
                const ctx = await this.orm.call(
                    "bfsi.coaching.flow", "coaching_get_context", [this.props.bankerId]
                );
                if (ctx.error) { this.state.error = ctx.error; }
                else {
                    this.state.ctx = ctx;
                    this.state.useExisting = !!(ctx.existing_strategy
                        && ctx.existing_strategy.is_fresh);
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
    get existingStrategy() { return this.state.ctx?.existing_strategy || null; }
    toggleRebuild() { this.state.useExisting = !this.state.useExisting; }
    goto(n) {
        this.state.step = n;
        this.state.maxStep = Math.max(this.state.maxStep, n);
        const b = document.querySelector(".bcw-body"); if (b) b.scrollTop = 0;
    }
    next() { this.goto(this.state.step + 1); }
    back() { this.goto(this.state.step - 1); }
    /* clickable stepper: jump back to any completed/current step (never skip
       forward past validation like the required session outcome) */
    goStep(i) { if (i <= this.state.maxStep && this.state.step < 4) this.goto(i); }
    /* true when revisiting a step already completed — the forward button then
       just names the next step instead of repeating the first-time action */
    get reviewing() { return this.state.step < this.state.maxStep; }
    close() { this.props.onClose(this.state.result); }
    viewPlan() {
        this.props.onClose(this.state.result
            ? { ...this.state.result, view_plan: true } : null);
    }
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
    togglePerf(i) { this.state.perfOpen = this.state.perfOpen === i ? null : i; }

    /* Ready-made AI prompts derived from the talking points / KPI gaps —
       one click asks the AI for concrete help on that exact lever. */
    get quickPrompts() {
        const first = (this.banker.name || "").split(" ")[0] || "them";
        const out = [];
        for (const bar of (this.state.ctx?.bars || [])) {
            if (bar.below) {
                out.push({
                    label: bar.name,
                    text: `Give me 3 specific, practical suggestions to help ${first} improve `
                        + `${bar.name.toLowerCase()} — it's at ${bar.value} vs a target of ${bar.target}.`,
                });
            }
        }
        out.push({
            label: "Opening line",
            text: `Suggest a warm, non-judgemental opening question to start the session with ${first}.`,
        });
        out.push({
            label: "Lock a commitment",
            text: `How do I help ${first} commit to one measurable goal for this week?`,
        });
        return out.slice(0, 5);
    }
    askQuick(text) {
        this.state.chatInput = text;
        this.sendChat();
    }
    setOutcome(v) { this.state.outcome = v; }
    setSatisfaction(v) { this.state.satisfaction = this.state.satisfaction === v ? "" : v; }
    get OUTCOMES() {
        return [
            { v: "excellent", l: "Excellent" }, { v: "good", l: "Good" },
            { v: "moderate", l: "Moderate" }, { v: "needs_improvement", l: "Needs work" },
        ];
    }
    onChatInput(ev) { this.state.chatInput = ev.target.value; }
    onChatKey(ev) { if (ev.key === "Enter") this.sendChat(); }

    async sendChat() {
        const msg = (this.state.chatInput || "").trim();
        if (!msg || this.state.chatBusy) return;
        this.state.chat.push({ role: "me", text: msg });
        this.state.chatInput = "";
        this.state.chatBusy = true;
        this._pendingScroll = true;        // scroll to the user's message + typing dots
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
            this._pendingScroll = true;    // scroll to the AI's full answer
        }
    }

    /* render an AI/user message: lightweight markdown → clean HTML so answers
       read as formatted lists/paragraphs, not one wall of text.
       The list number is rendered explicitly and counted in JS, so it's
       always 1,2,3… regardless of how the model wrote the source markers
       (some models repeat "1." or split items with blank lines). */
    fmtMsg(text) {
        if (!text) return markup("");
        const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const inline = s => esc(s)
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.+?)\*/g, "<em>$1</em>")
            .replace(/`(.+?)`/g, "<code>$1</code>");
        const out = [];
        let list = null;       // 'ol' | 'ul' | null
        let olNum = 0;         // running counter for the current ordered list
        const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
        for (const raw of String(text).split(/\r?\n/)) {
            const line = raw.trim();
            // a blank line between list items is ignored (keeps one list);
            // a blank line is only meaningful as paragraph separation, handled implicitly
            if (!line) { continue; }
            let m;
            if ((m = line.match(/^\s*\d+[.)]\s+(.+)$/))) {
                if (list !== "ol") { close(); out.push('<ol class="bcw-md-list">'); list = "ol"; olNum = 0; }
                olNum += 1;
                out.push(`<li><span class="bcw-md-n">${olNum}</span><span class="bcw-md-t">${inline(m[1])}</span></li>`);
            } else if ((m = line.match(/^[-•*]\s+(.+)$/))) {
                if (list !== "ul") { close(); out.push('<ul class="bcw-md-list">'); list = "ul"; }
                out.push(`<li><span class="bcw-md-t">${inline(m[1])}</span></li>`);
            } else if ((m = line.match(/^#{1,4}\s+(.+)$/))) {
                close(); out.push(`<h5 class="bcw-md-h">${inline(m[1])}</h5>`);
            } else {
                close(); out.push(`<p>${inline(line)}</p>`);
            }
        }
        close();
        return markup(out.join(""));
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
                    outcome: this.state.outcome || "moderate",
                    satisfaction: this.state.satisfaction || false,
                    strategy_id: (this.state.useExisting && this.existingStrategy)
                        ? this.existingStrategy.id : false,
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
