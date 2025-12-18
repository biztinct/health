/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
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

        this.state = useState({
            activePrimary: null, // Currently active primary circle
            panelOpen: false,
            panelTitle: '',
            panelItems: [],
        });

        // Panel data configuration
        this.panelData = {
            crm: {
                title: 'CRM',
                color: '#4299e1', // Blue
                items: [
                    { key: 'crm-search', label: 'Search', icon: 'fa-search', desc: 'Search opportunities' },
                    { key: 'crm-initial', label: 'Initial Contact', icon: 'fa-phone', desc: 'Initial contact leads' },
                    { key: 'crm-activities', label: 'Planned Activities', icon: 'fa-tasks', desc: 'Planned activities' },
                    { key: 'crm-calendar', label: 'Calendar', icon: 'fa-calendar', desc: 'CRM calendar view' },
                ],
            },
            booking: {
                title: 'Booking',
                color: '#ed8936', // Orange
                items: [
                    { key: 'booking-calendar', label: 'Booking Calendar', icon: 'fa-calendar-check-o', desc: 'Visual booking calendar' },
                    { key: 'booking-staff', label: 'Staff Assignment', icon: 'fa-user-md', desc: 'Staff workload & assignment' },
                    { key: 'booking-draft', label: 'Draft', icon: 'fa-file-o', desc: 'Draft bookings' },
                    { key: 'booking-assigned', label: 'Assigned', icon: 'fa-check-circle', desc: 'Assigned bookings' },
                    { key: 'booking-scheduled', label: 'Scheduled', icon: 'fa-clock-o', desc: 'Scheduled bookings' },
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

        onMounted(() => {
            console.log('[Health Flow] Component mounted');
            // Add escape key listener
            this.escapeListener = this.onEscape.bind(this);
            document.addEventListener('keydown', this.escapeListener);
        });

        onWillUnmount(() => {
            // Remove escape key listener
            if (this.escapeListener) {
                document.removeEventListener('keydown', this.escapeListener);
            }
        });
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
        await this.launchAction(item.key);
    }

    /**
     * Close panel
     */
    closePanel() {
        this.state.panelOpen = false;
        this.state.activePrimary = null;
        this.state.panelItems = [];
    }

    /**
     * Handle escape key
     */
    onEscape(event) {
        if (event.key === 'Escape' && this.state.panelOpen) {
            this.closePanel();
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
