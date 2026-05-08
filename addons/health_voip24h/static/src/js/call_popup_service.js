/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Call Popup Service
 *
 * Manages incoming call popups via bus notifications.
 * Listens for 'voip_incoming_call' events and displays popup notifications.
 */
export class CallPopupService extends Component {
    static template = "health_voip24h.CallPopup";

    setup() {
        this.state = useState({
            activeCall: null,
            isVisible: false,
        });

        this.notification = useService("notification");
        this.orm = useService("orm");
        this.action = useService("action");
        this.bus = useService("bus_service");

        // Subscribe to VoIP notifications
        this.bus.addEventListener("notification", this.onNotification.bind(this));
        this.bus.addChannel("voip_notifications");
    }

    t(text) {
        return _t(text);
    }

    /**
     * Handle incoming bus notifications
     */
    onNotification({ detail: notifications }) {
        for (const { type, payload } of notifications) {
            if (type === "voip_incoming_call") {
                this.showIncomingCallPopup(payload);
            } else if (type === "voip_call_ended") {
                this.hideCallPopup(payload);
            }
        }
    }

    /**
     * Show incoming call popup
     */
    showIncomingCallPopup(callData) {
        this.state.activeCall = {
            call_id: callData.call_id,
            call_log_id: callData.call_log_id,
            caller_number: callData.caller_number,
            partner_id: callData.partner_id,
            partner_name: callData.partner_name,
            lead_id: callData.lead_id,
            lead_name: callData.lead_name,
        };
        this.state.isVisible = true;

        // Auto-hide after 30 seconds if not interacted
        setTimeout(() => {
            if (this.state.activeCall?.call_id === callData.call_id) {
                this.closePopup();
            }
        }, 30000);
    }

    /**
     * Hide call popup when call ends
     */
    hideCallPopup(callData) {
        if (this.state.activeCall?.call_id === callData.call_id) {
            this.state.isVisible = false;
            this.state.activeCall = null;
        }
    }

    /**
     * Close popup manually
     */
    closePopup() {
        this.state.isVisible = false;
        this.state.activeCall = null;
    }

    /**
     * Open partner form
     */
    async openPartner() {
        if (!this.state.activeCall.partner_id) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.state.activeCall.partner_id,
            views: [[false, "form"]],
            target: "current",
        });

        this.closePopup();
    }

    /**
     * Open lead form
     */
    async openLead() {
        if (!this.state.activeCall.lead_id) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: this.state.activeCall.lead_id,
            views: [[false, "form"]],
            target: "current",
        });

        this.closePopup();
    }

    /**
     * Open call log form
     */
    async openCallLog() {
        if (!this.state.activeCall.call_log_id) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "voip.call.log",
            res_id: this.state.activeCall.call_log_id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    /**
     * Get display name for caller
     */
    get callerDisplay() {
        const call = this.state.activeCall;
        if (!call) return "";

        if (call.partner_name) {
            return call.partner_name;
        } else if (call.lead_name) {
            return call.lead_name;
        } else {
            return call.caller_number;
        }
    }
}

// Register as a service
export const callPopupService = {
    dependencies: ["notification", "orm", "action", "bus_service"],
    start(env, { notification, orm, action, bus_service }) {
        return new CallPopupService(env, { notification, orm, action, bus_service });
    },
};

registry.category("services").add("call_popup", callPopupService);
