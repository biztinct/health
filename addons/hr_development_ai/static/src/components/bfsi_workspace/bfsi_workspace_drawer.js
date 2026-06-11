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
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, busy: false, data: null, openPhase: null });

        onWillStart(() => this.reloadDrawer());
        onWillUpdateProps((next) => {
            if (next.recordId !== this.props.recordId) this.reloadDrawer(next.recordId);
        });
    }

    async reloadDrawer(recId) {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_drawer_data",
                [this.props.model, recId || this.props.recordId],
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

    togglePhase(key) { this.state.openPhase = this.state.openPhase === key ? null : key; }

    close() { this.props.onClose(); }
    openForm() { this.props.openForm(this.props.model, this.props.recordId); }
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
