/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";
import { useState, onMounted, onPatched, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const PAYMENT_LABELS = {
    not_paid: "Not Paid",
    in_payment: "In Payment",
    paid: "Paid",
    partial: "Partial",
    reversed: "Reversed",
    invoicing_legacy: "Legacy",
};

export class FinInvoiceFormController extends FormController {
    static template = "health_invoicing.FinInvoiceFormView";

    setup() {
        super.setup(...arguments);
        this.rootRef = useRef("root");
        this.orm = useService("orm");

        this.headerState = useState({
            header: {},
            isLoaded: false,
        });

        onMounted(() => {
            this._adjustLayout();
            this._loadHeaderData();
        });
        onPatched(() => {
            this._adjustLayout();
        });
    }

    async _loadHeaderData() {
        const resId = this.model.root.resId;
        if (!resId) return;
        try {
            const data = await this.orm.call(
                "account.move",
                "get_invoice_header_data",
                [resId]
            );
            this.headerState.header = data;
            this.headerState.isLoaded = true;
        } catch (e) {
            console.error("Failed to load invoice header:", e);
        }
    }

    async saveButtonClicked(params) {
        const res = await super.saveButtonClicked(params);
        await this._loadHeaderData();
        return res;
    }

    _adjustLayout() {
        const el = this.rootRef.el;
        if (el) {
            const fc = el.querySelector(".o_form_view_container");
            const oc = el.querySelector(".o_content");
            if (fc) fc.style.width = "100%";
            if (oc) oc.style.width = "100%";
            requestAnimationFrame(() => {
                el.classList.add("fin-mounted");
            });
        }
    }

    get className() {
        const result = super.className;
        result["fin-invoice-form-page"] = true;
        return result;
    }

    getPaymentLabel(state) {
        return PAYMENT_LABELS[state] || state || "Unknown";
    }

    getPaymentClass(state) {
        return "fin-pay-" + (state || "not_paid");
    }

    formatCurrency(val) {
        if (!val && val !== 0) return "0";
        return Number(val).toLocaleString();
    }

    goToInvoices() {
        this.actionService.doAction(
            "health_invoicing.action_fin_invoice_list",
            { clearBreadcrumbs: true }
        );
    }
}

registry.category("views").add("fin_invoice_form_view", {
    ...registry.category("views").get("form"),
    Controller: FinInvoiceFormController,
});
