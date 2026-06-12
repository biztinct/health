/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * SettingsScreen — KPI Targets & Integrations, fully in-workspace.
 * Card lists + slide-up dialogs instead of backend list/form views.
 * Admin-only (the RPC layer enforces it too).
 */
export class SettingsScreen extends Component {
    static template = "hr_development_ai.SettingsScreen";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            tab: "targets",        // targets | integrations | providers
            targets: [],
            integrations: [],
            providers: [],
            options: {},
            // dialog
            dialog: null,          // 'target' | 'integration' | 'provider'
            recId: false,
            vals: {},
            advancedOpen: false,
            busy: false,
            busyAction: null,      // `${id}:${method}` while an action runs
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const d = await this.orm.call("bfsi.coaching.flow", "workspace_settings_data", []);
            this.state.targets = d.targets || [];
            this.state.integrations = d.integrations || [];
            this.state.providers = d.providers || [];
            this.state.options = d.options || {};
            this.state.error = null;
        } catch (e) {
            console.error("settings load failed", e);
            this.state.error = e.data?.message || "Could not load settings.";
        } finally {
            this.state.loading = false;
        }
    }

    /* ── dialogs ── */
    newTarget() {
        this.state.vals = {
            employee_id: "", job_id: "", branch_id: "", banker_type: "",
            period_type: "monthly", valid_from: "", valid_to: "",
            is_active: true, notes: "",
            target_overall_score: 75, target_revenue: 0,
            target_dials_per_hour: 0, target_total_dials: 0, target_connects: 0,
            target_meetings_scheduled: 0, target_meetings_conducted: 0,
            target_script_adherence: 0, target_objection_handling: 0,
            target_need_analysis: 0, target_product_knowledge: 0,
            target_compliance: 0, target_customer_satisfaction: 0,
            target_conversions: 0, target_conversion_rate: 0,
        };
        this.state.recId = false;
        this.state.advancedOpen = false;
        this.state.dialog = "target";
    }
    editTarget(t) {
        this.state.vals = {
            employee_id: t.employee_id || "", job_id: t.job_id || "",
            branch_id: t.branch_id || "", banker_type: t.banker_type || "",
            period_type: t.period_type, valid_from: t.valid_from,
            valid_to: t.valid_to, is_active: t.is_active, notes: t.notes,
            ...t.values,
        };
        this.state.recId = t.id;
        this.state.advancedOpen = false;
        this.state.dialog = "target";
    }
    newIntegration() {
        this.state.vals = {
            name: "", source_system: "crm", api_base_url: "", auth_type: "api_key",
            api_key: "", username: "", sync_frequency: "daily",
            data_endpoint: "", notes: "", active: true,
        };
        this.state.recId = false;
        this.state.dialog = "integration";
    }
    editIntegration(i) {
        this.state.vals = {
            name: i.name, source_system: i.source_system,
            api_base_url: i.api_base_url, auth_type: i.auth_type || "api_key",
            api_key: "", username: "", sync_frequency: i.sync_frequency,
            data_endpoint: i.data_endpoint, notes: i.notes, active: i.active,
        };
        this.state.recId = i.id;
        this.state.dialog = "integration";
    }
    editProvider(p) {
        this.state.vals = {
            provider: p.provider, is_active: p.is_active,
            model_name: p.model_name, timeout: p.timeout,
            openai_api_key: "", llama_endpoint: p.llama_endpoint,
            mistral_endpoint: p.mistral_endpoint,
        };
        this.state.recId = p.id;
        this.state.dialog = "provider";
    }
    closeDialog() { this.state.dialog = null; }

    setVal(field, value) { this.state.vals[field] = value; }
    onInput(field, ev) { this.state.vals[field] = ev.target.value; }
    onNumber(field, ev) { this.state.vals[field] = parseFloat(ev.target.value) || 0; }

    async saveDialog() {
        if (this.state.busy) return;
        const model = { target: "bfsi.kpi.target", integration: "bfsi.kpi.integration",
                        provider: "hr.ai.provider.config" }[this.state.dialog];
        const vals = { ...this.state.vals };
        // keys with empty api credentials on edit → don't overwrite
        if (model === "bfsi.kpi.integration" && this.state.recId && !vals.api_key) {
            delete vals.api_key;
        }
        if (model === "hr.ai.provider.config" && !vals.openai_api_key) {
            delete vals.openai_api_key;   // keep the stored key when left blank
        }
        this.state.busy = true;
        try {
            await this.orm.call("bfsi.coaching.flow", "workspace_settings_save",
                [model, this.state.recId, vals]);
            this.notification.add("Saved.", { type: "success" });
            this.state.dialog = null;
            await this.load();
        } catch (e) {
            console.error(e);
            this.notification.add(e.data?.message || "Could not save.", { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async toggleTargetActive(t) {
        await this.orm.call("bfsi.coaching.flow", "workspace_settings_save",
            ["bfsi.kpi.target", t.id, { is_active: !t.is_active }]);
        await this.load();
    }

    async runIntegrationAction(i, method) {
        const key = `${i.id}:${method}`;
        if (this.state.busyAction) return;
        this.state.busyAction = key;
        try {
            await this.orm.call("bfsi.coaching.flow", "workspace_settings_action",
                ["bfsi.kpi.integration", i.id, method]);
            this.notification.add(
                method === "action_sync_now" ? "Sync started." : "Done.",
                { type: "success" });
            await this.load();
        } catch (e) {
            console.error(e);
            this.notification.add(e.data?.message || "Action failed.", { type: "danger" });
        } finally {
            this.state.busyAction = null;
        }
    }

    async testProvider(p) {
        const key = `${p.id}:test`;
        if (this.state.busyAction) return;
        this.state.busyAction = key;
        try {
            await this.orm.call("bfsi.coaching.flow", "workspace_settings_action",
                ["hr.ai.provider.config", p.id, "action_test_connection"]);
            await this.load();
            const fresh = this.state.providers.find(x => x.id === p.id);
            this.notification.add(
                fresh && fresh.status === "success" ? "Connection successful." : "Connection failed — check the settings.",
                { type: fresh && fresh.status === "success" ? "success" : "warning" });
        } catch (e) {
            console.error(e);
            this.notification.add(e.data?.message || "Test failed.", { type: "danger" });
        } finally {
            this.state.busyAction = null;
        }
    }
    async toggleProviderActive(p) {
        await this.orm.call("bfsi.coaching.flow", "workspace_settings_save",
            ["hr.ai.provider.config", p.id, { is_active: !p.is_active }]);
        await this.load();
    }

    stateChip(st) {
        return { connected: "bfsi-chip-ok", active: "bfsi-chip-ok", success: "bfsi-chip-ok",
                 testing: "bfsi-chip-warn", error: "bfsi-chip-crit", failed: "bfsi-chip-crit",
                 not_tested: "bfsi-chip-muted", draft: "bfsi-chip-muted" }[st] || "bfsi-chip-muted";
    }

    get ADVANCED_FIELDS() {
        return [
            ["target_dials_per_hour", "Dials / hour"],
            ["target_total_dials", "Total dials"],
            ["target_connects", "Connects"],
            ["target_meetings_scheduled", "Meetings scheduled"],
            ["target_meetings_conducted", "Meetings conducted"],
            ["target_script_adherence", "Script adherence %"],
            ["target_objection_handling", "Objection handling"],
            ["target_need_analysis", "Need analysis"],
            ["target_product_knowledge", "Product knowledge"],
            ["target_compliance", "Compliance"],
            ["target_customer_satisfaction", "Customer satisfaction"],
            ["target_conversions", "Conversions"],
            ["target_conversion_rate", "Conversion rate %"],
        ];
    }
}
