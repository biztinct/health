/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
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
            selectedTimeRange: 'week'
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
                ['name', 'healthcare_role', 'employment_status']
            );
            
            // Debug: Log staff data to check names are loading
            console.log('Staff member names:', staffMembers.map(s => s.name));
            
            console.log('Loaded staff members:', staffMembers);

            // Load current assignments
            const assignments = await this.orm.searchRead(
                "health.staff.assignment",
                [['state', 'in', ['assigned', 'confirmed', 'in_progress']]],
                ['name', 'fso_id', 'staff_id', 'assignment_role', 'state']
            );
            
            console.log('Loaded assignments:', assignments);

            this.state.staffMembers = staffMembers || [];
            this.state.assignments = assignments || [];
            this.state.isLoading = false;
            
            console.log('Dashboard data loaded successfully');

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.notification.add(_t("Error loading dashboard data: ") + (error.message || _t('Unknown error')), { type: "danger" });
            this.state.isLoading = false;
        }
    }

    getStaffAssignments(staffId) {
        return this.state.assignments.filter(a => a.staff_id[0] === staffId);
    }

    getWorkloadStatusClass(workloadPercentage) {
        if (workloadPercentage <= 80) {
            return 'success'; // Green
        } else if (workloadPercentage <= 95) {
            return 'warning'; // Yellow
        } else {
            return 'danger'; // Red
        }
    }

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
