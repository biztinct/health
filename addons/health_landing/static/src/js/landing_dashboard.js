/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { HubSpokeWidget } from "./hub_spoke_widget";
import { PatientSpokeModal } from "./patient_spoke_modal";

/**
 * Healthcare Landing Dashboard Component v2.0
 *
 * Enhanced with:
 * - Modal popup for module details
 * - Search and filter functionality
 * - Recently accessed tracking
 * - Favorites system
 * - Keyboard shortcuts
 * - Professional animations
 */
class HealthLandingDashboard extends Component {
    setup() {
        this.actionService = useService("action");
        this.searchInputRef = useRef("searchInput");

        this.state = useState({
            currentView: "main", // "main", "submenu", "hub_spoke", or "modal"
            currentModule: null,
            modalModule: null,
            selectedPatientId: null,
            selectedPatientName: null,
            selectedSpoke: null,
            breadcrumb: ["Home"],
            searchQuery: "",
            recentlyAccessed: this.getRecentlyAccessed(),
            favorites: this.getFavorites(),
            filteredModules: [],
        });

        // Keyboard shortcuts
        onMounted(() => {
            document.addEventListener("keydown", this.handleKeyboard.bind(this));

            // Focus search on mount
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        });

        // Main dashboard modules configuration
        this.modules = [
            {
                id: "patient",
                name: "Patient Management",
                icon: "fa-users",
                description: "Manage patient records and information",
                class: "module-patient",
                submenus: [
                    {
                        name: "Client",
                        icon: "fa-user-circle",
                        action: "hub_spoke",  // Special action to trigger hub-and-spoke
                        description: "View patient hub-and-spoke dashboard"
                    },
                ],
            },
            {
                id: "scheduling",
                name: "Scheduling & Staff",
                icon: "fa-calendar-check-o",
                description: "Staff scheduling and workload management",
                class: "module-scheduling",
                submenus: [
                    {
                        name: "Assignment Dashboard",
                        icon: "fa-dashboard",
                        action: "health_fieldservice.action_fso_assignment_dashboard",
                        description: "View staff assignments"
                    },
                    {
                        name: "Visual Scheduler",
                        icon: "fa-calendar",
                        action: "health_fieldservice.action_assignment_scheduler_grid",
                        description: "Visual scheduling interface"
                    },
                    {
                        name: "Timeline View",
                        icon: "fa-clock-o",
                        action: "health_fieldservice.action_assignment_web_timeline_view",
                        description: "Timeline of assignments"
                    },
                    {
                        name: "Staff Availability",
                        icon: "fa-user-circle",
                        action: "health_fieldservice.action_health_staff_availability",
                        description: "Manage staff availability"
                    },
                    {
                        name: "Staff Workload",
                        icon: "fa-bar-chart",
                        action: "health_fieldservice.action_staff_workload_dashboard",
                        description: "Monitor staff workload"
                    },
                    {
                        name: "Healthcare Skills",
                        icon: "fa-graduation-cap",
                        action: "health_fieldservice.action_healthcare_skills",
                        description: "Manage staff skills"
                    },
                    {
                        name: "Service Areas",
                        icon: "fa-map",
                        action: "health_fieldservice.action_service_areas",
                        description: "Configure service areas"
                    },
                    {
                        name: "Healthcare Staff",
                        icon: "fa-user-md",
                        action: "health_fieldservice.action_healthcare_staff",
                        description: "Manage healthcare staff"
                    },
                ],
            },
            {
                id: "crm",
                name: "CRM",
                icon: "fa-handshake-o",
                description: "Customer relationship management",
                class: "module-crm",
                submenus: [
                    {
                        name: "Leads",
                        icon: "fa-star-o",
                        action: "crm.crm_lead_all_leads",
                        description: "Manage potential customers"
                    },
                    {
                        name: "CRM Contacts",
                        icon: "fa-address-card",
                        action: "health_crm.action_healthcare_opportunities",
                        description: "Track customer interactions"
                    },
                    {
                        name: "Customers",
                        icon: "fa-user-circle",
                        action: "base.action_partner_form",
                        description: "View all customers"
                    },
                    {
                        name: "Healthcare Relationships",
                        icon: "fa-users",
                        action: "health_crm.action_health_client_relation",
                        description: "Manage patient relationships"
                    },
                ],
            },
            {
                id: "fieldservice",
                name: "Field Service",
                icon: "fa-ambulance",
                description: "Mobile healthcare service management",
                class: "module-fieldservice",
                submenus: [
                    {
                        name: "Field Service Orders",
                        icon: "fa-clipboard",
                        action: "health_fieldservice.action_health_fieldservice_order",
                        description: "Manage service orders"
                    },
                    {
                        name: "Communications",
                        icon: "fa-comments",
                        action: "health_fieldservice.action_health_fieldservice_communication",
                        description: "Real-time team communications"
                    },
                    {
                        name: "Portable Equipment",
                        icon: "fa-briefcase",
                        action: "health_fieldservice.action_health_portable_equipment",
                        description: "Track medical equipment"
                    },
                    {
                        name: "Clinical Protocols",
                        icon: "fa-file-text-o",
                        action: "health_fieldservice.action_health_clinical_protocol",
                        description: "Clinical guidelines"
                    },
                    {
                        name: "Field Service Teams",
                        icon: "fa-users",
                        action: "health_fieldservice.action_health_fieldservice_team",
                        description: "Manage service teams"
                    },
                ],
            },
            {
                id: "packages",
                name: "Service Packages",
                icon: "fa-gift",
                description: "Manage service packages and products",
                class: "module-packages",
                submenus: [
                    {
                        name: "Package Products",
                        icon: "fa-cube",
                        action: "health_invoicing.action_healthcare_package_products",
                        description: "Configure package products"
                    },
                    {
                        name: "Patient Packages",
                        icon: "fa-gift",
                        action: "health_invoicing.action_health_service_package",
                        description: "View patient subscriptions"
                    },
                ],
            },
            {
                id: "pricing",
                name: "Advanced Pricelist",
                icon: "fa-tags",
                description: "Dynamic pricing rules and engines",
                class: "module-pricing",
                submenus: [
                    {
                        name: "Pricing Engines",
                        icon: "fa-cog",
                        action: "advanced_pricing.action_advanced_pricing_engines",
                        description: "Configure pricing engines"
                    },
                    {
                        name: "Pricing Rules",
                        icon: "fa-list-ul",
                        action: "advanced_pricing.action_pricing_rules_with_visual",
                        description: "Manage pricing rules"
                    },
                    {
                        name: "Quick Edit Rules",
                        icon: "fa-edit",
                        action: "advanced_pricing.action_pricing_rules_quick_edit",
                        description: "Inline edit pricing rules"
                    },
                ],
            },
            {
                id: "billing",
                name: "Billing & Invoicing",
                icon: "fa-money",
                description: "Financial management and billing",
                class: "module-billing",
                submenus: [
                    {
                        name: "Service Billing",
                        icon: "fa-file-text",
                        action: "health_invoicing.action_health_service_billing",
                        description: "Create and manage invoices"
                    },
                    {
                        name: "AR Dashboard",
                        icon: "fa-dashboard",
                        action: "health_invoicing.action_healthcare_ar_dashboard",
                        description: "Accounts receivable overview"
                    },
                    {
                        name: "Overdue Patients",
                        icon: "fa-exclamation-triangle",
                        action: "health_invoicing.action_healthcare_overdue_patients",
                        description: "Track outstanding payments"
                    },
                    {
                        name: "Payment Transactions",
                        icon: "fa-credit-card",
                        action: "health_invoicing.action_health_payment_transaction",
                        description: "View payment history"
                    },
                    {
                        name: "Process Payments",
                        icon: "fa-cogs",
                        action: "health_invoicing.action_health_payment_workflow_wizard",
                        description: "Payment workflow"
                    },
                ],
            },
            {
                id: "facilities",
                name: "Facilities",
                icon: "fa-hospital-o",
                description: "Healthcare facility management",
                class: "module-facilities",
                submenus: [
                    {
                        name: "Healthcare Facilities",
                        icon: "fa-building",
                        action: "health_base.action_health_facility",
                        description: "Manage facility locations"
                    },
                ],
            },
            {
                id: "config",
                name: "Configuration",
                icon: "fa-cogs",
                description: "System configuration and settings",
                class: "module-config",
                submenus: [
                    {
                        name: "Patient Categories",
                        icon: "fa-tags",
                        action: "health_base.action_health_patient_category",
                        description: "Configure patient types"
                    },
                    {
                        name: "Service Types",
                        icon: "fa-list",
                        action: "health_base.action_health_service_type",
                        description: "Define service types"
                    },
                    {
                        name: "Medical Specialties",
                        icon: "fa-stethoscope",
                        action: "health_base.action_health_medical_specialty",
                        description: "Manage specialties"
                    },
                    {
                        name: "Symptoms",
                        icon: "fa-heartbeat",
                        action: "health_base.action_health_symptom",
                        description: "Symptom catalog"
                    },
                    {
                        name: "Referral Sources",
                        icon: "fa-share-alt",
                        action: "health_base.action_health_referral_source",
                        description: "Track referral sources"
                    },
                    {
                        name: "Insurance Providers",
                        icon: "fa-shield",
                        action: "health_base.action_health_insurance_provider",
                        description: "Insurance companies"
                    },
                    {
                        name: "Urgency Levels",
                        icon: "fa-exclamation-circle",
                        action: "health_base.action_health_urgency_level",
                        description: "Priority levels"
                    },
                ],
            },
        ];
    }

    /**
     * Navigate to submenu dashboard
     */
    showSubmenu(module) {
        this.state.currentView = "submenu";
        this.state.currentModule = module;
        this.state.breadcrumb = ["Home", module.name];
        this.trackRecentAccess(module.id, module.name, module.icon);
    }

    /**
     * Navigate back to main dashboard
     */
    showMain() {
        this.state.currentView = "main";
        this.state.currentModule = null;
        this.state.breadcrumb = ["Home"];
        this.state.searchQuery = "";
    }

    /**
     * Show modal with module details
     */
    showModal(module) {
        this.state.modalModule = module;
    }

    /**
     * Close modal
     */
    closeModal() {
        this.state.modalModule = null;
    }

    /**
     * Launch Odoo action window or special hub-and-spoke view
     */
    async launchAction(actionXmlId, actionName, icon) {
        // Check for hub-and-spoke special action
        if (actionXmlId === "hub_spoke") {
            await this.showPatientSelection();
            return;
        }

        // Track recent access
        this.trackRecentAccess(actionXmlId, actionName, icon);

        try {
            await this.actionService.doAction(actionXmlId);
        } catch (error) {
            console.error("Failed to launch action:", actionXmlId, error);
            // Fallback: try to parse XML ID and load directly
            const [module, action] = actionXmlId.split(".");
            if (module && action) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    xml_id: actionXmlId,
                });
            }
        }
    }

    /**
     * Show patient selection list
     */
    async showPatientSelection() {
        await this.actionService.doAction("health_base.action_health_patient");
    }

    /**
     * Show hub-and-spoke for specific patient
     */
    showPatientHub(patientId, patientName) {
        this.state.currentView = "hub_spoke";
        this.state.selectedPatientId = patientId;
        this.state.selectedPatientName = patientName;
        this.state.breadcrumb = ["Home", "Patient Management", "Client", patientName];
    }

    /**
     * Handle spoke click - open modal
     */
    onSpokeClick(spoke, patientId) {
        this.state.selectedSpoke = spoke;
        // Modal will be shown by template conditional
    }

    /**
     * Close spoke modal
     */
    closeSpokeModal() {
        this.state.selectedSpoke = null;
    }

    /**
     * Handle spoke modal edit button
     */
    onSpokeEdit(spokeId) {
        // Close modal and navigate as needed
        this.closeSpokeModal();
    }

    /**
     * Handle item click in spoke modal (e.g., booking card)
     */
    onSpokeItemClick(item, itemType, spokeId) {
        if (itemType === "booking" && item.id) {
            // TODO: Show nested hub-and-spoke for booking
            console.log("Show booking hub-and-spoke for:", item.id);
        }
    }

    /**
     * Search and filter modules
     */
    onSearchInput(event) {
        const query = event.target.value.toLowerCase();
        this.state.searchQuery = query;

        if (!query) {
            this.state.filteredModules = [];
            return;
        }

        // Search across all modules and submenus
        const results = [];
        this.modules.forEach(module => {
            // Search module name
            if (module.name.toLowerCase().includes(query) ||
                module.description.toLowerCase().includes(query)) {
                results.push({
                    type: 'module',
                    data: module,
                });
            }

            // Search submenu items
            module.submenus.forEach(submenu => {
                if (submenu.name.toLowerCase().includes(query) ||
                    submenu.description.toLowerCase().includes(query)) {
                    results.push({
                        type: 'action',
                        data: submenu,
                        parent: module,
                    });
                }
            });
        });

        this.state.filteredModules = results;
    }

    /**
     * Clear search
     */
    clearSearch() {
        this.state.searchQuery = "";
        this.state.filteredModules = [];
        if (this.searchInputRef.el) {
            this.searchInputRef.el.focus();
        }
    }

    /**
     * Track recently accessed items
     */
    trackRecentAccess(id, name, icon) {
        const recent = this.getRecentlyAccessed();
        const item = { id, name, icon, timestamp: Date.now() };

        // Remove if already exists
        const filtered = recent.filter(r => r.id !== id);

        // Add to front
        filtered.unshift(item);

        // Keep only last 5
        const updated = filtered.slice(0, 5);

        localStorage.setItem('health_landing_recent', JSON.stringify(updated));
        this.state.recentlyAccessed = updated;
    }

    /**
     * Get recently accessed from localStorage
     */
    getRecentlyAccessed() {
        try {
            const stored = localStorage.getItem('health_landing_recent');
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    }

    /**
     * Toggle favorite
     */
    toggleFavorite(id, name, icon) {
        const favorites = this.getFavorites();
        const index = favorites.findIndex(f => f.id === id);

        if (index >= 0) {
            // Remove from favorites
            favorites.splice(index, 1);
        } else {
            // Add to favorites
            favorites.push({ id, name, icon });
        }

        localStorage.setItem('health_landing_favorites', JSON.stringify(favorites));
        this.state.favorites = favorites;
    }

    /**
     * Check if item is favorited
     */
    isFavorite(id) {
        return this.state.favorites.some(f => f.id === id);
    }

    /**
     * Get favorites from localStorage
     */
    getFavorites() {
        try {
            const stored = localStorage.getItem('health_landing_favorites');
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    }

    /**
     * Keyboard shortcuts
     */
    handleKeyboard(event) {
        // ESC to close modal or go back
        if (event.key === 'Escape') {
            if (this.state.modalModule) {
                this.closeModal();
            } else if (this.state.currentView === 'submenu') {
                this.showMain();
            }
        }

        // Number keys 1-9 for quick module access (when not in search)
        if (event.target.tagName !== 'INPUT' && /^[1-9]$/.test(event.key)) {
            const index = parseInt(event.key) - 1;
            if (this.modules[index]) {
                this.showSubmenu(this.modules[index]);
            }
        }

        // Ctrl/Cmd + K for search focus
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        }
    }

    /**
     * Get filtered or all modules
     */
    getDisplayModules() {
        if (this.state.searchQuery && this.state.filteredModules.length > 0) {
            return this.state.filteredModules.filter(r => r.type === 'module').map(r => r.data);
        }
        return this.modules;
    }
}

HealthLandingDashboard.template = "health_landing.DashboardTemplate";
HealthLandingDashboard.components = { HubSpokeWidget, PatientSpokeModal };

// Register the component as a client action
registry.category("actions").add("health_landing_dashboard", HealthLandingDashboard);
