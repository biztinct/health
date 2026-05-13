/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const SERVICE_TYPE_COLORS = {
    home_visit: '#1565C0',
    clinic_visit: '#7c3aed',
    consultation: '#42A5F5',
    follow_up: '#43A047',
    emergency: '#E53935',
    preventive: '#00897B',
    rehabilitation: '#FB8C00',
    telemedicine: '#5C6BC0',
    vaccination: '#00ACC1',
    diagnostic: '#8E24AA',
};

const STAFF_COLORS = [
    '#1565C0', '#43A047', '#7c3aed', '#E53935', '#FB8C00',
    '#00897B', '#5C6BC0', '#F4511E', '#8E24AA', '#00ACC1',
    '#6D4C41', '#546E7A',
];

const PRIORITY_CLASSES = { '0': 'low', '1': 'normal', '2': 'high', '3': 'urgent', '4': 'emergency' };

class RosterPlanning extends Component {
    static template = "health_roster.RosterPlanning";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const sessionName = (window.odoo && window.odoo.session_info && window.odoo.session_info.name) || '';
        this.currentUserName = sessionName || 'Operations Manager';
        this.currentUserInitials = this.currentUserName.split(' ').filter(p => p).map(p => p[0]).join('').substring(0, 2).toUpperCase() || 'OM';

        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));

        this.state = useState({
            isLoading: true,
            weekStart: this.formatDateISO(monday),
            searchQuery: '',
            facilityFilter: '',
            catchmentFilter: '',
            statusFilter: '',
            days: [],
            staff: [],
            unassigned: {},
            summary: {},
            filters: { facilities: [], catchments: [] },
            dragData: null,
            dropTarget: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    formatDateISO(d) { return d.toISOString().split('T')[0]; }

    get weekLabel() {
        const start = new Date(this.state.weekStart);
        const end = new Date(start);
        end.setDate(start.getDate() + 6);
        const opts = { month: 'short', day: 'numeric' };
        return `${start.toLocaleDateString('en-US', opts)} — ${end.toLocaleDateString('en-US', { ...opts, year: 'numeric' })}`;
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const filters = {};
            if (this.state.facilityFilter) filters.facility_id = this.state.facilityFilter;
            if (this.state.catchmentFilter) filters.catchment_id = this.state.catchmentFilter;
            if (this.state.searchQuery) filters.search = this.state.searchQuery;
            if (this.state.statusFilter) filters.status = this.state.statusFilter;

            const data = await this.orm.call(
                "health.roster.grid", "get_roster_grid_data",
                [this.state.weekStart, filters]
            );
            this.state.days = data.days || [];
            this.state.staff = data.staff || [];
            this.state.unassigned = data.unassigned || {};
            this.state.summary = data.summary || {};
            this.state.filters = data.filters || { facilities: [], catchments: [] };
        } catch (e) {
            console.error('Failed to load roster grid:', e);
            this.notification.add(_t("Error loading roster data"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    prevWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() - 7);
        this.state.weekStart = this.formatDateISO(d);
        this.loadData();
    }

    nextWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + 7);
        this.state.weekStart = this.formatDateISO(d);
        this.loadData();
    }

    goToday() {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));
        this.state.weekStart = this.formatDateISO(monday);
        this.loadData();
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadData(), 400);
    }

    onFacilityChange(ev) { this.state.facilityFilter = ev.target.value; this.loadData(); }
    onCatchmentChange(ev) { this.state.catchmentFilter = ev.target.value; this.loadData(); }
    onStatusChange(ev) { this.state.statusFilter = ev.target.value; this.loadData(); }

    getStaffColor(idx) { return STAFF_COLORS[idx % STAFF_COLORS.length]; }
    getServiceColor(serviceType) { return SERVICE_TYPE_COLORS[serviceType] || '#546E7A'; }
    getPriorityClass(priority) { return PRIORITY_CLASSES[priority] || 'normal'; }

    getUtilClass(pct) {
        if (pct > 90) return 'overloaded';
        if (pct > 70) return 'high';
        if (pct > 40) return 'medium';
        return 'low';
    }

    getCardStyle(entry) {
        return `border-left-color: ${this.getServiceColor(entry.service_type)};`;
    }

    getUnassignedCount() {
        let count = 0;
        for (const d in this.state.unassigned) {
            count += (this.state.unassigned[d] || []).length;
        }
        return count;
    }

    getDayUnassigned(dateStr) { return this.state.unassigned[dateStr] || []; }
    getDayAssignments(staff, dateStr) { return (staff.assignments && staff.assignments[dateStr]) || []; }
    isOnLeave(staff, dateStr) { return staff.leaves && staff.leaves[dateStr]; }
    getLeaveType(staff, dateStr) { return (staff.leaves && staff.leaves[dateStr] && staff.leaves[dateStr].type) || 'Leave'; }

    // ===== DRAG AND DROP =====

    onDragStart(ev, fsoId, bookingRef) {
        this.state.dragData = { fsoId, bookingRef };
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', JSON.stringify({ fsoId, bookingRef }));
        ev.target.classList.add('rp-dragging');
    }

    onDragEnd(ev) {
        this.state.dragData = null;
        this.state.dropTarget = null;
        ev.target.classList.remove('rp-dragging');
        document.querySelectorAll('.rp-drop-hover').forEach(el => el.classList.remove('rp-drop-hover'));
    }

    onDragOver(ev, staffId) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = 'move';
        ev.currentTarget.classList.add('rp-drop-hover');
    }

    onDragLeave(ev) {
        ev.currentTarget.classList.remove('rp-drop-hover');
    }

    async onDrop(ev, staffId) {
        ev.preventDefault();
        ev.currentTarget.classList.remove('rp-drop-hover');

        let dragData = this.state.dragData;
        if (!dragData) {
            try { dragData = JSON.parse(ev.dataTransfer.getData('text/plain')); } catch (e) { return; }
        }
        if (!dragData || !dragData.fsoId || !staffId) return;

        this.state.dragData = null;
        this.state.dropTarget = null;

        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.staff.assignment.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_fso_id: dragData.fsoId,
                default_assigned_staff_ids: [[6, 0, [staffId]]],
                default_lead_staff_id: staffId,
            },
        });
    }

    openAssignmentWizard(fsoId) {
        if (!fsoId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.staff.assignment.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: { default_fso_id: fsoId },
        });
    }

    openStaffProfile(staffId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: staffId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async onRefresh() {
        await this.loadData();
        this.notification.add(_t("Roster refreshed"), { type: "success" });
    }

    navigateTo(page) {
        const actions = {
            dashboard: 'health_fieldservice.action_ops_command_center',
            bookings: 'health_fieldservice.action_ops_booking_queue',
            recurring: 'health_fieldservice.action_ops_recurring_booking',
            staff: 'health_fieldservice.action_ops_staff_roster',
            roster: 'health_roster.action_roster_planning',
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

registry.category("actions").add("roster_planning", RosterPlanning);

export default RosterPlanning;
