/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Assignment Timeline View
 * Professional timeline/Gantt-style view for assignment management
 * Inspired by Monday.com, Asana Timeline, and Microsoft Project
 */
export class AssignmentTimelineView extends Component {
    static template = "health_staff_assignment.AssignmentTimelineView";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        
        this.timelineRef = useRef("timeline");
        
        this.state = useState({
            staffMembers: [],
            assignments: [],
            isLoading: true,
            selectedTimeRange: 'week',
            viewMode: 'day', // day, week, month
            currentDate: new Date(),
            draggedAssignment: null,
            selectedAssignment: null,
            timeSlots: [],
            zoomLevel: 1
        });
        
        // Timeline configuration
        this.timelineConfig = {
            hourWidth: 60,  // pixels per hour
            rowHeight: 80,  // pixels per staff row
            headerHeight: 120,
            leftPanelWidth: 250,
            minDuration: 15, // minimum assignment duration in minutes
            snapToGrid: 15,  // snap to 15-minute intervals
        };
        
        onWillStart(this.loadData);
        onMounted(this.initializeTimeline);
    }

    /**
     * Load timeline data
     */
    async loadData() {
        try {
            // Load staff and assignments
            const timelineData = await this.orm.call(
                'health.staff',
                'get_timeline_data',
                [],
                {
                    date: this.state.currentDate.toISOString().split('T')[0],
                    view_mode: this.state.viewMode,
                    include_assignments: true
                }
            );
            
            this.state.staffMembers = timelineData.staff_members || [];
            this.state.assignments = timelineData.assignments || [];
            this.state.timeSlots = this.generateTimeSlots();
            this.state.isLoading = false;
            
            // Re-setup drag and drop after data loads
            setTimeout(() => {
                this.setupDragAndDrop();
            }, 100);
            
        } catch (error) {
            console.error('Error loading timeline data:', error);
            this.notification.add(_t("Failed to load timeline data"), {
                type: "danger"
            });
            this.state.isLoading = false;
        }
    }

    /**
     * Initialize timeline interactions
     */
    initializeTimeline() {
        if (!this.timelineRef.el) return;
        
        this.setupTimelineScrolling();
        this.setupZoomControls();
        this.setupTimelineResize();
        
        // Setup drag and drop after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.setupDragAndDrop();
        }, 200);
    }

    /**
     * Generate time slots for the current view
     */
    generateTimeSlots() {
        const slots = [];
        const startDate = new Date(this.state.currentDate);
        
        if (this.state.viewMode === 'day') {
            // Generate hourly slots for the day
            for (let hour = 0; hour < 24; hour++) {
                slots.push({
                    time: `${hour.toString().padStart(2, '0')}:00`,
                    datetime: new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), hour),
                    type: 'hour'
                });
            }
        } else if (this.state.viewMode === 'week') {
            // Generate daily slots for the week
            startDate.setDate(startDate.getDate() - startDate.getDay()); // Start of week
            for (let day = 0; day < 7; day++) {
                const slotDate = new Date(startDate);
                slotDate.setDate(startDate.getDate() + day);
                slots.push({
                    time: slotDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
                    datetime: slotDate,
                    type: 'day'
                });
            }
        } else if (this.state.viewMode === 'month') {
            // Generate weekly slots for the month
            const startOfMonth = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
            const endOfMonth = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0);
            
            for (let week = 0; week < 6; week++) {
                const weekStart = new Date(startOfMonth);
                weekStart.setDate(1 + (week * 7));
                if (weekStart <= endOfMonth) {
                    slots.push({
                        time: `Week ${week + 1}`,
                        datetime: weekStart,
                        type: 'week'
                    });
                }
            }
        }
        
        return slots;
    }

    /**
     * Setup timeline scrolling synchronization
     */
    setupTimelineScrolling() {
        const header = this.timelineRef.el.querySelector('.o_timeline_header');
        const body = this.timelineRef.el.querySelector('.o_timeline_body');
        
        if (header && body) {
            body.addEventListener('scroll', () => {
                header.scrollLeft = body.scrollLeft;
            });
        }
    }

    /**
     * Setup drag and drop for timeline
     */
    setupDragAndDrop() {
        this.setupAssignmentDragging();
        this.setupTimelineDropZones();
    }

    /**
     * Setup assignment dragging
     */
    setupAssignmentDragging() {
        if (!this.timelineRef.el) {
            console.warn('Timeline element not found for drag setup');
            return;
        }
        
        const assignmentElements = this.timelineRef.el.querySelectorAll('.o_timeline_assignment');
        console.log(`Setting up drag for ${assignmentElements.length} assignment elements`);
        
        assignmentElements.forEach(element => {
            element.draggable = true;
            element.addEventListener('dragstart', this.onAssignmentDragStart.bind(this));
            element.addEventListener('drag', this.onAssignmentDrag.bind(this));
            element.addEventListener('dragend', this.onAssignmentDragEnd.bind(this));
            
            // Add visual indicator for draggable elements
            element.style.cursor = 'move';
            element.title = 'Drag to move assignment';
        });
    }

    /**
     * Setup timeline drop zones
     */
    setupTimelineDropZones() {
        if (!this.timelineRef.el) {
            console.warn('Timeline element not found for drop zone setup');
            return;
        }
        
        // Setup drop zones on time slots
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        console.log(`Setting up drop zones for ${timeSlots.length} time slots`);
        
        timeSlots.forEach(slot => {
            slot.addEventListener('dragover', this.onTimeSlotDragOver.bind(this));
            slot.addEventListener('drop', this.onTimeSlotDrop.bind(this));
            slot.addEventListener('dragenter', this.onTimeSlotDragEnter.bind(this));
            slot.addEventListener('dragleave', this.onTimeSlotDragLeave.bind(this));
            
            // Visual indication for drop zones
            slot.style.minHeight = '60px';
        });
        
        // Also setup staff row drop zones for staff reassignment
        const staffRows = this.timelineRef.el.querySelectorAll('.o_timeline_staff_row');
        console.log(`Setting up staff drop zones for ${staffRows.length} staff rows`);
        
        staffRows.forEach(element => {
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
        console.log('Drag start event triggered', event.target);
        
        const assignmentId = parseInt(event.target.dataset.assignmentId);
        console.log('Assignment ID:', assignmentId);
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        console.log('Found assignment:', assignment);
        
        if (!assignment) {
            console.warn('Assignment not found for ID:', assignmentId);
            return;
        }
        
        this.state.draggedAssignment = assignment;
        
        // Create drag ghost with assignment info
        const dragGhost = document.createElement('div');
        dragGhost.className = 'o_timeline_drag_ghost';
        dragGhost.innerHTML = `
            <div class="o_drag_ghost_content">
                <i class="fa fa-arrows-alt"></i>
                <span>${assignment.name}</span>
            </div>
        `;
        document.body.appendChild(dragGhost);
        event.dataTransfer.setDragImage(dragGhost, 10, 10);
        
        // Clean up ghost after drag
        setTimeout(() => document.body.removeChild(dragGhost), 0);
        
        event.dataTransfer.setData('text/plain', assignmentId.toString());
        event.dataTransfer.effectAllowed = 'move';
        
        // Add visual feedback
        event.target.classList.add('o_dragging');
        this.timelineRef.el.classList.add('o_timeline_dragging');
        
        // Highlight valid drop zones
        this.highlightValidDropZones(assignment);
    }

    /**
     * Handle assignment drag
     */
    onAssignmentDrag(event) {
        // Update drag preview position if needed
        this.updateDragPreview(event);
    }

    /**
     * Handle assignment drag end
     */
    onAssignmentDragEnd(event) {
        // Clean up visual feedback
        event.target.classList.remove('o_dragging');
        this.timelineRef.el.classList.remove('o_timeline_dragging');
        
        // Remove drop zone highlights
        this.removeDropZoneHighlights();
        
        // Reset state
        this.state.draggedAssignment = null;
    }

    /**
     * Handle time slot drag over
     */
    onTimeSlotDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }

    /**
     * Handle time slot drag enter
     */
    onTimeSlotDragEnter(event) {
        if (!this.state.draggedAssignment) return;
        
        const slot = event.currentTarget;
        const staffId = parseInt(slot.dataset.staffId);
        const timeSlot = slot.dataset.timeSlot;
        
        // Validate drop
        if (this.validateTimeSlotDrop(staffId, timeSlot, this.state.draggedAssignment)) {
            slot.classList.add('o_valid_drop_target');
        } else {
            slot.classList.add('o_invalid_drop_target');
        }
    }

    /**
     * Handle time slot drag leave
     */
    onTimeSlotDragLeave(event) {
        event.currentTarget.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
    }

    /**
     * Handle time slot drop
     */
    async onTimeSlotDrop(event) {
        event.preventDefault();
        
        const slot = event.currentTarget;
        const staffId = parseInt(slot.dataset.staffId);
        const timeSlot = slot.dataset.timeSlot;
        const assignmentId = parseInt(event.dataTransfer.getData('text/plain'));
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        if (!assignment) return;
        
        // Clean up visual states
        slot.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
        
        // Validate and execute the move
        if (this.validateTimeSlotDrop(staffId, timeSlot, assignment)) {
            await this.moveAssignmentToTimeSlot(assignment, staffId, timeSlot);
        } else {
            this.notification.add(_t("Cannot move assignment to this time slot"), {
                type: "warning"
            });
        }
    }

    /**
     * Validate if assignment can be dropped in time slot
     */
    validateTimeSlotDrop(staffId, timeSlot, assignment) {
        // Check if staff exists and is active
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        if (!staff || staff.employment_status !== 'active') {
            return false;
        }
        
        // Check for time conflicts
        // In full implementation, this would check for overlapping assignments
        
        // Check staff availability for the time slot
        // In full implementation, this would check staff working hours
        
        return true;
    }

    /**
     * Move assignment to new time slot
     */
    async moveAssignmentToTimeSlot(assignment, staffId, timeSlot) {
        try {
            // Calculate new assignment time based on time slot
            const newDateTime = this.calculateAssignmentDateTime(timeSlot);
            
            // Update assignment
            await this.orm.write('health.staff.assignment', [assignment.id], {
                assigned_staff_ids: [[6, 0, [staffId]]],
                lead_staff_id: staffId,
                assignment_date: newDateTime.toISOString().split('T')[0],
                // Add time fields if they exist
            });
            
            // Update local state
            assignment.assigned_staff_ids = [staffId];
            assignment.lead_staff_id = staffId;
            assignment.assignment_date = newDateTime.toISOString().split('T')[0];
            
            // Show success notification
            const staff = this.state.staffMembers.find(s => s.id === staffId);
            this.notification.add(
                _t("Assignment '%s' moved to %s at %s", 
                   assignment.name, staff.name, timeSlot),
                { type: "success" }
            );
            
            // Refresh timeline
            await this.loadData();
            
        } catch (error) {
            console.error('Error moving assignment:', error);
            this.notification.add(_t("Failed to move assignment"), {
                type: "danger"
            });
        }
    }

    /**
     * Calculate assignment date/time from time slot
     */
    calculateAssignmentDateTime(timeSlot) {
        // This would parse the time slot and return appropriate DateTime
        // For now, return current date
        return new Date();
    }

    /**
     * Highlight valid drop zones
     */
    highlightValidDropZones(assignment) {
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        
        timeSlots.forEach(slot => {
            const staffId = parseInt(slot.dataset.staffId);
            const timeSlot = slot.dataset.timeSlot;
            
            if (this.validateTimeSlotDrop(staffId, timeSlot, assignment)) {
                slot.classList.add('o_potential_drop_zone');
            } else {
                slot.classList.add('o_invalid_drop_zone');
            }
        });
    }

    /**
     * Remove drop zone highlights
     */
    removeDropZoneHighlights() {
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        timeSlots.forEach(slot => {
            slot.classList.remove('o_potential_drop_zone', 'o_invalid_drop_zone');
        });
    }

    /**
     * Setup zoom controls
     */
    setupZoomControls() {
        // This would handle timeline zoom in/out
    }

    /**
     * Setup timeline resize
     */
    setupTimelineResize() {
        // This would handle timeline panel resizing
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
        if (!this.state.draggedAssignment) return;
        
        const staffRow = event.currentTarget;
        const staffId = parseInt(staffRow.dataset.staffId);
        
        // Validate drop on staff
        if (this.validateStaffDrop(staffId, this.state.draggedAssignment)) {
            staffRow.classList.add('o_valid_staff_drop_target');
        } else {
            staffRow.classList.add('o_invalid_staff_drop_target');
        }
    }

    /**
     * Handle staff drag leave  
     */
    onStaffDragLeave(event) {
        event.currentTarget.classList.remove('o_valid_staff_drop_target', 'o_invalid_staff_drop_target');
    }

    /**
     * Handle staff drop
     */
    async onStaffDrop(event) {
        event.preventDefault();
        
        const staffRow = event.currentTarget;
        const staffId = parseInt(staffRow.dataset.staffId);
        const assignmentId = parseInt(event.dataTransfer.getData('text/plain'));
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        if (!assignment) return;
        
        // Clean up visual states
        staffRow.classList.remove('o_valid_staff_drop_target', 'o_invalid_staff_drop_target');
        
        // Validate and execute the staff reassignment
        if (this.validateStaffDrop(staffId, assignment)) {
            await this.reassignToStaff(assignment, staffId);
        } else {
            this.notification.add(_t("Cannot reassign assignment to this staff member"), {
                type: "warning"
            });
        }
    }

    /**
     * Validate if assignment can be dropped on staff
     */
    validateStaffDrop(staffId, assignment) {
        // Check if staff exists and is active
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        if (!staff || staff.employment_status !== 'active') {
            return false;
        }
        
        // Check if assignment is already assigned to this staff
        if (assignment.assigned_staff_ids.includes(staffId)) {
            return false;
        }
        
        // Additional validation can be added here
        return true;
    }

    /**
     * Reassign assignment to different staff
     */
    async reassignToStaff(assignment, staffId) {
        try {
            // Update assignment
            await this.orm.write('health.staff.assignment', [assignment.id], {
                assigned_staff_ids: [[6, 0, [staffId]]],
                lead_staff_id: staffId,
            });
            
            // Update local state
            assignment.assigned_staff_ids = [staffId];
            assignment.lead_staff_id = staffId;
            
            // Show success notification
            const staff = this.state.staffMembers.find(s => s.id === staffId);
            this.notification.add(
                _t("Assignment '%s' reassigned to %s", assignment.name, staff.name),
                { type: "success" }
            );
            
            // Refresh timeline
            await this.loadData();
            
        } catch (error) {
            console.error('Error reassigning assignment:', error);
            this.notification.add(_t("Failed to reassign assignment"), {
                type: "danger"
            });
        }
    }

    /**
     * Update drag preview
     */
    updateDragPreview(event) {
        // Update visual drag preview position
    }

    /**
     * Get assignment position in timeline
     */
    getAssignmentPosition(assignment) {
        // Calculate position based on assignment date/time and duration
        const assignmentDate = new Date(assignment.start_datetime || assignment.assignment_date);
        const duration = assignment.estimated_duration || 60; // minutes
        
        return {
            left: this.dateToPixels(assignmentDate),
            width: this.durationToPixels(duration),
        };
    }

    /**
     * Convert date to pixel position
     */
    dateToPixels(date) {
        // Convert date/time to horizontal pixel position based on view mode
        if (this.state.viewMode === 'day') {
            // For day view, calculate position within 24 hours
            const dayStart = new Date(this.state.currentDate);
            dayStart.setHours(0, 0, 0, 0);
            
            const diffHours = (date - dayStart) / (1000 * 60 * 60);
            return Math.max(0, diffHours * this.timelineConfig.hourWidth * this.state.zoomLevel);
            
        } else if (this.state.viewMode === 'week') {
            // For week view, calculate position within the week
            const weekStart = new Date(this.state.currentDate);
            const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1; // Make Monday = 0
            weekStart.setDate(weekStart.getDate() - daysFromMonday);
            weekStart.setHours(0, 0, 0, 0);
            
            const diffDays = (date - weekStart) / (1000 * 60 * 60 * 24);
            return Math.max(0, diffDays * this.timelineConfig.hourWidth * this.state.zoomLevel);
            
        } else if (this.state.viewMode === 'month') {
            // For month view, calculate position within the month
            const monthStart = new Date(this.state.currentDate.getFullYear(), this.state.currentDate.getMonth(), 1);
            
            const diffDays = (date - monthStart) / (1000 * 60 * 60 * 24);
            const daysPerWeek = 7;
            const weekPosition = Math.floor(diffDays / daysPerWeek);
            return Math.max(0, weekPosition * this.timelineConfig.hourWidth * this.state.zoomLevel);
        }
        
        return 0;
    }

    /**
     * Convert duration to pixel width
     */
    durationToPixels(minutes) {
        if (this.state.viewMode === 'day') {
            // For day view, duration in hours
            const hours = minutes / 60;
            return hours * this.timelineConfig.hourWidth * this.state.zoomLevel;
        } else if (this.state.viewMode === 'week') {
            // For week view, minimum width is partial day
            const days = minutes / (60 * 24); // Convert to days
            return Math.max(
                this.timelineConfig.hourWidth * this.state.zoomLevel * 0.5, // Minimum half-day width
                days * this.timelineConfig.hourWidth * this.state.zoomLevel
            );
        } else if (this.state.viewMode === 'month') {
            // For month view, minimum width spans some portion of a week
            const days = minutes / (60 * 24);
            const weeks = days / 7;
            return Math.max(
                this.timelineConfig.hourWidth * this.state.zoomLevel * 0.3, // Minimum width
                weeks * this.timelineConfig.hourWidth * this.state.zoomLevel
            );
        }
        
        return this.timelineConfig.hourWidth * this.state.zoomLevel * 0.5; // Default minimum width
    }

    /**
     * Handle view mode change
     */
    async onViewModeChange(newMode) {
        this.state.viewMode = newMode;
        this.state.isLoading = true;
        await this.loadData();
    }

    /**
     * Navigate timeline
     */
    async onNavigate(direction) {
        const currentDate = new Date(this.state.currentDate);
        
        if (this.state.viewMode === 'day') {
            currentDate.setDate(currentDate.getDate() + (direction === 'next' ? 1 : -1));
        } else if (this.state.viewMode === 'week') {
            currentDate.setDate(currentDate.getDate() + (direction === 'next' ? 7 : -7));
        } else if (this.state.viewMode === 'month') {
            currentDate.setMonth(currentDate.getMonth() + (direction === 'next' ? 1 : -1));
        }
        
        this.state.currentDate = currentDate;
        this.state.isLoading = true;
        await this.loadData();
    }

    /**
     * Handle zoom change
     */
    onZoomChange(newZoom) {
        this.state.zoomLevel = newZoom;
        // Redraw timeline with new zoom level
        this.redrawTimeline();
    }

    /**
     * Redraw timeline
     */
    redrawTimeline() {
        // Recalculate positions and redraw
        this.state.timeSlots = this.generateTimeSlots();
    }

    /**
     * Open assignment details
     */
    openAssignmentDetails(assignmentId) {
        // Open assignment form view
        return {
            type: 'ir.actions.act_window',
            res_model: 'health.staff.assignment',
            res_id: assignmentId,
            view_mode: 'form',
            target: 'new'
        };
    }
}

// Register the component
registry.category("actions").add("assignment_timeline_view", AssignmentTimelineView);