/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class OpsClientProfile extends Component {
    static template = "health_fieldservice.OpsClientProfile";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const sessionName = (window.odoo && window.odoo.session_info && window.odoo.session_info.name) || '';
        this.currentUserName = sessionName || 'Operations Manager';
        this.currentUserInitials = this.currentUserName.split(' ').filter(p => p).map(p => p[0]).join('').substring(0, 2).toUpperCase() || 'OM';

        const context = this.props.action && this.props.action.context || {};
        this.partnerId = context.active_id || context.default_partner_id || false;

        this.state = useState({
            isLoading: true,
            activeTab: 'overview',
            profile: {},
            stats: {},
            bookings: [],
            packages: [],
            payments: [],
            timeline: [],
            totalBookings: 0,
            totalPackages: 0,
            totalPayments: 0,
            needsStaffCount: 0,
        });

        onWillStart(async () => {
            if (this.partnerId) {
                await this.loadProfileData();
            }
            await this.loadNeedsStaffCount();
        });
    }

    async loadProfileData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "res.partner",
                "get_client_profile_data",
                [this.partnerId]
            );
            this.state.profile = data.profile || {};
            this.state.stats = data.stats || {};
            this.state.bookings = data.bookings || [];
            this.state.packages = data.packages || [];
            this.state.payments = data.payments || [];
            this.state.timeline = data.timeline || [];
            this.state.totalBookings = data.total_bookings || 0;
            this.state.totalPackages = data.total_packages || 0;
            this.state.totalPayments = data.total_payments || 0;
        } catch (e) {
            console.error('Failed to load client profile:', e);
            this.notification.add(_t("Error loading client profile"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    async loadNeedsStaffCount() {
        try {
            const count = await this.orm.searchCount("health.fieldservice.order", [
                ['has_staff_assigned', '=', false],
                ['state', 'in', ['draft', 'confirmed']],
            ]);
            this.state.needsStaffCount = count;
        } catch (e) { /* ignore */ }
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    formatCurrency(amount) {
        if (!amount) return '0';
        if (amount >= 1000000) {
            return (amount / 1000000).toFixed(1) + 'M';
        }
        return amount.toLocaleString('vi-VN');
    }

    formatCurrencyFull(amount) {
        if (!amount) return '0 ₫';
        return amount.toLocaleString('vi-VN') + ' ₫';
    }

    getStatusChipClass(state) {
        const map = {
            draft: 'chip-draft',
            confirmed: 'chip-confirmed',
            assigned: 'chip-assigned',
            in_progress: 'chip-active',
            completed: 'chip-completed',
            completed_pending_invoice: 'chip-completed',
            cancelled: 'chip-cancelled',
        };
        return 'ops-status-chip ' + (map[state] || 'chip-draft');
    }

    getPayIconClass(payment) {
        if (payment.is_paid) return 'cp-pay-icon paid';
        return 'cp-pay-icon pending';
    }

    getPayAmountClass(payment) {
        if (payment.is_paid) return 'cp-pay-amount paid';
        return 'cp-pay-amount pending';
    }

    // Actions
    openBooking(bookingId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: bookingId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    openCreateBooking() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Create Booking'),
            res_model: 'health.quick.booking.wizard',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_client_id: this.partnerId,
            },
        });
    }

    editClient() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: this.partnerId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    openPackage(packageId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.service.package',
            res_id: packageId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    openInvoice(invoiceId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'account.move',
            res_id: invoiceId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // Sidebar navigation
    navigateTo(page) {
        const actions = {
            dashboard: 'health_fieldservice.action_ops_command_center',
            bookings: 'health_fieldservice.action_ops_booking_queue',
            clients: 'health_fieldservice.action_ops_client_list',
            recurring: 'health_fieldservice.action_ops_recurring_booking',
            staff: 'health_fieldservice.action_ops_staff_roster',
            calendar: 'health_fieldservice.action_ops_calendar',
            workload: 'health_fieldservice.action_staff_workload_dashboard',
            analytics: 'health_fieldservice.action_staff_workload_dashboard',
        };
        if (actions[page]) {
            this.action.doAction(actions[page], { clearBreadcrumbs: true });
        }
    }

    navigateHome() {
        window.location.href = '/web';
    }
}

registry.category("actions").add("ops_client_profile", OpsClientProfile);

export default OpsClientProfile;
