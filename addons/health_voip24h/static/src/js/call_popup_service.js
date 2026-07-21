/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * VoIP Call Popup
 *
 * Overlay component (main_components registry) that listens on the
 * shared "voip_notifications" bus channel and shows a popup for
 * incoming calls. The server only emits these events when incoming
 * popups are enabled on the active voip.config.
 */
export class VoipCallPopup extends Component {
    static template = "health_voip24h.CallPopup";
    static props = {};

    setup() {
        this.state = useState({
            activeCall: null,
        });

        this.action = useService("action");
        this.busService = useService("bus_service");

        this.busService.addChannel("voip_notifications");
        this.busService.subscribe("voip_incoming_call", (payload) =>
            this.showIncomingCallPopup(payload)
        );
        this.busService.subscribe("voip_call_ended", (payload) =>
            this.hideCallPopup(payload)
        );
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

        // Auto-hide after 30 seconds if not interacted with
        clearTimeout(this._autoHideTimer);
        this._autoHideTimer = setTimeout(() => {
            if (this.state.activeCall?.call_id === callData.call_id) {
                this.closePopup();
            }
        }, 30000);
    }

    /**
     * Hide call popup when the call ends
     */
    hideCallPopup(callData) {
        if (this.state.activeCall?.call_id === callData.call_id) {
            this.closePopup();
        }
    }

    /**
     * Close popup manually
     */
    closePopup() {
        clearTimeout(this._autoHideTimer);
        this.state.activeCall = null;
    }

    /**
     * Open partner form
     */
    async openPartner() {
        const call = this.state.activeCall;
        if (!call?.partner_id) {
            return;
        }
        this.closePopup();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: call.partner_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * Open lead form
     */
    async openLead() {
        const call = this.state.activeCall;
        if (!call?.lead_id) {
            return;
        }
        this.closePopup();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: call.lead_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /**
     * Open call log form
     */
    async openCallLog() {
        const call = this.state.activeCall;
        if (!call?.call_log_id) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "voip.call.log",
            res_id: call.call_log_id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    /**
     * Get display name for caller
     */
    get callerDisplay() {
        const call = this.state.activeCall;
        if (!call) {
            return "";
        }
        return call.partner_name || call.lead_name || call.caller_number || "";
    }
}

registry
    .category("main_components")
    .add("VoipCallPopup", { Component: VoipCallPopup });
