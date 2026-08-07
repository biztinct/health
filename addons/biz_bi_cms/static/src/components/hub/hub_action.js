/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ReportWizard } from "../wizard/report_wizard";

// ---------------------------------------------------------------------------
// Inline SVG icons.
//
// The CMS sidebar renders `item.icon` as a font-awesome class because that is
// the only render path its template has. Inside the hub's own body the repo
// convention applies again: inline SVG, coloured by `currentColor`, never
// emoji and never font-awesome. `bi.workspace.icon` holds a LUCIDE icon name
// (the seeds use stethoscope / credit-card / target, the model default is
// layout-grid) which the old Home never rendered at all — this is the map that
// turns those names into something visible, with a chart glyph as the fallback
// for any name that is not in it.
// ---------------------------------------------------------------------------

function svgIcon(body, size) {
    return markup(
        `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" ` +
            `stroke="currentColor" stroke-width="2" stroke-linecap="round" ` +
            `stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`
    );
}

const CHART_GLYPH = '<path d="M3 3v18h18"/><path d="M18 17V9"/>' +
    '<path d="M13 17V5"/><path d="M8 17v-3"/>';

const WORKSPACE_ICONS = {
    "stethoscope":
        '<path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 12 0V4a2 2 0 0 0-2-2h-1a.3.3 0 1 0 .2.3"/>' +
        '<path d="M8 15v1a6 6 0 0 0 12 0v-4"/>' +
        '<circle cx="20" cy="10" r="2"/>',
    "credit-card":
        '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "target":
        '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/>' +
        '<circle cx="12" cy="12" r="2"/>',
    "layout-grid":
        '<rect x="3" y="3" width="7" height="7" rx="1"/>' +
        '<rect x="14" y="3" width="7" height="7" rx="1"/>' +
        '<rect x="14" y="14" width="7" height="7" rx="1"/>' +
        '<rect x="3" y="14" width="7" height="7" rx="1"/>',
    "bar-chart": CHART_GLYPH,
};

const UI_ICONS = {
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    clear: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    empty: '<path d="M3 3v18h18"/><path d="M7 16h.01"/><path d="M12 16h.01"/>' +
        '<path d="M17 16h.01"/>',
};

// Six flat mono accents, indexed by `bi.workspace.color`. Flat single colours
// only — no gradients, no dual-tone.
const ACCENT_COUNT = 6;

export class BiHubAction extends Component {
    static template = "biz_bi_cms.Hub";
    static components = { ReportWizard };
    static props = { "*": true };
    static displayName = _t("Analytics");

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            denied: false,
            workspaces: [],
            recents: [],
            isCreator: false,
            isModeler: false,
            isAdmin: false,
            aiAvailable: false,
            query: "",
            wizardOpen: false,
        });

        onWillStart(async () => {
            try {
                // ONE round trip for the whole landing (the old Home awaited
                // three in sequence).
                const data = await this.orm.call("bi.workspace", "get_hub_data", []);
                this.state.workspaces = data.workspaces || [];
                this.state.recents = data.recents || [];
                this.state.isCreator = !!data.is_creator;
                this.state.isModeler = !!data.is_modeler;
                this.state.isAdmin = !!data.is_admin;
                this.state.aiAvailable = !!data.ai_available;
            } catch (error) {
                // An access_roles administrator is served every sidebar item
                // but may hold no BI group at all, so the very first read
                // raises. That is a configuration state, not a crash: show a
                // friendly explanation instead of an error dialog. Anything
                // that is NOT an access refusal still propagates.
                const name = error?.data?.name || "";
                if (name.includes("AccessError") || name.includes("AccessDenied")) {
                    this.state.denied = true;
                } else {
                    throw error;
                }
            } finally {
                this.state.loading = false;
            }
        });
    }

    // ------------------------------------------------------------------
    // Icons
    // ------------------------------------------------------------------

    workspaceIcon(name) {
        return svgIcon(WORKSPACE_ICONS[name] || CHART_GLYPH, 18);
    }

    uiIcon(name, size = 16) {
        return svgIcon(UI_ICONS[name] || CHART_GLYPH, size);
    }

    get bigEmptyIcon() {
        return svgIcon(UI_ICONS.empty, 40);
    }

    // ------------------------------------------------------------------
    // Presentation helpers
    // ------------------------------------------------------------------

    accentOf(workspace) {
        const color = Number(workspace.color) || 0;
        return ((color % ACCENT_COUNT) + ACCENT_COUNT) % ACCENT_COUNT;
    }

    countsLabel(workspace) {
        return _t("%(dashboards)s dashboards · %(datasets)s datasets", {
            dashboards: workspace.dashboard_count,
            datasets: workspace.dataset_count,
        });
    }

    get searchPlaceholder() {
        return _t("Search dashboards…");
    }

    get clearLabel() {
        return _t("Clear search");
    }

    // ------------------------------------------------------------------
    // Search — client side over the payload we already hold. No RPC on
    // keystroke: the complete dashboard list is already in memory.
    // ------------------------------------------------------------------

    get isSearching() {
        return this.state.query.trim().length > 0;
    }

    get searchResults() {
        const needle = this.state.query.trim().toLowerCase();
        if (!needle) {
            return [];
        }
        const results = [];
        for (const workspace of this.state.workspaces) {
            for (const dashboard of workspace.dashboards || []) {
                const haystack = `${dashboard.name || ""} ${dashboard.description || ""}`;
                if (haystack.toLowerCase().includes(needle)) {
                    results.push({
                        id: dashboard.id,
                        name: dashboard.name,
                        description: dashboard.description,
                        workspace: workspace.name,
                    });
                }
            }
        }
        return results;
    }

    clearSearch() {
        this.state.query = "";
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    openDashboard(dashboardId) {
        this.actionService.doAction(
            {
                type: "ir.actions.client",
                tag: "biz_bi.dashboard",
                params: { dashboard_id: dashboardId },
            },
            { clearBreadcrumbs: true }
        );
    }

    /**
     * Phase 2: the CTA opens the guided three-step report wizard as an
     * overlay on the hub. The button, its creator gating and its placement
     * are unchanged from Phase 1; only the target moved. The raw Explore
     * builder is still one click away, from inside the wizard.
     */
    createReport() {
        this.state.wizardOpen = true;
    }

    closeWizard() {
        this.state.wizardOpen = false;
    }
}

registry.category("actions").add("biz_bi.hub", BiHubAction);
