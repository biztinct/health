/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Hub-and-Spoke Patient Dashboard Widget
 *
 * Interactive radial visualization with patient at center and 6 data spokes:
 * - Client Info (Blue)
 * - Relations (Teal)
 * - Map (Cyan)
 * - Packages (Purple)
 * - Bookings (Orange)
 * - Financials (Green)
 *
 * Click spoke → Opens modal with summarized data + Edit button
 */
export class HubSpokeWidget extends Component {
    static template = "health_landing.HubSpokeTemplate";

    static props = {
        patientId: Number,
        patientName: String,
        onBack: Function,
        onSpokeClick: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.svgRef = useRef("hubSpokeSvg");

        this.state = useState({
            hoveredSpoke: null,
            patientData: null,
            loading: true,
        });

        // Hub-and-spoke configuration
        this.spokes = [
            {
                id: "client_info",
                label: "Client Info",
                icon: "fa-user",
                color: "#1565C0",
                lightColor: "#E4F4FD",
                angle: 0,
                description: "Personal details and contact"
            },
            {
                id: "relations",
                label: "Relations",
                icon: "fa-users",
                color: "#00796B",
                lightColor: "#D9F2F0",
                angle: 60,
                description: "Caregivers, payers, contacts"
            },
            {
                id: "map",
                label: "Map",
                icon: "fa-map-marker",
                color: "#0097A7",
                lightColor: "#B2EBF2",
                angle: 120,
                description: "Address and location"
            },
            {
                id: "packages",
                label: "Packages",
                icon: "fa-gift",
                color: "#6B4BA8",
                lightColor: "#E8E0F5",
                angle: 180,
                description: "Active service packages"
            },
            {
                id: "bookings",
                label: "Bookings",
                icon: "fa-calendar",
                color: "#D46E00",
                lightColor: "#FEE8C9",
                angle: 240,
                description: "Appointments and visits"
            },
            {
                id: "financials",
                label: "Financials",
                icon: "fa-money",
                color: "#43A047",
                lightColor: "#DBF0DB",
                angle: 300,
                description: "Invoices and payments"
            },
        ];

        // SVG dimensions
        this.svgWidth = 800;
        this.svgHeight = 600;
        this.centerX = this.svgWidth / 2;
        this.centerY = this.svgHeight / 2;
        this.hubRadius = 80;
        this.spokeRadius = 220;
        this.spokeNodeRadius = 60;

        onMounted(() => {
            this.loadPatientData();
        });
    }

    /**
     * Load patient data from backend
     */
    async loadPatientData() {
        try {
            const data = await this.orm.call(
                "res.partner",
                "read",
                [this.props.patientId],
                {
                    fields: [
                        "name", "patient_code", "age", "gender",
                        "phone", "mobile", "email",
                        "street", "city", "state_id", "country_id",
                        "partner_latitude", "partner_longitude",
                    ],
                }
            );

            this.state.patientData = data[0] || {};
            this.state.loading = false;
        } catch (error) {
            console.error("Failed to load patient data:", error);
            this.state.loading = false;
        }
    }

    /**
     * Calculate spoke node position
     */
    getSpokePosition(angle) {
        const radians = (angle - 90) * (Math.PI / 180); // -90 to start from top
        const x = this.centerX + this.spokeRadius * Math.cos(radians);
        const y = this.centerY + this.spokeRadius * Math.sin(radians);
        return { x, y };
    }

    /**
     * Calculate spoke line path
     */
    getSpokePath(angle) {
        const radians = (angle - 90) * (Math.PI / 180);

        // Start from edge of hub circle
        const startX = this.centerX + this.hubRadius * Math.cos(radians);
        const startY = this.centerY + this.hubRadius * Math.sin(radians);

        // End at edge of spoke node circle
        const endX = this.centerX + (this.spokeRadius - this.spokeNodeRadius) * Math.cos(radians);
        const endY = this.centerY + (this.spokeRadius - this.spokeNodeRadius) * Math.sin(radians);

        return `M ${startX} ${startY} L ${endX} ${endY}`;
    }

    /**
     * Handle spoke hover
     */
    onSpokeMouseEnter(spoke) {
        this.state.hoveredSpoke = spoke.id;
    }

    onSpokeMouseLeave() {
        this.state.hoveredSpoke = null;
    }

    /**
     * Handle spoke click - open custom modal views
     */
    async onSpokeClick(spoke) {
        const spokeId = spoke.id;
        let action = null;

        switch (spokeId) {
            case "client_info":
                // Open Client Info modal with summary
                action = {
                    type: "ir.actions.act_window",
                    name: "Client Information",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_client_info_modal',
                    },
                };
                break;

            case "relations":
                // Open Relations modal with hierarchy widget
                action = {
                    type: "ir.actions.act_window",
                    name: "Patient Relationships",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_relations_modal',
                    },
                };
                break;

            case "map":
                // Open Map modal with address and map widget
                action = {
                    type: "ir.actions.act_window",
                    name: "Patient Location",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_map_modal',
                    },
                };
                break;

            case "packages":
                // Open Packages modal with summary
                action = {
                    type: "ir.actions.act_window",
                    name: "Service Packages",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_packages_modal',
                    },
                };
                break;

            case "bookings":
                // Open Bookings modal with appointments
                action = {
                    type: "ir.actions.act_window",
                    name: "Patient Bookings",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_bookings_modal',
                    },
                };
                break;

            case "financials":
                // Open Financials modal with invoice summary
                action = {
                    type: "ir.actions.act_window",
                    name: "Patient Financials",
                    res_model: "res.partner",
                    res_id: this.props.patientId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        'form_view_ref': 'health_landing.view_patient_financials_modal',
                    },
                };
                break;
        }

        if (action) {
            await this.actionService.doAction(action);
        }
    }

    /**
     * Handle center hub click - open full patient form
     */
    async onHubClick() {
        // Open patient using the standard action - this ensures we get the right form view
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.props.patientId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                'form_view_ref': 'health_base.view_health_patient_form',
            },
        });
    }

    /**
     * Get spoke classes for styling
     */
    getSpokeClasses(spoke) {
        const classes = ["hub_spoke_node"];
        if (this.state.hoveredSpoke === spoke.id) {
            classes.push("hub_spoke_node_hovered");
        }
        return classes.join(" ");
    }

    /**
     * Get line classes for styling
     */
    getLineClasses(spoke) {
        const classes = ["hub_spoke_line"];
        if (this.state.hoveredSpoke === spoke.id) {
            classes.push("hub_spoke_line_hovered");
        }
        return classes.join(" ");
    }
}
