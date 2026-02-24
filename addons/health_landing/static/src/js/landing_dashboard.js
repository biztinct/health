/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
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
                name: _t("Patient Management"),
                icon: "fa-users",
                description: _t("Manage patient records and information"),
                class: "module-patient",
                submenus: [
                    {
                        name: _t("Client"),
                        icon: "fa-user-circle",
                        action: "hub_spoke",
                        description: _t("View patient hub-and-spoke dashboard")
                    },
                ],
            },
            {
                id: "scheduling",
                name: _t("Scheduling & Staff"),
                icon: "fa-calendar-check-o",
                description: _t("Staff scheduling and workload management"),
                class: "module-scheduling",
                submenus: [
                    {
                        name: _t("Assignment Dashboard"),
                        icon: "fa-dashboard",
                        action: "health_fieldservice.action_fso_assignment_dashboard",
                        description: _t("View staff assignments")
                    },
                    {
                        name: _t("Visual Scheduler"),
                        icon: "fa-calendar",
                        action: "health_fieldservice.action_assignment_scheduler_grid",
                        description: _t("Visual scheduling interface")
                    },
                    {
                        name: _t("Timeline View"),
                        icon: "fa-clock-o",
                        action: "health_fieldservice.action_assignment_web_timeline_view",
                        description: _t("Timeline of assignments")
                    },
                    {
                        name: _t("Staff Availability"),
                        icon: "fa-user-circle",
                        action: "health_fieldservice.action_health_staff_availability",
                        description: _t("Manage staff availability")
                    },
                    {
                        name: _t("Staff Workload"),
                        icon: "fa-bar-chart",
                        action: "health_fieldservice.action_staff_workload_dashboard",
                        description: _t("Monitor staff workload")
                    },
                    {
                        name: _t("Healthcare Skills"),
                        icon: "fa-graduation-cap",
                        action: "health_fieldservice.action_healthcare_skills",
                        description: _t("Manage staff skills")
                    },
                    {
                        name: _t("Service Areas"),
                        icon: "fa-map",
                        action: "health_fieldservice.action_service_areas",
                        description: _t("Configure service areas")
                    },
                    {
                        name: _t("Healthcare Staff"),
                        icon: "fa-user-md",
                        action: "health_fieldservice.action_healthcare_staff",
                        description: _t("Manage healthcare staff")
                    },
                ],
            },
            {
                id: "crm",
                name: _t("CRM"),
                icon: "fa-handshake-o",
                description: _t("Customer relationship management"),
                class: "module-crm",
                submenus: [
                    {
                        name: _t("Leads"),
                        icon: "fa-star-o",
                        action: "crm.crm_lead_all_leads",
                        description: _t("Manage potential customers")
                    },
                    {
                        name: _t("CRM Contacts"),
                        icon: "fa-address-card",
                        action: "health_crm.action_healthcare_opportunities",
                        description: _t("Track customer interactions")
                    },
                    {
                        name: _t("Customers"),
                        icon: "fa-user-circle",
                        action: "base.action_partner_form",
                        description: _t("View all customers")
                    },
                    {
                        name: _t("Healthcare Relationships"),
                        icon: "fa-users",
                        action: "health_crm.action_health_client_relation",
                        description: _t("Manage patient relationships")
                    },
                ],
            },
            {
                id: "fieldservice",
                name: _t("Field Service"),
                icon: "fa-ambulance",
                description: _t("Mobile healthcare service management"),
                class: "module-fieldservice",
                submenus: [
                    {
                        name: _t("Field Service Orders"),
                        icon: "fa-clipboard",
                        action: "health_fieldservice.action_health_fieldservice_order",
                        description: _t("Manage service orders")
                    },
                    {
                        name: _t("Communications"),
                        icon: "fa-comments",
                        action: "health_fieldservice.action_health_fieldservice_communication",
                        description: _t("Real-time team communications")
                    },
                    {
                        name: _t("Portable Equipment"),
                        icon: "fa-briefcase",
                        action: "health_fieldservice.action_health_portable_equipment",
                        description: _t("Track medical equipment")
                    },
                    {
                        name: _t("Clinical Protocols"),
                        icon: "fa-file-text-o",
                        action: "health_fieldservice.action_health_clinical_protocol",
                        description: _t("Clinical guidelines")
                    },
                    {
                        name: _t("Field Service Teams"),
                        icon: "fa-users",
                        action: "health_fieldservice.action_health_fieldservice_team",
                        description: _t("Manage service teams")
                    },
                ],
            },
            {
                id: "packages",
                name: _t("Service Packages"),
                icon: "fa-gift",
                description: _t("Manage service packages and products"),
                class: "module-packages",
                submenus: [
                    {
                        name: _t("Package Products"),
                        icon: "fa-cube",
                        action: "health_invoicing.action_healthcare_package_products",
                        description: _t("Configure package products")
                    },
                    {
                        name: _t("Patient Packages"),
                        icon: "fa-gift",
                        action: "health_invoicing.action_health_service_package",
                        description: _t("View patient subscriptions")
                    },
                ],
            },
            {
                id: "pricing",
                name: _t("Advanced Pricelist"),
                icon: "fa-tags",
                description: _t("Dynamic pricing rules and engines"),
                class: "module-pricing",
                submenus: [
                    {
                        name: _t("Pricing Engines"),
                        icon: "fa-cog",
                        action: "advanced_pricing.action_advanced_pricing_engines",
                        description: _t("Configure pricing engines")
                    },
                    {
                        name: _t("Pricing Rules"),
                        icon: "fa-list-ul",
                        action: "advanced_pricing.action_pricing_rules_with_visual",
                        description: _t("Manage pricing rules")
                    },
                    {
                        name: _t("Quick Edit Rules"),
                        icon: "fa-edit",
                        action: "advanced_pricing.action_pricing_rules_quick_edit",
                        description: _t("Inline edit pricing rules")
                    },
                ],
            },
            {
                id: "billing",
                name: _t("Billing & Invoicing"),
                icon: "fa-money",
                description: _t("Financial management and billing"),
                class: "module-billing",
                submenus: [
                    {
                        name: _t("Service Billing"),
                        icon: "fa-file-text",
                        action: "health_invoicing.action_health_service_billing",
                        description: _t("Create and manage invoices")
                    },
                    {
                        name: _t("AR Dashboard"),
                        icon: "fa-dashboard",
                        action: "health_invoicing.action_healthcare_ar_dashboard",
                        description: _t("Accounts receivable overview")
                    },
                    {
                        name: _t("Overdue Patients"),
                        icon: "fa-exclamation-triangle",
                        action: "health_invoicing.action_healthcare_overdue_patients",
                        description: _t("Track outstanding payments")
                    },
                    {
                        name: _t("Payment Transactions"),
                        icon: "fa-credit-card",
                        action: "health_invoicing.action_health_payment_transaction",
                        description: _t("View payment history")
                    },
                    {
                        name: _t("Process Payments"),
                        icon: "fa-cogs",
                        action: "health_invoicing.action_health_payment_workflow_wizard",
                        description: _t("Payment workflow")
                    },
                ],
            },
            {
                id: "facilities",
                name: _t("Facilities"),
                icon: "fa-hospital-o",
                description: _t("Healthcare facility management"),
                class: "module-facilities",
                submenus: [
                    {
                        name: _t("Healthcare Facilities"),
                        icon: "fa-building",
                        action: "health_base.action_health_facility",
                        description: _t("Manage facility locations")
                    },
                ],
            },
            {
                id: "config",
                name: _t("Configuration"),
                icon: "fa-cogs",
                description: _t("System configuration and settings"),
                class: "module-config",
                submenus: [
                    {
                        name: _t("Patient Categories"),
                        icon: "fa-tags",
                        action: "health_base.action_health_patient_category",
                        description: _t("Configure patient types")
                    },
                    {
                        name: _t("Service Types"),
                        icon: "fa-list",
                        action: "health_base.action_health_service_type",
                        description: _t("Define service types")
                    },
                    {
                        name: _t("Medical Specialties"),
                        icon: "fa-stethoscope",
                        action: "health_base.action_health_medical_specialty",
                        description: _t("Manage specialties")
                    },
                    {
                        name: _t("Symptoms"),
                        icon: "fa-heartbeat",
                        action: "health_base.action_health_symptom",
                        description: _t("Symptom catalog")
                    },
                    {
                        name: _t("Referral Sources"),
                        icon: "fa-share-alt",
                        action: "health_base.action_health_referral_source",
                        description: _t("Track referral sources")
                    },
                    {
                        name: _t("Insurance Providers"),
                        icon: "fa-shield",
                        action: "health_base.action_health_insurance_provider",
                        description: _t("Insurance companies")
                    },
                    {
                        name: _t("Urgency Levels"),
                        icon: "fa-exclamation-circle",
                        action: "health_base.action_health_urgency_level",
                        description: _t("Priority levels")
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
