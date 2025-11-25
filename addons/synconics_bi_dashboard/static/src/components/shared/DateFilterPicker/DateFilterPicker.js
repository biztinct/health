/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * DateFilterPicker Component
 *
 * Provides a visual date range picker for dashboard-level date filtering.
 * Applies filters to each chart's configured date_filter_field_id.
 *
 * Features:
 * - Quick filter options (Today, This Week, Last Month, etc.)
 * - Custom date range selection with visual calendar
 * - Clear filters
 * - Integration with filter service
 */
export class DateFilterPicker extends Component {
    static template = "synconics_bi_dashboard.DateFilterPicker";
    static props = {};

    setup() {
        this.filterService = useService("dashboardFilterService");

        this.state = useState({
            showPicker: false,
            startDate: null,
            endDate: null,
            activeQuickFilter: null,
            dateFilterLabel: 'All Time',
        });

        this.startDateRef = useRef("startDate");
        this.endDateRef = useRef("endDate");

        // Subscribe to filter changes to update active state
        this.unsubscribe = null;
        onWillStart(() => {
            this.unsubscribe = this.filterService.subscribe(() => {
                const dateFilter = this.filterService.getDateFilterState();
                if (!dateFilter.active) {
                    this.state.activeQuickFilter = null;
                    this.state.dateFilterLabel = 'All Time';
                }
            });
        });

        onWillUnmount(() => {
            if (this.unsubscribe) {
                this.unsubscribe();
            }
        });
    }

    /**
     * Quick filter options
     */
    get quickFilters() {
        return [
            { id: 'today', label: 'Today', icon: 'fa-calendar-day' },
            { id: 'this_week', label: 'This Week', icon: 'fa-calendar-week' },
            { id: 'this_month', label: 'This Month', icon: 'fa-calendar' },
            { id: 'this_quarter', label: 'This Quarter', icon: 'fa-calendar-alt' },
            { id: 'this_year', label: 'This Year', icon: 'fa-calendar-check' },
            { id: 'last_7_days', label: 'Last 7 Days', icon: 'fa-clock' },
            { id: 'last_30_days', label: 'Last 30 Days', icon: 'fa-clock' },
            { id: 'last_quarter', label: 'Last Quarter', icon: 'fa-history' },
            { id: 'last_year', label: 'Last Year', icon: 'fa-history' },
            { id: 'custom', label: 'Custom Range', icon: 'fa-calendar-plus' },
        ];
    }

    /**
     * Quick access buttons (most commonly used filters)
     */
    get quickAccessButtons() {
        return [
            { id: 'today', label: 'Today' },
            { id: 'this_week', label: 'This Week' },
            { id: 'this_month', label: 'This Month' },
            { id: 'this_year', label: 'This Year' },
            { id: 'last_year', label: 'Last Year' },
        ];
    }

    /**
     * Toggle date picker dropdown
     */
    togglePicker() {
        this.state.showPicker = !this.state.showPicker;
    }

    /**
     * Apply quick filter
     */
    onQuickFilter(filterId, applyImmediately = false) {
        const dateRange = this.calculateDateRange(filterId);

        if (filterId === 'custom') {
            // Show custom date inputs
            this.state.activeQuickFilter = 'custom';
            return;
        }

        this.state.activeQuickFilter = filterId;
        this.state.startDate = dateRange.start;
        this.state.endDate = dateRange.end;
        this.state.dateFilterLabel = this.quickFilters.find(f => f.id === filterId).label;

        // If applyImmediately is true (from quick button), apply the filter right away
        if (applyImmediately) {
            this.onApplyFilter();
        }
    }

    /**
     * Calculate date range based on quick filter
     */
    calculateDateRange(filterId) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        let start = new Date(today);
        let end = new Date(today);
        end.setHours(23, 59, 59, 999);

        switch(filterId) {
            case 'today':
                // start and end already set to today
                break;

            case 'this_week':
                // Start of week (Monday)
                const dayOfWeek = today.getDay();
                const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
                start.setDate(today.getDate() + diffToMonday);
                // End of week (Sunday)
                end.setDate(start.getDate() + 6);
                break;

            case 'this_month':
                start.setDate(1);
                end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                end.setHours(23, 59, 59, 999);
                break;

            case 'this_quarter':
                const currentQuarter = Math.floor(today.getMonth() / 3);
                start = new Date(today.getFullYear(), currentQuarter * 3, 1);
                end = new Date(today.getFullYear(), currentQuarter * 3 + 3, 0);
                end.setHours(23, 59, 59, 999);
                break;

            case 'this_year':
                start = new Date(today.getFullYear(), 0, 1);
                end = new Date(today.getFullYear(), 11, 31);
                end.setHours(23, 59, 59, 999);
                break;

            case 'last_7_days':
                start.setDate(today.getDate() - 6);
                break;

            case 'last_30_days':
                start.setDate(today.getDate() - 29);
                break;

            case 'last_quarter':
                const lastQuarter = Math.floor(today.getMonth() / 3) - 1;
                const year = lastQuarter < 0 ? today.getFullYear() - 1 : today.getFullYear();
                const quarter = lastQuarter < 0 ? 3 : lastQuarter;
                start = new Date(year, quarter * 3, 1);
                end = new Date(year, quarter * 3 + 3, 0);
                end.setHours(23, 59, 59, 999);
                break;

            case 'last_year':
                start = new Date(today.getFullYear() - 1, 0, 1);
                end = new Date(today.getFullYear() - 1, 11, 31);
                end.setHours(23, 59, 59, 999);
                break;
        }

        return {
            start: this.formatDateForInput(start),
            end: this.formatDateForInput(end),
        };
    }

    /**
     * Format date for input field (YYYY-MM-DD)
     */
    formatDateForInput(date) {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
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
     * Handle start date change
     */
    onStartDateChange(ev) {
        this.state.startDate = ev.target.value;
        this.state.activeQuickFilter = 'custom';
    }

    /**
     * Handle end date change
     */
    onEndDateChange(ev) {
        this.state.endDate = ev.target.value;
        this.state.activeQuickFilter = 'custom';
    }

    /**
     * Apply date filter
     */
    onApplyFilter() {
        if (!this.state.startDate || !this.state.endDate) {
            // Show validation message
            console.warn('[DateFilterPicker] Please select both start and end dates');
            return;
        }

        // Validate date range
        if (new Date(this.state.startDate) > new Date(this.state.endDate)) {
            console.warn('[DateFilterPicker] Start date must be before end date');
            return;
        }

        // Update label
        if (this.state.activeQuickFilter && this.state.activeQuickFilter !== 'custom') {
            this.state.dateFilterLabel = this.quickFilters.find(f => f.id === this.state.activeQuickFilter).label;
        } else {
            this.state.dateFilterLabel = `${this.formatDateForDisplay(this.state.startDate)} - ${this.formatDateForDisplay(this.state.endDate)}`;
        }

        console.log('[DateFilterPicker] Applying date filter:', {
            startDate: this.state.startDate,
            endDate: this.state.endDate,
            label: this.state.dateFilterLabel
        });

        // Apply date filter through service
        this.filterService.applyDateFilter(this.state.startDate, this.state.endDate);

        // Close picker
        this.state.showPicker = false;
    }

    /**
     * Clear date filter
     */
    onClearFilter() {
        this.state.startDate = null;
        this.state.endDate = null;
        this.state.activeQuickFilter = null;
        this.state.dateFilterLabel = 'All Time';

        // Clear date filter through service
        this.filterService.clearDateFilter();

        // Close picker
        this.state.showPicker = false;
    }

    /**
     * Close picker when clicking outside
     */
    onClickOutside(ev) {
        if (!ev.target.closest('.o_date_filter_picker') && !ev.target.closest('.o_date_filter_button')) {
            this.state.showPicker = false;
        }
    }
}
