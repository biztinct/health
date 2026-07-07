/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
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
        });

        this._tagIndex = {};
        this._xmlidIndex = {};
        this._modelIndex = {};
        this._childParent = {};

        this._loadCollapseState();

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveActiveItem());

        onMounted(async () => {
            await this._loadSidebarData();
            this._resolveActiveItem();
        });
    }

    async _loadSidebarData() {
        const data = await this.orm.call("cms.sidebar.item", "get_sidebar_data", []);
        this.state.sections = data;
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

    navigateTo(item) {
        this.state.activeItemId = item.id;
        const actionRef = item.action_xmlid || item.action_tag;
        if (actionRef) {
            this.actionService.doAction(actionRef, { clearBreadcrumbs: true });
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
    "fin_dashboard", "fin_ar_management", "fin_settings",
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
