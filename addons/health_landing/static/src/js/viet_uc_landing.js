/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Viet Uc Dashboard Component
 *
 * Main dashboard with 5 modules:
 * - Client (Patient Management)
 * - Booking (Appointments)
 * - CRM
 * - Accounts (Billing & Invoicing)
 * - Configuration
 */
class VietUcDashboard extends Component {
    setup() {
        this.actionService = useService("action");
        this.searchInputRef = useRef("searchInput");

        this.state = useState({
            currentView: "main", // "main" or "submenu"
            currentModule: null,
            searchQuery: "",
            breadcrumb: ["Viet Uc"],
        });

        // Initialize on mount
        onMounted(() => {
            document.addEventListener("keydown", this.handleKeyboard.bind(this));
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        });

        // Main Viet Uc modules (5 items)
        this.vietUcModules = [
            {
                id: "client",
                name: "Client",
                icon: "fa-users",
                description: "Patient management and client information",
                class: "module-patient",
                action: "health_base.action_health_patient",
                type: "direct_action", // Direct action, no submenu
            },
            {
                id: "booking",
                name: "Booking",
                icon: "fa-calendar-check-o",
                description: "Field service orders and booking management",
                class: "module-scheduling",
                action: "health_fieldservice.action_health_fieldservice_order",
                type: "direct_action", // Direct action, no submenu
            },
            {
                id: "crm",
                name: "CRM",
                icon: "fa-handshake-o",
                description: "Customer relationship management",
                class: "module-crm",
                type: "submenu",
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
                id: "accounts",
                name: "Accounts",
                icon: "fa-money",
                description: "Billing, invoicing, and financial management",
                class: "module-billing",
                type: "submenu",
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
                id: "config",
                name: "Configuration",
                icon: "fa-cogs",
                description: "System configuration and settings",
                class: "module-config",
                type: "submenu",
                submenus: [
                    {
                        name: "Patient Categories",
                        icon: "fa-bookmark",
                        action: "health_base.action_health_patient_category",
                        description: "Configure patient categories"
                    },
                    {
                        name: "Service Types",
                        icon: "fa-list-ul",
                        action: "health_base.action_health_service_type",
                        description: "Define service types"
                    },
                    {
                        name: "Medical Specialties",
                        icon: "fa-stethoscope",
                        action: "health_base.action_health_specialty",
                        description: "Manage medical specialties"
                    },
                    {
                        name: "Symptoms",
                        icon: "fa-heartbeat",
                        action: "health_base.action_health_symptom",
                        description: "Configure symptoms"
                    },
                    {
                        name: "Referral Sources",
                        icon: "fa-share-alt",
                        action: "health_base.action_health_referral_source",
                        description: "Manage referral sources"
                    },
                    {
                        name: "Insurance Providers",
                        icon: "fa-shield",
                        action: "health_base.action_health_insurance_provider",
                        description: "Configure insurance"
                    },
                    {
                        name: "Urgency Levels",
                        icon: "fa-exclamation-circle",
                        action: "health_base.action_health_urgency_level",
                        description: "Define urgency levels"
                    },
                ],
            },
        ];
    }

    /**
     * Get filtered modules based on search query
     */
    getVietUcModules() {
        if (!this.state.searchQuery) {
            return this.vietUcModules;
        }

        const query = this.state.searchQuery.toLowerCase();
        return this.vietUcModules.filter(module =>
            module.name.toLowerCase().includes(query) ||
            module.description.toLowerCase().includes(query)
        );
    }

    /**
     * Get CRM submenus
     */
    getCrmSubmenus() {
        const crm = this.vietUcModules.find(m => m.id === "crm");
        return crm ? crm.submenus : [];
    }

    /**
     * Get Accounts submenus
     */
    getAccountsSubmenus() {
        const accounts = this.vietUcModules.find(m => m.id === "accounts");
        return accounts ? accounts.submenus : [];
    }

    /**
     * Get Configuration submenus
     */
    getConfigurationSubmenus() {
        const config = this.vietUcModules.find(m => m.id === "config");
        return config ? config.submenus : [];
    }

    /**
     * Handle module click - route to appropriate view
     */
    async handleModuleClick(module) {
        if (module.type === "direct_action") {
            // Client or Booking - open directly
            await this.launchAction(module.action, module.name, module.icon);
        } else if (module.type === "submenu") {
            // CRM, Accounts, Config - show submenu dashboard
            this.showSubmenu(module);
        }
    }

    /**
     * Navigate to submenu dashboard
     */
    showSubmenu(module) {
        this.state.currentView = "submenu";
        this.state.currentModule = module;
        this.state.breadcrumb = ["Viet Uc", module.name];
    }

    /**
     * Navigate back to main dashboard
     */
    showMain() {
        this.state.currentView = "main";
        this.state.currentModule = null;
        this.state.breadcrumb = ["Viet Uc"];
        this.state.searchQuery = "";
    }

    /**
     * Launch Odoo action
     */
    async launchAction(actionXmlId, actionName, icon) {
        try {
            await this.actionService.doAction(actionXmlId);
        } catch (error) {
            console.error("Failed to launch action:", actionXmlId, error);
        }
    }

    /**
     * Go back to root dashboard
     */
    goBackToRoot() {
        this.showMain();
    }

    /**
     * Clear search query
     */
    clearSearch() {
        this.state.searchQuery = "";
    }

    /**
     * Search input handler
     */
    onSearchInput(event) {
        this.state.searchQuery = event.target.value;
    }

    /**
     * Keyboard shortcuts
     */
    handleKeyboard(event) {
        // Ctrl+K or Cmd+K to focus search
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }
        }
        // Escape to close search
        if (event.key === 'Escape') {
            this.clearSearch();
        }
    }
}

VietUcDashboard.template = "health_landing.VietUcDashboardTemplate";

// Register components
registry.category("actions").add("viet_uc_dashboard", VietUcDashboard);
