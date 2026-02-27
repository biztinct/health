/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

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
        breadcrumbRootLabel: String,
        breadcrumbBookingLabel: String,
        onBreadcrumbRoot: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notificationService = useService("notification");
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
            // Top row nodes - Uniform sizing (160x60 standard)
            {
                id: "service_packages",
                label: _t("Service Packages"),
                icon: "fa-gift",
                color: "#0ea5e9",  // Modern sky blue
                lightColor: "#e0f2fe",
                type: "info",
                shape: "rect",
                x: 100,
                y: 40,
                width: 160,
                height: 60,
                description: _t("View service packages")
            },
            {
                id: "quote",
                label: _t("Quote"),
                icon: "fa-file-text-o",
                color: "#0284c7",  // Modern primary blue
                lightColor: "#e0f2fe",
                type: "info",
                shape: "rect",
                x: 400,
                y: 40,
                width: 160,
                height: 60,
                actionField: "sale_order_id",
                description: _t("Healthcare quote")
            },
            {
                id: "confirm_booking",
                label: _t("Confirm Booking"),
                icon: "fa-check-circle",
                color: "#10b981",  // Modern emerald green
                lightColor: "#d1fae5",
                type: "action",
                shape: "oval",
                x: 740,
                y: 70,
                width: 200,
                height: 60,
                actionField: "show_booked_indicator",
                description: _t("Confirm the booking")
            },

            // Middle row - Uniform sizing
            {
                id: "equipment",
                label: _t("Equipment"),
                icon: "fa-briefcase",
                color: "#64748b",  // Modern slate gray
                lightColor: "#f1f5f9",
                type: "info",
                shape: "rect",
                x: 60,
                y: 170,
                width: 160,
                height: 60,
                description: _t("Required equipment")
            },
            {
                id: "booking_hub",
                label: _t("Booking"),
                icon: "fa-calendar",
                color: "#0284c7",  // Modern primary blue
                lightColor: "#e0f2fe",
                type: "hub",
                shape: "rect",
                x: 400,
                y: 160,
                width: 160,
                height: 80,
                description: _t("Main booking hub")
            },
            {
                id: "staff_assignment",
                label: _t("Staff Assignment"),
                icon: "fa-user-md",
                color: "#0ea5e9",  // Modern sky blue
                lightColor: "#e0f2fe",
                type: "action",
                shape: "rect",
                x: 720,
                y: 170,
                width: 160,
                height: 60,
                actionField: "show_assigned_indicator",
                description: _t("Assign staff to booking")
            },

            // Start Service - Oval centered below Booking
            {
                id: "start_service",
                label: _t("Start Service"),
                icon: "fa-play-circle",
                color: "#f97316",  // Modern orange
                lightColor: "#ffedd5",
                type: "transition",
                shape: "oval",
                x: 380,
                y: 280,
                width: 200,
                height: 60,
                actionField: "show_in_progress_indicator",
                description: _t("Start the service")
            },

            // Bottom row - Moved up to fit screen (160x60)
            {
                id: "clinical_notes",
                label: _t("Clinical Notes"),
                icon: "fa-stethoscope",
                color: "#3b82f6",  // Modern blue
                lightColor: "#dbeafe",
                type: "action",
                shape: "rect",
                x: 60,
                y: 400,
                width: 160,
                height: 60,
                actionField: "show_clinical_notes_arrow",
                description: _t("Fill clinical notes")
            },
            {
                id: "invoice",
                label: _t("Invoice"),
                icon: "fa-file-text-o",
                color: "#10b981",  // Modern emerald
                lightColor: "#d1fae5",
                type: "action",
                shape: "rect",
                x: 270,
                y: 400,
                width: 160,
                height: 60,
                actionField: "show_invoice_arrow",
                description: _t("Create invoice")
            },
            {
                id: "pay_now",
                label: _t("Pay Now"),
                icon: "fa-money",
                color: "#22c55e",  // Modern green
                lightColor: "#dcfce7",
                type: "action",
                shape: "rect",
                x: 540,
                y: 400,
                width: 160,
                height: 60,
                actionField: "show_pay_now_arrow",
                description: _t("Immediate payment")
            },
            {
                id: "pay_later",
                label: _t("Pay Later"),
                icon: "fa-clock-o",
                color: "#f59e0b",  // Modern amber
                lightColor: "#fef3c7",
                type: "action",
                shape: "rect",
                x: 750,
                y: 400,
                width: 160,
                height: 60,
                actionField: "show_pay_later_arrow",
                description: _t("Defer payment")
            },

            // Sub-nodes - Moved up to fit screen (160x60)
            {
                id: "collect_cash",
                label: _t("Collect Cash"),
                icon: "fa-dollar",
                color: "#f97316",  // Modern orange
                lightColor: "#ffedd5",
                type: "sub",
                shape: "rect",
                x: 540,
                y: 490,
                width: 160,
                height: 60,
                parent: "pay_now",
                actionField: "show_collect_cash_arrow",
                description: _t("OM collect cash")
            },
            {
                id: "payment_received",
                label: _t("Payment Received"),
                icon: "fa-check-circle",
                color: "#10b981",  // Modern emerald
                lightColor: "#d1fae5",
                type: "sub",
                shape: "rect",
                x: 750,
                y: 490,
                width: 160,
                height: 60,
                parent: "pay_later",
                actionField: "show_payment_received_arrow",
                description: _t("Payment received")
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

        // SVG dimensions - adjusted to fit screen better
        this.svgWidth = 1000;
        this.svgHeight = 600;
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
                        "payment_status", "invoice_id",
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
            // Oval with width/height - center is x + width/2, y + height/2
            return {
                x: node.x + (node.width / 2),
                y: node.y + (node.height / 2)
            };
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
            // For oval with width/height, calculate ellipse edge
            const rx = node.width / 2;
            const ry = node.height / 2;

            // Parametric ellipse equation
            const cos = Math.cos(angle);
            const sin = Math.sin(angle);
            const scale = Math.sqrt((rx * rx * sin * sin) + (ry * ry * cos * cos));

            return {
                x: center.x + (rx * ry * cos) / scale,
                y: center.y + (rx * ry * sin) / scale
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
     * Get connecting line path between two nodes - straight for vertical, curved for others
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

        // Calculate if connection is primarily vertical (within 30 degrees of vertical)
        const dx = endPoint.x - startPoint.x;
        const dy = endPoint.y - startPoint.y;
        const absAngle = Math.abs(angle);
        const isVertical = (absAngle > Math.PI / 3 && absAngle < 2 * Math.PI / 3) ||
            (absAngle > 4 * Math.PI / 3 && absAngle < 5 * Math.PI / 3);

        // Use straight line for vertical connections
        if (isVertical || Math.abs(dx) < 50) {
            return `M ${startPoint.x} ${startPoint.y} L ${endPoint.x} ${endPoint.y}`;
        }

        // Use S-curve for horizontal/diagonal connections
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Enhanced control point offset for visible curves
        const controlOffset = distance * 0.5;

        // Add perpendicular offset for visible curvature
        const perpOffset = distance * 0.15;

        // Calculate control points for smooth S-shaped curve with lateral deviation
        const cp1x = startPoint.x + controlOffset * Math.cos(angle) + perpOffset * Math.cos(angle + Math.PI / 2);
        const cp1y = startPoint.y + controlOffset * Math.sin(angle) + perpOffset * Math.sin(angle + Math.PI / 2);

        const cp2x = endPoint.x - controlOffset * Math.cos(angle) - perpOffset * Math.cos(angle + Math.PI / 2);
        const cp2y = endPoint.y - controlOffset * Math.sin(angle) - perpOffset * Math.sin(angle + Math.PI / 2);

        // Create smooth cubic Bezier curve (S-shape)
        return `M ${startPoint.x} ${startPoint.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${endPoint.x} ${endPoint.y}`;
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
     * Check if a node is disabled
     */
    isNodeDisabled(node) {
        if (!this.state.fsoData) return false;

        // Disable Pay Now/Pay Later if payment is already done or no invoice
        if ((node.id === "pay_now" || node.id === "pay_later")) {
            // Disabled if payment is already paid
            if (this.state.fsoData.payment_status === 'paid') {
                return true;
            }
            // Disabled if no invoice exists
            if (!this.state.fsoData.invoice_id) {
                return true;
            }
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

        // Add disabled class if node is disabled
        if (this.isNodeDisabled(node)) {
            classes.push("fso_node_disabled");
        }

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

    onBreadcrumbRoot() {
        if (this.props.onBreadcrumbRoot) {
            this.props.onBreadcrumbRoot();
        } else if (this.props.onBack) {
            this.props.onBack();
        }
    }

    /**
     * Handle node click - open wizards or actions
     */
    async onNodeClick(node) {
        const nodeId = node.id;
        let action = null;

        // Prevent Pay Now action if payment is already done
        if ((nodeId === "pay_now" || nodeId === "pay_later") && this.state.fsoData.payment_status === 'paid') {
            this.notificationService.add(
                _t('Payment has already been received for this booking. No further payment actions are needed.'),
                { type: 'warning', title: _t('Payment Completed') }
            );
            return;
        }

        // Prevent Pay Now if invoice doesn't exist
        if ((nodeId === "pay_now" || nodeId === "pay_later") && !this.state.fsoData.invoice_id) {
            this.notificationService.add(
                _t('Please create an invoice before processing payment.'),
                { type: 'warning', title: _t('Invoice Required') }
            );
            return;
        }

        switch (nodeId) {
            case "booking_hub":
                // Hub - open FSO form
                action = await this.openFSOForm();
                break;

            case "service_packages":
                // Open service packages wizard
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Service Packages"),
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
                    name: _t("Confirm Booking"),
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
                    name: _t("Equipment Requirements"),
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
                        // Action name is already set to "Booking Dashboard" in Python
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
                    name: _t("Start Service"),
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
                    name: _t("Clinical Notes"),
                    res_model: "health.fso.clinical.notes.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_fso_id: this.props.fsoId,
                    },
                };
                break;

            case "invoice":
                // Open invoice in modal if one exists
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
                            // Open as modal (target: "new") instead of full screen (target: "current")
                            const invoiceAction = {
                                ...result,
                                views: [[result.view_id || false, 'form']],  // Ensure views array is present
                                target: 'new',  // Open as modal dialog instead of full screen
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
                    name: _t("Payment Collection"),
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
                    name: _t("Collect Cash from Nurse"),
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
                    name: _t("Payment Received"),
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
