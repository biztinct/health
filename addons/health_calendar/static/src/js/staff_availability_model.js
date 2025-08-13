/** @odoo-module **/

import { CalendarModel } from "@web/views/calendar/calendar_model";
import { registry } from "@web/core/registry";

/**
 * Enhanced Calendar Model for Staff Availability
 * Integrates with staff assignment system and provides real-time updates
 */
export class StaffAvailabilityCalendarModel extends CalendarModel {
    
    setup(params, services) {
        super.setup(params, services);
        this.orm = services.orm;
        this.notification = services.notification;
        
        // Cache for performance optimization
        this.staffCache = new Map();
        this.conflictCache = new Map();
    }

    /**
     * Load calendar data with enhanced staff information
     */
    async load(params = {}) {
        const result = await super.load(params);
        
        // Enhance records with additional staff and assignment data
        await this._enhanceRecords();
        
        return result;
    }

    /**
     * Enhance records with staff information and assignment data
     */
    async _enhanceRecords() {
        const records = this.data.records;
        if (!records || records.length === 0) return;
        
        // Get unique staff IDs
        const staffIds = [...new Set(records.map(record => record.staff_id).filter(Boolean))];
        
        // Load staff information if not cached
        await this._loadStaffData(staffIds);
        
        // Enhance each record
        for (const record of records) {
            await this._enhanceRecord(record);
        }
    }

    /**
     * Load staff data and cache it
     */
    async _loadStaffData(staffIds) {
        const uncachedIds = staffIds.filter(id => !this.staffCache.has(id));
        
        if (uncachedIds.length === 0) return;
        
        try {
            const staffData = await this.orm.searchRead(
                'hr.employee',
                [['id', 'in', uncachedIds]],
                ['id', 'name', 'staff_code', 'healthcare_role', 'work_email', 'mobile_phone', 'primary_facility_id']
            );
            
            // Cache staff data
            staffData.forEach(staff => {
                this.staffCache.set(staff.id, staff);
            });
            
        } catch (error) {
            console.error('Error loading staff data:', error);
        }
    }

    /**
     * Enhance individual record with additional data
     */
    async _enhanceRecord(record) {
        // Add staff information
        if (record.staff_id && this.staffCache.has(record.staff_id)) {
            const staffData = this.staffCache.get(record.staff_id);
            record.extendedProps = {
                ...record.extendedProps,
                staff_name: staffData.name,
                staff_code: staffData.staff_code,
                staff_type: staffData.healthcare_role,
                staff_email: staffData.work_email,
                staff_mobile: staffData.mobile_phone,
                facility_name: staffData.primary_facility_id ? staffData.primary_facility_id[1] : null
            };
        }
        
        // Add status styling
        record.className = [
            ...(record.className || []),
            `o_availability_${record.status}`,
            `o_staff_${record.staff_id}`
        ];
        
        // Set event title with staff name and status
        const staffName = record.extendedProps?.staff_name || 'Unknown Staff';
        const status = record.status || 'available';
        record.title = `${staffName} - ${status.charAt(0).toUpperCase() + status.slice(1)}`;
        
        // Add data attributes for drag & drop
        record.extendedProps = {
            ...record.extendedProps,
            'data-event-id': record.id,
            'data-staff-id': record.staff_id,
            'data-status': record.status
        };
    }

    /**
     * Create new availability record with enhanced validation
     */
    async createRecord(record) {
        // Validate before creating
        const validation = await this._validateRecord(record);
        if (!validation.isValid) {
            throw new Error(validation.message);
        }
        
        // Check for conflicts
        const conflicts = await this._checkConflicts(record);
        if (conflicts.length > 0) {
            // Handle conflicts based on user preference
            const shouldContinue = await this._handleConflicts(conflicts);
            if (!shouldContinue) {
                throw new Error('Operation cancelled due to conflicts');
            }
        }
        
        const result = await super.createRecord(record);
        
        // Update assignment system if needed
        await this._updateAssignmentSystem(record, 'create');
        
        return result;
    }

    /**
     * Update availability record with enhanced validation
     */
    async updateRecord(record) {
        // Validate before updating
        const validation = await this._validateRecord(record);
        if (!validation.isValid) {
            throw new Error(validation.message);
        }
        
        // Check for conflicts
        const conflicts = await this._checkConflicts(record);
        if (conflicts.length > 0) {
            const shouldContinue = await this._handleConflicts(conflicts);
            if (!shouldContinue) {
                throw new Error('Operation cancelled due to conflicts');
            }
        }
        
        const result = await super.updateRecord(record);
        
        // Update assignment system
        await this._updateAssignmentSystem(record, 'update');
        
        // Clear relevant caches
        this._clearConflictCache(record.staff_id);
        
        return result;
    }

    /**
     * Delete availability record with assignment system integration
     */
    async unlinkRecord(record) {
        // Check if this availability is linked to any assignments
        const linkedAssignments = await this._getLinkedAssignments(record.id);
        
        if (linkedAssignments.length > 0) {
            const shouldContinue = await this._confirmDeletionWithAssignments(linkedAssignments);
            if (!shouldContinue) {
                throw new Error('Deletion cancelled - availability is linked to assignments');
            }
        }
        
        const result = await super.unlinkRecord(record);
        
        // Update assignment system
        await this._updateAssignmentSystem(record, 'delete');
        
        // Clear caches
        this._clearConflictCache(record.staff_id);
        
        return result;
    }

    /**
     * Validate availability record
     */
    async _validateRecord(record) {
        // Check required fields
        if (!record.staff_id) {
            return { isValid: false, message: 'Staff member is required' };
        }
        
        if (!record.availability_date || record.start_time === undefined || record.end_time === undefined) {
            return { isValid: false, message: 'Date and time slots are required' };
        }
        
        // Check time range
        if (record.end_time <= record.start_time) {
            return { isValid: false, message: 'End time must be after start time' };
        }
        
        // Convert to proper date objects for validation
        const startDate = new Date(`${record.availability_date} ${record.start_time}:00`);
        const endDate = new Date(`${record.availability_date} ${record.end_time}:00`);
        
        if (endDate <= startDate) {
            return { isValid: false, message: 'End date must be after start date' };
        }
        
        // Check minimum duration (15 minutes)
        const duration = (endDate - startDate) / (1000 * 60);
        if (duration < 15) {
            return { isValid: false, message: 'Minimum duration is 15 minutes' };
        }
        
        // Check maximum duration (24 hours)
        if (duration > 24 * 60) {
            return { isValid: false, message: 'Maximum duration is 24 hours' };
        }
        
        return { isValid: true };
    }

    /**
     * Check for scheduling conflicts
     */
    async _checkConflicts(record) {
        const cacheKey = `${record.staff_id}-${record.availability_date}-${record.start_time}-${record.end_time}`;
        
        if (this.conflictCache.has(cacheKey)) {
            return this.conflictCache.get(cacheKey);
        }
        
        try {
            const conflicts = await this.orm.searchRead(
                'health.staff.availability.matrix',
                [
                    ['staff_id', '=', record.staff_id],
                    ['id', '!=', record.id || 0],
                    ['availability_date', '=', record.availability_date],
                    '|',
                    '&', ['start_time', '<=', record.start_time], ['end_time', '>', record.start_time],
                    '&', ['start_time', '<', record.end_time], ['end_time', '>=', record.end_time]
                ],
                ['id', 'availability_date', 'start_time', 'end_time', 'status']
            );
            
            // Cache result for 30 seconds
            this.conflictCache.set(cacheKey, conflicts);
            setTimeout(() => this.conflictCache.delete(cacheKey), 30000);
            
            return conflicts;
            
        } catch (error) {
            console.error('Error checking conflicts:', error);
            return [];
        }
    }

    /**
     * Handle conflicts with user interaction
     */
    async _handleConflicts(conflicts) {
        // This would typically show a dialog to the user
        // For now, we'll log the conflicts and continue
        console.warn('Scheduling conflicts detected:', conflicts);
        return true; // Allow operation to continue
    }

    /**
     * Get assignments linked to an availability record
     */
    async _getLinkedAssignments(availabilityId) {
        try {
            return await this.orm.searchRead(
                'health.staff.assignment',
                [['assignment_id', '=', availabilityId]],
                ['id', 'name', 'state', 'assignment_date']
            );
        } catch (error) {
            console.error('Error getting linked assignments:', error);
            return [];
        }
    }

    /**
     * Confirm deletion when assignments are linked
     */
    async _confirmDeletionWithAssignments(assignments) {
        // This would typically show a confirmation dialog
        console.warn('Availability is linked to assignments:', assignments);
        return false; // Prevent deletion by default
    }

    /**
     * Update assignment system when availability changes
     */
    async _updateAssignmentSystem(record, operation) {
        try {
            // Trigger assignment recalculation for affected staff
            await this.orm.call(
                'health.staff.assignment.engine',
                'recalculate_staff_availability',
                [record.staff_id],
                {
                    availability_change: {
                        operation: operation,
                        record_id: record.id,
                        availability_date: record.availability_date,
                        start_time: record.start_time,
                        end_time: record.end_time,
                        status: record.status
                    }
                }
            );
        } catch (error) {
            console.error('Error updating assignment system:', error);
            // Don't fail the main operation if assignment update fails
        }
    }

    /**
     * Clear conflict cache for specific staff
     */
    _clearConflictCache(staffId) {
        const keysToDelete = [];
        for (const key of this.conflictCache.keys()) {
            if (key.startsWith(`${staffId}-`)) {
                keysToDelete.push(key);
            }
        }
        keysToDelete.forEach(key => this.conflictCache.delete(key));
    }

    /**
     * Get availability statistics for dashboard
     */
    async getAvailabilityStats(dateRange) {
        try {
            const stats = await this.orm.call(
                'health.staff.availability.matrix',
                'get_availability_summary',
                [],
                {
                    date_from: dateRange.start,
                    date_to: dateRange.end
                }
            );
            
            return stats;
        } catch (error) {
            console.error('Error getting availability stats:', error);
            return null;
        }
    }

    /**
     * Generate optimal schedule suggestions
     */
    async generateScheduleSuggestions(staffId, preferences = {}) {
        try {
            const suggestions = await this.orm.call(
                'health.staff.assignment.engine',
                'generate_availability_suggestions',
                [staffId],
                {
                    preferences: preferences,
                    date_range: {
                        start: this.data.range.start,
                        end: this.data.range.end
                    }
                }
            );
            
            return suggestions;
        } catch (error) {
            console.error('Error generating schedule suggestions:', error);
            return [];
        }
    }
}

// Register the enhanced model
registry.category("views").add("staff_availability_calendar_model", StaffAvailabilityCalendarModel);