/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STAFF_COLORS = [
    '#1565C0', '#43A047', '#7c3aed', '#E53935', '#FB8C00',
    '#00897B', '#5C6BC0', '#F4511E', '#8E24AA', '#00ACC1',
];

const SERVICE_LABELS = {
    home_visit: _t('Home Visit'), clinic_visit: _t('Clinic Visit'),
    consultation: _t('Consultation'), follow_up: _t('Follow-up'),
    emergency: _t('Emergency'), telemedicine: _t('Telehealth'),
    preventive: _t('Preventive'), rehabilitation: _t('Rehab'),
    vaccination: _t('Vaccination'), diagnostic: _t('Diagnostic'),
};

const STATE_LABELS = {
    draft: _t('New'), confirmed: _t('Confirmed'), assigned: _t('Assigned'),
    in_progress: _t('In Progress'), completed: _t('Completed'),
    completed_pending_invoice: _t('Pending Invoice'), cancelled: _t('Cancelled'), closed: _t('Closed'),
};

const PAGE_SIZE = 20;

class OpsBookingQueue extends Component {
    static template = "health_fieldservice.OpsBookingQueue";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const sessionName = (window.odoo && window.odoo.session_info && window.odoo.session_info.name) || '';
        this.currentUserName = sessionName || 'Operations Manager';
        this.currentUserInitials = this.currentUserName.split(' ').filter(p => p).map(p => p[0]).join('').substring(0, 2).toUpperCase() || 'OM';

        const today = new Date();
        this.state = useState({
            isLoading: true,
            activeTab: 'all',
            searchQuery: '',
            serviceTypeFilter: '',
            dateFilter: this.formatDateISO(today),
            priorityFilter: '',
            bookings: [],
            totalCount: 0,
            page: 0,
            selectedIds: new Set(),
            availableStaff: [],
            openDropdownId: false,
            needsStaffCount: 0,
        });

        onWillStart(async () => {
            await this.loadStaff();
            await this.loadBookings();
            await this.loadNeedsStaffCount();
        });
    }

    formatDateISO(d) { return d.toISOString().split('T')[0]; }

    // ===== DATA =====

    async loadStaff() {
        try {
            const staff = await this.orm.searchRead(
                "hr.employee",
                [['is_healthcare_staff', '=', true], ['employment_status', '=', 'active']],
                ['name', 'color', 'access_role_display'],
                { order: 'name asc' }
            );
            this.state.availableStaff = staff.map(s => ({
                ...s,
                initials: s.name ? s.name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase() : 'U',
                staffColor: STAFF_COLORS[(s.color || 0) % STAFF_COLORS.length],
            }));
        } catch (e) {
            console.error('Failed to load staff:', e);
        }
    }

    get domain() {
        const domain = [];

        if (this.state.dateFilter) {
            const d = new Date(this.state.dateFilter);
            const start = new Date(d); start.setHours(0, 0, 0, 0);
            const end = new Date(d); end.setHours(23, 59, 59, 999);
            domain.push(['scheduled_datetime', '>=', start.toISOString().replace('T', ' ').substring(0, 19)]);
            domain.push(['scheduled_datetime', '<=', end.toISOString().replace('T', ' ').substring(0, 19)]);
        }

        switch (this.state.activeTab) {
            case 'needs_staff':
                domain.push(['has_staff_assigned', '=', false]);
                domain.push(['state', 'in', ['draft', 'confirmed']]);
                break;
            case 'active':
                domain.push(['state', '=', 'in_progress']);
                break;
            case 'completed':
                domain.push(['state', 'in', ['completed', 'completed_pending_invoice']]);
                break;
            case 'issues':
                domain.push('|');
                domain.push(['state', '=', 'cancelled']);
                domain.push(['priority', '>=', '3']);
                break;
            default:
                domain.push(['state', '!=', 'cancelled']);
                break;
        }

        if (this.state.serviceTypeFilter) {
            domain.push(['service_type', '=', this.state.serviceTypeFilter]);
        }
        if (this.state.priorityFilter) {
            domain.push(['priority', '=', this.state.priorityFilter]);
        }
        if (this.state.searchQuery) {
            domain.push('|', '|');
            domain.push(['name', 'ilike', this.state.searchQuery]);
            domain.push(['patient_id.name', 'ilike', this.state.searchQuery]);
            domain.push(['patient_id.phone', 'ilike', this.state.searchQuery]);
        }

        return domain;
    }

    async loadBookings() {
        this.state.isLoading = true;
        try {
            const fields = [
                'name', 'state', 'priority', 'service_type', 'service_location',
                'scheduled_datetime', 'scheduled_duration', 'has_staff_assigned',
                'patient_id', 'lead_staff_id', 'facility_id', 'catchment_province_id',
                'total_price', 'appointment_type_id',
            ];
            const bookings = await this.orm.searchRead(
                "health.fieldservice.order",
                this.domain,
                fields,
                { limit: PAGE_SIZE, offset: this.state.page * PAGE_SIZE, order: 'scheduled_datetime asc' }
            );
            const count = await this.orm.searchCount("health.fieldservice.order", this.domain);
            this.state.bookings = bookings;
            this.state.totalCount = count;
        } catch (e) {
            console.error('Failed to load bookings:', e);
            this.notification.add(_t("Error loading bookings"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    // ===== TABS =====

    setTab(tab) {
        this.state.activeTab = tab;
        this.state.page = 0;
        this.state.selectedIds = new Set();
        this.loadBookings();
    }

    // ===== FILTERS =====

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    onSearchKeydown(ev) {
        if (ev.key === 'Enter') {
            this.state.page = 0;
            this.loadBookings();
        }
    }

    onServiceTypeChange(ev) {
        this.state.serviceTypeFilter = ev.target.value;
        this.state.page = 0;
        this.loadBookings();
    }

    onDateChange(ev) {
        this.state.dateFilter = ev.target.value;
        this.state.page = 0;
        this.loadBookings();
    }

    onPriorityChange(ev) {
        this.state.priorityFilter = ev.target.value;
        this.state.page = 0;
        this.loadBookings();
    }

    // ===== PAGINATION =====

    get totalPages() { return Math.ceil(this.state.totalCount / PAGE_SIZE); }
    get showingFrom() { return this.state.totalCount ? this.state.page * PAGE_SIZE + 1 : 0; }
    get showingTo() { return Math.min((this.state.page + 1) * PAGE_SIZE, this.state.totalCount); }

    prevPage() {
        if (this.state.page > 0) {
            this.state.page--;
            this.loadBookings();
        }
    }

    nextPage() {
        if (this.state.page < this.totalPages - 1) {
            this.state.page++;
            this.loadBookings();
        }
    }

    // ===== HELPERS =====

    getStateChipClass(state) { return 'chip-' + (state || 'draft'); }
    getStateLabel(state) { return STATE_LABELS[state] || state; }
    getServiceLabel(st) { return SERVICE_LABELS[st] || st || ''; }
    isUrgent(b) { return b.priority >= '3'; }

    formatTime(dt) {
        if (!dt) return '';
        const d = new Date(dt);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    }

    formatDuration(mins) {
        if (!mins) return '';
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        if (h && m) return `${h}h ${m}m`;
        if (h) return `${h}h`;
        return `${m}m`;
    }

    formatCurrency(amount) {
        if (!amount) return '';
        if (amount >= 1000000) return '₫' + (amount / 1000000).toFixed(1) + 'M';
        if (amount >= 1000) return '₫' + Math.round(amount / 1000) + 'K';
        return '₫' + amount;
    }

    getPatientName(b) { return b.patient_id ? b.patient_id[1] : ''; }
    getStaffName(b) { return b.lead_staff_id ? b.lead_staff_id[1] : ''; }
    getFacilityName(b) { return b.facility_id ? b.facility_id[1] : ''; }

    // ===== INLINE ASSIGNMENT =====

    toggleDropdown(bookingId) {
        this.state.openDropdownId = this.state.openDropdownId === bookingId ? false : bookingId;
    }

    async selectStaff(bookingId, staffId) {
        this.state.openDropdownId = false;
        try {
            await this.orm.call("health.fieldservice.order", "action_quick_assign_staff", [[bookingId], staffId]);
            this.notification.add(_t("Staff assigned"), { type: "success" });
            await this.loadBookings();
        } catch (e) {
            this.notification.add(_t("Assignment failed"), { type: "danger" });
        }
    }

    // ===== NEEDS STAFF COUNT =====

    async loadNeedsStaffCount() {
        try {
            const count = await this.orm.searchCount("health.fieldservice.order", [
                ['has_staff_assigned', '=', false],
                ['state', 'in', ['draft', 'confirmed']],
            ]);
            this.state.needsStaffCount = count;
        } catch (e) {
            // ignore
        }
    }

    // ===== NAVIGATION =====

    openBooking(bookingId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.fieldservice.order',
            res_id: bookingId,
            views: [[false, 'form']],
            target: 'fullscreen',
            context: { form_view_ref: 'health_fieldservice.view_health_fso_form_ops' },
        }, { clearBreadcrumbs: true });
    }

    openDashboard() {
        this.action.doAction('health_fieldservice.action_ops_command_center', { clearBreadcrumbs: true });
    }

    openCreateBooking() {
        this.action.doAction('health_fieldservice.action_ops_booking_wizard', { clearBreadcrumbs: true });
    }

    // ===== SIDEBAR NAVIGATION =====

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

registry.category("actions").add("ops_booking_queue", OpsBookingQueue);

export default OpsBookingQueue;
