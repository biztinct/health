/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Click-to-Dial Field Widget
 *
 * Renders a phone number (char field) with a dial button that initiates
 * a VoIP24h call via the backend click-to-dial endpoint.
 *
 * Usage in a form view:  <field name="phone" widget="click_to_dial"/>
 */
export class ClickToDialField extends Component {
    static template = "health_voip24h.ClickToDialWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
    }

    get phoneNumber() {
        return this.props.record.data[this.props.name] || "";
    }

    /**
     * Handle click on dial button
     */
    async onClickDial() {
        const phoneNumber = this.phoneNumber;

        if (!phoneNumber) {
            this.notification.add(_t("No phone number available"), {
                type: "warning",
            });
            return;
        }

        try {
            const result = await rpc("/voip24h/click_to_dial", {
                phone_number: phoneNumber,
            });

            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else {
                this.notification.add(_t("Call initiated to %s", phoneNumber), {
                    type: "success",
                });
            }
        } catch (error) {
            this.notification.add(
                _t("Failed to initiate call: %s", error.message || error),
                { type: "danger" }
            );
        }
    }
}

export const clickToDialField = {
    component: ClickToDialField,
    displayName: _t("Click to Dial"),
    supportedTypes: ["char"],
};

registry.category("fields").add("click_to_dial", clickToDialField);
