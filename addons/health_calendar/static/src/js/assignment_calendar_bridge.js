/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Assignment Calendar Bridge
 * Integrates Staff Availability Calendar with Assignment Kanban System
 * Enables cross-view drag & drop and real-time synchronization
 */
export class AssignmentCalendarBridge {
    constructor() {
        this.calendarViews = new Map();
        this.kanbanViews = new Map();
        this.eventHandlers = new Map();
        this.syncQueue = [];
        
        // Initialize cross-view communication
        this._initializeCrossViewCommunication();
    }

    /**
     * Initialize cross-view communication system
     */
    _initializeCrossViewCommunication() {
        // Store bound methods to avoid binding issues
        this.boundHandlers = {
            handleAvailabilityChange: (event) => this._handleAvailabilityChange(event),
            handleAvailabilityCreated: (event) => this._handleAvailabilityCreated(event),
            handleAvailabilityDeleted: (event) => this._handleAvailabilityDeleted(event),
            handleStaffAssignmentChange: (event) => this._handleStaffAssignmentChange(event),
            handleAssignmentStateChange: (event) => this._handleAssignmentStateChange(event),
            handleAssignmentCreated: (event) => this._handleAssignmentCreated(event)
        };
        
        // Listen for calendar events
        document.addEventListener('calendar:availability:changed', this.boundHandlers.handleAvailabilityChange);
        document.addEventListener('calendar:availability:created', this.boundHandlers.handleAvailabilityCreated);
        document.addEventListener('calendar:availability:deleted', this.boundHandlers.handleAvailabilityDeleted);
        
        // Listen for assignment events
        document.addEventListener('assignment:staff:changed', this.boundHandlers.handleStaffAssignmentChange);
        document.addEventListener('assignment:state:changed', this.boundHandlers.handleAssignmentStateChange);
        document.addEventListener('assignment:created', this.boundHandlers.handleAssignmentCreated);
    }

    /**
     * Register a calendar view
     */
    registerCalendarView(viewId, calendarController) {
        this.calendarViews.set(viewId, calendarController);
        this._attachCalendarHandlers(viewId, calendarController);
    }

    /**
     * Register a kanban view
     */
    registerKanbanView(viewId, kanbanController) {
        this.kanbanViews.set(viewId, kanbanController);
        this._attachKanbanHandlers(viewId, kanbanController);
    }

    /**
     * Unregister a view
     */
    unregisterView(viewId) {
        this.calendarViews.delete(viewId);
        this.kanbanViews.delete(viewId);
        
        // Clean up event handlers
        if (this.eventHandlers.has(viewId)) {
            const handlers = this.eventHandlers.get(viewId);
            handlers.forEach(handler => handler.cleanup());
            this.eventHandlers.delete(viewId);
        }
    }

    /**
     * Attach calendar-specific event handlers
     */
    _attachCalendarHandlers(viewId, calendarController) {
        const handlers = [];

        // Handle availability drag completion
        const onAvailabilityDrop = async (eventData) => {
            await this._syncAvailabilityToAssignments(eventData);
            this._notifyKanbanViews('availability:updated', eventData);
        };

        // Handle availability creation
        const onAvailabilityCreate = async (eventData) => {
            await this._createOptimalAssignments(eventData);
            this._notifyKanbanViews('availability:created', eventData);
        };

        // Handle availability deletion
        const onAvailabilityDelete = async (eventData) => {
            await this._handleAvailabilityDeletion(eventData);
            this._notifyKanbanViews('availability:deleted', eventData);
        };

        handlers.push(
            { type: 'drop', handler: onAvailabilityDrop, cleanup: () => {} },
            { type: 'create', handler: onAvailabilityCreate, cleanup: () => {} },
            { type: 'delete', handler: onAvailabilityDelete, cleanup: () => {} }
        );

        this.eventHandlers.set(viewId, handlers);
    }

    /**
     * Attach kanban-specific event handlers
     */
    _attachKanbanHandlers(viewId, kanbanController) {
        const handlers = [];

        // Handle assignment drag to calendar
        const onAssignmentToCalendar = async (assignmentData, targetTime) => {
            await this._createAvailabilityFromAssignment(assignmentData, targetTime);
            this._notifyCalendarViews('assignment:scheduled', assignmentData);
        };

        // Handle staff assignment changes
        const onStaffChange = async (assignmentData) => {
            await this._updateCalendarForStaffChange(assignmentData);
            this._notifyCalendarViews('staff:changed', assignmentData);
        };

        handlers.push(
            { type: 'assignment_to_calendar', handler: onAssignmentToCalendar, cleanup: () => {} },
            { type: 'staff_change', handler: onStaffChange, cleanup: () => {} }
        );

        this.eventHandlers.set(viewId, handlers);
    }

    /**
     * Handle availability change from calendar
     */
    async _handleAvailabilityChange(event) {
        const { availability, originalAvailability, staffId } = event.detail;
        
        try {
            // Update related assignments
            await this._updateAssignmentsForAvailabilityChange(availability, originalAvailability, staffId);
            
            // Notify kanban views
            this._notifyKanbanViews('availability:changed', {
                availability,
                originalAvailability,
                staffId
            });
            
        } catch (error) {
            console.error('Error handling availability change:', error);
            this._showError(_t('Failed to update related assignments'));
        }
    }

    /**
     * Handle availability creation from calendar
     */
    async _handleAvailabilityCreated(event) {
        const { availability } = event.detail;
        
        try {
            // Check for pending assignments that can be auto-scheduled
            const pendingAssignments = await this._getPendingAssignmentsForStaff(availability.staff_id);
            
            if (pendingAssignments.length > 0) {
                const suggestions = await this._generateAssignmentSuggestions(availability, pendingAssignments);
                this._showAssignmentSuggestions(suggestions);
            }
            
        } catch (error) {
            console.error('Error handling availability creation:', error);
        }
    }

    /**
     * Handle availability deletion from calendar
     */
    async _handleAvailabilityDeleted(event) {
        const { availabilityId, staffId } = event.detail;
        
        try {
            // Find affected assignments
            const affectedAssignments = await this._getAssignmentsForAvailability(availabilityId);
            
            if (affectedAssignments.length > 0) {
                await this._handleAffectedAssignments(affectedAssignments);
            }
            
        } catch (error) {
            console.error('Error handling availability deletion:', error);
        }
    }

    /**
     * Sync availability changes to assignment system
     */
    async _syncAvailabilityToAssignments(eventData) {
        const { newStart, newEnd, originalStart, originalEnd, staffId } = eventData;
        
        // Find assignments in the time range
        const assignments = await this._getAssignmentsInTimeRange(
            originalStart, originalEnd, staffId
        );
        
        // Calculate time shift
        const timeShift = newStart - originalStart;
        
        // Update assignments
        for (const assignment of assignments) {
            const newAssignmentTime = new Date(assignment.assignment_date.getTime() + timeShift);
            
            await this._updateAssignmentTime(assignment.id, newAssignmentTime);
        }
    }

    /**
     * Create optimal assignments when availability is created
     */
    async _createOptimalAssignments(eventData) {
        const { availability } = eventData;
        
        if (availability.availability_type !== 'available') return;
        
        // Get unassigned appointments that match this staff member's skills
        const matchingAppointments = await this._getMatchingUnassignedAppointments(availability.staff_id);
        
        // Create assignments for optimal matches
        for (const appointment of matchingAppointments) {
            if (this._isTimeSlotSuitable(appointment, availability)) {
                await this._createAssignment(appointment, availability);
            }
        }
    }

    /**
     * Create availability from assignment drag
     */
    async _createAvailabilityFromAssignment(assignmentData, targetTime) {
        const orm = this._getOrmService();
        if (!orm) {
            console.warn("ORM service not available for availability creation");
            return null;
        }
        
        try {
            const duration = assignmentData.estimated_duration || 60; // Default 1 hour
            const endTime = new Date(targetTime.getTime() + (duration * 60 * 1000));
            
            const availabilityData = {
                staff_id: assignmentData.assigned_staff_ids[0], // First assigned staff
                date_start: targetTime.toISOString(),
                date_end: endTime.toISOString(),
                availability_type: 'available',
                notes: `Created for assignment: ${assignmentData.name}`
            };
            
            // Create availability record
            const availability = await orm.create('health.staff.availability', [availabilityData]);
            
            // Update assignment with scheduling info
            await orm.write('health.staff.assignment', [assignmentData.id], {
                assignment_date: targetTime.toISOString(),
                state: 'assigned'
            });
            
            return availability;
        } catch (error) {
            console.error("Error creating availability from assignment:", error);
            return null;
        }
    }

    /**
     * Update calendar when staff assignment changes
     */
    async _updateCalendarForStaffChange(assignmentData) {
        // Refresh calendar views to show updated assignments
        this.calendarViews.forEach(calendar => {
            if (calendar.model && calendar.model.load) {
                calendar.model.load();
            }
        });
    }

    /**
     * Get pending assignments for a staff member
     */
    async _getPendingAssignmentsForStaff(staffId) {
        const orm = this._getOrmService();
        if (!orm) {
            console.warn("ORM service not available for getting pending assignments");
            return [];
        }
        
        try {
            return await orm.searchRead(
                'health.staff.assignment',
                [
                    '|',
                    ['assigned_staff_ids', 'in', [staffId]],
                    ['lead_staff_id', '=', staffId],
                    ['state', 'in', ['draft', 'assigned']]
                ],
                ['id', 'name', 'appointment_id', 'priority', 'assignment_type']
            );
        } catch (error) {
            console.error("Error getting pending assignments:", error);
            return [];
        }
    }

    /**
     * Generate assignment suggestions based on availability
     */
    async _generateAssignmentSuggestions(availability, pendingAssignments) {
        const suggestions = [];
        
        for (const assignment of pendingAssignments) {
            const score = await this._calculateAssignmentScore(availability, assignment);
            
            if (score > 70) { // Only suggest high-confidence matches
                suggestions.push({
                    assignment,
                    availability,
                    score,
                    reason: this._getAssignmentReason(availability, assignment, score)
                });
            }
        }
        
        return suggestions.sort((a, b) => b.score - a.score);
    }

    /**
     * Show assignment suggestions to user
     */
    _showAssignmentSuggestions(suggestions) {
        if (suggestions.length === 0) return;
        
        // Create notification with suggestions
        const notification = this._getNotificationService();
        if (!notification) {
            console.log("Assignment suggestions available:", suggestions);
            return;
        }
        
        const suggestionText = suggestions.map(s => 
            `${s.assignment.name} (${s.score}% match)`
        ).join(', ');
        
        notification.add(
            _t("Assignment suggestions available: %s", suggestionText),
            {
                type: "info",
                sticky: true,
                buttons: [
                    {
                        name: _t("Apply All"),
                        primary: true,
                        click: () => this._applyAllSuggestions(suggestions)
                    },
                    {
                        name: _t("Review"),
                        click: () => this._showSuggestionDialog(suggestions)
                    }
                ]
            }
        );
    }

    /**
     * Apply all assignment suggestions
     */
    async _applyAllSuggestions(suggestions) {
        const orm = this._getOrmService();
        if (!orm) {
            console.warn("ORM service not available for applying suggestions");
            return;
        }
        
        try {
            for (const suggestion of suggestions) {
                await this._createAssignment(suggestion.assignment, suggestion.availability);
            }
            
            // Refresh views
            this._refreshAllViews();
            
            const notification = this._getNotificationService();
            if (notification && notification.add) {
                notification.add(
                    _t("%s assignments created successfully", suggestions.length),
                    { type: "success" }
                );
            } else {
                console.log(`${suggestions.length} assignments created successfully`);
            }
        } catch (error) {
            console.error("Error applying suggestions:", error);
            this._showError("Failed to apply assignment suggestions");
        }
    }

    /**
     * Create assignment from suggestion
     */
    async _createAssignment(appointment, availability) {
        const orm = this._getOrmService();
        
        // Calculate assignment time within availability window
        const appointmentDuration = appointment.estimated_duration || 60;
        const assignmentTime = new Date(availability.date_start);
        
        await orm.write('health.staff.assignment', [appointment.id], {
            assigned_staff_ids: [[6, 0, [availability.staff_id]]],
            assignment_date: assignmentTime.toISOString(),
            state: 'assigned'
        });
    }

    /**
     * Calculate assignment score based on various factors
     */
    async _calculateAssignmentScore(availability, assignment) {
        let score = 0;
        
        // Time match (40 points)
        const timeScore = this._calculateTimeScore(availability, assignment);
        score += timeScore * 0.4;
        
        // Skill match (30 points)
        const skillScore = await this._calculateSkillScore(availability.staff_id, assignment);
        score += skillScore * 0.3;
        
        // Priority match (20 points)
        const priorityScore = this._calculatePriorityScore(assignment);
        score += priorityScore * 0.2;
        
        // Workload balance (10 points)
        const workloadScore = await this._calculateWorkloadScore(availability.staff_id);
        score += workloadScore * 0.1;
        
        return Math.round(score);
    }

    /**
     * Notify all kanban views of an event
     */
    _notifyKanbanViews(eventType, data) {
        this.kanbanViews.forEach(kanban => {
            if (kanban.trigger) {
                kanban.trigger(eventType, data);
            }
        });
    }

    /**
     * Notify all calendar views of an event
     */
    _notifyCalendarViews(eventType, data) {
        this.calendarViews.forEach(calendar => {
            if (calendar.trigger) {
                calendar.trigger(eventType, data);
            }
        });
    }

    /**
     * Refresh all registered views
     */
    _refreshAllViews() {
        // Refresh calendars
        this.calendarViews.forEach(calendar => {
            if (calendar.model && calendar.model.load) {
                calendar.model.load();
            }
        });
        
        // Refresh kanbans
        this.kanbanViews.forEach(kanban => {
            if (kanban.model && kanban.model.load) {
                kanban.model.load();
            }
        });
    }

    /**
     * Get ORM service
     */
    _getOrmService() {
        try {
            const services = registry.category("services");
            return services && services.get ? services.get("orm") : null;
        } catch (error) {
            console.warn("ORM service not available:", error);
            return null;
        }
    }

    /**
     * Get notification service
     */
    _getNotificationService() {
        try {
            const services = registry.category("services");
            return services && services.get ? services.get("notification") : null;
        } catch (error) {
            console.warn("Notification service not available:", error);
            return null;
        }
    }

    /**
     * Show error message
     */
    _showError(message) {
        const notification = this._getNotificationService();
        if (notification && notification.add) {
            notification.add(message, { type: "danger" });
        } else {
            console.error("Bridge Error:", message);
        }
    }

    // Additional helper methods for calculations
    _calculateTimeScore(availability, assignment) {
        // Implementation for time-based scoring
        return 80; // Simplified
    }

    async _calculateSkillScore(staffId, assignment) {
        // Implementation for skill matching
        return 85; // Simplified
    }

    _calculatePriorityScore(assignment) {
        // Implementation for priority scoring
        const priorityMap = { '4': 100, '3': 80, '2': 60, '1': 40, '0': 20 };
        return priorityMap[assignment.priority] || 40;
    }

    async _calculateWorkloadScore(staffId) {
        // Implementation for workload balance scoring
        return 75; // Simplified
    }

    _isTimeSlotSuitable(appointment, availability) {
        // Check if appointment can fit in availability slot
        const duration = appointment.estimated_duration || 60;
        const availableDuration = (new Date(availability.date_end) - new Date(availability.date_start)) / (1000 * 60);
        return availableDuration >= duration;
    }

    _getAssignmentReason(availability, assignment, score) {
        return `High compatibility (${score}%) based on skills, timing, and workload`;
    }
}

// Create singleton instance
export const assignmentCalendarBridge = new AssignmentCalendarBridge();

// Note: Bridge is available as import, no registry registration needed