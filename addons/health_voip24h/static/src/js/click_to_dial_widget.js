/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Click-to-Dial Widget
 *
 * Displays a clickable phone icon next to phone numbers in partner/lead forms.
 * When clicked, initiates a VoIP call via the VoIP24h API.
 */
export class ClickToDialWidget extends Component {
    static template = "health_voip24h.ClickToDialWidget";
    static props = {
        phoneNumber: { type: String, optional: true },
        record: { type: Object, optional: true },
    };

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    t(text) {
        return _t(text);
    }

    /**
     * Handle click on dial button
     */
    async onClickDial() {
        const phoneNumber = this.props.phoneNumber;

        if (!phoneNumber) {
            this.notification.add(_t("No phone number available"), {
                type: "warning",
            });
            return;
        }

        try {
            // Call the backend API to initiate the call
            const result = await this.rpc("/voip24h/click_to_dial", {
                phone_number: phoneNumber,
            });

            if (result.error) {
                this.notification.add(result.error, {
                    type: "danger",
                });
            } else {
                this.notification.add(
                    _t("Call initiated to %s", phoneNumber),
                    {
                        type: "success",
                    }
                );
            }
        } catch (error) {
            this.notification.add(
                _t("Failed to initiate call: %s", error.message),
                {
                    type: "danger",
                }
            );
        }
    }

    /**
     * Check if dial button should be visible
     */
    get isVisible() {
        return !!this.props.phoneNumber;
    }
}

// Register the widget
registry.category("fields").add("click_to_dial", ClickToDialWidget);
