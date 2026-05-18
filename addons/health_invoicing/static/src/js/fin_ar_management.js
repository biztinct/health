/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class FinARManagement extends Component {
    static template = "health_invoicing.FinARManagement";

    setup() {
        this.action = useService("action");
    }

    openPaymentCollection() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Collect Payment"),
            res_model: "health.payment.collection.wizard",
            view_mode: "form",
            target: "new",
        });
    }

    openCashCollections() {
        this.action.doAction("health_invoicing.action_fin_cash_collections", { clearBreadcrumbs: true });
    }

    openCreditNote() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Credit Note"),
            res_model: "account.move",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: { default_move_type: "out_refund" },
        });
    }
}

registry.category("actions").add("fin_ar_management", FinARManagement);
