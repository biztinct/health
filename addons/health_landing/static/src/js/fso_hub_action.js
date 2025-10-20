/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { FSOHubSpokeWidget } from "./fso_hub_spoke_widget";

/**
 * FSO Hub-and-Spoke Action
 *
 * Client action that launches the FSO dashboard
 */
class FSOHubSpokeAction extends Component {
    static template = "health_landing.FSOHubSpokeAction";
    static components = { FSOHubSpokeWidget };

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            fsoId: null,
            fsoName: null,
        });

        onWillStart(async () => {
            // Get FSO ID and name from action params
            const params = this.props.action.params || {};
            this.state.fsoId = params.fso_id;
            this.state.fsoName = params.fso_name || `Booking #${params.fso_id}`;
        });
    }

    /**
     * Handle back button - return to FSO form
     */
    async onBack() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "health.fieldservice.order",
            res_id: this.state.fsoId,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
        });
    }
}

// Template for the action
FSOHubSpokeAction.template = "health_landing.FSOHubSpokeActionTemplate";

// Register the client action
registry.category("actions").add("health_landing.fso_hub_spoke_action", FSOHubSpokeAction);

export { FSOHubSpokeAction };
