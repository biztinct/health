/** @odoo-module **/

/**
 * Calendar Utilities for Advanced Drag & Drop Functionality
 * Helper functions for time calculations, conflict detection, and UI interactions
 */

export class CalendarUtils {
    /**
     * Convert mouse position to calendar time
     */
    static getTimeFromPosition(mouseEvent, calendarView) {
        const calendarEl = calendarView.el;
        const rect = calendarEl.getBoundingClientRect();
        
        // Get relative position within calendar
        const relativeX = mouseEvent.clientX - rect.left;
        const relativeY = mouseEvent.clientY - rect.top;
        
        // Find the time slot element at this position
        const timeSlot = document.elementFromPoint(mouseEvent.clientX, mouseEvent.clientY);
        if (!timeSlot) return null;
        
        // Extract time from FullCalendar data attributes or classes
        const timeSlotParent = timeSlot.closest('[data-time], .fc-timegrid-slot, .fc-daygrid-day');
        if (!timeSlotParent) return null;
        
        return this.extractTimeFromElement(timeSlotParent);
    }
    
    /**
     * Extract time information from calendar element
     */
    static extractTimeFromElement(element) {
        // Try data-time attribute first (FullCalendar standard)
        if (element.dataset.time) {
            return new Date(element.dataset.time);
        }
        
        // Try to extract from classes or other attributes
        const dateAttr = element.getAttribute('data-date');
        const timeAttr = element.getAttribute('data-time');
        
        if (dateAttr) {
            if (timeAttr) {
                return new Date(`${dateAttr}T${timeAttr}`);
            } else {
                return new Date(dateAttr);
            }
        }
        
        // For timegrid slots, try to calculate from position
        if (element.classList.contains('fc-timegrid-slot')) {
            return this.calculateTimeFromSlot(element);
        }
        
        return null;
    }
    
    /**
     * Calculate time from timegrid slot position
     */
    static calculateTimeFromSlot(slotElement) {
        const timeCol = slotElement.closest('.fc-timegrid-col');
        if (!timeCol) return null;
        
        const dateAttr = timeCol.getAttribute('data-date');
        if (!dateAttr) return null;
        
        // Find all slots in this column
        const allSlots = timeCol.querySelectorAll('.fc-timegrid-slot');
        const slotIndex = Array.from(allSlots).indexOf(slotElement);
        
        if (slotIndex === -1) return null;
        
        // Calculate time based on slot index (assuming 30-minute slots)
        const startHour = 0; // Usually starts at midnight or configured start time
        const slotDuration = 30; // minutes per slot
        
        const totalMinutes = startHour * 60 + (slotIndex * slotDuration);
        const hour = Math.floor(totalMinutes / 60);
        const minute = totalMinutes % 60;
        
        const date = new Date(dateAttr);
        date.setHours(hour, minute, 0, 0);
        
        return date;
    }
    
    /**
     * Extract staff ID from calendar element
     */
    static extractStaffFromElement(element) {
        // For resource-based calendars
        const resourceEl = element.closest('[data-resource-id]');
        if (resourceEl) {
            return parseInt(resourceEl.dataset.resourceId);
        }
        
        // For single-staff calendars, return current staff
        const calendarEl = element.closest('.o_staff_availability_calendar');
        if (calendarEl && calendarEl.dataset.staffId) {
            return parseInt(calendarEl.dataset.staffId);
        }
        
        return null;
    }
    
    /**
     * Snap time to grid intervals
     */
    static snapTimeToGrid(time, gridSizeMinutes = 15) {
        const totalMinutes = time.getHours() * 60 + time.getMinutes();
        const snappedMinutes = Math.round(totalMinutes / gridSizeMinutes) * gridSizeMinutes;
        
        const snappedTime = new Date(time);
        snappedTime.setHours(Math.floor(snappedMinutes / 60), snappedMinutes % 60, 0, 0);
        
        return snappedTime;
    }
    
    /**
     * Check if two time ranges overlap
     */
    static timeRangesOverlap(start1, end1, start2, end2) {
        return start1 < end2 && start2 < end1;
    }
    
    /**
     * Format time duration for display
     */
    static formatDuration(start, end) {
        const diffMs = end - start;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        
        if (diffMinutes < 60) {
            return `${diffMinutes}m`;
        } else {
            const hours = Math.floor(diffMinutes / 60);
            const remainingMinutes = diffMinutes % 60;
            return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
        }
    }
    
    /**
     * Format time for display
     */
    static formatTime(date, use24Hour = true) {
        return date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            hour12: !use24Hour
        });
    }
    
    /**
     * Check if drop target is valid
     */
    static isValidDropTarget(start, end, staffId, constraints = {}) {
        // Check minimum duration
        if (constraints.minDuration) {
            const duration = end - start;
            if (duration < constraints.minDuration * 60 * 1000) {
                return false;
            }
        }
        
        // Check maximum duration
        if (constraints.maxDuration) {
            const duration = end - start;
            if (duration > constraints.maxDuration * 60 * 1000) {
                return false;
            }
        }
        
        // Check working hours
        if (constraints.workingHours) {
            const startHour = start.getHours() + (start.getMinutes() / 60);
            const endHour = end.getHours() + (end.getMinutes() / 60);
            
            if (startHour < constraints.workingHours.start || endHour > constraints.workingHours.end) {
                return false;
            }
        }
        
        // Check if staff is available
        if (constraints.staffAvailability && staffId) {
            // This would typically check against staff working schedule
            // Implementation depends on staff availability data structure
        }
        
        return true;
    }
    
    /**
     * Create visual feedback element
     */
    static createFeedbackElement(type, message) {
        const element = document.createElement('div');
        element.className = `o_calendar_feedback o_feedback_${type}`;
        element.textContent = message;
        
        element.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: feedbackSlideIn 0.3s ease-out;
        `;
        
        switch (type) {
            case 'success':
                element.style.background = 'var(--success)';
                break;
            case 'error':
                element.style.background = 'var(--danger)';
                break;
            case 'warning':
                element.style.background = 'var(--warning)';
                break;
            default:
                element.style.background = 'var(--info)';
        }
        
        document.body.appendChild(element);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            element.style.animation = 'feedbackSlideOut 0.3s ease-in forwards';
            setTimeout(() => element.remove(), 300);
        }, 3000);
        
        return element;
    }
    
    /**
     * Calculate optimal event positioning to avoid overlaps
     */
    static calculateEventPosition(events, newEvent) {
        const overlapping = events.filter(event => 
            this.timeRangesOverlap(
                event.start, event.end,
                newEvent.start, newEvent.end
            )
        );
        
        if (overlapping.length === 0) {
            return { left: 0, width: 100 };
        }
        
        // Calculate column layout for overlapping events
        const columns = this.calculateEventColumns(overlapping.concat(newEvent));
        const eventColumn = columns.find(col => col.events.includes(newEvent));
        
        return {
            left: (eventColumn.index / columns.length) * 100,
            width: 100 / columns.length
        };
    }
    
    /**
     * Calculate column layout for overlapping events
     */
    static calculateEventColumns(events) {
        const sortedEvents = events.sort((a, b) => a.start - b.start);
        const columns = [];
        
        sortedEvents.forEach(event => {
            let placed = false;
            
            // Try to place in existing column
            for (let col of columns) {
                const lastEvent = col.events[col.events.length - 1];
                if (lastEvent.end <= event.start) {
                    col.events.push(event);
                    placed = true;
                    break;
                }
            }
            
            // Create new column if needed
            if (!placed) {
                columns.push({
                    index: columns.length,
                    events: [event]
                });
            }
        });
        
        return columns;
    }
    
    /**
     * Debounce function for performance optimization
     */
    static debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    }
    
    /**
     * Throttle function for performance optimization
     */
    static throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    /**
     * Generate unique ID for drag operations
     */
    static generateId() {
        return Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Deep clone object
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== "object") return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === "object") {
            const clonedObj = {};
            for (let key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = this.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    }
}