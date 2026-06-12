/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { WORKSPACE_CONFIGS } from "./workspace_configs";
import { BfsiWorkspaceDrawer } from "./bfsi_workspace_drawer";
import { BfsiCoachingWizard } from "../bfsi_coaching_wizard/bfsi_coaching_wizard";

/**
 * BfsiWorkspace — one reusable OWL workspace driven by a config object.
 * Replaces the standard Odoo list/form views behind the Coaching (and later
 * Performance / Organization) menus with: segmented tabs + My/Team toggle +
 * chip filters + search + sort + a rich card list + slide-over drawer.
 */
export class BfsiWorkspace extends Component {
    static template = "hr_development_ai.BfsiWorkspace";
    static props = ["*"];
    static components = { BfsiWorkspaceDrawer, BfsiCoachingWizard };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const key = this.props.action?.params?.workspace
            || this.props.action?.context?.workspace || "coaching";
        this.config = WORKSPACE_CONFIGS[key] || WORKSPACE_CONFIGS.coaching;

        this.state = useState({
            loading: true,
            ctxReady: false,
            isManager: false,
            eid: null,
            branchId: false,
            scope: this.config.scope?.default || "team",
            segmentKey: this.config.segments[0].key,
            chips: {},            // {chipKey: Set(values) | datePreset}
            search: "",
            sort: this.config.segments[0].sorts[0].key,
            rows: [],
            limit: 80,
            hasMore: false,
            latestOnly: true,     // default: one (newest) record per person
            // drawer
            drawerModel: null,
            drawerId: null,
            drawerKind: null,
            // wizard overlay
            wizardBankerId: null,
        });

        onWillStart(async () => {
            try {
                const ctx = await this.orm.call("hr.employee", "get_dashboard_context", []);
                this.state.eid = ctx.id;
                this.state.isManager = !!ctx.is_manager;
                this.state.branchId = ctx.branch_id || false;
            } catch (e) {
                console.error("workspace ctx failed", e);
            }
            if (!this.state.isManager) this.state.scope = "my";
            this.state.ctxReady = true;
            await this.loadSegment();
        });
    }

    /* ── config helpers ── */
    get segment() {
        return this.config.segments.find(s => s.key === this.state.segmentKey)
            || this.config.segments[0];
    }
    get scopeEnabled() {
        return !!this.config.scope?.enabled && this.segment.scopeDomains
            && this.state.isManager;
    }

    /* ── interactions ── */
    async selectSegment(key) {
        if (key === this.state.segmentKey) return;
        this.state.segmentKey = key;
        this.state.chips = {};
        this.state.search = "";
        this.state.sort = this.segment.sorts[0].key;
        await this.loadSegment();
    }
    async setScope(scope) {
        if (scope === this.state.scope) return;
        this.state.scope = scope;
        await this.loadSegment();
    }
    async toggleChip(chipKey, value) {
        const cur = this.state.chips[chipKey];
        if (value === "__clear__") { delete this.state.chips[chipKey]; }
        else {
            const set = cur instanceof Set ? cur : new Set();
            if (set.has(value)) set.delete(value); else set.add(value);
            if (set.size) this.state.chips[chipKey] = set; else delete this.state.chips[chipKey];
        }
        await this.loadSegment();
    }
    setDatePreset(chipKey, preset) {
        if (this.state.chips[chipKey] === preset) delete this.state.chips[chipKey];
        else this.state.chips[chipKey] = preset;
        this.loadSegment();
    }
    isChipActive(chipKey, value) {
        const c = this.state.chips[chipKey];
        if (c instanceof Set) return c.has(value);
        return c === value;
    }
    onSearchInput(ev) {
        this.state.search = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadSegment(), 250);
    }
    async setSort(key) { this.state.sort = key; await this.loadSegment(); }
    async toggleLatest() { this.state.latestOnly = !this.state.latestOnly; await this.loadSegment(); }
    get hasPersonField() { return !!this.segment.personField; }

    /* back to the Command Center home dashboard */
    goHome() {
        this.action.doAction("hr_development_ai.action_bfsi_manager_dashboard");
    }

    /* ── domain builder ── */
    buildDomain() {
        const seg = this.segment;
        const uid = user.userId;
        let domain = [];
        // scope
        if (this.config.scope?.enabled && seg.scopeDomains) {
            const scope = this.scopeEnabled ? this.state.scope : "my";
            const leaves = (seg.scopeDomains[scope] || seg.scopeDomains.my)(uid, this.state.eid, this.state.branchId);
            domain = domain.concat(leaves);
        }
        // chips
        for (const chip of (seg.chips || [])) {
            const sel = this.state.chips[chip.key];
            if (!sel) continue;
            if (chip.kind === "date") {
                domain = domain.concat(this._dateLeaves(chip.field, sel));
            } else if (sel instanceof Set && sel.size) {
                domain.push([chip.key, "in", [...sel]]);
            }
        }
        // search (ilike OR)
        const q = (this.state.search || "").trim();
        if (q && seg.search?.length) {
            const ors = seg.search.map(f => [f, "ilike", q]);
            for (let i = 0; i < ors.length - 1; i++) domain.unshift("|");
            domain = domain.concat(ors);
        }
        return domain;
    }
    _dateLeaves(field, preset) {
        const today = new Date();
        const iso = d => d.toISOString().slice(0, 10);
        if (preset === "today") return [[field, ">=", iso(today)]];
        if (preset === "overdue") return [[field, "<", iso(today)]];
        if (preset === "week") {
            const s = new Date(today); s.setDate(today.getDate() - today.getDay());
            return [[field, ">=", iso(s)]];
        }
        if (preset === "month") {
            const s = new Date(today.getFullYear(), today.getMonth(), 1);
            return [[field, ">=", iso(s)]];
        }
        return [];
    }

    /* ── data load ── */
    async loadSegment() {
        const seg = this.segment;
        this.state.loading = true;
        try {
            let rows = await this.orm.searchRead(
                seg.model, this.buildDomain(), seg.fields,
                { order: this.state.sort, limit: this.state.limit },
            );
            const fetched = rows.length;
            // "Latest only": keep the newest record per person (one row each)
            if (this.state.latestOnly && seg.personField) {
                const seen = new Set();
                rows = rows.filter(r => {
                    const k = r[seg.personField] && r[seg.personField][0];
                    if (k == null) return true;
                    if (seen.has(k)) return false;
                    seen.add(k); return true;
                });
            }
            this.state.rows = rows;
            this.state.hasMore = fetched === this.state.limit;
        } catch (e) {
            console.error("workspace load failed", e);
            this.state.rows = [];
            this.notification.add("Could not load records.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    /* ── drawer ── */
    openDrawer(row) {
        const seg = this.segment;
        if (!seg.drawer) {           // no drawer -> open the full record form directly
            this.openForm(seg.model, row.id);
            return;
        }
        this.state.drawerModel = seg.model;
        this.state.drawerId = row.id;
        this.state.drawerKind = seg.drawer;
    }
    closeDrawer() {
        this.state.drawerModel = null;
        this.state.drawerId = null;
        this.state.drawerKind = null;
    }
    /* re-target the drawer onto a linked record (plan ↔ strategy ↔ session) */
    openRecordDrawer(model, id, kind) {
        this.state.drawerModel = model;
        this.state.drawerId = id;
        this.state.drawerKind = kind;
    }
    onDrawerAction() { this.loadSegment(); }

    openForm(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: model, res_id: id,
            views: [[false, "form"]], target: "current",
        });
    }

    /* avatar click → Person 360 when hosted inside the shell */
    openPerson(m2o) {
        const empId = m2o && m2o[0];
        if (empId && this.props.onOpenPerson) {
            this.props.onOpenPerson(empId);
        }
    }

    /* ── wizard overlay (Coach now) ── */
    openWizard(bankerId) {
        this.closeDrawer();
        this.state.wizardBankerId = bankerId;
    }
    async closeWizard(result) {
        this.state.wizardBankerId = null;
        if (result && result.ok) {
            this.notification.add(`${result.banker_name} coached — plan committed.`, { type: "success" });
            await this.loadSegment();
        }
    }

    /* ── row visual helpers ── */
    initial(m2o) { return ((m2o && m2o[1]) || "?").trim()[0].toUpperCase(); }
    name(m2o) { return (m2o && m2o[1]) || "—"; }
    avatarColor(id) {
        const palette = ["#3B82F6", "#1E40AF", "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#14B8A6", "#EC4899"];
        return palette[(id || 0) % palette.length];
    }
    ringColor(v) { return v >= 50 ? "#10B981" : v >= 25 ? "#F59E0B" : "#EF4444"; }
    fmtDate(s) {
        if (!s) return "—";
        const d = new Date(s);
        return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }
    stateClass(st) {
        return {
            draft: "bws-st-draft", scheduled: "bws-st-info", committed: "bws-st-info",
            generated: "bws-st-info", in_progress: "bws-st-warn", in_use: "bws-st-warn",
            completed: "bws-st-ok", overdue: "bws-st-crit", cancelled: "bws-st-muted",
        }[st] || "bws-st-muted";
    }
    stateLabel(st) {
        return (st || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
    prioClass(p) {
        return { critical: "bws-st-crit", high: "bws-st-warn", medium: "bws-st-info", low: "bws-st-ok" }[p] || "bws-st-muted";
    }
    typeIcon(t) {
        return { ai: "bot", human: "users", hybrid: "sparkles" }[t] || "messages-square";
    }
}

registry.category("actions").add("bfsi_workspace", BfsiWorkspace);
