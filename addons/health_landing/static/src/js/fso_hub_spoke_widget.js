/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Hub-and-Spoke FSO Dashboard Widget — 4-Tier Visual State System
 *
 * Every node exists in exactly one of four visual tiers:
 *   completed  → green fill, white ✓ badge, no animation
 *   active     → bright fill, breathing pulse, guide arrow
 *   available  → light fill + border, no animation
 *   locked     → dashed grey, lock icon, tooltip prerequisite
 *
 * Only ONE node is the primary "next step" (breathing pulse + label).
 * Completed connection paths turn green; active paths animate.
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

        // ── Node Definitions ──
        this.allNodes = [
            // Top row
            {
                id: "service_packages", label: _t("Service Packages"),
                icon: "fa-gift", color: "#0ea5e9", lightColor: "#e0f2fe",
                type: "info", shape: "rect",
                x: 100, y: 40, width: 160, height: 60,
                description: _t("View service packages"),
            },
            {
                id: "quote", label: _t("Quote"),
                icon: "fa-file-text-o", color: "#0284c7", lightColor: "#e0f2fe",
                type: "info", shape: "rect",
                x: 400, y: 40, width: 160, height: 60,
                description: _t("Healthcare quote"),
            },
            {
                id: "confirm_booking", label: _t("Confirm Booking"),
                icon: "fa-calendar-check-o", color: "#10b981", lightColor: "#d1fae5",
                type: "action", shape: "oval",
                x: 740, y: 70, width: 200, height: 60,
                description: _t("Confirm the booking"),
            },

            // Middle row
            {
                id: "equipment", label: _t("Equipment"),
                icon: "fa-briefcase", color: "#64748b", lightColor: "#f1f5f9",
                type: "info", shape: "rect",
                x: 60, y: 170, width: 160, height: 60,
                description: _t("Required equipment"),
            },
            {
                id: "booking_hub", label: _t("Booking"),
                icon: "fa-calendar", color: "#0284c7", lightColor: "#e0f2fe",
                type: "hub", shape: "rect",
                x: 400, y: 160, width: 160, height: 80,
                description: _t("Main booking hub"),
            },
            {
                id: "staff_assignment", label: _t("Staff Assignment"),
                icon: "fa-user-md", color: "#0ea5e9", lightColor: "#e0f2fe",
                type: "action", shape: "rect",
                x: 720, y: 170, width: 160, height: 60,
                description: _t("Assign staff to booking"),
            },

            // Start Service
            {
                id: "start_service", label: _t("Start Service"),
                icon: "fa-play-circle", color: "#f97316", lightColor: "#ffedd5",
                type: "transition", shape: "oval",
                x: 380, y: 260, width: 200, height: 55,
                description: _t("Start the service"),
            },

            // Bottom row — post-service (left to right flow)
            {
                id: "clinical_notes", label: _t("Clinical Notes"),
                icon: "fa-stethoscope", color: "#3b82f6", lightColor: "#dbeafe",
                type: "action", shape: "rect",
                x: 30, y: 340, width: 145, height: 55,
                description: _t("Fill clinical notes"),
            },
            {
                id: "invoice", label: _t("Invoice"),
                icon: "fa-file-text-o", color: "#10b981", lightColor: "#d1fae5",
                type: "action", shape: "rect",
                x: 480, y: 340, width: 145, height: 55,
                description: _t("Create invoice"),
            },
            {
                id: "pay_now", label: _t("Pay Now"),
                icon: "fa-money", color: "#22c55e", lightColor: "#dcfce7",
                type: "action", shape: "rect",
                x: 650, y: 340, width: 145, height: 55,
                description: _t("Immediate payment"),
            },
            {
                id: "pay_later", label: _t("Pay Later"),
                icon: "fa-clock-o", color: "#f59e0b", lightColor: "#fef3c7",
                type: "action", shape: "rect",
                x: 820, y: 340, width: 145, height: 55,
                description: _t("Defer payment"),
            },

            // Sub-nodes
            {
                id: "collect_cash", label: _t("Collect Cash"),
                icon: "fa-dollar", color: "#f97316", lightColor: "#ffedd5",
                type: "sub", shape: "rect",
                x: 650, y: 420, width: 145, height: 50,
                parent: "pay_now",
                description: _t("OM collect cash"),
            },
            {
                id: "payment_received", label: _t("Payment Received"),
                icon: "fa-check-circle", color: "#10b981", lightColor: "#d1fae5",
                type: "sub", shape: "rect",
                x: 820, y: 420, width: 145, height: 50,
                parent: "pay_later",
                description: _t("Payment received"),
            },

            // Complete Service — between clinical notes and invoice/payment
            {
                id: "complete_service", label: _t("Complete Service"),
                icon: "fa-flag-checkered", color: "#059669", lightColor: "#d1fae5",
                type: "action", shape: "oval",
                x: 240, y: 340, width: 190, height: 55,
                description: _t("Complete service and collect payment"),
            },
        ];

        // ── Connection definitions ──
        this.connections = [
            { from: "booking_hub", to: "service_packages" },
            { from: "booking_hub", to: "quote" },
            { from: "booking_hub", to: "confirm_booking" },
            { from: "booking_hub", to: "equipment" },
            { from: "booking_hub", to: "staff_assignment" },
            { from: "booking_hub", to: "start_service" },
            { from: "start_service", to: "clinical_notes" },
            { from: "start_service", to: "complete_service" },
            { from: "complete_service", to: "invoice" },
            { from: "complete_service", to: "pay_now" },
            { from: "complete_service", to: "pay_later" },
            { from: "pay_now", to: "collect_cash" },
            { from: "pay_later", to: "payment_received" },
        ];

        this.svgWidth = 1000;
        this.svgHeight = 540;

        onMounted(() => this.loadFSOData());
    }

    // ════════════════════════════════════════════════════════════════
    //  DATA
    // ════════════════════════════════════════════════════════════════

    async loadFSOData() {
        try {
            const nodeIds = [
                "service_packages", "quote", "confirm_booking", "equipment",
                "staff_assignment", "start_service", "clinical_notes",
                "invoice", "pay_now", "pay_later", "collect_cash", "payment_received",
                "complete_service",
            ];
            const stateFields = nodeIds.map(id => `node_state_${id}`);
            const tipFields = nodeIds.map(id => `node_tip_${id}`);

            const data = await this.orm.call(
                "health.fieldservice.order", "read",
                [this.props.fsoId],
                {
                    fields: [
                        "name", "state", "stage_id", "patient_id", "service_type",
                        "scheduled_datetime", "actual_start_datetime", "actual_end_datetime",
                        "clinical_notes_submitted", "invoice_submitted",
                        "sale_order_id", "invoice_id",
                        // status bar
                        "show_draft_indicator", "show_booked_indicator",
                        "show_assigned_indicator", "show_in_progress_indicator",
                        "show_completed_indicator",
                        // legacy arrows
                        "show_clinical_notes_arrow", "show_invoice_arrow",
                        "show_pay_now_arrow", "show_pay_later_arrow",
                        "show_collect_cash_arrow", "show_payment_received_arrow",
                        // 4-tier
                        ...stateFields,
                        ...tipFields,
                        "primary_next_step",
                        "hub_stage_color",
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

    // ════════════════════════════════════════════════════════════════
    //  NODE STATE HELPERS
    // ════════════════════════════════════════════════════════════════

    /** Get the 4-tier state for a node: completed / active / available / locked */
    getNodeTier(node) {
        if (!this.state.fsoData || node.type === "hub") return "hub";
        const field = `node_state_${node.id}`;
        return this.state.fsoData[field] || "available";
    }

    /** Get tooltip text for a node */
    getNodeTooltip(node) {
        if (!this.state.fsoData || node.type === "hub") return node.description;
        const field = `node_tip_${node.id}`;
        return this.state.fsoData[field] || node.description;
    }

    /** Is this the primary next step? */
    isPrimaryNext(node) {
        if (!this.state.fsoData) return false;
        return this.state.fsoData.primary_next_step === node.id;
    }

    /** Get hub color based on current stage */
    getHubColor() {
        if (!this.state.fsoData) return "#0284c7";
        return this.state.fsoData.hub_stage_color || "#0284c7";
    }

    // ════════════════════════════════════════════════════════════════
    //  VISUAL PROPERTIES  (called from template)
    // ════════════════════════════════════════════════════════════════

    /** Fill color for the node shape */
    getNodeFill(node) {
        const tier = this.getNodeTier(node);
        if (tier === "hub") return this.state.fsoData?.hub_stage_color ? this._lighten(this.getHubColor()) : "#e0f2fe";
        if (tier === "completed") return "#dcfce7";
        if (tier === "active") return node.lightColor;
        if (tier === "locked") return "#f1f5f9";
        return "#f8fafc"; // available — neutral light grey
    }

    /** Stroke color for the node shape */
    getNodeStroke(node) {
        const tier = this.getNodeTier(node);
        if (tier === "hub") return this.getHubColor();
        if (tier === "completed") return "#22c55e";
        if (tier === "active") return node.color;
        if (tier === "locked") return "#cbd5e1";
        return "#94a3b8"; // available — neutral grey
    }

    /** Stroke dasharray */
    getNodeStrokeDash(node) {
        return this.getNodeTier(node) === "locked" ? "6,3" : "none";
    }

    /** Stroke width */
    getNodeStrokeWidth(node) {
        const tier = this.getNodeTier(node);
        if (tier === "hub") return 3;
        if (tier === "active") return 3;
        return 2;
    }

    /** Icon color */
    getNodeIconColor(node) {
        const tier = this.getNodeTier(node);
        if (tier === "hub") return this.getHubColor();
        if (tier === "completed") return "#16a34a";
        if (tier === "active") return node.color;
        if (tier === "locked") return "#94a3b8";
        return "#64748b"; // available — neutral grey
    }

    /** Label color */
    getNodeLabelColor(node) {
        const tier = this.getNodeTier(node);
        if (tier === "hub") return this.getHubColor();
        if (tier === "completed") return "#166534";
        if (tier === "active") return node.color;
        if (tier === "locked") return "#94a3b8";
        return "#64748b"; // available
    }

    /** CSS class for the node group */
    getNodeClasses(node) {
        const tier = this.getNodeTier(node);
        const classes = ["fso_flowchart_node", `fso_tier_${tier}`];
        if (node.type === "hub") classes.push("fso_node_hub");
        if (this.isPrimaryNext(node)) classes.push("fso_primary_next");
        if (this.state.hoveredSpoke === node.id) classes.push("fso_node_hovered");
        return classes.join(" ");
    }

    /** Should we show the ✓ badge? */
    showCheckBadge(node) {
        return this.getNodeTier(node) === "completed";
    }

    /** Should we show the 🔒 badge? */
    showLockBadge(node) {
        return this.getNodeTier(node) === "locked";
    }

    /** Helper – lighten a hex color for hub fill */
    _lighten(hex) {
        const colors = {
            "#94a3b8": "#f1f5f9",
            "#3b82f6": "#dbeafe",
            "#0ea5e9": "#e0f2fe",
            "#f97316": "#ffedd5",
            "#22c55e": "#dcfce7",
        };
        return colors[hex] || "#e0f2fe";
    }

    // ════════════════════════════════════════════════════════════════
    //  CONNECTION STATES
    // ════════════════════════════════════════════════════════════════

    /** Get connection tier based on the TARGET node's state */
    getConnectionTier(connection) {
        if (!this.state.fsoData) return "available";
        const toNode = this.getNode(connection.to);
        if (!toNode || toNode.type === "hub") return "available";
        const tier = this.getNodeTier(toNode);
        // If the target is completed, the path is completed (green)
        if (tier === "completed") return "completed";
        // If the target is the active next step, the path is active (animated)
        if (tier === "active") return "active";
        // If the target is locked, the path is locked (grey dotted)
        if (tier === "locked") return "locked";
        return "available";
    }

    getConnectionStroke(connection) {
        const tier = this.getConnectionTier(connection);
        if (tier === "completed") return "#22c55e";
        if (tier === "active") return "#0284c7";
        if (tier === "locked") return "#cbd5e1";
        return "#94a3b8";
    }

    getConnectionClasses(connection) {
        const tier = this.getConnectionTier(connection);
        return `fso_connection_line fso_conn_${tier}`;
    }

    getConnectionDash(connection) {
        const tier = this.getConnectionTier(connection);
        if (tier === "active") return "8,4";
        if (tier === "locked") return "4,4";
        return "none";
    }

    getConnectionOpacity(connection) {
        const tier = this.getConnectionTier(connection);
        if (tier === "completed") return 1;
        if (tier === "active") return 1;
        if (tier === "locked") return 0.3;
        return 0.5;
    }

    getConnectionWidth(connection) {
        const tier = this.getConnectionTier(connection);
        if (tier === "active") return 2.5;
        return 2;
    }

    getArrowMarker(connection) {
        const tier = this.getConnectionTier(connection);
        if (tier === "completed") return "url(#arrowCompleted)";
        if (tier === "active") return "url(#arrowActive)";
        return "url(#arrowDefault)";
    }

    // ════════════════════════════════════════════════════════════════
    //  GEOMETRY (unchanged from original)
    // ════════════════════════════════════════════════════════════════

    getNode(nodeId) {
        return this.allNodes.find(n => n.id === nodeId);
    }

    getNodeCenter(node) {
        return { x: node.x + node.width / 2, y: node.y + node.height / 2 };
    }

    getNodeEdgePoint(node, angle) {
        const center = this.getNodeCenter(node);
        if (node.shape === "oval") {
            const rx = node.width / 2, ry = node.height / 2;
            const cos = Math.cos(angle), sin = Math.sin(angle);
            const scale = Math.sqrt(rx * rx * sin * sin + ry * ry * cos * cos);
            return { x: center.x + (rx * ry * cos) / scale, y: center.y + (rx * ry * sin) / scale };
        }
        const hw = node.width / 2, hh = node.height / 2;
        const dx = Math.cos(angle), dy = Math.sin(angle);
        const tx = dx !== 0 ? hw / Math.abs(dx) : Infinity;
        const ty = dy !== 0 ? hh / Math.abs(dy) : Infinity;
        const t = Math.min(tx, ty);
        return { x: center.x + t * dx, y: center.y + t * dy };
    }

    getLinePath(connection) {
        const fromNode = this.getNode(connection.from);
        const toNode = this.getNode(connection.to);
        if (!fromNode || !toNode) return "";

        const fc = this.getNodeCenter(fromNode);
        const tc = this.getNodeCenter(toNode);
        const angle = Math.atan2(tc.y - fc.y, tc.x - fc.x);
        const sp = this.getNodeEdgePoint(fromNode, angle);
        const ep = this.getNodeEdgePoint(toNode, angle + Math.PI);

        const dx = ep.x - sp.x, dy = ep.y - sp.y;
        const absAngle = Math.abs(angle);
        const isVertical = (absAngle > Math.PI / 3 && absAngle < 2 * Math.PI / 3);

        if (isVertical || Math.abs(dx) < 50) {
            return `M ${sp.x} ${sp.y} L ${ep.x} ${ep.y}`;
        }

        const distance = Math.sqrt(dx * dx + dy * dy);
        const co = distance * 0.5, po = distance * 0.15;
        const cp1x = sp.x + co * Math.cos(angle) + po * Math.cos(angle + Math.PI / 2);
        const cp1y = sp.y + co * Math.sin(angle) + po * Math.sin(angle + Math.PI / 2);
        const cp2x = ep.x - co * Math.cos(angle) - po * Math.cos(angle + Math.PI / 2);
        const cp2y = ep.y - co * Math.sin(angle) - po * Math.sin(angle + Math.PI / 2);
        return `M ${sp.x} ${sp.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${ep.x} ${ep.y}`;
    }

    // ════════════════════════════════════════════════════════════════
    //  INTERACTION
    // ════════════════════════════════════════════════════════════════

    onNodeMouseEnter(node) { this.state.hoveredSpoke = node.id; }
    onNodeMouseLeave() { this.state.hoveredSpoke = null; }

    onBreadcrumbRoot() {
        if (this.props.onBreadcrumbRoot) this.props.onBreadcrumbRoot();
        else if (this.props.onBack) this.props.onBack();
    }

    async onNodeClick(node) {
        const tier = this.getNodeTier(node);

        // Locked nodes → show notification with reason
        if (tier === "locked") {
            this.notificationService.add(
                this.getNodeTooltip(node),
                { type: "warning", title: _t("Step Locked") }
            );
            return;
        }

        const nodeId = node.id;
        let action = null;

        switch (nodeId) {
            case "booking_hub":
                action = await this.openFSOForm();
                break;

            case "service_packages":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Service Packages"),
                    res_model: "health.fso.service.packages.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "quote":
                (async () => {
                    try {
                        const result = await this.orm.call(
                            "health.fieldservice.order", "action_view_quote",
                            [this.props.fsoId]
                        );
                        if (result && result.res_id) {
                            await this.actionService.doAction({
                                ...result,
                                views: [[result.view_id || false, "form"]],
                            });
                        }
                    } catch (e) { console.error("Error opening quote:", e); }
                })();
                break;

            case "confirm_booking":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Confirm Booking"),
                    res_model: "health.fso.confirm.booking.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "equipment":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Equipment Requirements"),
                    res_model: "health.fso.equipment.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "staff_assignment":
                try {
                    const result = await this.orm.call(
                        "health.fieldservice.order", "action_manual_assign_staff",
                        [this.props.fsoId]
                    );
                    if (result) await this.actionService.doAction(result);
                } catch (e) { console.error("Error opening staff assignment:", e); }
                return;

            case "start_service":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Start Service"),
                    res_model: "health.fso.start.service.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "clinical_notes":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Clinical Notes"),
                    res_model: "health.fso.clinical.notes.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "invoice":
                (async () => {
                    try {
                        // Try to open actual invoice first
                        const result = await this.orm.call(
                            "health.fieldservice.order", "action_view_invoice",
                            [this.props.fsoId]
                        );
                        if (result && result.res_id) {
                            await this.actionService.doAction({
                                ...result,
                                views: [[result.view_id || false, "form"]],
                                target: "new",
                            });
                        } else {
                            // No invoice — open the sale order/quote instead
                            const fsoData = this.state.fsoData;
                            const soId = fsoData && fsoData.sale_order_id && fsoData.sale_order_id[0];
                            if (soId) {
                                await this.actionService.doAction({
                                    type: "ir.actions.act_window",
                                    name: _t("Quote"),
                                    res_model: "sale.order",
                                    res_id: soId,
                                    views: [[false, "form"]],
                                    target: "new",
                                });
                            } else {
                                this.notificationService.add(
                                    _t("No invoice or quote found for this booking."),
                                    { type: "warning" }
                                );
                            }
                        }
                    } catch (e) { console.error("Error opening invoice:", e); }
                })();
                break;

            case "pay_now":
            case "pay_later":
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
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Collect Cash from Nurse"),
                    res_model: "health.fso.cash.collection.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "payment_received":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Payment Received"),
                    res_model: "health.fso.payment.received.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_fso_id: this.props.fsoId },
                };
                break;

            case "complete_service":
                try {
                    await this.orm.call(
                        "health.fieldservice.order", "action_complete_service",
                        [this.props.fsoId]
                    );
                    this.notificationService.add(
                        _t("Service completed successfully!"),
                        { type: "success", title: _t("Service Completed") }
                    );
                    setTimeout(() => this.loadFSOData(), 500);
                } catch (e) {
                    console.error("Error completing service:", e);
                    this.notificationService.add(
                        e.message || _t("Could not complete service"),
                        { type: "danger", title: _t("Error") }
                    );
                }
                return;
        }

        if (action) {
            await this.actionService.doAction(action);
            setTimeout(() => this.loadFSOData(), 500);
        }
    }

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

    async onHubClick() {
        await this.actionService.doAction(await this.openFSOForm());
    }
}
