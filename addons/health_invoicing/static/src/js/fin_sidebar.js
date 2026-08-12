/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

const TAG_TO_PAGE = {
    fin_dashboard: "dashboard",
    fin_ar_management: "ar_management",
};

const XMLID_TO_PAGE = {
    "health_invoicing.action_fin_invoice_list": "invoices",
    "health_invoicing.action_fin_package_list": "packages",
    "health_invoicing.action_fin_ar_dashboard": "ar_dashboard",
    "health_invoicing.action_fin_payment_list": "payments",
    "health_invoicing.action_fin_overdue": "overdue",
    "health_invoicing.action_fin_cash_collections": "ar_management",
    "health_invoicing.action_fin_vat_log": "vat_log",
    "health_invoicing.action_fin_ar_transactions": "ar_transactions",
};

const NAV_ACTIONS = {
    dashboard: "health_invoicing.action_fin_dashboard",
    invoices: "health_invoicing.action_fin_invoice_list",
    packages: "health_invoicing.action_fin_package_list",
    ar_dashboard: "health_invoicing.action_fin_ar_dashboard",
    ar_management: "health_invoicing.action_fin_ar_management",
    payments: "health_invoicing.action_fin_payment_list",
    overdue: "health_invoicing.action_fin_overdue",
    vat_log: "health_invoicing.action_fin_vat_log",
    ar_transactions: "health_invoicing.action_fin_ar_transactions",
};

export class FinanceSidebar extends Component {
    static template = "health_invoicing.FinanceSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");

        const sessionName = window.odoo?.session_info?.name || "";
        this.currentUserName = sessionName || "Finance Agent";
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map(p => p[0]).join("").substring(0, 2).toUpperCase() || "FA";

        this.state = useState({ activePage: "" });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this._updateActivePage();
        });

        onMounted(() => {
            this._updateActivePage();
        });
    }

    _updateActivePage() {
        const controller = this.actionService.currentController;
        if (!controller) return;

        const action = controller.action;
        const tag = action.tag;

        if (tag && TAG_TO_PAGE[tag]) {
            this.state.activePage = TAG_TO_PAGE[tag];
            return;
        }

        const xmlId = action.xml_id;
        if (xmlId && XMLID_TO_PAGE[xmlId]) {
            this.state.activePage = XMLID_TO_PAGE[xmlId];
            return;
        }

        if (action.type === "ir.actions.act_window") {
            const model = action.res_model;
            if (model === "account.move") {
                this.state.activePage = "invoices";
                return;
            }
            if (model === "health.payment.transaction") {
                this.state.activePage = "payments";
                return;
            }
            if (model === "health.service.package") {
                this.state.activePage = "packages";
                return;
            }
            if (model === "account.move.line") {
                this.state.activePage = "ar_dashboard";
                return;
            }
            if (model === "health.ar.transaction.log") {
                this.state.activePage = "ar_transactions";
                return;
            }
        }
    }

    navigateTo(page) {
        const action = NAV_ACTIONS[page];
        if (action) {
            this.state.activePage = page;
            this.actionService.doAction(action, { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        window.location.href = "/web";
    }

    isActive(page) {
        return this.state.activePage === page;
    }
}

sidebarRegistry.add("finance_center", {
    actionTags: new Set(Object.keys(TAG_TO_PAGE)),
    windowModels: new Set([
        "health.payment.transaction",
        "health.ar.transaction.log",
        "health.service.package",
        "health.service.billing",
    ]),
    actionXmlIds: new Set(Object.keys(XMLID_TO_PAGE)),
    Component: FinanceSidebar,
});
