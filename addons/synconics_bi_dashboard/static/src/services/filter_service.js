/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Dashboard Cross-Filtering Service
 *
 * Manages shared filter state across all charts on a dashboard.
 * Allows charts to publish filters when clicked and subscribe to filter changes.
 *
 * Architecture:
 * - Reactive filter state using OWL reactive()
 * - Publisher-Subscriber pattern for chart communication
 * - Converts filter state to Odoo domain format
 * - Provides visual filter pills UI data
 */
export class DashboardFilterService {
    constructor() {
        // Reactive filter state: { chartId: { field, label, values, model } }
        this.filterState = reactive({});

        // Subscribers are notified when filters change
        this.subscribers = new Set();

        // Track filter metadata for display
        this.filterMetadata = reactive({});

        // Date filter state (dashboard-level)
        this.dateFilterState = reactive({
            active: false,
            startDate: null,
            endDate: null,
        });
    }

    /**
     * Apply a filter from a chart click
     * @param {string} chartId - ID of the chart applying the filter
     * @param {string} field - Field name being filtered
     * @param {string} label - Human-readable label for the filter
     * @param {array} values - Array of values to filter by
     * @param {string} model - Model name for the filter
     * @param {string} chartType - Type of chart (for UI display)
     */
    applyFilter(chartId, field, label, values, model, chartType = 'chart') {
        console.log('[FilterService] Applying filter:', { chartId, field, label, values, model });

        // Ensure values is an array
        if (!Array.isArray(values)) {
            values = [values];
        }

        // Store filter in state
        this.filterState[chartId] = {
            field,
            label,
            values,
            model,
            chartType,
            timestamp: Date.now(),
        };

        // Update metadata for UI display
        this.filterMetadata[chartId] = {
            chartName: label,
            fieldName: field,
            valueCount: values.length,
            displayValue: this._getDisplayValue(values),
        };

        // Notify all subscribers
        this.notifySubscribers();
    }

    /**
     * Clear a specific filter
     * @param {string} chartId - ID of the chart whose filter to clear
     */
    clearFilter(chartId) {
        console.log('[FilterService] Clearing filter:', chartId);
        delete this.filterState[chartId];
        delete this.filterMetadata[chartId];
        this.notifySubscribers();
    }

    /**
     * Clear all active filters
     */
    clearAllFilters() {
        console.log('[FilterService] Clearing all filters');
        Object.keys(this.filterState).forEach(chartId => {
            delete this.filterState[chartId];
            delete this.filterMetadata[chartId];
        });
        this.notifySubscribers();
    }

    /**
     * Apply dashboard-level date filter
     * @param {string} startDate - Start date (YYYY-MM-DD)
     * @param {string} endDate - End date (YYYY-MM-DD)
     */
    applyDateFilter(startDate, endDate) {
        console.log('[FilterService] Applying date filter:', { startDate, endDate });

        this.dateFilterState.active = true;
        this.dateFilterState.startDate = startDate;
        this.dateFilterState.endDate = endDate;

        // Notify all subscribers
        this.notifySubscribers();
    }

    /**
     * Clear dashboard-level date filter
     */
    clearDateFilter() {
        console.log('[FilterService] Clearing date filter');
        this.dateFilterState.active = false;
        this.dateFilterState.startDate = null;
        this.dateFilterState.endDate = null;

        // Notify all subscribers
        this.notifySubscribers();
    }

    /**
     * Check if date filter is active
     * @returns {boolean}
     */
    hasActiveDateFilter() {
        return this.dateFilterState.active;
    }

    /**
     * Get date filter state
     * @returns {object} Date filter state { active, startDate, endDate }
     */
    getDateFilterState() {
        return {
            active: this.dateFilterState.active,
            startDate: this.dateFilterState.startDate,
            endDate: this.dateFilterState.endDate,
        };
    }

    /**
     * Get active filters as Odoo domain
     * Combines all active filters with AND logic
     * @returns {array} Odoo domain array
     */
    getActiveDomain() {
        const domains = [];

        for (const [chartId, filter] of Object.entries(this.filterState)) {
            if (filter.values && filter.values.length > 0) {
                // For single value: ('field', '=', value)
                // For multiple values: ('field', 'in', [values])
                if (filter.values.length === 1) {
                    domains.push([filter.field, '=', filter.values[0]]);
                } else {
                    domains.push([filter.field, 'in', filter.values]);
                }
            }
        }

        console.log('[FilterService] Active domain:', domains);
        return domains;
    }

    /**
     * Get active filters for a specific model
     * @param {string} model - Model name to filter by
     * @returns {array} Odoo domain array for the specified model
     */
    getActiveDomainForModel(model) {
        const domains = [];

        for (const [chartId, filter] of Object.entries(this.filterState)) {
            // Only include filters for the specified model
            if (filter.model === model && filter.values && filter.values.length > 0) {
                if (filter.values.length === 1) {
                    domains.push([filter.field, '=', filter.values[0]]);
                } else {
                    domains.push([filter.field, 'in', filter.values]);
                }
            }
        }

        return domains;
    }

    /**
     * Check if any filters are active
     * @returns {boolean}
     */
    hasActiveFilters() {
        return Object.keys(this.filterState).length > 0;
    }

    /**
     * Get count of active filters
     * @returns {number}
     */
    getActiveFilterCount() {
        return Object.keys(this.filterState).length;
    }

    /**
     * Get all active filter metadata for UI display
     * @returns {array} Array of filter display objects
     */
    getActiveFiltersForDisplay() {
        return Object.entries(this.filterMetadata).map(([chartId, meta]) => ({
            chartId,
            ...meta,
        }));
    }

    /**
     * Subscribe to filter changes
     * @param {function} callback - Function to call when filters change
     * @returns {function} Unsubscribe function
     */
    subscribe(callback) {
        this.subscribers.add(callback);
        console.log('[FilterService] Subscriber added, total:', this.subscribers.size);

        // Return unsubscribe function
        return () => {
            this.subscribers.delete(callback);
            console.log('[FilterService] Subscriber removed, total:', this.subscribers.size);
        };
    }

    /**
     * Notify all subscribers of filter changes
     */
    notifySubscribers() {
        console.log('[FilterService] Notifying', this.subscribers.size, 'subscribers');
        const domain = this.getActiveDomain();
        const filterCount = this.getActiveFilterCount();
        const dateFilter = this.getDateFilterState();

        this.subscribers.forEach(callback => {
            try {
                callback({
                    domain,
                    filterCount,
                    filters: this.filterState,
                    metadata: this.filterMetadata,
                    dateFilter: dateFilter,
                });
            } catch (error) {
                console.error('[FilterService] Error notifying subscriber:', error);
            }
        });
    }

    /**
     * Get display value for filter pill (truncate if too long)
     * @private
     */
    _getDisplayValue(values) {
        if (!values || values.length === 0) {
            return '';
        }

        if (values.length === 1) {
            const val = String(values[0]);
            return val.length > 30 ? val.substring(0, 27) + '...' : val;
        }

        return `${values.length} values`;
    }

    /**
     * Check if a specific chart has an active filter
     * @param {string} chartId
     * @returns {boolean}
     */
    hasFilterForChart(chartId) {
        return chartId in this.filterState;
    }

    /**
     * Get filter for a specific chart
     * @param {string} chartId
     * @returns {object|null}
     */
    getFilterForChart(chartId) {
        return this.filterState[chartId] || null;
    }
}

// Create singleton instance
const filterServiceInstance = new DashboardFilterService();

// Register as Odoo service
export const filterService = {
    dependencies: [],
    start() {
        return filterServiceInstance;
    },
};

registry.category("services").add("dashboardFilterService", filterService);
