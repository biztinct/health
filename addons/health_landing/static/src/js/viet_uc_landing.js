/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Viet Uc Dashboard Component
 *
 * Main dashboard with 7 modules:
 * - CRM (Customer Relationship Management)
 * - Client (Patient Management)
 * - Booking (Appointments)
 * - Staff (Staff Scheduling & Workload)
 * - Accounts (Billing & Invoicing)
 * - Configuration
 * - Audit Log (System Audit Log)
 */
class VietUcDashboard extends Component {
    setup() {
        this.actionService = useService("action");
        this.searchInputRef = useRef("searchInput");

        this.state = useState({
            currentView: "main", // "main" or "submenu"
            currentModule: null,
            parentModule: null, // Track parent module for breadcrumb navigation
            searchQuery: "",
            breadcrumb: ["Viet Uc"],
            recentlyAccessed: this.getRecentlyAccessed(),
            favorites: this.getFavorites(),
        });

        // Initialize on mount
        onMounted(() => {
            document.addEventListener("keydown", this.handleKeyboard.bind(this));
            if (this.searchInputRef.el) {
                this.searchInputRef.el.focus();
            }

            // Check if we need to navigate to a specific module
            setTimeout(() => {
                if (window.vietUcNavigateToModule) {
                    const moduleId = window.vietUcNavigateToModule.moduleId;
                    const module = this.vietUcModules.find(m => m.id === moduleId);
                    if (module && module.type === 'submenu') {
                        this.showSubmenu(module);
                    }
                    // Clean up the navigation context
                    delete window.vietUcNavigateToModule;
                }
            }, 100);
        });

        // Main Viet Uc modules (7 items)
        this.vietUcModules = [
            {
                id: "crm",
                name: "CRM",
                icon: "fa-handshake-o",
                description: "Customer relationship management",
                class: "module-crm",
                type: "direct_action",
                action: "health_crm.action_healthcare_opportunities",
            },
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
                id: "staff",
                name: "Staff",
                icon: "fa-tasks",
                description: "Staff scheduling and workload management",
                class: "module-staff",
                type: "submenu",
                submenus: [
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
                id: "accounts",
                name: "Accounts",
                icon: "fa-money",
                description: "Billing, invoicing, and financial management",
                class: "module-billing",
                type: "submenu",
                submenus: [
                    {
                        name: "AR Dashboard",
                        icon: "fa-dashboard",
                        action: "health_invoicing.action_healthcare_ar_dashboard",
                        description: "Accounts receivable overview"
                    },
                    {
                        name: "Payment Transactions",
                        icon: "fa-credit-card",
                        action: "health_invoicing.action_health_payment_transaction",
                        description: "View payment history"
                    },
                    {
                        name: "Invoices",
                        icon: "fa-file-text-o",
                        action: "health_invoicing.action_healthcare_invoices",
                        description: "View all invoices"
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
                    {
                        name: "Pricing Engines",
                        icon: "fa-cogs",
                        action: "advanced_pricing.action_advanced_pricing_engines",
                        description: "Configure pricing engines"
                    },
                    {
                        name: "Pricing Rules",
                        icon: "fa-list-ul",
                        action: "advanced_pricing.action_pricing_rules_with_visual",
                        description: "Define pricing rules"
                    },
                    {
                        name: "Quick Edit Rules",
                        icon: "fa-edit",
                        action: "advanced_pricing.action_pricing_rules_quick_edit",
                        description: "Quick edit pricing rules"
                    },
                    {
                        name: "Healthcare Facilities",
                        icon: "fa-building",
                        action: "health_base.action_health_facility",
                        description: "Configure healthcare facilities"
                    },
                    {
                        name: "Portable Equipment",
                        icon: "fa-briefcase",
                        action: "health_fieldservice.action_health_portable_equipment",
                        description: "Track medical equipment"
                    },
                    {
                        name: "Package Products",
                        icon: "fa-cube",
                        action: "health_invoicing.action_healthcare_package_products",
                        description: "Configure service packages"
                    },
                ],
            },
            {
                id: "audit_log",
                name: "Audit Log",
                icon: "fa-history",
                description: "System audit log and change tracking",
                class: "module-audit",
                action: "health_base.action_health_audit_log",
                type: "direct_action", // Direct action, no submenu
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
     * Get Staff submenus
     */
    getStaffSubmenus() {
        const staff = this.vietUcModules.find(m => m.id === "staff");
        return staff ? staff.submenus : [];
    }

    /**
     * Handle module click - route to appropriate view
     */
    async handleModuleClick(module) {
        // Record the module click in recents (module-level entry)
        this.trackRecentAccess(module.id, module.name, module.icon);

        if (module.type === "direct_action") {
            // Client or Booking - open directly (skip double tracking in launchAction)
            await this.launchAction(module.action, module.name, module.icon, { skipTrack: true });
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
        // Track module-level access
        this.trackRecentAccess(module.id, module.name, module.icon);
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
     * Stores parent module context before launching action
     */
    async launchAction(actionXmlId, actionName, icon, options = {}) {
        try {
            // Store the current module as parent so breadcrumb can navigate back to it
            if (this.state.currentModule) {
                this.state.parentModule = this.state.currentModule;
                // Store breadcrumb context for the opened action
                window.vietUcBreadcrumb = {
                    parentModule: this.state.currentModule.name,
                    parentModuleId: this.state.currentModule.id,
                    actionName: actionName
                };
            }

            // Track recents unless explicitly skipped (to avoid double entries)
            if (!options.skipTrack) {
                this.trackRecentAccess(actionXmlId, actionName, icon);
            }

            // Launch action with custom context
            const action = await this.actionService.doAction(actionXmlId);

            // After action opens, inject breadcrumb if needed
            setTimeout(() => {
                this.injectBreadcrumb(actionName);
            }, 500);

            return action;
        } catch (error) {
            console.error("Failed to launch action:", actionXmlId, error);
        }
    }

    /**
     * Inject breadcrumb navigation into the action view
     */
    injectBreadcrumb(actionName) {
        const breadcrumb = window.vietUcBreadcrumb;
        if (!breadcrumb) return;

        // Look for the page title area and modify it
        const titleElements = document.querySelectorAll('.o_control_panel_main_buttons, .o_cp_top');

        if (titleElements.length > 0) {
            // Create custom breadcrumb element with data attributes for navigation
            const breadcrumbHtml = `
                <div class="viet_uc_action_breadcrumb" style="padding: 10px 16px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 8px; font-size: 13px;">
                    <i class="fa fa-home viet_uc_breadcrumb_home" style="cursor: pointer; color: #0084D8;" data-action="go-to-viet-uc"></i>
                    <span>Viet Uc</span>
                    <i class="fa fa-chevron-right" style="font-size: 10px; color: #999;"></i>
                    <span class="viet_uc_breadcrumb_module" style="color: #0084D8; cursor: pointer;" data-module-id="${breadcrumb.parentModuleId}" data-module-name="${breadcrumb.parentModule}">${breadcrumb.parentModule}</span>
                    <i class="fa fa-chevron-right" style="font-size: 10px; color: #999;"></i>
                    <span>${actionName}</span>
                </div>
            `;

            // Find the control panel and insert breadcrumb
            const controlPanel = document.querySelector('.o_control_panel');
            if (controlPanel && !document.querySelector('.viet_uc_action_breadcrumb')) {
                const breadcrumbDiv = document.createElement('div');
                breadcrumbDiv.innerHTML = breadcrumbHtml;
                const breadcrumbElement = breadcrumbDiv.firstElementChild;
                controlPanel.insertBefore(breadcrumbElement, controlPanel.firstChild);

                // Add click handlers after insertion
                setTimeout(() => {
                    this.attachBreadcrumbHandlers();
                }, 100);
            }
        }
    }

    /**
     * Attach click handlers to breadcrumb elements
     */
    attachBreadcrumbHandlers() {
        // Home icon click handler
        const homeIcon = document.querySelector('.viet_uc_breadcrumb_home');
        if (homeIcon) {
            homeIcon.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.actionService.doAction('health_landing.action_viet_uc_dashboard');
            });
        }

        // Module name click handler
        const moduleSpan = document.querySelector('.viet_uc_breadcrumb_module');
        if (moduleSpan) {
            moduleSpan.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const moduleId = moduleSpan.getAttribute('data-module-id');
                const moduleName = moduleSpan.getAttribute('data-module-name');
                // Store context and navigate to show the submenu
                window.vietUcNavigateToModule = {
                    moduleId: moduleId,
                    moduleName: moduleName
                };
                this.actionService.doAction('health_landing.action_viet_uc_dashboard');
            });
        }
    }

    /**
     * Go back to parent module (submenu) or root dashboard
     */
    goBack() {
        if (this.state.parentModule) {
            // Return to the parent submenu
            this.showSubmenu(this.state.parentModule);
        } else {
            // Return to root dashboard
            this.showMain();
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

    /**
     * Filtered modules based on search
     */
    getDisplayModules() {
        const query = (this.state.searchQuery || "").toLowerCase();
        if (!query) {
            return this.vietUcModules;
        }
        return this.vietUcModules.filter((m) => {
            const inModule =
                m.name.toLowerCase().includes(query) ||
                (m.description || "").toLowerCase().includes(query);
            const inSubmenu = (m.submenus || []).some(
                (s) =>
                    s.name.toLowerCase().includes(query) ||
                    (s.description || "").toLowerCase().includes(query)
            );
            return inModule || inSubmenu;
        });
    }

    /**
     * Track recently accessed items
     */
    trackRecentAccess(id, name, icon) {
        const recent = this.getRecentlyAccessed();
        const item = { id, name, icon, timestamp: Date.now() };
        const filtered = recent.filter((r) => r.id !== id);
        filtered.unshift(item);
        const updated = filtered.slice(0, 5);
        localStorage.setItem("viet_uc_recent", JSON.stringify(updated));
        this.state.recentlyAccessed = updated;
    }

    getRecentlyAccessed() {
        try {
            const stored = localStorage.getItem("viet_uc_recent");
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            return [];
        }
    }

    toggleFavorite(id, name, icon) {
        const favorites = this.getFavorites();
        const index = favorites.findIndex((f) => f.id === id);
        if (index >= 0) {
            favorites.splice(index, 1);
        } else {
            favorites.push({ id, name, icon });
        }
        localStorage.setItem("viet_uc_favorites", JSON.stringify(favorites));
        this.state.favorites = favorites;
    }

    isFavorite(id) {
        return this.state.favorites.some((f) => f.id === id);
    }

    getFavorites() {
        try {
            const stored = localStorage.getItem("viet_uc_favorites");
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            return [];
        }
    }
}

VietUcDashboard.template = "health_landing.VietUcDashboardTemplate";

// Global function to navigate back to parent module
window.vietUcGoBackToModule = function() {
    const breadcrumb = window.vietUcBreadcrumb;
    if (breadcrumb && breadcrumb.parentModuleId) {
        // Navigate back to Viet Uc dashboard with the parent module
        window.location.href = `/web#action=health_landing.action_viet_uc_dashboard&menu_id=${breadcrumb.parentModuleId}`;
    } else {
        // Fallback to main dashboard
        window.location.href = '/web#action=health_landing.action_viet_uc_dashboard';
    }
};

// Register components
registry.category("actions").add("viet_uc_dashboard", VietUcDashboard);
