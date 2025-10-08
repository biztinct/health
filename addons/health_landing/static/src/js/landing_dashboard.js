/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Healthcare Landing Dashboard Component
 *
 * Provides a modern, icon-driven navigation interface with two-level dashboard structure.
 * Main Dashboard → Submenu Dashboard → Action Window
 */
class HealthLandingDashboard extends Component {
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            currentView: "main", // "main" or "submenu"
            currentModule: null,
            breadcrumb: ["Home"],
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
                        name: "Patient Registry",
                        icon: "fa-address-book",
                        action: "health_base.action_health_patient",
                        description: "View and manage all patients"
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
    }

    /**
     * Navigate back to main dashboard
     */
    showMain() {
        this.state.currentView = "main";
        this.state.currentModule = null;
        this.state.breadcrumb = ["Home"];
    }

    /**
     * Launch Odoo action window
     */
    async launchAction(actionXmlId) {
        try {
            await this.actionService.doAction(actionXmlId);
        } catch (error) {
            console.error("Failed to launch action:", actionXmlId, error);
            // Fallback: try to parse XML ID and load directly
            const [module, actionName] = actionXmlId.split(".");
            if (module && actionName) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    xml_id: actionXmlId,
                });
            }
        }
    }
}

HealthLandingDashboard.template = "health_landing.DashboardTemplate";

// Register the component as a client action
registry.category("actions").add("health_landing_dashboard", HealthLandingDashboard);
