/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Hub-and-Spoke FSO Dashboard Widget
 *
 * Interactive radial visualization with FSO at center and workflow spokes:
 * - Draft, Booked, Assigned, In Progress (Stage indicators)
 * - Clinical Notes, Invoice (Conditional action indicators)
 * - Pay Now, Pay Later (Payment options)
 * - Collect Cash, Payment Received (Payment tracking)
 * - Completed (Final stage)
 *
 * Arrows blink based on conditions to guide user through workflow
 */
export class FSOHubSpokeWidget extends Component {
    static template = "health_landing.FSOHubSpokeTemplate";

    static props = {
        fsoId: Number,
        fsoName: String,
        onBack: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.svgRef = useRef("hubSpokeSvg");

        this.state = useState({
            hoveredSpoke: null,
            fsoData: null,
            loading: true,
        });

        // Excalidraw Flowchart Layout - Exact positioning as wireframe
        // Hub: Booking (center)
        // Top row: Service Packages, Quote, Confirm Booking
        // Middle row: Equipment, Booking (hub), Staff Assignment
        // Below hub: Start Service
        // Bottom row: Clinical Notes, Invoice, Pay Now, Pay Later
        // Sub-nodes: Collect Cash, Payment Received

        this.allNodes = [
            // Top row nodes - compressed layout
            {
                id: "service_packages",
                label: "Service Packages",
                icon: "fa-gift",
                color: "#9C27B0",
                lightColor: "#F3E5F5",
                type: "info",
                shape: "rect",
                x: 120,
                y: 40,
                width: 140,
                height: 60,
                description: "View service packages"
            },
            {
                id: "quote",
                label: "Quote",
                icon: "fa-file-text-o",
                color: "#2196F3",
                lightColor: "#E3F2FD",
                type: "info",
                shape: "rect",
                x: 400,
                y: 15,
                width: 120,
                height: 60,
                actionField: "sale_order_id",
                description: "Healthcare quote"
            },
            {
                id: "confirm_booking",
                label: "Confirm Booking",
                icon: "fa-check-circle",
                color: "#4CAF50",
                lightColor: "#E8F5E9",
                type: "action",
                shape: "oval",
                x: 740,
                y: 70,
                radius: 55,
                actionField: "show_booked_indicator",
                description: "Confirm the booking"
            },

            // Middle row - compressed closer to hub
            {
                id: "equipment",
                label: "Equipment",
                icon: "fa-briefcase",
                color: "#607D8B",
                lightColor: "#ECEFF1",
                type: "info",
                shape: "rect",
                x: 80,
                y: 170,
                width: 130,
                height: 60,
                description: "Required equipment"
            },
            {
                id: "booking_hub",
                label: "Booking",
                icon: "fa-calendar",
                color: "#3498db",
                lightColor: "#E3F2FD",
                type: "hub",
                shape: "rect",
                x: 400,
                y: 160,
                width: 160,
                height: 80,
                description: "Main booking hub"
            },
            {
                id: "staff_assignment",
                label: "Staff Assignment",
                icon: "fa-user-md",
                color: "#9C27B0",
                lightColor: "#F3E5F5",
                type: "action",
                shape: "rect",
                x: 720,
                y: 170,
                width: 160,
                height: 60,
                actionField: "show_assigned_indicator",
                description: "Assign staff to booking"
            },

            // Start Service (compressed closer to hub)
            {
                id: "start_service",
                label: "Start Service",
                icon: "fa-play-circle",
                color: "#FF9800",
                lightColor: "#FFF3E0",
                type: "transition",
                shape: "oval",
                x: 480,
                y: 310,
                radius: 60,
                actionField: "show_in_progress_indicator",
                description: "Start the service"
            },

            // Bottom row (compressed)
            {
                id: "clinical_notes",
                label: "Clinical Notes",
                icon: "fa-stethoscope",
                color: "#00BCD4",
                lightColor: "#E0F7FA",
                type: "action",
                shape: "rect",
                x: 80,
                y: 430,
                width: 130,
                height: 55,
                actionField: "show_clinical_notes_arrow",
                description: "Fill clinical notes"
            },
            {
                id: "invoice",
                label: "Invoice",
                icon: "fa-file-invoice",
                color: "#4CAF50",
                lightColor: "#E8F5E9",
                type: "action",
                shape: "rect",
                x: 270,
                y: 430,
                width: 120,
                height: 55,
                actionField: "show_invoice_arrow",
                description: "Create invoice"
            },
            {
                id: "pay_now",
                label: "Pay Now",
                icon: "fa-money",
                color: "#8BC34A",
                lightColor: "#F1F8E9",
                type: "action",
                shape: "rect",
                x: 540,
                y: 430,
                width: 120,
                height: 55,
                actionField: "show_pay_now_arrow",
                description: "Immediate payment"
            },
            {
                id: "pay_later",
                label: "Pay Later",
                icon: "fa-clock-o",
                color: "#CDDC39",
                lightColor: "#F9FBE7",
                type: "action",
                shape: "rect",
                x: 720,
                y: 430,
                width: 120,
                height: 55,
                actionField: "show_pay_later_arrow",
                description: "Defer payment"
            },

            // Sub-nodes (compressed)
            {
                id: "collect_cash",
                label: "Collect Cash",
                icon: "fa-hand-holding-usd",
                color: "#FFC107",
                lightColor: "#FFF8E1",
                type: "sub",
                shape: "rect",
                x: 540,
                y: 520,
                width: 110,
                height: 45,
                parent: "pay_now",
                actionField: "show_collect_cash_arrow",
                description: "OM collect cash"
            },
            {
                id: "payment_received",
                label: "Payment Received",
                icon: "fa-check-circle",
                color: "#4CAF50",
                lightColor: "#E8F5E9",
                type: "sub",
                shape: "rect",
                x: 720,
                y: 520,
                width: 120,
                height: 45,
                parent: "pay_later",
                actionField: "show_payment_received_arrow",
                description: "Payment received"
            },
        ];

        // Connection definitions
        this.connections = [
            // From Booking hub
            { from: "booking_hub", to: "service_packages", active: false },
            { from: "booking_hub", to: "quote", active: true },
            { from: "booking_hub", to: "confirm_booking", active: true },
            { from: "booking_hub", to: "equipment", active: false },
            { from: "booking_hub", to: "staff_assignment", active: true },
            { from: "booking_hub", to: "start_service", active: true },

            // From Start Service
            { from: "start_service", to: "clinical_notes", activeField: "show_clinical_notes_arrow" },
            { from: "start_service", to: "invoice", activeField: "show_invoice_arrow" },
            { from: "start_service", to: "pay_now", activeField: "show_pay_now_arrow" },
            { from: "start_service", to: "pay_later", activeField: "show_pay_later_arrow" },

            // Sub-connections
            { from: "pay_now", to: "collect_cash", activeField: "show_collect_cash_arrow" },
            { from: "pay_later", to: "payment_received", activeField: "show_payment_received_arrow" },
        ];

        // SVG dimensions - reduced to fit on screen
        this.svgWidth = 1000;
        this.svgHeight = 700;
        this.centerX = this.svgWidth / 2;
        this.centerY = this.svgHeight / 2;

        onMounted(() => {
            this.loadFSOData();
        });
    }

    /**
     * Load FSO data from backend including spoke states
     */
    async loadFSOData() {
        try {
            const data = await this.orm.call(
                "health.fieldservice.order",
                "read",
                [this.props.fsoId],
                {
                    fields: [
                        "name", "state", "stage_id", "patient_id", "service_type",
                        "scheduled_datetime", "actual_start_datetime", "actual_end_datetime",
                        "clinical_notes_submitted", "invoice_submitted",
                        "show_draft_indicator", "show_booked_indicator", "show_assigned_indicator",
                        "show_in_progress_indicator", "show_completed_indicator",
                        "show_clinical_notes_arrow", "show_invoice_arrow",
                        "show_pay_now_arrow", "show_pay_later_arrow",
                        "show_collect_cash_arrow", "show_payment_received_arrow",
                    ],
                }
            );

            this.state.fsoData = data[0] || {};
            this.state.loading = false;
        } catch (error) {
            console.error("Failed to load FSO data:", error);
            this.state.loading = false;
        }
    }

    /**
     * Get node by ID
     */
    getNode(nodeId) {
        return this.allNodes.find(n => n.id === nodeId);
    }

    /**
     * Get node center position (accounting for shape)
     */
    getNodeCenter(node) {
        if (node.shape === "oval") {
            return { x: node.x, y: node.y };
        } else {
            // Rectangle - center is x + width/2, y + height/2
            return {
                x: node.x + (node.width / 2),
                y: node.y + (node.height / 2)
            };
        }
    }

    /**
     * Get edge point on node boundary for connection
     */
    getNodeEdgePoint(node, angle) {
        const center = this.getNodeCenter(node);

        if (node.shape === "oval") {
            // For oval, use radius
            const radius = node.radius || 50;
            return {
                x: center.x + radius * Math.cos(angle),
                y: center.y + radius * Math.sin(angle)
            };
        } else {
            // For rectangle, calculate intersection with edge
            const hw = node.width / 2;
            const hh = node.height / 2;
            const dx = Math.cos(angle);
            const dy = Math.sin(angle);

            // Find which edge the angle intersects
            const tx = dx !== 0 ? hw / Math.abs(dx) : Infinity;
            const ty = dy !== 0 ? hh / Math.abs(dy) : Infinity;
            const t = Math.min(tx, ty);

            return {
                x: center.x + t * dx,
                y: center.y + t * dy
            };
        }
    }

    /**
     * Get connecting line path between two nodes
     */
    getLinePath(connection) {
        const fromNode = this.getNode(connection.from);
        const toNode = this.getNode(connection.to);

        if (!fromNode || !toNode) return "";

        const fromCenter = this.getNodeCenter(fromNode);
        const toCenter = this.getNodeCenter(toNode);

        // Calculate angle from 'from' to 'to'
        const angle = Math.atan2(toCenter.y - fromCenter.y, toCenter.x - fromCenter.x);

        // Get edge points on both nodes
        const startPoint = this.getNodeEdgePoint(fromNode, angle);
        const endPoint = this.getNodeEdgePoint(toNode, angle + Math.PI);

        return `M ${startPoint.x} ${startPoint.y} L ${endPoint.x} ${endPoint.y}`;
    }

    /**
     * Check if connection is active
     */
    isConnectionActive(connection) {
        if (!this.state.fsoData) return false;

        // If connection has activeField, check that field
        if (connection.activeField) {
            return this.state.fsoData[connection.activeField] === true;
        }

        // Otherwise use the static active property
        return connection.active === true;
    }

    /**
     * Check if node is active (current stage or condition met)
     */
    isNodeActive(node) {
        if (!this.state.fsoData) return false;

        // If node has actionField, check that field
        if (node.actionField) {
            return this.state.fsoData[node.actionField] === true;
        }

        // Hub and info nodes are always active
        if (node.type === "hub" || node.type === "info") {
            return true;
        }

        return false;
    }

    /**
     * Get node classes for styling
     */
    getNodeClasses(node) {
        const classes = ["fso_flowchart_node"];

        if (this.state.hoveredSpoke === node.id) {
            classes.push("fso_node_hovered");
        }

        if (this.isNodeActive(node)) {
            classes.push("fso_node_active");
        }

        // Add type-specific class
        classes.push(`fso_node_${node.type}`);

        return classes.join(" ");
    }

    /**
     * Get connection classes for styling
     */
    getConnectionClasses(connection) {
        const classes = ["fso_connection_line"];

        if (this.isConnectionActive(connection)) {
            classes.push("fso_connection_active");
        }

        return classes.join(" ");
    }

    /**
     * Handle node hover
     */
    onNodeMouseEnter(node) {
        this.state.hoveredSpoke = node.id;
    }

    onNodeMouseLeave() {
        this.state.hoveredSpoke = null;
    }

    /**
     * Handle node click - open wizards or actions
     */
    async onNodeClick(node) {
        const nodeId = node.id;
        let action = null;

        switch (nodeId) {
            case "booking_hub":
                // Hub - open FSO form
                action = await this.openFSOForm();
                break;

            case "service_packages":
                // Open service packages wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Service Packages",
                    res_model: "health.fso.service.packages.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "quote":
                // Open quote (same as Quote smart button)
                (async () => {
                    try {
                        console.log("Calling action_view_quote for FSO:", this.props.fsoId);
                        const result = await this.orm.call(
                            "health.fieldservice.order",
                            "action_view_quote",
                            [this.props.fsoId]
                        );
                        console.log("Quote action result:", result);

                        if (result && result.res_id) {
                            // Add views array on the client side since RPC serialization strips it
                            const quotAction = {
                                ...result,
                                views: [[result.view_id || false, 'form']],  // Ensure views array is present
                            };
                            console.log("Executing quote action with views:", quotAction);
                            await this.actionService.doAction(quotAction);
                        } else {
                            console.warn("No quote action returned or missing res_id");
                        }
                    } catch (error) {
                        console.error("Error opening quote:", error);
                        console.error("Error stack:", error.stack);
                    }
                })();
                break;

            case "confirm_booking":
                // Open confirm booking wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Confirm Booking",
                    res_model: "health.fso.confirm.booking.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "equipment":
                // Open equipment wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Equipment Requirements",
                    res_model: "health.fso.equipment.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "staff_assignment":
                // Open timeline view for manual staff assignment (same as Manual Staff Assignment button)
                try {
                    const result = await this.orm.call(
                        "health.fieldservice.order",
                        "action_manual_assign_staff",
                        [this.props.fsoId]
                    );
                    if (result) {
                        await this.actionService.doAction(result);
                    }
                } catch (error) {
                    console.error("Error opening staff assignment timeline:", error);
                }
                return;

            case "start_service":
                // Open start service wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Start Service",
                    res_model: "health.fso.start.service.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "clinical_notes":
                // Open clinical notes wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Clinical Notes",
                    res_model: "health.fso.clinical.notes.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "invoice":
                // Open invoice if one exists
                (async () => {
                    try {
                        console.log("Calling action_view_invoice for FSO:", this.props.fsoId);
                        const result = await this.orm.call(
                            "health.fieldservice.order",
                            "action_view_invoice",
                            [this.props.fsoId]
                        );
                        console.log("Invoice action result:", result);

                        if (result && result.res_id) {
                            // Add views array on the client side since RPC serialization strips it
                            const invoiceAction = {
                                ...result,
                                views: [[result.view_id || false, 'form']],  // Ensure views array is present
                            };
                            console.log("Executing invoice action with views:", invoiceAction);
                            await this.actionService.doAction(invoiceAction);
                        } else {
                            console.warn("No invoice action returned or missing res_id");
                        }
                    } catch (error) {
                        console.error("Error opening invoice:", error);
                        console.error("Error stack:", error.stack);
                    }
                })();
                break;

            case "pay_now":
            case "pay_later":
                // Open payment collection wizard (from health_invoicing module)
                action = {
                    type: "ir.actions.act_window",
                    name: "Payment Collection",
                    res_model: "health.nurse.payment.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                        default_payment_method: nodeId === "pay_now" ? "cash" : "pay_later",
                    },
                };
                break;

            case "collect_cash":
                // Open cash collection wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Collect Cash from Nurse",
                    res_model: "health.fso.cash.collection.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "payment_received":
                // Open payment received wizard
                action = {
                    type: "ir.actions.act_window",
                    name: "Payment Received",
                    res_model: "health.fso.payment.received.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;
        }

        if (action) {
            await this.actionService.doAction(action);
            // Reload FSO data after action to update node states
            setTimeout(() => this.loadFSOData(), 500);
        }
    }

    /**
     * Open FSO form in current view
     */
    async openFSOForm() {
        return {
            type: "ir.actions.act_window",
            res_model: "health.fieldservice.order",
            res_id: this.props.fsoId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        };
    }

    /**
     * Handle center hub click - open FSO form
     */
    async onHubClick() {
        await this.actionService.doAction(await this.openFSOForm());
    }
}
