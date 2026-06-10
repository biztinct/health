/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Rich checkout dialog for purchasing a prepaid package — replaces the basic
 * "Select Package" wizard form. Opened from the PackageWizardDialog after a
 * product card is chosen. Reuses the pw-* dialog styling.
 */
export class PackagePurchaseDialog extends Component {
    static template = "health_invoicing.PackagePurchaseDialog";
    static props = {
        product: { type: Object },            // {id, name, price, price_per_service, service_count, package_type_label, expiration}
        patientId: { type: Number },
        patientName: { type: String, optional: true },
        fsoId: { type: [Number, Boolean], optional: true },
        close: { type: Function },
        onDone: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            createInvoice: true,
            processPayment: false,
            paymentMethod: "cash",
            paymentAmount: this.props.product.price || 0,
            isSaving: false,
        });
    }

    formatCurrency(amount) {
        if (!amount && amount !== 0) return "0 đ";
        return Math.round(amount).toLocaleString("vi-VN") + " đ";
    }

    toggleInvoice() {
        this.state.createInvoice = !this.state.createInvoice;
    }

    togglePayment() {
        this.state.processPayment = !this.state.processPayment;
        if (this.state.processPayment && !this.state.paymentAmount) {
            this.state.paymentAmount = this.props.product.price || 0;
        }
    }

    onMethodChange(ev) {
        this.state.paymentMethod = ev.target.value;
    }

    onAmountChange(ev) {
        this.state.paymentAmount = parseFloat(ev.target.value) || 0;
    }

    onClose() {
        this.props.close();
    }

    async onPurchase() {
        if (this.state.isSaving) {
            return;
        }
        this.state.isSaving = true;
        const onDone = this.props.onDone;
        try {
            await this.orm.call(
                "res.partner",
                "execute_package_purchase",
                [this.props.patientId, this.props.product.id],
                {
                    create_invoice: this.state.createInvoice,
                    process_payment: this.state.processPayment,
                    payment_method: this.state.paymentMethod,
                    payment_amount: this.state.paymentAmount,
                    source_fso_id: this.props.fsoId || false,
                }
            );
            this.notification.add(
                _t("%s purchased successfully", this.props.product.name),
                { type: "success" }
            );
            this.props.close();
            if (onDone) {
                onDone();
            }
        } catch (e) {
            const msg = e?.data?.message || e?.message || _t("Failed to purchase package");
            this.notification.add(msg, { type: "danger" });
            this.state.isSaving = false;
        }
    }
}
