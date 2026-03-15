/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Hub-and-Spoke Lead Dashboard Widget
 *
 * Interactive radial visualization with lead at center and 5 spokes:
 * - Client Info
 * - Relations
 * - Map
 * - Source
 * - Internal Notes
 */
export class LeadHubSpokeWidget extends Component {
    static template = "health_landing.LeadHubSpokeTemplate";

    static props = {
        leadId: Number,
        leadName: String,
        onBack: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.svgRef = useRef("hubSpokeSvg");

        this.state = useState({
            hoveredSpoke: null,
            leadData: null,
            loading: true,
        });

        this.spokes = [
            {
                id: "client_info",
                label: _t("Lead Info"),
                icon: "fa-user",
                color: "#1565C0",
                lightColor: "#ffffff",
                description: _t("Lead details and contact"),
            },
            {
                id: "relations",
                label: _t("Relations"),
                icon: "fa-users",
                color: "#00796B",
                lightColor: "#ffffff",
                description: _t("Caregivers, payers, contacts"),
            },
            {
                id: "source",
                label: _t("Source"),
                icon: "fa-bullseye",
                color: "#D46E00",
                lightColor: "#ffffff",
                description: _t("Lead acquisition source"),
            },
            {
                id: "internal_notes",
                label: _t("Internal Notes"),
                icon: "fa-sticky-note",
                color: "#6B4BA8",
                lightColor: "#ffffff",
                description: _t("Notes and requirements"),
            },
            {
                id: "map",
                label: _t("Map"),
                icon: "fa-map-marker",
                color: "#0097A7",
                lightColor: "#ffffff",
                description: _t("Address and location"),
            },
        ];

        const angleStep = 360 / this.spokes.length;
        this.spokes.forEach((spoke, index) => {
            spoke.angle = angleStep * index;
        });

        this.svgWidth = 800;
        this.svgHeight = 600;
        this.centerX = this.svgWidth / 2;
        this.centerY = this.svgHeight / 2;
        this.hubRadius = 80;
        this.spokeRadius = 220;
        this.spokeNodeRadius = 60;

        onMounted(() => {
            this.loadLeadData();
        });
    }

    async loadLeadData() {
        try {
            const data = await this.orm.call(
                "crm.lead",
                "read",
                [this.props.leadId],
                {
                    fields: [
                        "name",
                        "is_spam_caller",
                        "contact_status",
                        "contact_outcome",
                        "health_contact_outcome",
                        "lead_followup_required",
                        "next_action_at"
                    ]
                }
            );
            this.state.leadData = data[0] || {};
        } catch (error) {
            console.error("Failed to load lead data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    getLeadName() {
        return this.props.leadName || this.state.leadData?.name || "Lead";
    }

    isSpamCaller() {
        // Don't show spam badge if contact_status is 'booking' (Service Booked takes priority)
        const contactStatus = this.state.leadData?.contact_status;
        if (contactStatus === 'booking') {
            return false;
        }
        return this.state.leadData?.is_spam_caller || false;
    }

    getContactStatus() {
        const status = this.state.leadData?.contact_status;
        const statusLabels = {
            'active': _t('Initial Contact'),
            'booking': _t('Booking'),
            'lead': _t('Lead'),
            'lost_booking': _t('Lost Booking'),
            'spam': _t('Spam Call')
        };
        return statusLabels[status] || status || '';
    }

    getContactOutcome() {
        // Get the display name for contact outcome
        const outcome = this.state.leadData?.health_contact_outcome || this.state.leadData?.contact_outcome;
        const outcomeLabels = {
            'pending_callback': _t('Pending Callback'),
            'pending_follow_up': _t('Pending Follow-up'),
            'service_booked': _t('Service Booked'),
            'interested': _t('Interested'),
            'not_interested': _t('Not Interested'),
            'rejected': _t('Rejected'),
            'no_followup_required': _t('No Follow-up Required')
        };
        return outcomeLabels[outcome] || outcome || '';
    }

    getOutcomeBadgeStyle() {
        // Return CSS style based on outcome
        const outcome = this.state.leadData?.health_contact_outcome || this.state.leadData?.contact_outcome;
        const styles = {
            'pending_callback': 'background-color: #ffc107; color: #000;',       // Yellow
            'pending_follow_up': 'background-color: #17a2b8; color: white;',     // Cyan
            'service_booked': 'background-color: #28a745; color: white;',        // Green
            'interested': 'background-color: #007bff; color: white;',            // Blue
            'not_interested': 'background-color: #6c757d; color: white;',        // Gray
            'rejected': 'background-color: #dc3545; color: white;',              // Red
            'no_followup_required': 'background-color: #6c757d; color: white;'   // Gray
        };
        return styles[outcome] || 'background-color: #6c757d; color: white;';
    }

    needsFollowup() {
        return this.state.leadData?.lead_followup_required || false;
    }

    getNextFollowupDate() {
        const nextAction = this.state.leadData?.next_action_at;
        if (!nextAction) return '';

        // Format the datetime to a readable date
        const date = new Date(nextAction);
        const options = { month: 'short', day: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    }

    hasNextFollowup() {
        return !!this.state.leadData?.next_action_at;
    }

    // Breadcrumb Navigation Handlers
    async onHomeClick(ev) {
        ev.preventDefault();
        // Navigate to the Health Flow Dashboard home page
        await this.actionService.doAction('health_flow.action_health_flow_dashboard');
    }

    async onContactsClick(ev) {
        ev.preventDefault();
        // Navigate to All Contacts view
        await this.actionService.doAction('health_crm.action_all_contacts_grouped');
    }

    async onLeadListClick(ev) {
        ev.preventDefault();
        // Navigate to Leads list view
        await this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: _t('Leads'),
            res_model: 'crm.lead',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            target: 'main',
            domain: [['type', '=', 'lead']],
        });
    }

    getSpokePosition(angle) {
        const radians = (angle - 90) * (Math.PI / 180);
        const x = this.centerX + this.spokeRadius * Math.cos(radians);
        const y = this.centerY + this.spokeRadius * Math.sin(radians);
        return { x, y };
    }

    getSpokePath(angle) {
        const radians = (angle - 90) * (Math.PI / 180);
        const startX = this.centerX + this.hubRadius * Math.cos(radians);
        const startY = this.centerY + this.hubRadius * Math.sin(radians);
        const endX = this.centerX + (this.spokeRadius - this.spokeNodeRadius) * Math.cos(radians);
        const endY = this.centerY + (this.spokeRadius - this.spokeNodeRadius) * Math.sin(radians);
        return `M ${startX} ${startY} L ${endX} ${endY}`;
    }

    onSpokeMouseEnter(spoke) {
        this.state.hoveredSpoke = spoke.id;
    }

    onSpokeMouseLeave() {
        this.state.hoveredSpoke = null;
    }

    async onSpokeClick(spoke) {
        let action = null;
        const context = {
            form_view_initial_mode: "edit",
        };

        switch (spoke.id) {
            case "client_info":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Lead Information"),
                    res_model: "crm.lead",
                    res_id: this.props.leadId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        ...context,
                        form_view_ref: "health_landing.view_lead_client_info_modal",
                    },
                };
                break;
            case "relations":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Lead Relationships"),
                    res_model: "crm.lead",
                    res_id: this.props.leadId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        ...context,
                        form_view_ref: "health_landing.view_lead_relations_modal",
                    },
                };
                break;
            case "map":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Lead Location"),
                    res_model: "crm.lead",
                    res_id: this.props.leadId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        ...context,
                        form_view_ref: "health_landing.view_lead_map_modal",
                    },
                };
                break;
            case "source":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Lead Source"),
                    res_model: "crm.lead",
                    res_id: this.props.leadId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        ...context,
                        form_view_ref: "health_landing.view_lead_source_modal",
                    },
                };
                break;
            case "internal_notes":
                action = {
                    type: "ir.actions.act_window",
                    name: _t("Internal Notes"),
                    res_model: "crm.lead",
                    res_id: this.props.leadId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        ...context,
                        form_view_ref: "health_landing.view_lead_internal_notes_modal",
                    },
                };
                break;
        }

        if (action) {
            await this.actionService.doAction(action);
        }
    }

    async onHubClick() {
        // Open form view directly WITHOUT triggering the redirect back to hub-spoke
        // The skip_hub_redirect context flag tells our JS controller to skip the redirect
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: this.props.leadId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                form_view_ref: "health_crm.view_healthcare_opportunity_form",
                skip_hub_redirect: true,  // Don't redirect back to hub-spoke
            },
        });
    }

    async onMarkSpamClick() {
        try {
            await this.orm.call(
                "crm.lead",
                "action_mark_spam_and_home",
                [this.props.leadId]
            );
            // Show notification
            this.notification.add(
                _t("This contact has been marked as spam"),
                {
                    type: "warning",
                    title: _t("Spam Marked"),
                    sticky: false,
                }
            );
            // Reload lead data to update badges
            await this.loadLeadData();
        } catch (error) {
            console.error("Failed to mark as spam:", error);
            this.notification.add(
                _t("Failed to mark as spam"),
                { type: "danger" }
            );
        }
    }

    async onBookingClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_convert_to_booking",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to open booking:", error);
        }
    }

    async onConsultationClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_escalate_consultation",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to open consultation:", error);
        }
    }

    async onEscalateClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_escalate_contact",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to escalate:", error);
        }
    }

    async onSendMessageClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_send_message",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to send message:", error);
        }
    }

    async onLogActivityClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_schedule_follow_up",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to log activity:", error);
        }
    }

    async onLogNoteClick() {
        try {
            const action = await this.orm.call(
                "crm.lead",
                "action_log_note",
                [this.props.leadId]
            );
            if (action && action.type) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            console.error("Failed to log note:", error);
        }
    }

    getSpokeClasses(spoke) {
        const classes = ["hub_spoke_node"];
        if (this.state.hoveredSpoke === spoke.id) {
            classes.push("hub_spoke_node_hovered");
        }
        return classes.join(" ");
    }

    getLineClasses(spoke) {
        const classes = ["hub_spoke_line"];
        if (this.state.hoveredSpoke === spoke.id) {
            classes.push("hub_spoke_line_hovered");
        }
        return classes.join(" ");
    }
}
