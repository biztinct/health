/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class FinSettings extends Component {
    static template = "health_invoicing.FinSettings";

    setup() {
        this.action = useService("action");
    }

    openPackageProducts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Package Products"),
            res_model: "product.template",
            view_mode: "list,form",
            domain: [["type", "=", "healthcare_package"]],
            target: "current",
        });
    }

    openTaxConfig() {
        this.action.doAction("base_setup.action_general_configuration");
    }

    openPaymentMethods() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Payment Methods"),
            res_model: "account.payment.method",
            view_mode: "list,form",
            target: "current",
        });
    }

    openChartOfAccounts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Chart of Accounts"),
            res_model: "account.account",
            view_mode: "list,form",
            target: "current",
        });
    }

    openInvoicingSettings() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Invoicing Settings"),
            res_model: "res.config.settings",
            view_mode: "form",
            target: "inline",
            context: { module: "account" },
        });
    }
}

registry.category("actions").add("fin_settings", FinSettings);
