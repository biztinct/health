/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Click-to-dial on a phone field.
 *
 *   <field name="phone" widget="click_to_dial"/>
 *
 * The dial goes through the phone service, not through an RPC that claims to
 * start a call on the server. The old version posted to /voip24h/click_to_dial
 * and then showed "Call initiated" — a success message for a request whose
 * endpoint was never verified and which could not ring anything. Now the
 * browser places the call, and the button says what is actually possible:
 * it is disabled with a reason when the phone is not on.
 */
export class ClickToDialField extends Component {
    static template = "health_voip24h.ClickToDialWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.phone = useService("voip24h_phone");
    }

    get phoneNumber() {
        return this.props.record.data[this.props.name] || "";
    }

    get canDial() {
        const state = this.phone.state;
        return (
            state.browserState === "ready" &&
            state.profile &&
            state.profile.outgoing_enabled &&
            (state.callState === "idle" || state.callState === "wrap_up")
        );
    }

    get dialTitle() {
        if (!this.phoneNumber) {
            return _t("No phone number");
        }
        const state = this.phone.state;
        if (!state.available) {
            return _t("The phone system is not set up for you.");
        }
        if (state.browserState !== "ready") {
            return _t("Turn your phone on first, from the phone button.");
        }
        if (state.callState === "active" || state.callState === "dialling") {
            return _t("You are already on a call.");
        }
        if (state.profile && !state.profile.outgoing_enabled) {
            return _t("Outgoing calls are switched off.");
        }
        return _t("Call %s", this.phoneNumber);
    }

    async onClickDial() {
        if (!this.phoneNumber) {
            this.notification.add(_t("There is no number to call."), {
                type: "warning",
            });
            return;
        }
        if (!this.canDial) {
            this.notification.add(this.dialTitle, { type: "warning" });
            this.phone.state.panelOpen = true;
            return;
        }
        // The service holds the idempotency reference, the destination policy
        // check and the audit. This only asks.
        await this.phone.dial(this.phoneNumber, {
            resModel: this.props.record.resModel,
            resId: this.props.record.resId,
        });
        this.phone.state.panelOpen = true;
    }
}

export const clickToDialField = {
    component: ClickToDialField,
    displayName: _t("Click to Dial"),
    supportedTypes: ["char"],
};

registry.category("fields").add("click_to_dial", clickToDialField);
