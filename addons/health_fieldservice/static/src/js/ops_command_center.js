/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";

const STAFF_COLORS = [
    '#1565C0', '#43A047', '#7c3aed', '#E53935', '#FB8C00',
    '#00897B', '#5C6BC0', '#F4511E', '#8E24AA', '#00ACC1',
    '#6D4C41', '#546E7A',
];

const SERVICE_TYPE_LABELS = {
    home_visit: _t('Home Visit'),
    clinic_visit: _t('Clinic Visit'),
    consultation: _t('Consultation'),
    follow_up: _t('Follow-up'),
    emergency: _t('Emergency'),
    telemedicine: _t('Telehealth'),
    preventive: _t('Preventive'),
    rehabilitation: _t('Rehab'),
    vaccination: _t('Vaccination'),
    diagnostic: _t('Diagnostic'),
};

const SERVICE_TYPE_CSS = {
    home_visit: 'block-home-visit',
    clinic_visit: 'block-clinic-visit',
    consultation: 'block-consultation',
    follow_up: 'block-follow-up',
    emergency: 'block-emergency',
};

const STATE_LABELS = {
    draft: _t('New'),
    confirmed: _t('Confirmed'),
    assigned: _t('Assigned'),
    in_progress: _t('In Progress'),
    completed: _t('Completed'),
    completed_pending_invoice: _t('Pending Invoice'),
    cancelled: _t('Cancelled'),
    closed: _t('Closed'),
};

class OpsCommandCenter extends Component {
    static template = "health_fieldservice.OpsCommandCenter";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        this.state = useState({
            isLoading: true,
            date: this.formatDateISO(today),
            period: 'today',
            customFrom: '',
            customTo: '',
            facilityId: false,
            facilities: [],
            kpis: {},
            bookings: [],
            staff: [],
            timelineBlocks: [],
            activeTab: 'needs_staff',
            openDropdownId: false,
            openMenuId: false,
            dropdownStyle: "",
        });

        this.timeSlots = this.generateTimeSlots(7, 18);

        onWillStart(async () => {
            await this.loadFacilities();
            await this.loadDashboardData();
        });
    }

    // ===== DATA LOADING =====

    async loadFacilities() {
        try {
            const facilities = await this.orm.searchRead(
                "health.facility",
                [['active', '=', true]],
                ['name'],
                { order: 'name asc' }
            );
            this.state.facilities = facilities;
        } catch (e) {
            console.error('Failed to load facilities:', e);
        }
    }

    async loadDashboardData() {
        this.state.isLoading = true;
        try {
            const r = this._range();
            const data = await this.orm.call(
                "health.fieldservice.order",
                "get_ops_dashboard_data",
                [r.from, r.to, this.state.facilityId || false]
            );
            this.state.kpis = data.kpis || {};
            this.state.bookings = data.bookings || [];
            this.state.staff = data.staff || [];
            this.state.timelineBlocks = data.timeline_blocks || [];
        } catch (e) {
            console.error('Failed to load dashboard data:', e);
            this.notification.add(_t("Error loading dashboard data"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    // ===== DATE NAVIGATION =====

    formatDateISO(date) {
        // Build from local components (avoid UTC day-shift from toISOString)
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    formatDateLabel(date) {
        return date.toLocaleDateString(localization.code.replace("_", "-"), {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
    }

    _anchorDate() {
        return new Date(this.state.date + 'T00:00:00');
    }

    _fmtShort(iso) {
        return new Date(iso + 'T00:00:00').toLocaleDateString(localization.code.replace("_", "-"), {
            month: 'short', day: 'numeric', year: 'numeric',
        });
    }

    // Resolve the current period into {from, to} ISO date strings (or false)
    _range() {
        const p = this.state.period;
        if (p === 'all') return { from: false, to: false };
        if (p === 'custom') {
            return { from: this.state.customFrom || false, to: this.state.customTo || false };
        }
        const d = this._anchorDate();
        if (p === 'week') {
            const dow = (d.getDay() + 6) % 7; // Monday = 0
            const start = new Date(d); start.setDate(d.getDate() - dow);
            const end = new Date(start); end.setDate(start.getDate() + 6);
            return { from: this.formatDateISO(start), to: this.formatDateISO(end) };
        }
        if (p === 'month') {
            const start = new Date(d.getFullYear(), d.getMonth(), 1);
            const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
            return { from: this.formatDateISO(start), to: this.formatDateISO(end) };
        }
        // 'today' (single day)
        const s = this.formatDateISO(d);
        return { from: s, to: s };
    }

    get headerLabel() {
        const p = this.state.period;
        if (p === 'all') return _t('All dates');
        if (p === 'custom') {
            if (this.state.customFrom && this.state.customTo) {
                return `${this._fmtShort(this.state.customFrom)} – ${this._fmtShort(this.state.customTo)}`;
            }
            return _t('Select a date range');
        }
        const d = this._anchorDate();
        if (p === 'week') {
            const r = this._range();
            return `${this._fmtShort(r.from)} – ${this._fmtShort(r.to)}`;
        }
        if (p === 'month') {
            return d.toLocaleDateString(localization.code.replace("_", "-"), { month: 'long', year: 'numeric' });
        }
        return this.formatDateLabel(d);
    }

    get showArrows() {
        return ['today', 'week', 'month'].includes(this.state.period);
    }

    setPeriod(period) {
        this.state.period = period;
        // "Today" jumps the anchor back to today (replaces the old Today link)
        if (period === 'today') {
            this.state.date = this.formatDateISO(new Date());
        }
        if (period === 'custom' && !(this.state.customFrom && this.state.customTo)) {
            return; // wait until both custom dates are picked
        }
        this.loadDashboardData();
    }

    onCustomDate(which, value) {
        if (which === 'from') this.state.customFrom = value;
        else this.state.customTo = value;
        this.state.period = 'custom';
        if (this.state.customFrom && this.state.customTo) {
            this.loadDashboardData();
        }
    }

    _shift(dir) {
        const d = this._anchorDate();
        const p = this.state.period;
        if (p === 'today') d.setDate(d.getDate() + dir);
        else if (p === 'week') d.setDate(d.getDate() + dir * 7);
        else if (p === 'month') d.setMonth(d.getMonth() + dir);
        else return;
        this.state.date = this.formatDateISO(d);
        this.loadDashboardData();
    }

    prevDay() { this._shift(-1); }
    nextDay() { this._shift(1); }

    goToday() {
        this.state.period = 'today';
        this.state.date = this.formatDateISO(new Date());
        this.loadDashboardData();
    }

    setFacility(facilityId) {
        this.state.facilityId = facilityId || false;
        this.loadDashboardData();
    }

    // ===== TAB SWITCHING =====

    setTab(tab) {
        this.state.activeTab = tab;
    }

    get filteredBookings() {
        const bookings = this.state.bookings;
        switch (this.state.activeTab) {
            case 'needs_staff':
                return bookings.filter(b => !b.has_staff_assigned && ['draft', 'confirmed'].includes(b.state));
            case 'all':
                return bookings;
            case 'issues':
                return bookings.filter(b => b.priority >= '3' || b.state === 'cancelled');
            default:
                return bookings;
        }
    }

    get needsStaffCount() {
        return this.state.bookings.filter(b => !b.has_staff_assigned && ['draft', 'confirmed'].includes(b.state)).length;
    }

    // ===== BOOKING HELPERS =====

    getStateChipClass(state) {
        return 'chip-' + (state || 'draft');
    }

    getStateLabel(state) {
        return STATE_LABELS[state] || state;
    }

    getServiceLabel(serviceType) {
        return SERVICE_TYPE_LABELS[serviceType] || serviceType || '';
    }

    getServiceIcon(serviceType) {
        const icons = {
            home_visit: 'fa-house-medical',
            clinic_visit: 'fa-hospital',
            consultation: 'fa-comments-medical',
            follow_up: 'fa-rotate-right',
            emergency: 'fa-truck-medical',
            telemedicine: 'fa-video',
        };
        return icons[serviceType] || 'fa-stethoscope';
    }

    getLocationIcon(location) {
        return location === 'home' ? 'fa-house-medical' : location === 'facility' ? 'fa-hospital' : 'fa-globe';
    }

    isUrgent(booking) {
        return booking.priority >= '3';
    }

    getBookingCardClass(booking) {
        let cls = 'ops-booking-card';
        if (this.isUrgent(booking)) cls += ' urgent';
        if (!booking.has_staff_assigned && ['draft', 'confirmed'].includes(booking.state)) cls += ' needs-staff';
        if (booking.state === 'assigned') cls += ' assigned';
        if (booking.state === 'in_progress') cls += ' in-progress';
        return cls;
    }

    formatDuration(minutes) {
        if (!minutes) return '';
        const hrs = Math.floor(minutes / 60);
        const mins = minutes % 60;
        if (hrs && mins) return _t("%s hr %s min", hrs, mins);
        if (hrs) return hrs > 1 ? _t("%s hours", hrs) : _t("%s hour", hrs);
        return _t("%s min", mins);
    }

    formatCurrency(amount) {
        if (!amount) return '₫0';
        if (amount >= 1000000) return '₫' + (amount / 1000000).toFixed(1) + 'M';
        if (amount >= 1000) return '₫' + (amount / 1000).toFixed(0) + 'K';
        return '₫' + amount.toFixed(0);
    }

    // ===== STAFF HELPERS =====

    getStaffColor(colorIndex) {
        return STAFF_COLORS[colorIndex % STAFF_COLORS.length];
    }

    get availableStaff() {
        return this.state.staff.filter(s => s.status === 'available');
    }

    // ===== INLINE ASSIGNMENT =====

    toggleStaffDropdown(bookingId, ev) {
        this.state.openMenuId = false;
        if (this.state.openDropdownId === bookingId) {
            this.state.openDropdownId = false;
            return;
        }
        // Render the menu as position:fixed anchored to the trigger so it is not
        // clipped by the scrollable panel (.ops-panel-body has overflow:auto).
        const rect = ev.currentTarget.getBoundingClientRect();
        const width = Math.max(rect.width, 220);
        const menuMax = 260;
        const spaceBelow = window.innerHeight - rect.bottom;
        let style = `position:fixed; left:${Math.round(rect.left)}px; right:auto;`
            + ` width:${Math.round(width)}px; max-height:${menuMax}px; overflow:auto; z-index:1080;`;
        if (spaceBelow < menuMax && rect.top > spaceBelow) {
            style += ` bottom:${Math.round(window.innerHeight - rect.top + 4)}px; top:auto;`;
        } else {
            style += ` top:${Math.round(rect.bottom + 4)}px;`;
        }
        this.state.dropdownStyle = style;
        this.state.openDropdownId = bookingId;
    }

    async selectStaff(bookingId, staffId) {
        this.state.openDropdownId = false;
        try {
            await this.orm.call(
                "health.fieldservice.order",
                "action_quick_assign_staff",
                [[bookingId], staffId]
            );
            this.notification.add(_t("Staff assigned successfully"), { type: "success" });
            await this.loadDashboardData();
        } catch (e) {
            console.error('Assignment failed:', e);
            this.notification.add(_t("Assignment failed"), { type: "danger" });
        }
    }

    // ===== ACTIONS MENU =====

    toggleActionsMenu(bookingId, ev) {
        ev.stopPropagation();
        this.state.openDropdownId = false;
        this.state.openMenuId = this.state.openMenuId === bookingId ? false : bookingId;
    }

    // ===== NAVIGATION =====

    openBooking(bookingId) {
        // Open the rich booking detail (keeps the CMS left panel, unlike the
        // native form which renders full-width without it).
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_booking_detail',
            name: _t('Booking'),
            target: 'current',
            context: { active_id: bookingId },
        });
    }

    openAssignStaff(bookingId) {
        this.state.openMenuId = false;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_staff_assignment',
            name: _t('Assign Staff'),
            context: { active_id: bookingId },
        }, { clearBreadcrumbs: true });
    }

    openCollectPayment(bookingId) {
        this.state.openMenuId = false;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_payment_collection',
            name: _t('Collect Payment'),
            context: { active_id: bookingId },
        }, { clearBreadcrumbs: true });
    }

    openStartService(bookingId) {
        this.state.openMenuId = false;
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'ops_service_in_progress',
            name: _t('Active Service'),
            context: { active_id: bookingId },
        }, { clearBreadcrumbs: true });
    }

    async cancelBooking(bookingId) {
        this.state.openMenuId = false;
        try {
            await this.orm.call("health.fieldservice.order", "action_cancel_booking", [bookingId]);
            this.notification.add(_t("Booking cancelled"), { type: "warning" });
            await this.loadDashboardData();
        } catch (e) {
            this.notification.add(_t("Could not cancel booking"), { type: "danger" });
        }
    }

    openBookingQueue() {
        this.action.doAction('health_fieldservice.action_ops_booking_list_native', { clearBreadcrumbs: true });
    }

    openStaffRoster() {
        this.action.doAction('health_fieldservice.action_ops_staff_roster', { clearBreadcrumbs: true });
    }

    openCreateBooking() {
        this.action.doAction('health_fieldservice.action_ops_booking_wizard', { clearBreadcrumbs: true });
    }

    openStaffProfile(staffId) {
        // Open as an overlay so the Operations Center (and its left panel)
        // stays in place — the native employee form has no CMS sidebar.
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: staffId,
            views: [[false, 'form']],
            target: 'new',
        });
    }

    // ===== TIMELINE =====

    generateTimeSlots(startHour, endHour) {
        const slots = [];
        for (let h = startHour; h <= endHour; h++) {
            slots.push({
                hour: h,
                label: h === 0 ? '12 AM' : h < 12 ? `${h} AM` : h === 12 ? '12 PM' : `${h - 12} PM`,
            });
        }
        return slots;
    }

    get timelineStaff() {
        return this.state.staff.filter(s => s.status !== 'off').slice(0, 8);
    }

    getBlocksForStaff(staffId) {
        return this.state.timelineBlocks.filter(b => b.staff_id === staffId);
    }

    getBlockStyle(block) {
        const timeStart = 7;
        const timeRange = this.timeSlots.length;
        const startCol = Math.max(0, block.start_hour - timeStart);
        const endCol = Math.max(startCol + 0.5, block.end_hour - timeStart);
        const left = (startCol / timeRange) * 100;
        const width = Math.max(((endCol - startCol) / timeRange) * 100, 2);
        return `left: ${left}%; width: ${width}%;`;
    }

    getBlockClass(block) {
        let cls = 'ops-timeline-block';
        cls += ' ' + (SERVICE_TYPE_CSS[block.service_type] || 'block-home-visit');
        if (block.fso_state === 'in_progress') cls += ' timeline-block-active';
        return cls;
    }

    getBlockLabel(block) {
        const st = SERVICE_TYPE_LABELS[block.service_type] || '';
        const abbr = st ? st.toString().substring(0, 2).toUpperCase() : 'HV';
        return abbr;
    }

    isCurrentHour(hour) {
        const now = new Date();
        const todayISO = this.formatDateISO(now);
        return this.state.date === todayISO && now.getHours() === hour;
    }

    async onRefresh() {
        await this.loadDashboardData();
        this.notification.add(_t("Dashboard refreshed"), { type: "success" });
    }

}

registry.category("actions").add("ops_command_center", OpsCommandCenter);

export default OpsCommandCenter;
