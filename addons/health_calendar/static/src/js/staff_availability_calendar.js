/** @odoo-module **/

import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { CalendarUtils } from "./calendar_utils";
// Temporarily commented out bridge import
// import { assignmentCalendarBridge } from "./assignment_calendar_bridge";

/**
 * Advanced Staff Availability Calendar with Drag & Drop
 * Inspired by Google Calendar and Calendly's scheduling UX
 */
export class StaffAvailabilityCalendarController extends CalendarController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        
        // Register with assignment bridge (temporarily disabled)
        this.viewId = CalendarUtils.generateId();
        // assignmentCalendarBridge.registerCalendarView(this.viewId, this);
        
        // Drag & Drop state management
        this.dragState = {
            isDragging: false,
            draggedEvent: null,
            originalPosition: null,
            ghostElement: null,
            conflictElements: []
        };
        
        // Configuration for drag & drop behavior
        this.dragConfig = {
            snapToGrid: true,
            gridSize: 15, // 15-minute intervals
            showConflicts: true,
            allowCrossStaff: true,
            animationDuration: 200
        };
        
        // Listen for assignment bridge events
        this._setupBridgeListeners();
    }

    /**
     * Setup listeners for assignment bridge communication
     */
    _setupBridgeListeners() {
        document.addEventListener('assignment:scheduled', (event) => {
            this._handleAssignmentScheduled(event.detail);
        });
        
        document.addEventListener('staff:changed', (event) => {
            this._handleStaffChanged(event.detail);
        });
    }

    /**
     * Cleanup when component is destroyed
     */
    willUnmount() {
        super.willUnmount();
        // assignmentCalendarBridge.unregisterView(this.viewId);
    }

    /**
     * Enhanced event rendering with drag handles and visual improvements
     */
    async onEventRender(info) {
        const result = await super.onEventRender(info);
        
        // Add drag handles and enhanced styling
        this._enhanceEventElement(info.el, info.event);
        
        return result;
    }

    /**
     * Initialize drag and drop functionality
     */
    _enhanceEventElement(element, event) {
        // Add drag handle
        const dragHandle = document.createElement('div');
        dragHandle.className = 'o_availability_drag_handle';
        dragHandle.innerHTML = '<i class="fa fa-arrows-alt"></i>';
        element.appendChild(dragHandle);
        
        // Add resize handles
        const resizeHandleStart = document.createElement('div');
        resizeHandleStart.className = 'o_availability_resize_handle o_resize_start';
        element.appendChild(resizeHandleStart);
        
        const resizeHandleEnd = document.createElement('div');
        resizeHandleEnd.className = 'o_availability_resize_handle o_resize_end';
        element.appendChild(resizeHandleEnd);
        
        // Add event listeners
        this._attachDragListeners(element, event);
        this._attachResizeListeners(element, event, resizeHandleStart, resizeHandleEnd);
        
        // Add hover effects
        element.addEventListener('mouseenter', () => this._onEventHover(element, event, true));
        element.addEventListener('mouseleave', () => this._onEventHover(element, event, false));
    }

    /**
     * Attach drag event listeners
     */
    _attachDragListeners(element, event) {
        const dragHandle = element.querySelector('.o_availability_drag_handle');
        
        dragHandle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this._startDrag(element, event, e);
        });
        
        // Touch support for mobile
        dragHandle.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this._startDrag(element, event, e.touches[0]);
        });
    }

    /**
     * Attach resize event listeners
     */
    _attachResizeListeners(element, event, startHandle, endHandle) {
        startHandle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this._startResize(element, event, e, 'start');
        });
        
        endHandle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this._startResize(element, event, e, 'end');
        });
    }

    /**
     * Start dragging an availability event
     */
    _startDrag(element, event, mouseEvent) {
        if (this.dragState.isDragging) return;
        
        this.dragState.isDragging = true;
        this.dragState.draggedEvent = event;
        this.dragState.originalPosition = {
            start: event.start,
            end: event.end,
            staffId: event.extendedProps.staff_id
        };
        
        // Create ghost element
        this._createGhostElement(element, mouseEvent);
        
        // Add global event listeners
        document.addEventListener('mousemove', this._onDragMove.bind(this));
        document.addEventListener('mouseup', this._onDragEnd.bind(this));
        document.addEventListener('touchmove', this._onTouchDragMove.bind(this));
        document.addEventListener('touchend', this._onDragEnd.bind(this));
        
        // Add visual feedback
        element.classList.add('o_dragging');
        document.body.classList.add('o_availability_dragging');
        
        // Show drop zones
        this._showDropZones();
        
        this.notification.add(_t("Dragging availability block..."), {
            type: "info",
            sticky: false
        });
    }

    /**
     * Handle drag movement
     */
    _onDragMove(e) {
        if (!this.dragState.isDragging) return;
        
        // Update ghost element position
        this._updateGhostPosition(e);
        
        // Check for conflicts and valid drop zones
        const dropTarget = this._getDropTarget(e);
        this._updateConflictHighlights(dropTarget);
    }

    /**
     * Handle touch drag movement
     */
    _onTouchDragMove(e) {
        if (!this.dragState.isDragging) return;
        e.preventDefault();
        this._onDragMove(e.touches[0]);
    }

    /**
     * End dragging operation
     */
    async _onDragEnd(e) {
        if (!this.dragState.isDragging) return;
        
        // Remove global listeners
        document.removeEventListener('mousemove', this._onDragMove.bind(this));
        document.removeEventListener('mouseup', this._onDragEnd.bind(this));
        document.removeEventListener('touchmove', this._onTouchDragMove.bind(this));
        document.removeEventListener('touchend', this._onDragEnd.bind(this));
        
        // Get final drop position
        const dropTarget = this._getDropTarget(e);
        
        // Clean up visual feedback
        this._cleanupDrag();
        
        if (dropTarget && dropTarget.isValid) {
            await this._executeDrop(dropTarget);
        } else {
            // Revert to original position
            this._revertDrag();
        }
        
        // Reset drag state
        this._resetDragState();
    }

    /**
     * Execute the drop operation
     */
    async _executeDrop(dropTarget) {
        const event = this.dragState.draggedEvent;
        const newStart = dropTarget.start;
        const newEnd = dropTarget.end;
        const newStaffId = dropTarget.staffId;
        
        try {
            // Check for conflicts before updating
            const conflicts = await this._checkConflicts(newStart, newEnd, newStaffId, event.id);
            
            if (conflicts.length > 0 && this.dragConfig.showConflicts) {
                const confirmResult = await this._confirmConflictResolution(conflicts);
                if (!confirmResult) {
                    this._revertDrag();
                    return;
                }
            }
            
            // Update the availability record
            await this.orm.write('health.staff.availability', [event.id], {
                date_start: newStart.toISOString(),
                date_end: newEnd.toISOString(),
                staff_id: newStaffId
            });
            
            // Refresh the calendar
            await this.model.load();
            
            this.notification.add(_t("Availability updated successfully"), {
                type: "success"
            });
            
            // Notify assignment bridge
            this._notifyAvailabilityChange(event, newStart, newEnd, newStaffId);
            
        } catch (error) {
            console.error('Error updating availability:', error);
            this.notification.add(_t("Failed to update availability"), {
                type: "danger"
            });
            this._revertDrag();
        }
    }

    /**
     * Notify assignment bridge of availability changes
     */
    _notifyAvailabilityChange(event, newStart, newEnd, newStaffId) {
        const changeEvent = new CustomEvent('calendar:availability:changed', {
            detail: {
                availability: {
                    id: event.id,
                    staff_id: newStaffId,
                    date_start: newStart,
                    date_end: newEnd,
                    availability_type: event.extendedProps.availability_type
                },
                originalAvailability: this.dragState.originalPosition,
                staffId: newStaffId
            }
        });
        document.dispatchEvent(changeEvent);
    }

    /**
     * Handle assignment scheduled from kanban
     */
    _handleAssignmentScheduled(data) {
        // Refresh calendar to show new assignment-related availability
        if (this.model && this.model.load) {
            this.model.load();
        }
    }

    /**
     * Handle staff change from assignments
     */
    _handleStaffChanged(data) {
        // Refresh calendar to reflect staff changes
        if (this.model && this.model.load) {
            this.model.load();
        }
    }

    /**
     * Start resizing an availability event
     */
    _startResize(element, event, mouseEvent, direction) {
        this.dragState.isResizing = true;
        this.dragState.resizeDirection = direction;
        this.dragState.draggedEvent = event;
        this.dragState.originalPosition = {
            start: event.start,
            end: event.end
        };
        
        // Add global listeners for resize
        document.addEventListener('mousemove', this._onResizeMove.bind(this));
        document.addEventListener('mouseup', this._onResizeEnd.bind(this));
        
        element.classList.add('o_resizing');
    }

    /**
     * Handle resize movement
     */
    _onResizeMove(e) {
        if (!this.dragState.isResizing) return;
        
        // Calculate new time based on mouse position
        const newTime = this._getTimeFromPosition(e);
        if (!newTime) return;
        
        // Update visual feedback
        this._updateResizePreview(newTime);
    }

    /**
     * End resizing operation
     */
    async _onResizeEnd(e) {
        if (!this.dragState.isResizing) return;
        
        // Remove global listeners
        document.removeEventListener('mousemove', this._onResizeMove.bind(this));
        document.removeEventListener('mouseup', this._onResizeEnd.bind(this));
        
        // Calculate final time
        const newTime = this._getTimeFromPosition(e);
        
        if (newTime) {
            await this._executeResize(newTime);
        }
        
        // Clean up
        this._resetDragState();
    }

    /**
     * Execute the resize operation
     */
    async _executeResize(newTime) {
        const event = this.dragState.draggedEvent;
        const direction = this.dragState.resizeDirection;
        
        let newStart = event.start;
        let newEnd = event.end;
        
        if (direction === 'start') {
            newStart = newTime;
        } else {
            newEnd = newTime;
        }
        
        // Validate time range
        if (newEnd <= newStart) {
            this.notification.add(_t("Invalid time range"), {
                type: "warning"
            });
            return;
        }
        
        try {
            // Update the availability record
            await this.orm.write('health.staff.availability', [event.id], {
                date_start: newStart.toISOString(),
                date_end: newEnd.toISOString()
            });
            
            // Refresh the calendar
            await this.model.load();
            
            this.notification.add(_t("Availability duration updated"), {
                type: "success"
            });
            
        } catch (error) {
            console.error('Error resizing availability:', error);
            this.notification.add(_t("Failed to update availability duration"), {
                type: "danger"
            });
        }
    }

    /**
     * Create ghost element for drag feedback
     */
    _createGhostElement(originalElement, mouseEvent) {
        const ghost = originalElement.cloneNode(true);
        ghost.classList.add('o_availability_ghost');
        ghost.style.position = 'fixed';
        ghost.style.pointerEvents = 'none';
        ghost.style.zIndex = '9999';
        ghost.style.opacity = '0.8';
        
        document.body.appendChild(ghost);
        this.dragState.ghostElement = ghost;
        
        this._updateGhostPosition(mouseEvent);
    }

    /**
     * Update ghost element position
     */
    _updateGhostPosition(mouseEvent) {
        if (!this.dragState.ghostElement) return;
        
        this.dragState.ghostElement.style.left = (mouseEvent.clientX - 50) + 'px';
        this.dragState.ghostElement.style.top = (mouseEvent.clientY - 20) + 'px';
    }

    /**
     * Show valid drop zones
     */
    _showDropZones() {
        const calendarElement = this.el.querySelector('.fc-view');
        if (calendarElement) {
            calendarElement.classList.add('o_show_drop_zones');
        }
    }

    /**
     * Get drop target information from mouse position
     */
    _getDropTarget(mouseEvent) {
        const element = document.elementFromPoint(mouseEvent.clientX, mouseEvent.clientY);
        if (!element) return null;
        
        // Find the calendar cell or time slot
        const timeSlot = element.closest('.fc-timegrid-slot, .fc-daygrid-day');
        if (!timeSlot) return null;
        
        // Extract time and staff information
        const time = this._getTimeFromElement(timeSlot);
        const staffId = this._getStaffFromElement(timeSlot);
        
        if (!time) return null;
        
        // Calculate duration
        const originalDuration = this.dragState.draggedEvent.end - this.dragState.draggedEvent.start;
        const newEnd = new Date(time.getTime() + originalDuration);
        
        return {
            start: time,
            end: newEnd,
            staffId: staffId || this.dragState.originalPosition.staffId,
            isValid: this._isValidDropTarget(time, newEnd, staffId)
        };
    }

    /**
     * Check if conflicts exist for the new time slot
     */
    async _checkConflicts(start, end, staffId, excludeId) {
        try {
            const conflicts = await this.orm.searchRead(
                'health.staff.availability',
                [
                    ['staff_id', '=', staffId],
                    ['id', '!=', excludeId],
                    '|',
                    '&', ['date_start', '<=', start.toISOString()], ['date_end', '>', start.toISOString()],
                    '&', ['date_start', '<', end.toISOString()], ['date_end', '>=', end.toISOString()]
                ],
                ['id', 'date_start', 'date_end', 'availability_type']
            );
            
            return conflicts;
        } catch (error) {
            console.error('Error checking conflicts:', error);
            return [];
        }
    }

    /**
     * Show conflict resolution dialog
     */
    async _confirmConflictResolution(conflicts) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Scheduling Conflict Detected"),
                body: _t("This time slot conflicts with %s existing availability periods. Do you want to continue?", conflicts.length),
                confirm: () => resolve(true),
                cancel: () => resolve(false)
            });
        });
    }

    /**
     * Update conflict highlights
     */
    _updateConflictHighlights(dropTarget) {
        // Remove previous highlights
        this.dragState.conflictElements.forEach(el => {
            el.classList.remove('o_conflict_highlight');
        });
        this.dragState.conflictElements = [];
        
        if (!dropTarget || dropTarget.isValid) return;
        
        // Highlight conflicting elements
        const conflictElements = this.el.querySelectorAll('.fc-event');
        conflictElements.forEach(el => {
            if (this._isConflictingElement(el, dropTarget)) {
                el.classList.add('o_conflict_highlight');
                this.dragState.conflictElements.push(el);
            }
        });
    }

    /**
     * Clean up drag operation
     */
    _cleanupDrag() {
        // Remove ghost element
        if (this.dragState.ghostElement) {
            this.dragState.ghostElement.remove();
        }
        
        // Remove visual feedback classes
        document.body.classList.remove('o_availability_dragging');
        this.el.querySelectorAll('.o_dragging').forEach(el => {
            el.classList.remove('o_dragging');
        });
        
        // Remove drop zones
        const calendarElement = this.el.querySelector('.fc-view');
        if (calendarElement) {
            calendarElement.classList.remove('o_show_drop_zones');
        }
        
        // Remove conflict highlights
        this.dragState.conflictElements.forEach(el => {
            el.classList.remove('o_conflict_highlight');
        });
    }

    /**
     * Revert drag operation
     */
    _revertDrag() {
        this.notification.add(_t("Drag operation cancelled"), {
            type: "info"
        });
    }

    /**
     * Reset drag state
     */
    _resetDragState() {
        this.dragState = {
            isDragging: false,
            isResizing: false,
            draggedEvent: null,
            originalPosition: null,
            ghostElement: null,
            conflictElements: [],
            resizeDirection: null
        };
    }

    /**
     * Event hover handler
     */
    _onEventHover(element, event, isEntering) {
        if (isEntering) {
            element.classList.add('o_event_hover');
            // Show quick info tooltip
            this._showEventTooltip(element, event);
        } else {
            element.classList.remove('o_event_hover');
            this._hideEventTooltip();
        }
    }

    /**
     * Show event tooltip with quick info
     */
    _showEventTooltip(element, event) {
        const tooltip = document.getElementById('event-tooltip') || document.createElement('div');
        tooltip.id = 'event-tooltip';
        tooltip.className = 'o_availability_tooltip';
        
        // Build tooltip content
        const startTime = CalendarUtils.formatTime(event.start);
        const endTime = CalendarUtils.formatTime(event.end);
        const duration = CalendarUtils.formatDuration(event.start, event.end);
        const staffName = event.extendedProps.staff_name || 'Unknown Staff';
        const availabilityType = event.extendedProps.availability_type;
        
        tooltip.innerHTML = `
            <div class="o_tooltip_header">
                <strong>${staffName}</strong>
                <span class="o_availability_type o_type_${availabilityType}">${availabilityType}</span>
            </div>
            <div class="o_tooltip_time">
                ${startTime} - ${endTime} (${duration})
            </div>
            ${event.extendedProps.notes ? `<div class="o_tooltip_notes">${event.extendedProps.notes}</div>` : ''}
            <div class="o_tooltip_actions">
                <small>Drag to move • Drag edges to resize</small>
            </div>
        `;
        
        // Position tooltip
        const rect = element.getBoundingClientRect();
        tooltip.style.left = (rect.left + rect.width / 2) + 'px';
        tooltip.style.top = (rect.bottom + 5) + 'px';
        
        if (!tooltip.parentNode) {
            document.body.appendChild(tooltip);
        }
        
        // Store reference for cleanup
        this._currentTooltip = tooltip;
    }

    /**
     * Hide event tooltip
     */
    _hideEventTooltip() {
        const tooltip = document.getElementById('event-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
        this._currentTooltip = null;
    }

    // Helper methods for time and position calculations
    _getTimeFromPosition(mouseEvent) {
        return CalendarUtils.getTimeFromPosition(mouseEvent, this);
    }

    _getTimeFromElement(element) {
        return CalendarUtils.extractTimeFromElement(element);
    }

    _getStaffFromElement(element) {
        return CalendarUtils.extractStaffFromElement(element);
    }

    _isValidDropTarget(start, end, staffId) {
        const constraints = {
            minDuration: 15, // 15 minutes minimum
            maxDuration: 12 * 60, // 12 hours maximum
            workingHours: {
                start: 6, // 6 AM
                end: 22   // 10 PM
            }
        };
        return CalendarUtils.isValidDropTarget(start, end, staffId, constraints);
    }

    _isConflictingElement(element, dropTarget) {
        const eventData = this._getEventDataFromElement(element);
        if (!eventData) return false;
        
        return CalendarUtils.timeRangesOverlap(
            eventData.start, eventData.end,
            dropTarget.start, dropTarget.end
        ) && eventData.staffId === dropTarget.staffId;
    }

    _updateResizePreview(newTime) {
        const event = this.dragState.draggedEvent;
        const direction = this.dragState.resizeDirection;
        
        // Snap to grid
        const snappedTime = CalendarUtils.snapTimeToGrid(newTime, this.dragConfig.gridSize);
        
        // Update visual preview
        const eventElement = this.el.querySelector(`[data-event-id="${event.id}"]`);
        if (!eventElement) return;
        
        // Calculate new dimensions
        let newStart = event.start;
        let newEnd = event.end;
        
        if (direction === 'start') {
            newStart = snappedTime;
        } else {
            newEnd = snappedTime;
        }
        
        // Validate and apply preview
        if (newEnd > newStart) {
            const duration = CalendarUtils.formatDuration(newStart, newEnd);
            this._showResizeTooltip(eventElement, duration);
        }
    }

    _getEventDataFromElement(element) {
        const eventId = element.getAttribute('data-event-id');
        if (!eventId) return null;
        
        // Find event in calendar data
        const events = this.model.data.records;
        return events.find(event => event.id == eventId);
    }

    _showResizeTooltip(element, duration) {
        const tooltip = document.getElementById('resize-tooltip') || document.createElement('div');
        tooltip.id = 'resize-tooltip';
        tooltip.className = 'o_availability_tooltip';
        tooltip.textContent = `Duration: ${duration}`;
        
        const rect = element.getBoundingClientRect();
        tooltip.style.left = (rect.left + rect.width / 2) + 'px';
        tooltip.style.top = (rect.top - 35) + 'px';
        
        if (!tooltip.parentNode) {
            document.body.appendChild(tooltip);
        }
    }

    _hideResizeTooltip() {
        const tooltip = document.getElementById('resize-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }
}

// Register the enhanced calendar controller
registry.category("views").add("staff_availability_calendar", {
    ...registry.category("views").get("calendar"),
    Controller: StaffAvailabilityCalendarController,
});