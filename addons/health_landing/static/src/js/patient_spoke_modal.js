/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Patient Spoke Modal Component
 *
 * Displays summarized data for each spoke in a beautiful modal popup:
 * - Client Info: Personal details, contact info
 * - Relations: Caregivers, payers, emergency contacts
 * - Map: Address and location map
 * - Packages: Active service packages
 * - Bookings: Upcoming and recent bookings
 * - Financials: Pending invoices, payment status
 *
 * Each modal includes an "Edit" button to open the full Odoo form
 */
export class PatientSpokeModal extends Component {
    static template = "health_landing.PatientSpokeModalTemplate";

    static props = {
        spoke: Object,
        patientId: Number,
        onClose: Function,
        onEdit: Function,
        onItemClick: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            data: null,
            error: null,
        });

        onWillStart(async () => {
            await this.loadSpokeData();
        });
    }

    /**
     * Load data specific to each spoke type
     */
    async loadSpokeData() {
        try {
            const spokeId = this.props.spoke.id;

            switch (spokeId) {
                case "client_info":
                    await this.loadClientInfo();
                    break;
                case "relations":
                    await this.loadRelations();
                    break;
                case "map":
                    await this.loadMapData();
                    break;
                case "packages":
                    await this.loadPackages();
                    break;
                case "bookings":
                    await this.loadBookings();
                    break;
                case "financials":
                    await this.loadFinancials();
                    break;
                default:
                    throw new Error(`Unknown spoke type: ${spokeId}`);
            }

            this.state.loading = false;
        } catch (error) {
            console.error(`Failed to load ${this.props.spoke.id} data:`, error);
            this.state.error = error.message;
            this.state.loading = false;
        }
    }

    /**
     * Load client info data
     */
    async loadClientInfo() {
        const data = await this.orm.call(
            "res.partner",
            "read",
            [this.props.patientId],
            {
                fields: [
                    "name", "patient_code", "age", "gender", "date_of_birth",
                    "phone", "mobile", "email",
                    "street", "street2", "city", "state_id", "country_id", "zip",
                    "primary_caregiver_id", "primary_emergency_contact_id",
                ],
            }
        );

        this.state.data = data[0];
    }

    /**
     * Load relations data
     */
    async loadRelations() {
        // Load caregivers, payers, emergency contacts
        const relations = await this.orm.searchRead(
            "health.client.relation",
            [["client_id", "=", this.props.patientId]],
            ["representative_id", "role", "relationship_type", "is_primary", "phone"],
            {limit: 10}
        );

        this.state.data = {
            caregivers: relations.filter(r => r.role === "caregiver"),
            payers: relations.filter(r => r.role === "payer"),
            emergency: relations.filter(r => r.role === "emergency_contact"),
            referrers: relations.filter(r => r.role === "referrer"),
            total: relations.length,
        };
    }

    /**
     * Load map/address data
     */
    async loadMapData() {
        const data = await this.orm.call(
            "res.partner",
            "read",
            [this.props.patientId],
            {
                fields: [
                    "street", "street2", "city", "state_id", "country_id", "zip",
                    "partner_latitude", "partner_longitude",
                ],
            }
        );

        this.state.data = data[0];
    }

    /**
     * Load active packages
     */
    async loadPackages() {
        const packages = await this.orm.searchRead(
            "health.service.package",
            [
                ["patient_id", "=", this.props.patientId],
                ["state", "in", ["active", "partially_consumed"]],
            ],
            ["name", "package_product_id", "start_date", "expiry_date", "total_sessions", "remaining_sessions", "state"],
            {limit: 5, order: "expiry_date asc"}
        );

        this.state.data = {
            packages: packages,
            total: packages.length,
        };
    }

    /**
     * Load bookings (upcoming + recent)
     */
    async loadBookings() {
        const today = new Date().toISOString().split('T')[0];
        const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        // Upcoming bookings
        const upcoming = await this.orm.searchRead(
            "health.fieldservice.order",
            [
                ["patient_id", "=", this.props.patientId],
                ["scheduled_date", ">=", today],
                ["state", "not in", ["cancelled", "done"]],
            ],
            ["name", "scheduled_date", "scheduled_datetime", "service_type_id", "primary_staff_id", "state", "urgency_level"],
            {limit: 3, order: "scheduled_date asc"}
        );

        // Recent bookings (last 7 days)
        const recent = await this.orm.searchRead(
            "health.fieldservice.order",
            [
                ["patient_id", "=", this.props.patientId],
                ["scheduled_date", ">=", weekAgo],
                ["scheduled_date", "<", today],
            ],
            ["name", "scheduled_date", "scheduled_datetime", "service_type_id", "primary_staff_id", "state"],
            {limit: 3, order: "scheduled_date desc"}
        );

        this.state.data = {
            upcoming: upcoming,
            recent: recent,
            total: upcoming.length + recent.length,
        };
    }

    /**
     * Load financial data
     */
    async loadFinancials() {
        // Pending invoices
        const pending = await this.orm.searchRead(
            "account.move",
            [
                ["partner_id", "=", this.props.patientId],
                ["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
                ["payment_state", "in", ["not_paid", "partial"]],
            ],
            ["name", "invoice_date", "amount_total", "amount_residual", "payment_state", "invoice_date_due"],
            {limit: 5, order: "invoice_date_due asc"}
        );

        // Calculate totals
        const totalPending = pending.reduce((sum, inv) => sum + inv.amount_residual, 0);
        const overdueCount = pending.filter(inv => {
            if (!inv.invoice_date_due) return false;
            return new Date(inv.invoice_date_due) < new Date();
        }).length;

        // Last payment
        const payments = await this.orm.searchRead(
            "account.payment",
            [
                ["partner_id", "=", this.props.patientId],
                ["state", "=", "posted"],
            ],
            ["date", "amount"],
            {limit: 1, order: "date desc"}
        );

        this.state.data = {
            pending_invoices: pending,
            total_pending: totalPending,
            overdue_count: overdueCount,
            last_payment: payments.length > 0 ? payments[0] : null,
        };
    }

    /**
     * Handle Edit button click - opens full Odoo form
     */
    async onEditClick() {
        const spokeId = this.props.spoke.id;
        let action = null;

        switch (spokeId) {
            case "client_info":
                action = {
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "current",
                };
                break;

            case "relations":
                action = "health_crm.action_health_client_relation";
                break;

            case "map":
                action = {
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "current",
                };
                break;

            case "packages":
                action = "health_invoicing.action_health_service_package";
                break;

            case "bookings":
                action = "health_fieldservice.action_health_fieldservice_order";
                break;

            case "financials":
                action = "health_invoicing.action_health_service_billing";
                break;
        }

        if (action) {
            await this.actionService.doAction(action);
            if (this.props.onEdit) {
                this.props.onEdit(spokeId);
            }
        }
    }

    /**
     * Handle item click (e.g., booking card click for nested hub-and-spoke)
     */
    onItemClick(item, itemType) {
        if (this.props.onItemClick) {
            this.props.onItemClick(item, itemType, this.props.spoke.id);
        }
    }

    /**
     * Format currency
     */
    formatCurrency(amount) {
        return new Intl.NumberFormat('vi-VN', {
            style: 'currency',
            currency: 'VND',
        }).format(amount);
    }

    /**
     * Format date
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('vi-VN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    }

    /**
     * Get status badge class
     */
    getStatusBadge(state) {
        const badges = {
            'draft': 'badge-secondary',
            'confirmed': 'badge-info',
            'assigned': 'badge-primary',
            'in_progress': 'badge-warning',
            'done': 'badge-success',
            'cancelled': 'badge-danger',
            'active': 'badge-success',
            'partially_consumed': 'badge-warning',
            'consumed': 'badge-secondary',
            'expired': 'badge-danger',
        };
        return badges[state] || 'badge-secondary';
    }
}
