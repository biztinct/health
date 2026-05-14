/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STAFF_COLORS = [
    '#1565C0', '#43A047', '#7c3aed', '#E53935', '#FB8C00',
    '#00897B', '#5C6BC0', '#F4511E', '#8E24AA', '#00ACC1',
    '#6D4C41', '#546E7A',
];

const SERVICE_TYPE_CSS = {
    home_visit: '#1565C0',
    clinic_visit: '#7c3aed',
    consultation: '#42A5F5',
    follow_up: '#43A047',
    emergency: '#E53935',
};

class OpsStaffRoster extends Component {
    static template = "health_fieldservice.OpsStaffRoster";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");


        const today = new Date();
        this.state = useState({
            isLoading: true,
            date: this.formatDateISO(today),
            dateLabel: this.formatDateLabel(today),
            searchQuery: '',
            roleFilter: '',
            statusFilter: '',
            summary: { total: 0, available: 0, busy: 0, off: 0 },
            staff: [],
            needsStaffCount: 0,
        });

        onWillStart(async () => {
            await this.loadRosterData();
            await this.loadNeedsStaffCount();
        });
    }

    formatDateISO(d) { return d.toISOString().split('T')[0]; }
    formatDateLabel(d) {
        return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }

    // ===== DATA =====

    async loadRosterData() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call(
                "hr.employee", "get_staff_roster_data", [this.state.date]
            );
            this.state.summary = data.summary || {};
            this.state.staff = data.staff || [];
        } catch (e) {
            console.error('Failed to load roster:', e);
            this.notification.add(_t("Error loading staff roster"), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    // ===== DATE NAV =====

    prevDay() {
        const d = new Date(this.state.date); d.setDate(d.getDate() - 1);
        this.state.date = this.formatDateISO(d);
        this.state.dateLabel = this.formatDateLabel(d);
        this.loadRosterData();
    }

    nextDay() {
        const d = new Date(this.state.date); d.setDate(d.getDate() + 1);
        this.state.date = this.formatDateISO(d);
        this.state.dateLabel = this.formatDateLabel(d);
        this.loadRosterData();
    }

    goToday() {
        const today = new Date();
        this.state.date = this.formatDateISO(today);
        this.state.dateLabel = this.formatDateLabel(today);
        this.loadRosterData();
    }

    // ===== FILTERS =====

    onSearchInput(ev) { this.state.searchQuery = ev.target.value; }
    onRoleChange(ev) { this.state.roleFilter = ev.target.value; }
    onStatusChange(ev) { this.state.statusFilter = ev.target.value; }

    get filteredStaff() {
        let staff = this.state.staff;
        if (this.state.searchQuery) {
            const q = this.state.searchQuery.toLowerCase();
            staff = staff.filter(s => s.name.toLowerCase().includes(q));
        }
        if (this.state.roleFilter) {
            staff = staff.filter(s => s.role && s.role.toLowerCase().includes(this.state.roleFilter.toLowerCase()));
        }
        if (this.state.statusFilter) {
            staff = staff.filter(s => s.status === this.state.statusFilter);
        }
        return staff;
    }

    // ===== HELPERS =====

    getStaffColor(idx) { return STAFF_COLORS[idx % STAFF_COLORS.length]; }

    getStatusLabel(status) {
        if (status === 'available') return _t('Available');
        if (status === 'busy') return _t('In Service');
        return _t('Off Duty');
    }

    getScheduleBlockStyle(block) {
        const startPx = Math.max(0, (block.start_hour - 7) / 12 * 100);
        const widthPx = Math.max(2, (block.end_hour - block.start_hour) / 12 * 100);
        const color = SERVICE_TYPE_CSS[block.service_type] || '#1565C0';
        return `left:${startPx}%; width:${widthPx}%; background:${color};`;
    }

    getStarIcons(rating) {
        const full = Math.floor(rating);
        const half = rating - full >= 0.5 ? 1 : 0;
        const empty = 5 - full - half;
        return { full, half, empty };
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

    openDashboard() {
        this.action.doAction('health_fieldservice.action_ops_command_center', { clearBreadcrumbs: true });
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
        await this.loadRosterData();
        this.notification.add(_t("Roster refreshed"), { type: "success" });
    }

}

registry.category("actions").add("ops_staff_roster", OpsStaffRoster);

export default OpsStaffRoster;
