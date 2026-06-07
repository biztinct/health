/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class FinDashboard extends Component {
    static template = "health_invoicing.FinDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isLoading: true,
            kpis: {},
            recentPayments: [],
            invoiceBreakdown: [],
            redInvoice: {},
            revenueTrend: [],
            period: "month",
            dateFrom: "",
            dateTo: "",
            range: {},
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "account.move",
                "get_finance_dashboard_data",
                [this.state.period, this.state.dateFrom || null, this.state.dateTo || null]
            );
            this.state.kpis = data.kpis || {};
            this.state.recentPayments = data.recent_payments || [];
            this.state.invoiceBreakdown = data.invoice_breakdown || [];
            this.state.redInvoice = data.red_invoice || {};
            this.state.revenueTrend = data.revenue_trend || [];
            this.state.range = data.range || {};
        } catch (e) {
            console.error("Failed to load Finance dashboard:", e);
            this.notification.add(_t("Error loading dashboard"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    // ---- Date filter ----
    async setPeriod(period) {
        this.state.period = period;
        if (period !== "custom") {
            await this.loadDashboardData();
        }
    }

    async applyCustomRange() {
        this.state.period = "custom";
        await this.loadDashboardData();
    }

    onDateFromChange(ev) { this.state.dateFrom = ev.target.value; }
    onDateToChange(ev) { this.state.dateTo = ev.target.value; }

    // Period-bound domain piece (by invoice_date) for drill-downs
    _periodDomain() {
        const dom = [];
        if (this.state.range.from) dom.push(["invoice_date", ">=", this.state.range.from]);
        if (this.state.range.to) dom.push(["invoice_date", "<=", this.state.range.to]);
        return dom;
    }

    _openMoves(name, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t(name),
            res_model: "account.move",
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
            context: { active_center: "finance_center" },
        });
    }

    // Max revenue in the trend (for bar heights)
    get trendMax() {
        return Math.max(1, ...this.state.revenueTrend.map((m) => m.revenue || 0));
    }
    trendHeight(val) {
        return Math.round(((val || 0) / this.trendMax) * 100);
    }

    get periods() {
        return [
            { key: "all", label: _t("All") },
            { key: "today", label: _t("Today") },
            { key: "week", label: _t("This Week") },
            { key: "month", label: _t("This Month") },
            { key: "custom", label: _t("Custom") },
        ];
    }

    initials(name) {
        if (!name) return "?";
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return "?";
        const a = parts[0][0] || "";
        const b = parts.length > 1 ? parts[parts.length - 1][0] : "";
        return (a + b).toUpperCase();
    }

    formatCurrency(val) {
        if (!val && val !== 0) return "0";
        if (val >= 1000000) return (val / 1000000).toFixed(1) + "M";
        if (val >= 1000) return (val / 1000).toFixed(0) + "K";
        return val.toLocaleString();
    }

    getPaymentStatusClass(status) {
        const map = {
            collected: "fin-status-collected",
            pending_delivery: "fin-status-pending",
            delivered: "fin-status-delivered",
            delivered_to_om: "fin-status-delivered",
            reconciled: "fin-status-reconciled",
            failed: "fin-status-failed",
        };
        return map[status] || "fin-status-default";
    }

    getPaymentStatusLabel(status) {
        const map = {
            collected: _t("Collected"),
            pending_delivery: _t("Pending Delivery"),
            delivered: _t("Delivered"),
            delivered_to_om: _t("Delivered"),
            reconciled: _t("Reconciled"),
            failed: _t("Failed"),
        };
        return map[status] || status;
    }

    getInvoiceStatusColor(status) {
        const map = {
            draft: "#78909C",
            posted: "#1565C0",
            paid: "#2E7D32",
            partial: "#F57F17",
            overdue: "#C62828",
            cancelled: "#9E9E9E",
        };
        return map[status] || "#9E9E9E";
    }

    openNewInvoice() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Invoice"),
            res_model: "account.move",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: { default_move_type: "out_invoice" },
        });
    }

    openInvoices() {
        this.action.doAction("health_invoicing.action_fin_invoice_list", { clearBreadcrumbs: true });
    }

    openPayments() {
        this.action.doAction("health_invoicing.action_fin_payment_list", { clearBreadcrumbs: true });
    }

    openARDashboard() {
        this.action.doAction("health_invoicing.action_fin_ar_dashboard", { clearBreadcrumbs: true });
    }

    openVATLog() {
        this.action.doAction("health_invoicing.action_fin_vat_log", { clearBreadcrumbs: true });
    }

    // ---- Financial KPI drill-downs ----
    openRevenue() {
        this._openMoves("Revenue — Posted Invoices",
            [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ...this._periodDomain()]);
    }
    openOutstanding() {
        this._openMoves("Outstanding Receivables",
            [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "in", ["not_paid", "partial"]]]);
    }
    openOverdue() {
        this.action.doAction("health_invoicing.action_fin_overdue", { clearBreadcrumbs: true });
    }

    openRedInvoiceIssued() {
        this.action.doAction("health_redinvoice.action_redinvoice_issued", { clearBreadcrumbs: true });
    }

    openRedInvoiceFailed() {
        this.action.doAction("health_redinvoice.action_redinvoice_failed", { clearBreadcrumbs: true });
    }

    openRedInvoicePending() {
        this.action.doAction("health_redinvoice.action_redinvoice_pending", { clearBreadcrumbs: true });
    }

    openPackages() {
        this.action.doAction("health_invoicing.action_fin_package_list", { clearBreadcrumbs: true });
    }

    openPayment(paymentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.payment.transaction",
            res_id: paymentId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onRefresh() {
        await this.loadDashboardData();
        this.notification.add(_t("Dashboard refreshed"), { type: "success" });
    }
}

registry.category("actions").add("fin_dashboard", FinDashboard);

export default FinDashboard;
