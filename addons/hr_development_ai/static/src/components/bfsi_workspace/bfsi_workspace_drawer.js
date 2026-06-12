/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * BfsiWorkspaceDrawer — one slide-over drawer for any workspace record.
 * Loads an enriched payload via bfsi.coaching.flow.workspace_drawer_data and
 * renders a per-drawerKind sub-template. Action buttons call the existing model
 * methods through runMethod (orm.call -> action.doAction for dialog results).
 */
export class BfsiWorkspaceDrawer extends Component {
    static template = "hr_development_ai.BfsiWorkspaceDrawer";
    static props = {
        model: String,
        recordId: Number,
        drawerKind: String,
        onClose: Function,
        onAction: Function,
        openForm: Function,
        openWizard: Function,
        openRecord: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, busy: false, data: null, openPhase: null,
            editing: null, editValue: "",
            // in-drawer AI chat (sessions)
            chatOpen: false, chatInput: "", chatBusy: false,
            // in-drawer progress report (plans)
            progressOpen: false, progressNotes: "",
        });

        onWillStart(() => this.reloadDrawer());
        onWillUpdateProps((next) => {
            // re-target when ANY of model / id / kind changes (a session and a
            // plan can share a numeric id; checking recordId alone misses it)
            if (next.recordId !== this.props.recordId
                || next.model !== this.props.model
                || next.drawerKind !== this.props.drawerKind) {
                // drop stale data first so the template never renders the new
                // kind against the previous record's payload (→ foreach crash)
                this.state.data = null;
                this.reloadDrawer(next.recordId, next.model);
            }
        });
    }

    async reloadDrawer(recId, model) {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_drawer_data",
                [model || this.props.model, recId || this.props.recordId],
            );
            this.state.data = data.error ? null : data;
            if (data.error) this.notification.add(data.error, { type: "warning" });
        } catch (e) {
            console.error("drawer load failed", e);
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    /* Wire any model method; handle action-returning results + refresh. */
    async runMethod(method, args = [], model = null, recId = null) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                model || this.props.model, method,
                [recId || this.props.recordId, ...args],
            );
            if (result && result.type) {
                await this.action.doAction(result, { onClose: () => this.reloadDrawer() });
            }
            await this.reloadDrawer();
            this.props.onAction?.();
        } catch (e) {
            console.error(`${method} failed`, e);
            this.notification.add("Action failed. Please try again.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    runItem(itemId, method) {
        return this.runMethod(method, [], "bfsi.action.plan.item", itemId);
    }

    /* Plan/session lifecycle through the scoped, resilient workspace RPCs —
       a notification side-effect can never make a state change "fail". */
    async planAction(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_plan_action",
                [this.props.recordId, action]);
            if (!data.error) this.state.data = data;
            this.props.onAction?.();
        } catch (e) {
            console.error(`${action} failed`, e);
            this.notification.add(e.data?.message || "Action failed. Please try again.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async sessionAction(action) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_session_action",
                [this.props.recordId, action]);
            if (!data.error) this.state.data = data;
            if (data.follow_action) {
                await this.action.doAction(data.follow_action, { onClose: () => this.reloadDrawer() });
            }
            // clear, honest feedback whether the action did something or not
            if (data.action_message) {
                this.notification.add(data.action_message,
                    { type: data.action_ok === false ? "warning" : "success" });
            } else if (action === "action_generate_ai_summary") {
                this.notification.add("AI summary generated.", { type: "success" });
            }
            this.props.onAction?.();
        } catch (e) {
            console.error(`${action} failed`, e);
            this.notification.add(e.data?.message || "Action failed. Please try again.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /* Whitelisted inline edit through the workspace save endpoint. */
    async saveField(vals) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_record_save",
                [this.props.model, this.props.recordId, vals]);
            if (!data.error) this.state.data = data;
            this.state.editing = null;
            this.props.onAction?.();
        } catch (e) {
            console.error("workspace_record_save failed", e);
            this.notification.add(
                e.data?.message || "Could not save.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    startEdit(field, current) {
        this.state.editing = field;
        this.state.editValue = current || "";
    }
    cancelEdit() { this.state.editing = null; }
    onEditInput(ev) { this.state.editValue = ev.target.value; }
    saveEdit() {
        const field = this.state.editing;
        if (field) this.saveField({ [field]: this.state.editValue });
    }

    get OUTCOMES() {
        return [
            { v: "excellent", l: "Excellent" }, { v: "good", l: "Good" },
            { v: "moderate", l: "Moderate" }, { v: "needs_improvement", l: "Needs work" },
        ];
    }

    /* ── in-drawer AI chat (no popup dialog) ── */
    /* "AI chat" footer button → jump to the inline chat and focus the input
       (the conversation is rendered inline, not in a popup) */
    toggleChat() {
        const input = this.el?.querySelector(".bws-chatbar input")
            || document.querySelector(".bws-drawer .bws-chatbar input");
        if (input) {
            input.scrollIntoView({ behavior: "smooth", block: "center" });
            input.focus();
        }
    }
    onChatInput(ev) { this.state.chatInput = ev.target.value; }
    onChatKey(ev) { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); this.sendChat(); } }
    async sendChat() {
        const msg = (this.state.chatInput || "").trim();
        if (!msg || this.state.chatBusy) return;
        this.state.chatBusy = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_session_chat",
                [this.props.recordId, msg]);
            if (!data.error) this.state.data = data;
            this.state.chatInput = "";
        } catch (e) {
            console.error("session chat failed", e);
            this.notification.add(e.data?.message || "Chat failed — try again.", { type: "danger" });
        } finally {
            this.state.chatBusy = false;
        }
    }

    /* ── in-drawer progress report (replaces the backend wizard) ── */
    toggleProgress() {
        this.state.progressOpen = !this.state.progressOpen;
        this.state.progressNotes = "";
    }
    onProgressInput(ev) { this.state.progressNotes = ev.target.value; }
    async submitProgress() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_report_progress",
                [this.props.recordId, this.state.progressNotes]);
            if (!data.error) this.state.data = data;
            this.state.progressOpen = false;
            this.notification.add("Progress reported.", { type: "success" });
            this.props.onAction?.();
        } catch (e) {
            console.error("report progress failed", e);
            this.notification.add(e.data?.message || "Could not report progress.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    togglePhase(key) { this.state.openPhase = this.state.openPhase === key ? null : key; }

    close() { this.props.onClose(); }
    openForm() { this.props.openForm(this.props.model, this.props.recordId); }

    /* jump to a linked record inside the workspace (no backend form) */
    openLinked(model, id, kind) {
        if (this.props.openRecord) {
            this.props.openRecord(model, id, kind);
        } else {
            this.props.openForm(model, id);
        }
    }
    coachNow() {
        const d = this.state.data;
        const empId = d?.employee?.id || d?.banker?.id;
        if (empId) this.props.openWizard(empId);
    }

    /* render a trusted HTML string as raw markup (internal AI/notes fields) */
    raw(html) { return html ? markup(html) : ""; }

    /* visual helpers */
    get d() { return this.state.data || {}; }
    ringColor(v) { return v >= 50 ? "#10B981" : v >= 25 ? "#F59E0B" : "#EF4444"; }
    barColor(cat) { return cat === "input" ? "#3B82F6" : cat === "beh" ? "#F59E0B" : "#10B981"; }
    barPct(v, t) { return Math.min(100, t ? (v / t) * 100 : 0); }
    trendH(v, arr) { const mx = Math.max(...(arr || [1]), 1); return Math.max(6, (v / mx) * 100); }
    stateClass(st) {
        return {
            draft: "bws-st-draft", scheduled: "bws-st-info", committed: "bws-st-info",
            generated: "bws-st-info", in_progress: "bws-st-warn", in_use: "bws-st-warn",
            completed: "bws-st-ok", overdue: "bws-st-crit", cancelled: "bws-st-muted",
            pending: "bws-st-draft", blocked: "bws-st-crit",
        }[st] || "bws-st-muted";
    }
    stateLabel(st) { return (st || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()); }
    itemKpiClass(cat) {
        return cat === "input" ? "in" : cat === "behavior" ? "beh" : cat === "output" ? "out" : "";
    }
}
