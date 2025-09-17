/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FilterPanel extends Component {
    
    setup() {
        this.notification = useService("notification");
        
        this.state = useState({
            filters: this.props.model.getFilters() || {},
            activeFilters: [],
            searchText: '',
            dateRange: {
                from: null,
                to: null
            }
        });
    }

    // ===================
    // Filter Management
    // ===================

    getAvailableFilters() {
        // Get filters from all datasets used in dashboard
        const datasets = Object.values(this.props.model.getDatasets());
        const filters = [];
        
        for (const dataset of datasets) {
            if (dataset.metadata && dataset.metadata.fields) {
                // Add dimension fields as filters
                for (const field of dataset.metadata.fields.dimensions || []) {
                    filters.push({
                        id: `${dataset.id}_${field.id}`,
                        name: field.name,
                        label: field.label,
                        type: 'selection',
                        dataset: dataset.name,
                        field_type: field.type,
                        options: [] // Will be populated dynamically
                    });
                }
                
                // Add date fields as date range filters
                for (const field of dataset.metadata.fields.dates || []) {
                    filters.push({
                        id: `${dataset.id}_${field.id}`,
                        name: field.name,
                        label: field.label,
                        type: 'date_range',
                        dataset: dataset.name,
                        field_type: field.type
                    });
                }
                
                // Add measure fields as numeric range filters
                for (const field of dataset.metadata.fields.measures || []) {
                    filters.push({
                        id: `${dataset.id}_${field.id}`,
                        name: field.name,
                        label: field.label,
                        type: 'numeric_range',
                        dataset: dataset.name,
                        field_type: field.type
                    });
                }
            }
        }
        
        return filters;
    }

    getFiltersByType(filterType) {
        return this.getAvailableFilters().filter(f => f.type === filterType);
    }

    getActiveFilters() {
        const allFilters = this.getAvailableFilters();
        return allFilters.filter(f => this.state.filters[f.id] !== undefined);
    }

    // ===================
    // Filter Operations
    // ===================

    async addFilter(filterId) {
        const filter = this.getAvailableFilters().find(f => f.id === filterId);
        if (!filter) return;
        
        // Initialize filter with default value
        let defaultValue;
        switch (filter.type) {
            case 'selection':
                defaultValue = [];
                break;
            case 'date_range':
                defaultValue = { from: null, to: null };
                break;
            case 'numeric_range':
                defaultValue = { min: null, max: null };
                break;
            default:
                defaultValue = '';
        }
        
        this.state.filters[filterId] = defaultValue;
        await this._updateFilters();
    }

    async removeFilter(filterId) {
        delete this.state.filters[filterId];
        await this._updateFilters();
    }

    async updateFilterValue(filterId, value) {
        this.state.filters[filterId] = value;
        await this._updateFilters();
    }

    async clearAllFilters() {
        this.state.filters = {};
        this.state.searchText = '';
        this.state.dateRange = { from: null, to: null };
        await this._updateFilters();
    }

    async _updateFilters() {
        try {
            // Apply filters through the model
            await this.props.onFilterChange('dashboard_filters', this.state.filters);
            
            this.notification.add(_t("Filters applied"), { type: 'success' });
        } catch (error) {
            console.error('Error applying filters:', error);
            this.notification.add(_t("Error applying filters"), { type: 'danger' });
        }
    }

    // ===================
    // Quick Filters
    // ===================

    getQuickFilters() {
        return [
            {
                id: 'today',
                label: _t('Today'),
                icon: 'fa-calendar-day',
                action: () => this.applyDateFilter('today')
            },
            {
                id: 'this_week',
                label: _t('This Week'),
                icon: 'fa-calendar-week',
                action: () => this.applyDateFilter('this_week')
            },
            {
                id: 'this_month',
                label: _t('This Month'),
                icon: 'fa-calendar',
                action: () => this.applyDateFilter('this_month')
            },
            {
                id: 'this_quarter',
                label: _t('This Quarter'),
                icon: 'fa-calendar-alt',
                action: () => this.applyDateFilter('this_quarter')
            },
            {
                id: 'this_year',
                label: _t('This Year'),
                icon: 'fa-calendar-check',
                action: () => this.applyDateFilter('this_year')
            },
            {
                id: 'last_30_days',
                label: _t('Last 30 Days'),
                icon: 'fa-calendar-minus',
                action: () => this.applyDateFilter('last_30_days')
            }
        ];
    }

    async applyDateFilter(period) {
        const today = new Date();
        let fromDate, toDate;
        
        switch (period) {
            case 'today':
                fromDate = toDate = today.toISOString().split('T')[0];
                break;
            case 'this_week':
                const startOfWeek = new Date(today.setDate(today.getDate() - today.getDay()));
                const endOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + 6));
                fromDate = startOfWeek.toISOString().split('T')[0];
                toDate = endOfWeek.toISOString().split('T')[0];
                break;
            case 'this_month':
                fromDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
                toDate = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
                break;
            case 'this_quarter':
                const quarter = Math.floor(today.getMonth() / 3);
                fromDate = new Date(today.getFullYear(), quarter * 3, 1).toISOString().split('T')[0];
                toDate = new Date(today.getFullYear(), quarter * 3 + 3, 0).toISOString().split('T')[0];
                break;
            case 'this_year':
                fromDate = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
                toDate = new Date(today.getFullYear(), 11, 31).toISOString().split('T')[0];
                break;
            case 'last_30_days':
                fromDate = new Date(today.setDate(today.getDate() - 30)).toISOString().split('T')[0];
                toDate = new Date().toISOString().split('T')[0];
                break;
        }
        
        this.state.dateRange = { from: fromDate, to: toDate };
        
        // Apply to all date filters
        const dateFilters = this.getFiltersByType('date_range');
        for (const filter of dateFilters) {
            this.state.filters[filter.id] = { from: fromDate, to: toDate };
        }
        
        await this._updateFilters();
    }

    // ===================
    // Search
    // ===================

    async updateSearchText(searchText) {
        this.state.searchText = searchText;
        // Apply global search filter
        await this.props.onFilterChange('global_search', searchText);
    }

    // ===================
    // UI Helpers
    // ===================

    getFilterIcon(filterType) {
        const icons = {
            selection: 'fa-list',
            date_range: 'fa-calendar',
            numeric_range: 'fa-sliders-h',
            text: 'fa-search'
        };
        return icons[filterType] || 'fa-filter';
    }

    formatFilterValue(filter, value) {
        if (!value) return _t('Any');
        
        switch (filter.type) {
            case 'selection':
                return Array.isArray(value) ? value.join(', ') : value;
            case 'date_range':
                if (value.from && value.to) {
                    return `${value.from} - ${value.to}`;
                } else if (value.from) {
                    return `From ${value.from}`;
                } else if (value.to) {
                    return `Until ${value.to}`;
                }
                return _t('Any date');
            case 'numeric_range':
                if (value.min !== null && value.max !== null) {
                    return `${value.min} - ${value.max}`;
                } else if (value.min !== null) {
                    return `≥ ${value.min}`;
                } else if (value.max !== null) {
                    return `≤ ${value.max}`;
                }
                return _t('Any value');
            default:
                return String(value);
        }
    }

    getFilterCount() {
        return Object.keys(this.state.filters).length;
    }

    close() {
        this.props.onClose();
    }
}

FilterPanel.template = "biz_analytics.FilterPanel";
FilterPanel.props = {
    model: Object,
    onFilterChange: Function,
    onClose: Function,
};