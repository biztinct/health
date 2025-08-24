/**
 * VAFHS Healthcare - Visual Assignment Scheduler Grid JavaScript (Odoo 18)
 * Google Calendar meets When2meet for Healthcare Staff Assignment
 * Advanced Drag-and-Drop Time Grid Interface using OWL Framework
 */

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ============================================================================
// Visual Scheduler Grid Utilities (Odoo 18)
// ============================================================================

/**
 * Time slot utilities for the visual scheduler
 */
export class SchedulerGridUtils {
    
    /**
     * Generate time slots for the day
     */
    static generateTimeSlots(startHour = 8, endHour = 18, intervalMinutes = 30) {
        const slots = [];
        for (let hour = startHour; hour < endHour; hour++) {
            for (let minute = 0; minute < 60; minute += intervalMinutes) {
                const timeString = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                slots.push({
                    hour,
                    minute,
                    timeString,
                    id: `slot_${hour}_${minute}`
                });
            }
        }
        return slots;
    }

    /**
     * Format time slot for display
     */
    static formatTimeSlot(hour, minute) {
        const period = hour >= 12 ? 'PM' : 'AM';
        const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
        return minute === 0 
            ? `${displayHour} ${period}`
            : `${displayHour}:${minute.toString().padStart(2, '0')} ${period}`;
    }

    /**
     * Get CSS class for assignment priority
     */
    static getAssignmentPriorityClass(priority) {
        const priorityClasses = {
            'low': 'assignment-priority-low',
            'normal': 'assignment-priority-normal', 
            'high': 'assignment-priority-high',
            'urgent': 'assignment-priority-urgent'
        };
        return priorityClasses[priority] || 'assignment-priority-normal';
    }

    /**
     * Calculate assignment block position and size
     */
    static calculateAssignmentPosition(startTime, durationMinutes, slotHeight = 30) {
        const [startHour, startMinute] = startTime.split(':').map(Number);
        const totalStartMinutes = (startHour - 8) * 60 + startMinute; // Assuming 8 AM start
        const slotMinutes = 30; // Each slot is 30 minutes
        
        const topPosition = (totalStartMinutes / slotMinutes) * slotHeight;
        const blockHeight = (durationMinutes / slotMinutes) * slotHeight;
        
        return {
            top: `${topPosition}px`,
            height: `${Math.max(blockHeight, slotHeight)}px`
        };
    }

    /**
     * Get staff availability status
     */
    static getStaffAvailabilityClass(status) {
        const statusClasses = {
            'available': 'staff-available',
            'busy': 'staff-busy',
            'booked': 'staff-booked',
            'off_duty': 'staff-off-duty'
        };
        return statusClasses[status] || 'staff-unknown';
    }

    /**
     * Handle drag and drop positioning
     */
    static calculateDropPosition(event, gridContainer) {
        const rect = gridContainer.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        // Calculate time slot and staff column
        const slotHeight = 30;
        const staffColumnWidth = 200;
        
        const timeSlot = Math.floor(y / slotHeight);
        const staffColumn = Math.floor(x / staffColumnWidth);
        
        return {
            timeSlot,
            staffColumn,
            x,
            y
        };
    }

    /**
     * Create draggable assignment element
     */
    static createDraggableAssignment(assignmentData) {
        const element = document.createElement('div');
        element.className = `assignment-block draggable ${this.getAssignmentPriorityClass(assignmentData.priority)}`;
        element.draggable = true;
        element.dataset.assignmentId = assignmentData.id;
        
        const position = this.calculateAssignmentPosition(
            assignmentData.start_time, 
            assignmentData.duration_minutes
        );
        
        element.style.top = position.top;
        element.style.height = position.height;
        
        element.innerHTML = `
            <div class="assignment-content">
                <div class="assignment-patient">${assignmentData.patient_name}</div>
                <div class="assignment-service">${assignmentData.service_type}</div>
                <div class="assignment-time">${assignmentData.start_time}</div>
            </div>
        `;
        
        return element;
    }

    /**
     * Initialize drag and drop for the scheduler grid
     */
    static initializeDragAndDrop(gridContainer, callbacks = {}) {
        // Add drag event listeners
        gridContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            const dropPosition = this.calculateDropPosition(e, gridContainer);
            callbacks.onDragOver?.(e, dropPosition);
        });

        gridContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            const assignmentId = e.dataTransfer.getData('text/plain');
            const dropPosition = this.calculateDropPosition(e, gridContainer);
            callbacks.onDrop?.(e, assignmentId, dropPosition);
        });

        // Handle draggable elements
        gridContainer.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('draggable')) {
                e.dataTransfer.setData('text/plain', e.target.dataset.assignmentId);
                e.dataTransfer.effectAllowed = 'move';
                callbacks.onDragStart?.(e);
            }
        });

        gridContainer.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('draggable')) {
                callbacks.onDragEnd?.(e);
            }
        });
    }
}

// ============================================================================
// Date Navigation Utilities
// ============================================================================

export class DateNavigationUtils {
    
    /**
     * Get week dates starting from Monday
     */
    static getWeekDates(baseDate = new Date()) {
        const startOfWeek = new Date(baseDate);
        const day = startOfWeek.getDay();
        const diff = startOfWeek.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
        startOfWeek.setDate(diff);
        
        const weekDates = [];
        for (let i = 0; i < 7; i++) {
            const date = new Date(startOfWeek);
            date.setDate(startOfWeek.getDate() + i);
            weekDates.push({
                date: date,
                dayName: date.toLocaleDateString('en-US', { weekday: 'short' }),
                dayNumber: date.getDate(),
                isToday: this.isToday(date)
            });
        }
        
        return weekDates;
    }

    /**
     * Check if date is today
     */
    static isToday(date) {
        const today = new Date();
        return date.toDateString() === today.toDateString();
    }

    /**
     * Format date for display
     */
    static formatDate(date, format = 'short') {
        const options = {
            'short': { month: 'short', day: 'numeric' },
            'long': { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' },
            'time': { hour: '2-digit', minute: '2-digit' }
        };
        
        return date.toLocaleDateString('en-US', options[format]);
    }

    /**
     * Navigate to previous/next week
     */
    static navigateWeek(currentDate, direction) {
        const newDate = new Date(currentDate);
        newDate.setDate(newDate.getDate() + (direction === 'prev' ? -7 : 7));
        return newDate;
    }
}

// Register utilities for global use
registry.category("scheduler_utils").add("grid", SchedulerGridUtils);
registry.category("scheduler_utils").add("dates", DateNavigationUtils);