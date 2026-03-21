/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Health Flow Client Action
 *
 * Interactive circular dashboard for healthcare operations
 * Features primary circles with slide-in panel for detailed actions
 */
class HealthFlowAction extends Component {
    static template = "health_flow.HealthFlowTemplate";

    // Breadcrumb display name for Odoo 19
    static displayName = _t("Home Page");

    // Props definition for Odoo 19 action service
    static props = {
        "*": true,
    };

    // Getter for breadcrumb title
    get title() {
        return _t("Home Page");
    }

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
                in_progress: 0,
                completed: 0,
            },
            crmCounts: {
                planned_activities: 0,
                calendar: 0,
                all: 0,
                initial: 0,
                continue_followup: 0,
                client_acquired: 0,
                booking_lost: 0,
            },
            searchModalOpen: false,
            searchType: null, // 'booking' or 'crm'
            searchQuery: '',
            searchResults: {
                bookings: [],
                clients: [],
                leads: [],
            },
            selectedLeadIds: [], // For multi-select in search results
            // User info for top bar display
            userName: '',
            userFacility: '',
            // Booking notifications
            bookingNotifications: [],
            bookingNotificationsOpen: false,
            // Client choice modal (Select Existing / Add New)
            clientChoiceModalOpen: false,
            // Master Data modal
            masterDataModalOpen: false,
            // User Management modal
            userMgmtModalOpen: false,
            // AR Management modal
            arMgmtModalOpen: false,
        });

        // Panel data configuration
        this.panelData = {
            crm: {
                title: _t('Sales & CRM'),
                color: '#4299e1', // Blue
                items: [
                    // Contact-First Flow: Only TWO main options
                    { key: 'crm-contacts', label: _t('Contacts'), icon: 'fa-phone', desc: _t('Log new contact / View contacts'), hasCount: true, countKey: 'all', countSource: 'crm' },
                    { key: 'crm-followup', label: _t('Follow-up Activities'), icon: 'fa-calendar-check-o', desc: _t('Manage leads and activities'), hasCount: true, countKey: 'planned_activities', countSource: 'crm' },
                    { key: 'crm-all-contacts', label: _t('All Contacts'), icon: 'fa-address-book', desc: _t('View all contacts by status') },
                    { key: 'crm-all-clients', label: _t('All Clients'), icon: 'fa-user', desc: _t('View all clients') },
                ],
            },
            booking: {
                title: _t('Bookings and Assignments'),
                color: '#ed8936', // Orange
                items: [
                    { key: 'booking-search', label: _t('Search'), icon: 'fa-search', desc: _t('Search bookings'), isSearch: true },
                    { key: 'booking-calendar', label: _t('Booking Calendar'), icon: 'fa-calendar-check-o', desc: _t('Visual booking calendar') },
                    { key: 'booking-all', label: _t('All Bookings'), icon: 'fa-list', desc: _t('All bookings (grouped by month)') },
                    { key: 'booking-staff', label: _t('Staff Workload'), icon: 'fa-user-md', desc: _t('Staff workload overview') },
                    { key: 'booking-staff-assignment', label: _t('Staff Assignment'), icon: 'fa-users', desc: _t('Assignment timeline view') },
                    { key: 'booking-draft', label: _t('Draft'), icon: 'fa-file-o', desc: _t('Draft bookings'), hasCount: true, countKey: 'draft' },
                    { key: 'booking-assigned', label: _t('Assigned'), icon: 'fa-check-circle', desc: _t('Assigned bookings'), hasCount: true, countKey: 'assigned' },
                    { key: 'booking-scheduled', label: _t('Scheduled'), icon: 'fa-clock-o', desc: _t('Scheduled bookings'), hasCount: true, countKey: 'scheduled' },
                    { key: 'booking-in-progress', label: _t('In Progress'), icon: 'fa-play-circle', desc: _t('In progress bookings'), hasCount: true, countKey: 'in_progress' },
                    { key: 'booking-completed', label: _t('Completed'), icon: 'fa-check', desc: _t('Completed bookings'), hasCount: true, countKey: 'completed' },
                ],
            },
            invoicing: {
                title: _t('Finance'),
                color: '#48bb78', // Green
                items: [
                    { key: 'invoicing-invoices', label: _t('Invoices'), icon: 'fa-file-text-o', desc: _t('All invoices') },
                    { key: 'invoicing-ar', label: _t('Accounts Receivable'), icon: 'fa-dashboard', desc: _t('Unpaid invoices & aging') },
                    { key: 'invoicing-ar-management', label: _t('AR Management'), icon: 'fa-tasks', desc: _t('Payments, cash transit, refunds'), isArMgmt: true },
                    { key: 'invoicing-add-invoice', label: _t('Add New Invoice'), icon: 'fa-plus-circle', desc: _t('Create manual invoice') },
                    { key: 'invoicing-vat-log', label: _t('VAT Invoices Log'), icon: 'fa-book', desc: _t('VAT log for MISA validation') },
                    { key: 'invoicing-ar-log', label: _t('AR Transactions Log'), icon: 'fa-list-alt', desc: _t('Double-entry journal log') },
                    { key: 'invoicing-payments', label: _t('Payment Transactions'), icon: 'fa-credit-card', desc: _t('Payment history') },
                ],
            },
            admin: {
                title: _t('Admin'),
                color: '#9f7aea', // Purple
                items: [
                    { key: 'admin-user-management', label: _t('User Management'), icon: 'fa-users', desc: _t('Manage users & roles'), isUserMgmt: true },
                    { key: 'admin-master-data', label: _t('Master Data'), icon: 'fa-database', desc: _t('Master data management'), isMasterData: true },
                    { key: 'admin-package-products', label: _t('Package Products'), icon: 'fa-cube', desc: _t('Service packages') },
                    { key: 'admin-pricing-rules', label: _t('Pricing Rules'), icon: 'fa-list-ul', desc: _t('Define pricing rules') },
                    { key: 'admin-portable-equipment', label: _t('Portable Equipment'), icon: 'fa-briefcase', desc: _t('Track equipment') },
                    { key: 'admin-healthcare-staff', label: _t('Healthcare Staff'), icon: 'fa-user-md', desc: _t('Staff directory') },
                    { key: 'admin-patient-categories', label: _t('Patient Categories'), icon: 'fa-bookmark', desc: _t('Patient categories') },
                ],
            },
        };

        onWillStart(async () => {
            // Fetch user info
            await this.fetchUserInfo();
            // Fetch booking counts
            await this.fetchBookingCounts();
            await this.fetchCrmCounts();
            // Fetch booking notifications
            await this.fetchBookingNotifications();
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
     * Fetch CRM counts for CRM tiles
     */
    async fetchCrmCounts() {
        try {
            const counts = await this.orm.call(
                'health.flow.wizard',
                'get_crm_counts',
                []
            );
            this.state.crmCounts = counts;
        } catch (error) {
            console.error('[Health Flow] Failed to fetch CRM counts:', error);
        }
    }

    /**
     * Fetch current user info (name and facility)
     */
    async fetchUserInfo() {
        try {
            const userInfo = await this.orm.call(
                'health.flow.wizard',
                'get_user_info',
                []
            );
            this.state.userName = userInfo.userName || '';
            this.state.userFacility = userInfo.userFacility || '';
        } catch (error) {
            console.error('[Health Flow] Failed to fetch user info:', error);
        }
    }

    /**
     * Fetch booking notifications (new, upcoming, cancelled, rescheduled)
     */
    async fetchBookingNotifications() {
        try {
            const notifications = await this.orm.call(
                'health.flow.wizard',
                'get_booking_notifications',
                []
            );
            this.state.bookingNotifications = notifications || [];
        } catch (error) {
            console.error('[Health Flow] Failed to fetch booking notifications:', error);
        }
    }

    /**
     * Toggle booking notifications dropdown
     */
    toggleBookingNotifications() {
        this.state.bookingNotificationsOpen = !this.state.bookingNotificationsOpen;
    }

    /**
     * Open booking from notification and remove from list
     */
    async openNotificationBooking(notification) {
        try {
            // Remove from local list
            const idx = this.state.bookingNotifications.findIndex(n => n.id === notification.id);
            if (idx > -1) {
                this.state.bookingNotifications.splice(idx, 1);
            }
            // Open the booking (use booking_id, fallback to id for backwards compatibility)
            const bookingId = notification.booking_id || notification.id;
            await this.openBooking(bookingId);
            this.state.bookingNotificationsOpen = false;
        } catch (error) {
            console.error('[Health Flow] Failed to open notification booking:', error);
        }
    }

    /**
     * Navigate to Home Page
     */
    async goHome() {
        // Close any open panels/modals
        this.closePanel();
        this.closeSearchModal();
        this.state.bookingNotificationsOpen = false;
        // Refresh state
        await this.fetchBookingCounts();
        await this.fetchCrmCounts();
        await this.fetchBookingNotifications();
    }

    /**
     * Get notification icon based on type
     */
    getNotificationIcon(type) {
        const icons = {
            new: 'fa-plus-circle',
            upcoming: 'fa-calendar',
            cancelled: 'fa-times-circle',
            rescheduled: 'fa-refresh',
        };
        return icons[type] || 'fa-bell';
    }

    /**
     * Get notification color class based on type
     */
    getNotificationClass(type) {
        const classes = {
            new: 'notification-new',
            upcoming: 'notification-upcoming',
            cancelled: 'notification-cancelled',
            rescheduled: 'notification-rescheduled',
        };
        return classes[type] || '';
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
     * Handle center circle (Client) click - show choice popup
     */
    async onCenterClick() {
        console.log('[Health Flow] Center (Client) clicked');
        this.state.clientChoiceModalOpen = true;
    }

    /**
     * Select Existing Client - opens patient list (original behavior)
     */
    async onSelectExistingClient() {
        this.state.clientChoiceModalOpen = false;
        await this.launchAction('client');
    }

    /**
     * Add New Client - opens patient form in create mode
     */
    async onAddNewClient() {
        this.state.clientChoiceModalOpen = false;
        await this.launchAction('client-new');
    }

    /**
     * Close client choice modal
     */
    closeClientChoiceModal() {
        this.state.clientChoiceModalOpen = false;
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
            this.state.searchResults = {
                bookings: [],
                clients: [],
                leads: [],
            };
            this.state.selectedLeadIds = [];
            return;
        }

        // Handle Master Data popup
        if (item.isMasterData) {
            this.state.masterDataModalOpen = true;
            return;
        }

        // Handle User Management popup
        if (item.isUserMgmt) {
            this.state.userMgmtModalOpen = true;
            return;
        }

        // Handle AR Management popup
        if (item.isArMgmt) {
            this.state.arMgmtModalOpen = true;
            return;
        }

        // Save state before launching action (so breadcrumb return restores panel)
        if (!this.isRestoring) {
            this.saveState(this.state.activePrimary);
        }

        await this.launchAction(item.key);
    }

    /**
     * Close Master Data modal
     */
    closeMasterDataModal() {
        this.state.masterDataModalOpen = false;
    }

    /**
     * Handle Master Data option selection
     */
    async onMasterDataSelect(key) {
        this.state.masterDataModalOpen = false;
        if (!this.isRestoring) {
            this.saveState(this.state.activePrimary);
        }
        await this.launchAction(key);
    }

    /**
     * Close User Management modal
     */
    closeUserMgmtModal() {
        this.state.userMgmtModalOpen = false;
    }

    /**
     * Handle User Management option selection
     */
    async onUserMgmtSelect(key) {
        this.state.userMgmtModalOpen = false;
        if (!this.isRestoring) {
            this.saveState(this.state.activePrimary);
        }
        await this.launchAction(key);
    }

    /**
     * Close AR Management modal
     */
    closeArMgmtModal() {
        this.state.arMgmtModalOpen = false;
    }

    /**
     * Handle AR Management option selection
     */
    async onArMgmtSelect(key) {
        this.state.arMgmtModalOpen = false;
        if (!this.isRestoring) {
            this.saveState(this.state.activePrimary);
        }
        await this.launchAction(key);
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
            if (item.countSource === 'crm') {
                return this.state.crmCounts[item.countKey] || 0;
            }
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
            this.state.searchResults = {
                bookings: [],
                clients: [],
                leads: [],
            };
            this.state.selectedLeadIds = [];
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
                this.state.searchResults = {
                    bookings: [],
                    clients: results.clients || [],
                    leads: results.leads || [],
                };
                this.state.selectedLeadIds = [];
                return;
            } else {
                results = await this.orm.call(
                    'health.flow.wizard',
                    'search_bookings',
                    [query]
                );
            }
            this.state.searchResults = {
                bookings: results,
                clients: [],
                leads: [],
            };
        } catch (error) {
            console.error('[Health Flow] Search failed:', error);
            this.state.searchResults = {
                bookings: [],
                clients: [],
                leads: [],
            };
        }
    }

    /**
     * Handle search result click - toggle selection on click
     */
    async onSearchResultClick(resultType, recordId, event) {
        if (event && event.target && event.target.type === 'checkbox') {
            // Let checkbox handle itself
            return;
        }
        if (resultType === 'client') {
            await this.openClient(recordId);
            return;
        }
        if (resultType === 'lead') {
            await this.openCrmLead(recordId);
            return;
        }
        await this.openBooking(recordId);
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

    async openCrmLead(leadId) {
        const action = await this.orm.call(
            'health.flow.wizard',
            'get_crm_lead_form_action',
            [leadId]
        );
        if (action && action.type) {
            await this.action.doAction(action);
            this.closeSearchModal();
        }
    }

    async openClient(clientId) {
        const action = await this.orm.call(
            'health.flow.wizard',
            'get_client_form_action',
            [clientId]
        );
        if (action && action.type) {
            await this.action.doAction(action);
            this.closeSearchModal();
        }
    }

    async openBooking(bookingId) {
        const action = await this.orm.call(
            'health.flow.wizard',
            'get_booking_form_action',
            [bookingId]
        );
        if (action && action.type) {
            await this.action.doAction(action);
            this.closeSearchModal();
        }
    }

    getSearchResultCount() {
        if (this.state.searchType === 'crm') {
            return this.state.searchResults.clients.length + this.state.searchResults.leads.length;
        }
        if (this.state.searchType === 'booking') {
            return this.state.searchResults.bookings.length;
        }
        return 0;
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
