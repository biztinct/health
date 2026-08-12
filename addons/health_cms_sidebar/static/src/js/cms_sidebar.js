/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Domain } from "@web/core/domain";
import { user } from "@web/core/user";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

export class CmsSidebar extends Component {
    static template = "health_cms_sidebar.CmsSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");

        const sessionName = window.odoo?.session_info?.name || "";
        this.currentUserName = sessionName || "User";
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map(p => p[0]).join("").substring(0, 2).toUpperCase() || "U";

        this.state = useState({
            sections: [],
            activeItemId: null,
            collapsedSections: {},
            expandedItems: {},
            loaded: false,
            // Catchment scope. `pick` is the owner's chosen area — "" means
            // "my own area" (the default everyone starts on) and "all" means
            // no catchment filter at all, which only an owner can reach.
            catchment: { current_name: "", can_switch: false, options: [], mine_filter: "" },
            catchmentPick: "",
        });

        this._tagIndex = {};
        this._xmlidIndex = {};
        this._modelIndex = {};
        this._childParent = {};

        this._loadCollapseState();
        this._loadCatchmentPick();

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveActiveItem());

        onMounted(async () => {
            await this._loadSidebarData();
            this._resolveActiveItem();
        });
    }

    async _loadSidebarData() {
        const [data, scope] = await Promise.all([
            this.orm.call("cms.sidebar.item", "get_sidebar_data", []),
            this.orm.call("cms.sidebar.item", "get_catchment_scope", []),
        ]);
        this.state.sections = data;
        this.state.catchment = scope;
        if (!scope.can_switch) {
            // A scoped user has exactly one answer. Never let a stale
            // localStorage value from a previous account widen their view.
            this.state.catchmentPick = "";
        }
        this.state.loaded = true;
        this._buildMatchIndex();
    }

    _buildMatchIndex() {
        this._tagIndex = {};
        this._xmlidIndex = {};
        this._modelIndex = {};
        this._childParent = {};
        const indexOne = (item) => {
            if (item.action_tag) this._tagIndex[item.action_tag] = item.id;
            if (item.action_xmlid) this._xmlidIndex[item.action_xmlid] = item.id;
            for (const tag of (item.match_action_tags || [])) {
                if (tag) this._tagIndex[tag] = item.id;
            }
            for (const xmlid of (item.match_action_xmlids || [])) {
                if (xmlid) this._xmlidIndex[xmlid] = item.id;
            }
            for (const model of (item.match_models || [])) {
                if (model) this._modelIndex[model] = item.id;
            }
        };
        for (const section of this.state.sections) {
            for (const item of section.items) {
                indexOne(item);
                for (const child of (item.children || [])) {
                    indexOne(child);
                    this._childParent[child.id] = item.id;
                }
            }
        }
    }

    _resolveActiveItem() {
        const controller = this.actionService.currentController;
        if (!controller) return;

        const action = controller.action;
        const tag = action.tag;
        const xmlId = action.xml_id;
        const model = action.res_model;

        let found;
        if (tag && this._tagIndex[tag] !== undefined) {
            found = this._tagIndex[tag];
        } else if (xmlId && this._xmlidIndex[xmlId] !== undefined) {
            found = this._xmlidIndex[xmlId];
        } else if (model && this._modelIndex[model] !== undefined) {
            found = this._modelIndex[model];
        }
        if (found !== undefined) {
            this.state.activeItemId = found;
            this._expandParentOf(found);
        }
    }

    _expandParentOf(itemId) {
        const pid = this._childParent[itemId];
        if (pid !== undefined && !this.state.expandedItems[pid]) {
            this.state.expandedItems = { ...this.state.expandedItems, [pid]: true };
        }
    }

    toggleSection(sectionKey) {
        const current = this.state.collapsedSections[sectionKey] || false;
        this.state.collapsedSections = {
            ...this.state.collapsedSections,
            [sectionKey]: !current,
        };
        this._saveCollapseState();
    }

    isSectionCollapsed(sectionKey) {
        return !!this.state.collapsedSections[sectionKey];
    }

    onItemClick(item) {
        // Items with children act as expandable groups; leaves navigate.
        if (item.children && item.children.length) {
            this.toggleItem(item.id);
        } else {
            this.navigateTo(item);
        }
    }

    toggleItem(itemId) {
        this.state.expandedItems = {
            ...this.state.expandedItems,
            [itemId]: !this.state.expandedItems[itemId],
        };
    }

    isExpanded(itemId) {
        return !!this.state.expandedItems[itemId];
    }

    async navigateTo(item) {
        this.state.activeItemId = item.id;
        const actionRef = item.action_xmlid || item.action_tag;
        if (!actionRef) {
            return;
        }
        const options = { clearBreadcrumbs: true };
        const scope = this._catchmentDomain(item);
        if (scope) {
            try {
                const action = await this.actionService.loadAction(actionRef, {});
                action.domain = Domain.and([
                    new Domain(action.domain || []),
                    new Domain(scope),
                ]).toString();
                this.actionService.doAction(action, options);
                return;
            } catch {
                // Fall through to plain navigation. Record rules remain the
                // boundary, so the worst case here is an unscoped-looking
                // list, never access to something the rules forbid.
            }
        }
        this.actionService.doAction(actionRef, options);
    }

    /**
     * The catchment scope for this leaf, as a domain — NOT as a
     * `search_default_` facet.
     *
     * A facet was the first design and it was wrong twice over. It is
     * removable, so a scoped user could clear it and widen their own list
     * (on crm.lead the record rules alone let 296 rows through, because the
     * Sales "All Documents" rule ORs the catchment rule away) — and clearing
     * it produced a raw AccessError dialog. It also occupied
     * `searchModel.query`, which silently suppressed the Contacts view's own
     * default "Today" filter (crm_contact_list.js:162 only applies that when
     * the query is empty), so the same screen showed different totals
     * depending on whether an area was selected.
     *
     * As a domain it cannot be removed, cannot collide with the view's own
     * filters, and the sidebar pill above remains the visible indication of
     * what is being shown.
     *
     * Returns null when there is nothing to scope: reference-data leaves, the
     * OWL dashboards, or an owner who has chosen "All areas".
     */
    _catchmentDomain(item) {
        const field = item.catchment_field;
        if (!field) {
            return null;
        }
        const scope = this.state.catchment;
        const pick = this.state.catchmentPick;
        if (scope.can_switch && pick === "all") {
            return null;
        }
        if (scope.can_switch && pick) {
            const chosen = (scope.options || []).find((o) => String(o.id) === String(pick));
            if (chosen) {
                return [[field, "=", chosen.id]];
            }
        }
        if (!scope.current_id) {
            // An owner with no area set sees everything; a scoped user with no
            // area set sees nothing, which is the same fail-closed answer the
            // record rules give.
            return scope.can_switch ? null : [[0, "=", 1]];
        }
        return [[field, "=", scope.current_id]];
    }

    /**
     * QWeb expressions run in a restricted context with no access to global
     * builtins — `String(...)` inside the template throws "ctx.String is not a
     * function" and takes the whole sidebar down with it. Comparisons that need
     * coercion belong here, in the component.
     */
    isCatchmentPicked(value) {
        return String(this.state.catchmentPick) === String(value);
    }

    onCatchmentChange(ev) {
        this.state.catchmentPick = ev.target.value;
        this._saveCatchmentPick();
        // Re-open the current screen so the new scope takes effect immediately
        // rather than on the next click. Falls back to doing nothing when the
        // active item cannot be resolved (e.g. arrived via a breadcrumb).
        const item = this._findItem(this.state.activeItemId);
        if (item) {
            this.navigateTo(item);
        }
    }

    _findItem(itemId) {
        for (const section of this.state.sections) {
            for (const item of section.items) {
                if (item.id === itemId) {
                    return item;
                }
                for (const child of item.children || []) {
                    if (child.id === itemId) {
                        return child;
                    }
                }
            }
        }
        return null;
    }

    /**
     * `window.odoo.session_info.uid` is undefined in this build — the existing
     * collapse-state helpers below fall back to 0, so every account on a
     * browser shares one key. Harmless for "which sections are folded"; not
     * harmless for a scope pick, so this reads the real id from the user
     * service. (_loadSidebarData still resets the pick for anyone who cannot
     * switch, so a stale value can never widen a scoped user's view.)
     */
    _catchmentStorageKey() {
        return `cms_catchment_${user.userId || 0}`;
    }

    _loadCatchmentPick() {
        try {
            this.state.catchmentPick =
                localStorage.getItem(this._catchmentStorageKey()) || "";
        } catch {
            // ignore
        }
    }

    _saveCatchmentPick() {
        try {
            localStorage.setItem(this._catchmentStorageKey(), this.state.catchmentPick);
        } catch {
            // ignore
        }
    }

    navigateHome() {
        window.location.href = "/web";
    }

    isActive(itemId) {
        return this.state.activeItemId === itemId;
    }

    _loadCollapseState() {
        try {
            const uid = window.odoo?.session_info?.uid || 0;
            const stored = localStorage.getItem(`cms_sidebar_collapse_${uid}`);
            if (stored) {
                this.state.collapsedSections = JSON.parse(stored);
            }
        } catch {
            // ignore
        }
    }

    _saveCollapseState() {
        try {
            const uid = window.odoo?.session_info?.uid || 0;
            localStorage.setItem(
                `cms_sidebar_collapse_${uid}`,
                JSON.stringify(this.state.collapsedSections)
            );
        } catch {
            // ignore
        }
    }
}

// ---------------------------------------------------------------------------
// Registry takeover: remove old per-center sidebars, register unified entry
// ---------------------------------------------------------------------------
const OLD_KEYS = ["crm_center", "ops_center", "finance_center", "admin_center"];
for (const key of OLD_KEYS) {
    try {
        sidebarRegistry.remove(key);
    } catch {
        // key may not exist if that module isn't installed
    }
}

const ALL_ACTION_TAGS = new Set([
    // CRM
    "crm_dashboard", "crm_new_contact", "crm_booking_wizard", "crm_settings",
    // Operations
    "ops_command_center", "ops_booking_queue", "ops_booking_wizard", "ops_booking_detail",
    "ops_client_list", "ops_client_profile", "ops_quick_booking", "ops_reschedule_booking",
    "ops_recurring_booking", "ops_staff_roster", "ops_roster_planning", "ops_calendar",
    "ops_payment_collection", "ops_service_in_progress", "ops_staff_assignment",
    "staff_workload_dashboard",
    // Finance
    "fin_dashboard", "fin_ar_management",
    // Admin
    "admin_dashboard", "admin_settings", "field_requirements_dashboard",
]);

const ALL_XMLIDS = new Set([
    // CRM
    "health_crm.action_crm_contact_list_native",
    "health_crm.action_crm_contact_form_native",
    "health_crm.action_crm_client_list",
    "health_crm.action_crm_bookings_calendar",
    "health_crm.action_crm_followup_calendar",
    "health_crm.action_crm_activity_list",
    // Operations
    "health_fieldservice.action_ops_client_list_native",
    "health_fieldservice.action_ops_booking_list_native",
    "health_fieldservice.action_ops_booking_form",
    "health_fieldservice.action_ops_calendar",
    "health_fieldservice.action_staff_workload_dashboard",
    "health_fieldservice.action_assignment_web_timeline_view",
    "health_fieldservice.action_ops_client_profile_form",
    "health_fieldservice.action_health_staff_schedules",
    "health_fieldservice.action_health_staff_timeoff",
    // Finance
    "health_invoicing.action_fin_invoice_list",
    "health_invoicing.action_fin_package_list",
    "health_invoicing.action_fin_ar_dashboard",
    "health_invoicing.action_fin_payment_list",
    "health_invoicing.action_fin_overdue",
    "health_invoicing.action_fin_cash_collections",
    "health_invoicing.action_fin_vat_log",
    "health_invoicing.action_fin_ar_transactions",
    "health_invoicing.action_fin_account_payment",
    "health_invoicing.action_fin_refund_credit",
    // Admin
    "health_landing.action_admin_users",
    "health_landing.action_admin_facilities",
    "health_landing.action_admin_catchments",
    "health_landing.action_admin_service_types",
    "health_landing.action_admin_symptoms",
    "health_landing.action_admin_referral_sources",
    "health_landing.action_admin_insurance",
    "health_landing.action_admin_urgency",
    "health_landing.action_admin_categories",
    "health_landing.action_admin_specialties",
    "health_landing.action_admin_districts",
    "health_landing.action_admin_pricelists",
    "health_landing.action_admin_pricing_rules",
    "health_landing.action_admin_quick_edit_rules",
    "health_landing.action_admin_packages",
    "health_landing.action_admin_staff",
    "health_landing.action_admin_skills",
    "health_landing.action_admin_areas",
    "health_landing.action_admin_equipment",
    "health_landing.action_admin_holidays",
    "health_landing.action_admin_audit",
    // CMS Sidebar Config
    "health_cms_sidebar.action_cms_sidebar_item",
    "health_cms_sidebar.action_cms_sidebar_section",
    // NB: clinical / interop / any future items are added at runtime from
    // cms.sidebar.item data by the cms_sidebar_keys service below — no need
    // to hardcode new action XML IDs here.
]);

const ALL_MODELS = new Set([
    "crm.lead", "res.partner",
    "health.fieldservice.order", "health.staff.assignment",
    "health.payment.transaction", "health.ar.transaction.log",
    "health.service.package", "health.service.billing",
    "account.move", "account.move.line",
    "health.audit.log.view",
    "cms.sidebar.item", "cms.sidebar.section",
    // staff record form (opened from the Staff Roster, Staff Assignment, …)
    // must keep the CMS sidebar like every other CMS record form
    "hr.employee",
    // NB: clinical / interop / future record models are added at runtime
    // from cms.sidebar.item.match_models by the cms_sidebar_keys service.
]);

sidebarRegistry.add("cms_unified", {
    actionTags: ALL_ACTION_TAGS,
    actionXmlIds: ALL_XMLIDS,
    windowModels: ALL_MODELS,
    Component: CmsSidebar,
});

// ---------------------------------------------------------------------------
// Data-driven visibility: at startup, load the action tags / xml-ids / models
// declared by every cms.sidebar.item and add them to the (shared) registry
// sets, so a newly-wired feature keeps the CMS shell WITHOUT a JS edit. The
// hardcoded sets above are a bootstrap that keeps the core screens shell-y
// even before this RPC resolves (and if it ever fails). SidebarHost reads the
// sets live via .has(), so mutating them here is picked up on the next resolve.
// ---------------------------------------------------------------------------
const cmsSidebarKeysService = {
    dependencies: ["orm"],
    async start(env, { orm }) {
        try {
            const keys = await orm.call("cms.sidebar.item", "get_match_keys", []);
            (keys.tags || []).forEach((t) => ALL_ACTION_TAGS.add(t));
            (keys.xmlids || []).forEach((x) => ALL_XMLIDS.add(x));
            (keys.models || []).forEach((m) => ALL_MODELS.add(m));
            // Nudge the always-mounted SidebarHost to re-resolve now that the
            // sets include the freshly-loaded keys.
            env.bus.trigger("ACTION_MANAGER:UI-UPDATED");
        } catch {
            // Best-effort: the bootstrap sets still cover the core screens.
        }
    },
};
registry.category("services").add("cms_sidebar_keys", cmsSidebarKeysService);
