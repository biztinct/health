/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Visual Staff Workload Dashboard
 * Shows all staff members with their current assignments and capacity
 * Enables drag & drop assignment redistribution
 */
export class StaffWorkloadDashboard extends Component {
    static template = "health_staff_assignment.StaffWorkloadDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        
        this.state = useState({
            staffMembers: [],
            assignments: [],
            isLoading: true,
            selectedTimeRange: 'week',
            draggedAssignment: null,
            dropTarget: null
        });
        
        // Workload thresholds
        this.workloadConfig = {
            optimal: 80,    // Green - under 80%
            warning: 95,    // Yellow - 80-95%
            overload: 100   // Red - over 95%
        };
        
        onWillStart(this.loadData);
        onMounted(this.setupDragAndDrop);
    }

    /**
     * Load staff and assignment data
     */
    async loadData() {
        try {
            // Load staff members with workload data
            const staffData = await this.orm.call(
                'health.staff',
                'get_workload_dashboard_data',
                [],
                {
                    time_range: this.state.selectedTimeRange,
                    include_assignments: true,
                    include_availability: true
                }
            );
            
            this.state.staffMembers = staffData.staff_members || [];
            this.state.assignments = staffData.assignments || [];
            this.state.isLoading = false;
            
        } catch (error) {
            console.error('Error loading workload data:', error);
            this.notification.add(_t("Failed to load workload data"), {
                type: "danger"
            });
            this.state.isLoading = false;
        }
    }

    /**
     * Setup drag and drop functionality
     */
    setupDragAndDrop() {
        const dashboardEl = document.querySelector('.o_staff_workload_dashboard');
        if (!dashboardEl) return;

        // Make assignments draggable
        this.setupAssignmentDragging();
        
        // Setup staff drop zones
        this.setupStaffDropZones();
        
        // Global drag end handler
        document.addEventListener('dragend', this.onGlobalDragEnd.bind(this));
    }

    /**
     * Setup assignment dragging
     */
    setupAssignmentDragging() {
        const assignmentElements = document.querySelectorAll('.o_assignment_card');
        
        assignmentElements.forEach(element => {
            element.draggable = true;
            element.addEventListener('dragstart', this.onAssignmentDragStart.bind(this));
            element.addEventListener('dragend', this.onAssignmentDragEnd.bind(this));
        });
    }

    /**
     * Setup staff drop zones
     */
    setupStaffDropZones() {
        const staffElements = document.querySelectorAll('.o_staff_column');
        
        staffElements.forEach(element => {
            element.addEventListener('dragover', this.onStaffDragOver.bind(this));
            element.addEventListener('drop', this.onStaffDrop.bind(this));
            element.addEventListener('dragenter', this.onStaffDragEnter.bind(this));
            element.addEventListener('dragleave', this.onStaffDragLeave.bind(this));
        });
    }

    /**
     * Handle assignment drag start
     */
    onAssignmentDragStart(event) {
        const assignmentId = parseInt(event.target.dataset.assignmentId);
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        
        if (!assignment) return;
        
        this.state.draggedAssignment = assignment;
        
        // Set drag data
        event.dataTransfer.setData('text/plain', assignmentId.toString());
        event.dataTransfer.effectAllowed = 'move';
        
        // Add visual feedback
        event.target.classList.add('o_dragging');
        document.body.classList.add('o_assignment_dragging');
        
        // Show drop zones
        this.showDropZones(assignment);
        
        this.notification.add(_t("Dragging assignment: %s", assignment.name), {
            type: "info",
            sticky: false
        });
    }

    /**
     * Handle assignment drag end
     */
    onAssignmentDragEnd(event) {
        // Clean up visual feedback
        event.target.classList.remove('o_dragging');
        document.body.classList.remove('o_assignment_dragging');
        
        // Hide drop zones
        this.hideDropZones();
        
        // Reset state
        this.state.draggedAssignment = null;
        this.state.dropTarget = null;
    }

    /**
     * Handle staff drag over
     */
    onStaffDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }

    /**
     * Handle staff drag enter
     */
    onStaffDragEnter(event) {
        const staffId = parseInt(event.currentTarget.dataset.staffId);
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        
        if (!staff || !this.state.draggedAssignment) return;
        
        // Check if assignment can be moved to this staff
        const isValidDrop = this.validateStaffAssignment(staff, this.state.draggedAssignment);
        
        if (isValidDrop) {
            event.currentTarget.classList.add('o_valid_drop_target');
            this.state.dropTarget = staff;
        } else {
            event.currentTarget.classList.add('o_invalid_drop_target');
        }
    }

    /**
     * Handle staff drag leave
     */
    onStaffDragLeave(event) {
        event.currentTarget.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
        this.state.dropTarget = null;
    }

    /**
     * Handle staff drop
     */
    async onStaffDrop(event) {
        event.preventDefault();
        
        const staffId = parseInt(event.currentTarget.dataset.staffId);
        const assignmentId = parseInt(event.dataTransfer.getData('text/plain'));
        
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        
        if (!staff || !assignment) return;
        
        // Clean up visual states
        event.currentTarget.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
        
        // Validate the assignment
        if (!this.validateStaffAssignment(staff, assignment)) {
            this.notification.add(_t("Cannot assign to %s: Missing required skills or overloaded", staff.name), {
                type: "warning"
            });
            return;
        }
        
        // Execute the assignment
        await this.reassignToStaff(assignment, staff);
    }

    /**
     * Global drag end handler
     */
    onGlobalDragEnd(event) {
        // Clean up any remaining visual states
        document.querySelectorAll('.o_valid_drop_target, .o_invalid_drop_target')
            .forEach(el => el.classList.remove('o_valid_drop_target', 'o_invalid_drop_target'));
    }

    /**
     * Show drop zones for assignment
     */
    showDropZones(assignment) {
        const staffColumns = document.querySelectorAll('.o_staff_column');
        
        staffColumns.forEach(column => {
            const staffId = parseInt(column.dataset.staffId);
            const staff = this.state.staffMembers.find(s => s.id === staffId);
            
            if (staff && this.validateStaffAssignment(staff, assignment)) {
                column.classList.add('o_available_drop_zone');
            } else {
                column.classList.add('o_unavailable_drop_zone');
            }
        });
    }

    /**
     * Hide drop zones
     */
    hideDropZones() {
        document.querySelectorAll('.o_available_drop_zone, .o_unavailable_drop_zone')
            .forEach(el => el.classList.remove('o_available_drop_zone', 'o_unavailable_drop_zone'));
    }

    /**
     * Validate if assignment can be moved to staff
     */
    validateStaffAssignment(staff, assignment) {
        // Check if staff is active
        if (staff.employment_status !== 'active') {
            return false;
        }
        
        // Check workload capacity
        if (staff.workload_percentage > this.workloadConfig.overload) {
            return false;
        }
        
        // Check required skills (simplified for now)
        // In full implementation, this would check skill matching
        
        // Check availability for assignment time
        // In full implementation, this would check time conflicts
        
        return true;
    }

    /**
     * Reassign assignment to new staff member
     */
    async reassignToStaff(assignment, newStaff) {
        try {
            // Show loading
            const originalStaffName = this.getStaffNameById(assignment.assigned_staff_ids[0]);
            
            // Update assignment
            await this.orm.write('health.staff.assignment', [assignment.id], {
                assigned_staff_ids: [[6, 0, [newStaff.id]]],
                lead_staff_id: newStaff.id
            });
            
            // Update local state
            assignment.assigned_staff_ids = [newStaff.id];
            assignment.lead_staff_id = newStaff.id;
            
            // Recalculate workloads
            await this.recalculateWorkloads();
            
            // Show success notification
            this.notification.add(
                _t("Assignment '%s' moved from %s to %s", 
                   assignment.name, originalStaffName, newStaff.name),
                { type: "success" }
            );
            
            // Refresh data
            await this.loadData();
            
        } catch (error) {
            console.error('Error reassigning staff:', error);
            this.notification.add(_t("Failed to reassign assignment"), {
                type: "danger"
            });
        }
    }

    /**
     * Recalculate workloads for all staff
     */
    async recalculateWorkloads() {
        try {
            await this.orm.call(
                'health.staff.assignment.engine',
                'recalculate_all_workloads',
                [],
                { time_range: this.state.selectedTimeRange }
            );
        } catch (error) {
            console.error('Error recalculating workloads:', error);
        }
    }

    /**
     * Get staff name by ID
     */
    getStaffNameById(staffId) {
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        return staff ? staff.name : 'Unknown Staff';
    }

    /**
     * Get workload status class
     */
    getWorkloadStatusClass(workloadPercentage) {
        if (workloadPercentage <= this.workloadConfig.optimal) {
            return 'o_workload_optimal';
        } else if (workloadPercentage <= this.workloadConfig.warning) {
            return 'o_workload_warning';
        } else {
            return 'o_workload_overload';
        }
    }

    /**
     * Get workload status text
     */
    getWorkloadStatusText(workloadPercentage) {
        if (workloadPercentage <= this.workloadConfig.optimal) {
            return _t('Available');
        } else if (workloadPercentage <= this.workloadConfig.warning) {
            return _t('Busy');
        } else {
            return _t('Overloaded');
        }
    }

    /**
     * Handle time range change
     */
    async onTimeRangeChange(event) {
        this.state.selectedTimeRange = event.target.value;
        this.state.isLoading = true;
        await this.loadData();
    }

    /**
     * Handle assignment priority change
     */
    async onPriorityChange(assignmentId, newPriority) {
        try {
            await this.orm.write('health.staff.assignment', [assignmentId], {
                priority: newPriority
            });
            
            // Update local state
            const assignment = this.state.assignments.find(a => a.id === assignmentId);
            if (assignment) {
                assignment.priority = newPriority;
            }
            
            this.notification.add(_t("Priority updated"), { type: "success" });
            
        } catch (error) {
            console.error('Error updating priority:', error);
            this.notification.add(_t("Failed to update priority"), { type: "danger" });
        }
    }

    /**
     * Open assignment details
     */
    openAssignmentDetails(assignmentId) {
        return {
            type: 'ir.actions.act_window',
            res_model: 'health.staff.assignment',
            res_id: assignmentId,
            view_mode: 'form',
            target: 'current'
        };
    }

    /**
     * Auto-balance workload
     */
    async autoBalanceWorkload() {
        try {
            const result = await this.orm.call(
                'health.staff.assignment.engine',
                'auto_balance_workload',
                [],
                { time_range: this.state.selectedTimeRange }
            );
            
            this.notification.add(
                _t("%s assignments redistributed for optimal balance", result.redistributed_count),
                { type: "success" }
            );
            
            // Refresh data
            await this.loadData();
            
        } catch (error) {
            console.error('Error auto-balancing workload:', error);
            this.notification.add(_t("Failed to auto-balance workload"), { type: "danger" });
        }
    }
}

// Register the component
registry.category("actions").add("staff_workload_dashboard", StaffWorkloadDashboard);