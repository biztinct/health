/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * FilterPills Component
 *
 * Displays active cross-filters as pills with ability to remove individual
 * filters or clear all filters at once.
 *
 * Features:
 * - Visual indication of active filters
 * - Click to remove individual filters
 * - "Clear All" button when multiple filters active
 * - Responsive layout
 */
export class FilterPills extends Component {
    static template = "synconics_bi_dashboard.FilterPills";
    static props = {};

    setup() {
        this.filterService = useService("dashboardFilterService");

        this.state = useState({
            activeFilters: [],
            filterCount: 0,
            hasDateFilter: false,
            dateFilterLabel: '',
        });

        // Subscribe to filter changes
        this.unsubscribe = null;

        onWillStart(() => {
            this.updateFilterDisplay();

            // Subscribe to filter service
            this.unsubscribe = this.filterService.subscribe(() => {
                this.updateFilterDisplay();
            });
        });

        onWillUnmount(() => {
            if (this.unsubscribe) {
                this.unsubscribe();
            }
        });
    }

    /**
     * Update filter display from service
     */
    updateFilterDisplay() {
        this.state.activeFilters = this.filterService.getActiveFiltersForDisplay();
        const crossFilterCount = this.filterService.getActiveFilterCount();

        // Check for date filter
        const dateFilter = this.filterService.getDateFilterState();
        this.state.hasDateFilter = dateFilter.active;

        if (dateFilter.active) {
            // Format date range for display
            const startDate = this.formatDateForDisplay(dateFilter.startDate);
            const endDate = this.formatDateForDisplay(dateFilter.endDate);
            this.state.dateFilterLabel = startDate === endDate ? startDate : `${startDate} - ${endDate}`;
        }

        // Total count includes cross-filters + date filter (if active)
        this.state.filterCount = crossFilterCount + (dateFilter.active ? 1 : 0);
    }

    /**
     * Format date for display
     */
    formatDateForDisplay(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    /**
     * Remove a specific filter
     */
    onRemoveFilter(chartId) {
        this.filterService.clearFilter(chartId);
    }

    /**
     * Clear all filters (both cross-filters and date filter)
     */
    onClearAll() {
        this.filterService.clearAllFilters();
        this.filterService.clearDateFilter();
    }

    /**
     * Remove date filter
     */
    onRemoveDateFilter() {
        this.filterService.clearDateFilter();
    }
}
