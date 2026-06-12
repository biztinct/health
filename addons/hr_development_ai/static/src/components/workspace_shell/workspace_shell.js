/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { loadRoutes, persistRoutes } from "../../core/nav";
import { HomeBanker } from "../home_banker/home_banker";
import { HomeManager } from "../home_manager/home_manager";
import { HomeRegional } from "../home_regional/home_regional";
import { Person360 } from "../person_360/person_360";
import { TeamScreen } from "../team_screen/team_screen";
import { SettingsScreen } from "../settings_screen/settings_screen";
import { BfsiWorkspace } from "../bfsi_workspace/bfsi_workspace";
import { BfsiAiDashboard } from "../bfsi_ai_dashboard/bfsi_ai_dashboard";
import { BfsiCoachingWizard } from "../bfsi_coaching_wizard/bfsi_coaching_wizard";
import { BfsiWorkspaceDrawer } from "../bfsi_workspace/bfsi_workspace_drawer";

/**
 * WorkspaceShell — THE app. One adaptive workspace with a sidebar, a route
 * stack (real Back), role-aware screens, and global overlays (coaching
 * wizard + record drawer) so the flow never leaves the screen.
 *
 * Screens: home (role-adaptive) · coaching · performance · analytics ·
 *          branch (regional drill-in cockpit)
 */
export class BfsiWorkspaceShell extends Component {
    static template = "hr_development_ai.WorkspaceShell";
    static props = ["*"];
    static components = {
        HomeBanker, HomeManager, HomeRegional, Person360, TeamScreen, SettingsScreen,
        BfsiWorkspace, BfsiAiDashboard, BfsiCoachingWizard, BfsiWorkspaceDrawer,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const startScreen = this.legacyStart(
            this.props.action?.params?.start
            || this.props.action?.context?.start || "home");

        this.state = useState({
            loading: true,
            error: null,
            home: null,          // workspace_home_data payload
            role: "banker",
            isAdmin: false,
            routes: loadRoutes({ screen: startScreen, params: {} }),
            navOpen: false,      // mobile nav sheet
            // overlays
            wizardBankerId: null,
            drawer: null,        // {model, id, kind}
            // regional drill-in cache
            branchCockpit: null,
            branchLoading: false,
        });

        this.ensureInterFont();
        onWillStart(() => this.loadHome());
    }

    /* the workspace typography — loaded once per session */
    ensureInterFont() {
        if (document.getElementById("bfsi-inter-font")) return;
        const link = document.createElement("link");
        link.id = "bfsi-inter-font";
        link.rel = "stylesheet";
        link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap";
        document.head.appendChild(link);
    }

    /* map legacy re-tagged action params to shell screens */
    legacyStart(start) {
        const map = {
            command_center: "home", dashboard: "analytics",
            coaching: "coaching", performance: "performance",
            organization: "home", home: "home", analytics: "analytics",
            settings: "settings",
        };
        return map[start] || "home";
    }

    async loadHome() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("bfsi.coaching.flow", "workspace_home_data", []);
            if (data.error) {
                this.state.error = data.error;
            } else {
                this.state.home = data;
                this.state.role = data.role;
                this.state.isAdmin = !!data.is_admin;
            }
        } catch (e) {
            console.error("workspace home failed", e);
            this.state.error = "Could not load the workspace.";
        } finally {
            this.state.loading = false;
        }
        // a banker landing on a manager-only screen falls back home
        if (this.state.role === "banker"
            && ["analytics", "performance", "branch", "settings"].includes(this.route.screen)) {
            this.reset("home");
        }
        if (this.route.screen === "settings" && !this.state.isAdmin) {
            this.reset("home");
        }
    }

    /* ── routing ── */
    get route() { return this.state.routes[this.state.routes.length - 1]; }
    get canBack() { return this.state.routes.length > 1; }

    reset(screen, params = {}) {
        this.state.routes = [{ screen, params }];
        persistRoutes(this.state.routes);
        this.state.navOpen = false;
        this.afterNavigate();
    }
    push(screen, params = {}) {
        this.state.routes = [...this.state.routes, { screen, params }];
        persistRoutes(this.state.routes);
        this.afterNavigate();
    }
    back() {
        if (!this.canBack) return;
        this.state.routes = this.state.routes.slice(0, -1);
        persistRoutes(this.state.routes);
        this.afterNavigate();
    }
    afterNavigate() {
        if (this.route.screen === "branch" && this.route.params.branchId) {
            this.loadBranchCockpit(this.route.params.branchId);
        }
    }

    /* ── sidebar ── */
    get navItems() {
        const items = [{ key: "home", label: "Home", icon: "house" }];
        if (this.state.role === "banker") {
            items.push({ key: "coaching", label: "My Coaching", icon: "handshake" });
        } else {
            items.push(
                { key: "team", label: "Team", icon: "users" },
                { key: "coaching", label: "Coaching", icon: "handshake" },
                { key: "performance", label: "Performance", icon: "gauge" },
                { key: "analytics", label: "Analytics", icon: "layout-dashboard" },
            );
        }
        return items;
    }
    isActive(key) {
        const screen = this.route.screen;
        if (key === "home") return screen === "home" || screen === "branch";
        return screen === key;
    }
    get settingsActive() { return this.route.screen === "settings"; }
    openSettings() {
        this.reset("settings");
    }

    /* ── regional drill-in ── */
    async loadBranchCockpit(branchId) {
        this.state.branchLoading = true;
        this.state.branchCockpit = null;
        try {
            const data = await this.orm.call(
                "bfsi.coaching.flow", "workspace_branch_cockpit", [branchId]);
            if (data.error) {
                this.notification.add(data.error, { type: "warning" });
                this.back();
            } else {
                this.state.branchCockpit = data;
            }
        } finally {
            this.state.branchLoading = false;
        }
    }

    /* ── overlays: wizard + drawer ── */
    openWizard(bankerId) {
        this.state.drawer = null;
        this.state.wizardBankerId = bankerId;
    }
    async closeWizard(result) {
        this.state.wizardBankerId = null;
        if (result && result.ok) {
            this.notification.add(
                `${result.banker_name} coached — plan committed.`, { type: "success" });
            await this.loadHome();
            if (this.route.screen === "branch") {
                this.afterNavigate();
            }
            if (result.view_plan && result.plan_id) {
                this.openDrawer("bfsi.action.plan", result.plan_id, "plan");
            }
        }
    }
    openDrawer(model, id, kind) {
        this.state.drawer = { model, id, kind };
    }
    closeDrawer() { this.state.drawer = null; }
    async onDrawerAction() {
        await this.loadHome();
        if (this.route.screen === "branch") this.afterNavigate();
    }
    openForm(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: model, res_id: id,
            views: [[false, "form"]], target: "current",
        });
    }

    openPerson(employeeId) {
        this.push("person", { employeeId });
    }

    /* embedded legacy-workspace props */
    workspaceAction(key) {
        return { params: { workspace: key } };
    }
}

registry.category("actions").add("bfsi_coaching_workspace", BfsiWorkspaceShell);
