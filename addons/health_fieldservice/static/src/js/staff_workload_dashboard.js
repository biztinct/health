/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, useExternalListener } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Staff Workload Dashboard Client Action
 * Main component for the staff workload dashboard
 */
class StaffWorkloadDashboard extends Component {
    static template = "health_fieldservice.StaffWorkloadDashboardTemplate";

    t(text) {
        return _t(text);
    }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        
        this.state = useState({
            staffMembers: [],
            assignments: [],
            isLoading: true,
            // --- filters (govern everything below) ---
            statuses: { assigned: true, confirmed: true, in_progress: true },
            dateRange: 'all',     // all | today | week | month | custom
            customFrom: '',       // YYYY-MM-DD (when dateRange === 'custom')
            customTo: '',
            loadFilter: null,     // null | available | busy | overloaded (set by clicking a KPI)
            selectedStaffIds: [], // multi-select staff picker (default: all)
            staffPickerOpen: false,
            search: '',           // search inside the staff picker
            sortByLoad: false,    // busiest first
            hideEmpty: false,     // hide staff with no (filtered) assignments
        });
        this.staffPickerRef = useRef("staffPicker");
        useExternalListener(window, "click", (ev) => {
            if (this.state.staffPickerOpen && this.staffPickerRef.el && !this.staffPickerRef.el.contains(ev.target)) {
                this.state.staffPickerOpen = false;
            }
        });
        
        // Load data when component mounts
        this.loadDashboardData().catch(error => {
            console.error('Failed to load dashboard data:', error);
            this.state.isLoading = false;
        });
    }

    async loadDashboardData() {
        try {
            console.log('Loading dashboard data...');
            
            // Load healthcare staff with basic fields first
            const staffMembers = await this.orm.searchRead(
                "hr.employee",
                [['is_healthcare_staff', '=', true]],
                ['name', 'access_role_display', 'employment_status']
            );
            
            // Debug: Log staff data to check names are loading
            console.log('Staff member names:', staffMembers.map(s => s.name));
            
            console.log('Loaded staff members:', staffMembers);

            // Load current assignments
            const assignments = await this.orm.searchRead(
                "health.staff.assignment",
                [['state', 'in', ['assigned', 'confirmed', 'in_progress']]],
                ['name', 'fso_id', 'staff_id', 'assignment_role', 'state', 'planned_start_time']
            );
            
            console.log('Loaded assignments:', assignments);

            this.state.staffMembers = staffMembers || [];
            this.state.assignments = assignments || [];
            // Default: all staff selected. Keep any prior selection that still exists.
            const ids = this.state.staffMembers.map(s => s.id);
            const kept = this.state.selectedStaffIds.filter(id => ids.includes(id));
            this.state.selectedStaffIds = kept.length ? kept : ids;
            this.state.isLoading = false;
            
            console.log('Dashboard data loaded successfully');

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.notification.add(_t("Error loading dashboard data: ") + (error.message || _t('Unknown error')), { type: "danger" });
            this.state.isLoading = false;
        }
    }

    // ---- Filters ----
    _dateBounds() {
        const r = this.state.dateRange;
        if (r === "all") return null;
        if (r === "custom") {
            const f = this.state.customFrom, t = this.state.customTo;
            if (!f && !t) return null;
            const start = f ? new Date(f + "T00:00:00").getTime() : -Infinity;
            let end = Infinity;
            if (t) { const d = new Date(t + "T00:00:00"); d.setDate(d.getDate() + 1); end = d.getTime(); }
            return { start, end };
        }
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()); // local midnight
        let end;
        if (r === "today") {
            end = new Date(start); end.setDate(end.getDate() + 1);
        } else if (r === "week") {
            const dow = (start.getDay() + 6) % 7; // Mon=0
            start.setDate(start.getDate() - dow);
            end = new Date(start); end.setDate(end.getDate() + 7);
        } else { // month
            start.setDate(1);
            end = new Date(start.getFullYear(), start.getMonth() + 1, 1);
        }
        return { start: start.getTime(), end: end.getTime() };
    }
    _inDateRange(a) {
        const b = this._dateBounds();
        if (!b) return true;
        if (!a.planned_start_time) return false;
        const t = new Date(a.planned_start_time.replace(" ", "T") + "Z").getTime();
        return t >= b.start && t < b.end;
    }
    get filteredAssignments() {
        return this.state.assignments.filter(
            a => this.state.statuses[a.state] && this._inDateRange(a));
    }
    getStaffAssignments(staffId) {
        return this.filteredAssignments.filter(a => a.staff_id && a.staff_id[0] === staffId);
    }
    // count by state within the current date range (for the pill badges)
    statusCount(state) {
        return this.state.assignments.filter(a => a.state === state && this._inDateRange(a)).length;
    }
    // staff list shown in the grid: selected staff, KPI load-filter, hide-empty, sort
    get visibleStaff() {
        const sel = new Set(this.state.selectedStaffIds);
        let list = this.state.staffMembers.filter(s => {
            if (!sel.has(s.id)) return false;
            if (this.state.loadFilter && this.loadLevel(this.staffLoad(s.id)) !== this.state.loadFilter) return false;
            if (this.state.hideEmpty && this.staffLoad(s.id) === 0) return false;
            return true;
        });
        if (this.state.sortByLoad) {
            list = [...list].sort((a, b) => this.staffLoad(b.id) - this.staffLoad(a.id));
        }
        return list;
    }

    toggleStatus(s) { this.state.statuses[s] = !this.state.statuses[s]; }
    isStatusOn(s) { return !!this.state.statuses[s]; }
    setDateRange(r) { this.state.dateRange = r; }
    toggleSort() { this.state.sortByLoad = !this.state.sortByLoad; }
    toggleHideEmpty() { this.state.hideEmpty = !this.state.hideEmpty; }

    // KPI cards act as a load filter (click to focus that group, click again to clear)
    setLoadFilter(level) {
        this.state.loadFilter = (this.state.loadFilter === level) ? null : level;
    }
    isLoadFilter(level) { return this.state.loadFilter === level; }

    // Multi-select staff picker
    toggleStaffPicker() { this.state.staffPickerOpen = !this.state.staffPickerOpen; }
    isStaffSelected(id) { return this.state.selectedStaffIds.includes(id); }
    toggleStaff(id) {
        const i = this.state.selectedStaffIds.indexOf(id);
        if (i >= 0) this.state.selectedStaffIds.splice(i, 1);
        else this.state.selectedStaffIds.push(id);
    }
    selectAllStaff() { this.state.selectedStaffIds = this.state.staffMembers.map(s => s.id); }
    clearStaff() { this.state.selectedStaffIds = []; }
    get allStaffSelected() {
        return this.state.staffMembers.length > 0
            && this.state.selectedStaffIds.length === this.state.staffMembers.length;
    }
    get staffPickerLabel() {
        if (this.allStaffSelected) return "All staff";
        return `${this.state.selectedStaffIds.length} of ${this.state.staffMembers.length} staff`;
    }
    // staff list inside the picker dropdown (filtered by the search box)
    get pickerStaff() {
        const q = (this.state.search || "").trim().toLowerCase();
        return this.state.staffMembers.filter(s => !q || (s.name || "").toLowerCase().includes(q));
    }

    clearFilters() {
        this.state.statuses = { assigned: true, confirmed: true, in_progress: true };
        this.state.dateRange = "all";
        this.state.customFrom = "";
        this.state.customTo = "";
        this.state.loadFilter = null;
        this.state.search = "";
        this.state.sortByLoad = false;
        this.state.hideEmpty = false;
        this.selectAllStaff();
    }

    // --- Workload model (simple, capacity-based; thresholds are easy to tweak) ---
    // available: 0–2 active assignments · busy: 3–4 · overloaded: 5+
    get capacity() { return 5; }
    staffLoad(staffId) { return this.getStaffAssignments(staffId).length; }
    loadLevel(n) { return n <= 2 ? "available" : (n <= 4 ? "busy" : "overloaded"); }
    loadPercent(n) { return Math.min(100, Math.round((n / this.capacity) * 100)); }

    get totalStaff() { return this.state.staffMembers.length; }
    get totalAssignments() { return this.filteredAssignments.length; }
    get availableCount() {
        return this.state.staffMembers.filter(s => this.loadLevel(this.staffLoad(s.id)) === "available").length;
    }
    get busyCount() {
        return this.state.staffMembers.filter(s => this.loadLevel(this.staffLoad(s.id)) === "busy").length;
    }
    get overloadedCount() {
        return this.state.staffMembers.filter(s => this.loadLevel(this.staffLoad(s.id)) === "overloaded").length;
    }

    // Avatar initials + a stable palette index (matches the timeline-card look)
    initials(name) {
        const parts = (name || "?").trim().split(/\s+/);
        return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
    }
    avatarHue(name) {
        let h = 0;
        for (const ch of (name || "")) h = (h * 31 + ch.charCodeAt(0)) & 0xffffffff;
        return Math.abs(h) % 8;
    }
    stateLabel(s) { return (s || "").replace(/_/g, " "); }

    async onStaffClick(staffId) {
        // Open staff form
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: staffId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    async onAssignmentClick(assignmentId) {
        // Open assignment form
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'health.staff.assignment',
            res_id: assignmentId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    async onRefresh() {
        this.state.isLoading = true;
        await this.loadDashboardData();
        this.notification.add("Dashboard refreshed", { type: "success" });
    }

    async onTimeRangeChange(event) {
        console.log('Time range changed to:', event.target.value);
        this.state.selectedTimeRange = event.target.value;
        this.state.isLoading = true;
        await this.loadDashboardData();
        this.notification.add(`Showing data for: ${event.target.value}`, { type: "info" });
    }
}

// Register the client action
registry.category("actions").add("staff_workload_dashboard", StaffWorkloadDashboard);

export default StaffWorkloadDashboard;
