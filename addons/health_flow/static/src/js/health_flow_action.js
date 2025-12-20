/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Health Flow Client Action
 *
 * Interactive circular dashboard for healthcare operations
 * Features primary circles with slide-in panel for detailed actions
 */
class HealthFlowAction extends Component {
    static template = "health_flow.HealthFlowTemplate";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        // State persistence key
        this.STORAGE_KEY = 'health_flow_state';
        this.isRestoring = false;

        this.state = useState({
            activePrimary: null, // Currently active primary circle
            panelOpen: false,
            panelTitle: '',
            panelItems: [],
            bookingCounts: {
                draft: 0,
                assigned: 0,
                scheduled: 0,
            },
            searchModalOpen: false,
            searchType: null, // 'booking' or 'crm'
            searchQuery: '',
            searchResults: [],
            selectedLeadIds: [], // For multi-select in search results
        });

        // Panel data configuration
        this.panelData = {
            crm: {
                title: 'CRM',
                color: '#4299e1', // Blue
                items: [
                    { key: 'crm-search', label: 'Search', icon: 'fa-search', desc: 'Search opportunities', isSearch: true },
                    { key: 'crm-add-lead', label: 'Add Lead', icon: 'fa-plus-circle', desc: 'Create a new lead' },
                    { key: 'crm-activities', label: 'Planned Activities', icon: 'fa-tasks', desc: 'Planned activities' },
                    { key: 'crm-calendar', label: 'Calendar', icon: 'fa-calendar', desc: 'CRM calendar view' },
                    { key: 'crm-all', label: 'All Leads', icon: 'fa-address-card', desc: 'All leads (kanban first)' },
                    { key: 'crm-initial', label: 'Initial Contact', icon: 'fa-phone', desc: 'Initial contact leads' },
                    // Use a Font Awesome v4 compatible icon to ensure it renders
                    { key: 'crm-continue-followup', label: 'Continue Follow-up', icon: 'fa-refresh', desc: 'Leads pending follow-up' },
                    { key: 'crm-client-acquired', label: 'Client Acquired', icon: 'fa-check-circle', desc: 'Converted clients' },
                    { key: 'crm-booking-lost', label: 'Booking Lost', icon: 'fa-times-circle', desc: 'Lost opportunities' },
                ],
            },
            booking: {
                title: 'Booking',
                color: '#ed8936', // Orange
                items: [
                    { key: 'booking-search', label: 'Search', icon: 'fa-search', desc: 'Search bookings', isSearch: true },
                    { key: 'booking-calendar', label: 'Booking Calendar', icon: 'fa-calendar-check-o', desc: 'Visual booking calendar' },
                    { key: 'booking-staff', label: 'Staff Assignment', icon: 'fa-user-md', desc: 'Staff workload & assignment' },
                    { key: 'booking-draft', label: 'Draft', icon: 'fa-file-o', desc: 'Draft bookings', hasCount: true, countKey: 'draft' },
                    { key: 'booking-assigned', label: 'Assigned', icon: 'fa-check-circle', desc: 'Assigned bookings', hasCount: true, countKey: 'assigned' },
                    { key: 'booking-scheduled', label: 'Scheduled', icon: 'fa-clock-o', desc: 'Scheduled bookings', hasCount: true, countKey: 'scheduled' },
                ],
            },
            invoicing: {
                title: 'Invoicing',
                color: '#48bb78', // Green
                items: [
                    { key: 'invoicing-ar', label: 'AR Dashboard', icon: 'fa-dashboard', desc: 'Accounts receivable overview' },
                    { key: 'invoicing-payments', label: 'Payment Transactions', icon: 'fa-credit-card', desc: 'Payment history' },
                    { key: 'invoicing-invoices', label: 'Invoices', icon: 'fa-file-text-o', desc: 'All invoices' },
                ],
            },
            admin: {
                title: 'Admin',
                color: '#9f7aea', // Purple
                items: [
                    { key: 'admin-pricing-engines', label: 'Pricing Engines', icon: 'fa-cogs', desc: 'Configure pricing engines' },
                    { key: 'admin-package-products', label: 'Package Products', icon: 'fa-cube', desc: 'Service packages' },
                    { key: 'admin-pricing-rules', label: 'Pricing Rules', icon: 'fa-list-ul', desc: 'Define pricing rules' },
                    { key: 'admin-quick-edit-rules', label: 'Quick Edit Rules', icon: 'fa-edit', desc: 'Quick edit pricing' },
                    { key: 'admin-portable-equipment', label: 'Portable Equipment', icon: 'fa-briefcase', desc: 'Track equipment' },
                    { key: 'admin-facilities', label: 'Healthcare Facilities', icon: 'fa-building', desc: 'Facilities management' },
                    { key: 'admin-patient-categories', label: 'Patient Categories', icon: 'fa-bookmark', desc: 'Patient categories' },
                    { key: 'admin-service-types', label: 'Service Types', icon: 'fa-list-ul', desc: 'Define services' },
                    { key: 'admin-symptoms', label: 'Symptoms', icon: 'fa-heartbeat', desc: 'Configure symptoms' },
                    { key: 'admin-referral-sources', label: 'Referral Sources', icon: 'fa-share-alt', desc: 'Referral sources' },
                    { key: 'admin-insurance', label: 'Insurance Providers', icon: 'fa-shield', desc: 'Insurance providers' },
                    { key: 'admin-urgency-levels', label: 'Urgency Levels', icon: 'fa-exclamation-circle', desc: 'Urgency levels' },
                ],
            },
        };

        onWillStart(async () => {
            // Fetch booking counts
            await this.fetchBookingCounts();
        });

        onMounted(() => {
            console.log('[Health Flow] Component mounted');
            // Add escape key listener
            this.escapeListener = this.onEscape.bind(this);
            document.addEventListener('keydown', this.escapeListener);

            // Restore state if returning via breadcrumb
            this.restoreState();
        });

        onWillUnmount(() => {
            // Remove escape key listener
            if (this.escapeListener) {
                document.removeEventListener('keydown', this.escapeListener);
            }
        });
    }

    /**
     * Fetch booking counts for Draft/Assigned/Scheduled
     */
    async fetchBookingCounts() {
        try {
            const counts = await this.orm.call(
                'health.flow.wizard',
                'get_booking_counts',
                []
            );
            this.state.bookingCounts = counts;
        } catch (error) {
            console.error('[Health Flow] Failed to fetch booking counts:', error);
        }
    }

    /**
     * Save panel state to sessionStorage
     */
    saveState(primaryKey) {
        try {
            const payload = {
                activePrimary: primaryKey || null,
                panelOpen: this.state.panelOpen,
                panelTitle: this.state.panelTitle,
                panelItems: this.state.panelItems,
            };
            sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(payload));
            console.log('[Health Flow] State saved', payload);
        } catch (error) {
            console.warn('[Health Flow] Failed to save state', error);
        }
    }

    /**
     * Load panel state from sessionStorage
     */
    loadState() {
        try {
            const stored = sessionStorage.getItem(this.STORAGE_KEY);
            if (!stored) return null;
            const state = JSON.parse(stored);
            console.log('[Health Flow] State loaded', state);
            return state;
        } catch (error) {
            console.warn('[Health Flow] Failed to load state', error);
            return null;
        }
    }

    /**
     * Clear panel state from sessionStorage
     */
    clearState() {
        try {
            sessionStorage.removeItem(this.STORAGE_KEY);
            console.log('[Health Flow] State cleared');
        } catch (error) {
            console.warn('[Health Flow] Failed to clear state', error);
        }
    }

    /**
     * Restore panel state after component mount
     */
    restoreState() {
        const savedState = this.loadState();
        if (!savedState || !savedState.activePrimary) {
            return;
        }

        console.log('[Health Flow] Restoring state', savedState);
        this.isRestoring = true;

        // Restore panel state
        this.state.activePrimary = savedState.activePrimary;
        this.state.panelOpen = savedState.panelOpen;
        this.state.panelTitle = savedState.panelTitle;
        this.state.panelItems = savedState.panelItems;

        this.isRestoring = false;
    }

    /**
     * Handle primary circle click
     */
    async onPrimaryClick(primaryKey) {
        console.log('[Health Flow] Primary clicked:', primaryKey);

        // Direct actions (Analytics, Audit)
        if (primaryKey === 'analytics' || primaryKey === 'audit') {
            await this.launchAction(primaryKey);
            return;
        }

        // Panel actions (CRM, Booking, Invoicing, Admin)
        const panelConfig = this.panelData[primaryKey];
        if (panelConfig) {
            this.state.activePrimary = primaryKey;
            this.state.panelTitle = panelConfig.title;
            this.state.panelItems = panelConfig.items;
            this.state.panelOpen = true;

            // Save state for breadcrumb restoration
            if (!this.isRestoring) {
                this.saveState(primaryKey);
            }
        }
    }

    /**
     * Handle center circle (Client) click
     */
    async onCenterClick() {
        console.log('[Health Flow] Center (Client) clicked');
        await this.launchAction('client');
    }

    /**
     * Handle panel tile click
     */
    async onPanelTileClick(item) {
        console.log('[Health Flow] Panel tile clicked:', item.key);

        // Handle search modal
        if (item.isSearch) {
            this.state.searchModalOpen = true;
            // Determine search type based on which panel we're in
            this.state.searchType = this.state.activePrimary === 'crm' ? 'crm' : 'booking';
            this.state.searchQuery = '';
            this.state.searchResults = [];
            this.state.selectedLeadIds = [];
            return;
        }

        // Save state before launching action (so breadcrumb return restores panel)
        if (!this.isRestoring) {
            this.saveState(this.state.activePrimary);
        }

        await this.launchAction(item.key);
    }

    /**
     * Close panel
     */
    closePanel() {
        this.state.panelOpen = false;
        this.state.activePrimary = null;
        this.state.panelItems = [];

        // Clear saved state when manually closing panel
        this.clearState();
    }

    /**
     * Close search modal
     */
    closeSearchModal() {
        this.state.searchModalOpen = false;
    }

    /**
     * Get count for tile
     */
    getTileCount(item) {
        if (item.hasCount && item.countKey) {
            return this.state.bookingCounts[item.countKey] || 0;
        }
        return null;
    }

    /**
     * Handle search input for both booking and CRM searches
     */
    async onSearchInput(event) {
        const query = event.target.value;
        this.state.searchQuery = query;

        if (query.length < 2) {
            this.state.searchResults = [];
            return;
        }

        try {
            let results;
            if (this.state.searchType === 'crm') {
                results = await this.orm.call(
                    'health.flow.wizard',
                    'search_crm_leads',
                    [query]
                );
            } else {
                results = await this.orm.call(
                    'health.flow.wizard',
                    'search_bookings',
                    [query]
                );
            }
            this.state.searchResults = results;
        } catch (error) {
            console.error('[Health Flow] Search failed:', error);
            this.state.searchResults = [];
        }
    }

    /**
     * Handle search result click - toggle selection on click
     */
    onSearchResultClick(bookingId, event) {
        if (event && event.target && event.target.type === 'checkbox') {
            // Let checkbox handle itself
            return;
        }
        // Toggle selection
        const index = this.state.selectedLeadIds.indexOf(bookingId);
        if (index > -1) {
            this.state.selectedLeadIds.splice(index, 1);
        } else {
            this.state.selectedLeadIds.push(bookingId);
        }
    }

    /**
     * Handle checkbox change for lead selection
     */
    onLeadCheckboxChange(event, bookingId) {
        event.stopPropagation();
        if (event.target.checked) {
            if (!this.state.selectedLeadIds.includes(bookingId)) {
                this.state.selectedLeadIds.push(bookingId);
            }
        } else {
            const index = this.state.selectedLeadIds.indexOf(bookingId);
            if (index > -1) {
                this.state.selectedLeadIds.splice(index, 1);
            }
        }
    }

    /**
     * Check if a lead is selected
     */
    isLeadSelected(bookingId) {
        return this.state.selectedLeadIds.includes(bookingId);
    }

    /**
     * Merge selected leads
     */
    async mergeCrmLeads() {
        if (this.state.selectedLeadIds.length < 2) {
            console.warn('[Health Flow] Please select at least 2 leads to merge');
            return;
        }

        try {
            // Open the standard Odoo CRM merge wizard with selected leads
            const firstId = this.state.selectedLeadIds[0];
            const action = {
                type: 'ir.actions.act_window',
                res_model: 'crm.merge.opportunity',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    active_model: 'crm.lead',
                    active_ids: this.state.selectedLeadIds,
                    active_id: firstId,
                },
            };

            await this.action.doAction(action);
            this.closeSearchModal();
            this.state.selectedLeadIds = [];
        } catch (error) {
            console.error('[Health Flow] Failed to open merge wizard:', error);
        }
    }

    /**
     * Handle escape key
     */
    onEscape(event) {
        if (event.key === 'Escape') {
            if (this.state.searchModalOpen) {
                this.closeSearchModal();
            } else if (this.state.panelOpen) {
                this.closePanel();
            }
        }
    }

    /**
     * Launch action via server-side resolution
     */
    async launchAction(key) {
        try {
            const action = await this.orm.call(
                'health.flow.wizard',
                'get_action',
                [key]
            );

            if (action && action.type) {
                await this.action.doAction(action);
            }
        } catch (error) {
            console.error('[Health Flow] Failed to launch action:', key, error);
        }
    }

    /**
     * Get primary circle color class
     */
    getPrimaryClass(primaryKey) {
        const colorMap = {
            crm: 'badge-crm',
            booking: 'badge-booking',
            invoicing: 'badge-invoicing',
            analytics: 'badge-analytics',
            admin: 'badge-admin',
            audit: 'badge-audit',
        };
        return colorMap[primaryKey] || '';
    }

    /**
     * Get panel color for current primary
     */
    getPanelColor() {
        if (!this.state.activePrimary) return '#4299e1';
        const config = this.panelData[this.state.activePrimary];
        return config ? config.color : '#4299e1';
    }
}

HealthFlowAction.template = "health_flow.HealthFlowTemplate";

// Register as client action
registry.category("actions").add("health_flow_dashboard", HealthFlowAction);
