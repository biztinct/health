/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class OpsPaymentCollection extends Component {
    static template = "health_fieldservice.OpsPaymentCollection";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const context = this.props.action && this.props.action.context || {};
        this.bookingId = context.active_id || context.default_booking_id || false;

        this.state = useState({
            isLoading: true,
            isProcessing: false,
            booking: {},
            patient: {},
            amount: {},
            staffOptions: [],
            hasInvoice: false,
            invoiceId: false,

            paymentMethod: 'cash',
            amountReceived: 0,
            collectedById: false,
            bankName: '',
            transferRef: '',
            transferDate: new Date().toISOString().split('T')[0],
            notes: '',
            receiptType: 'retail',
        });

        onWillStart(async () => {
            if (this.bookingId) {
                await this.loadData();
            }
        });
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_payment_collection_data",
                [this.bookingId]
            );
            this.state.booking = data.booking || {};
            this.state.patient = data.patient || {};
            this.state.amount = data.amount || {};
            this.state.staffOptions = data.staff_options || [];
            this.state.hasInvoice = data.has_invoice;
            this.state.invoiceId = data.invoice_id;
            this.state.amountReceived = data.amount.due || 0;
        } catch (e) {
            console.error('Failed to load payment data:', e);
            this.notification.add(_t("Error loading payment data"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    formatCurrency(amount) {
        if (!amount) return '0 ₫';
        return Math.round(amount).toLocaleString('vi-VN') + ' ₫';
    }

    selectMethod(method) {
        this.state.paymentMethod = method;
    }

    isMethodSelected(method) {
        return this.state.paymentMethod === method;
    }

    onAmountChange(ev) {
        const raw = ev.target.value.replace(/[^0-9]/g, '');
        this.state.amountReceived = parseInt(raw) || 0;
    }

    get formattedAmount() {
        return this.state.amountReceived ? this.state.amountReceived.toLocaleString('vi-VN') : '0';
    }

    onCollectorChange(ev) {
        this.state.collectedById = parseInt(ev.target.value) || false;
    }

    onBankNameChange(ev) {
        this.state.bankName = ev.target.value;
    }

    onTransferRefChange(ev) {
        this.state.transferRef = ev.target.value;
    }

    onTransferDateChange(ev) {
        this.state.transferDate = ev.target.value;
    }

    onNotesChange(ev) {
        this.state.notes = ev.target.value;
    }

    onReceiptChange(ev) {
        this.state.receiptType = ev.target.value;
    }

    goBack() {
        if (this.bookingId) {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'health.fieldservice.order',
                res_id: this.bookingId,
                views: [[false, 'form']],
                target: 'fullscreen',
                context: { form_view_ref: 'health_fieldservice.view_health_fso_form_ops' },
            }, { clearBreadcrumbs: true });
        } else {
            this.action.doAction('health_fieldservice.action_ops_booking_list_native', { clearBreadcrumbs: true });
        }
    }

    async confirmPayment() {
        if (this.state.isProcessing) return;
        if (!this.state.amountReceived || this.state.amountReceived <= 0) {
            this.notification.add(_t("Please enter a valid payment amount"), { type: "warning" });
            return;
        }

        this.state.isProcessing = true;
        try {
            const result = await this.orm.call(
                "health.fieldservice.order",
                "action_process_owl_payment",
                [this.bookingId],
                {
                    payment_method: this.state.paymentMethod,
                    amount: this.state.amountReceived,
                    collected_by_id: this.state.collectedById || false,
                    bank_name: this.state.bankName,
                    transfer_ref: this.state.transferRef,
                    notes: this.state.notes,
                    receipt_type: this.state.receiptType,
                }
            );

            if (result.success) {
                this.notification.add(_t("Payment recorded successfully!"), { type: "success" });
                this.goBack();
            } else {
                this.notification.add(result.error || _t("Payment failed"), { type: "danger" });
            }
        } catch (e) {
            console.error('Payment processing error:', e);
            this.notification.add(_t("Could not process payment"), { type: "danger" });
        }
        this.state.isProcessing = false;
    }

    // Sidebar
}

registry.category("actions").add("ops_payment_collection", OpsPaymentCollection);

export default OpsPaymentCollection;
