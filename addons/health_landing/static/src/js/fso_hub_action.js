/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { FSOHubSpokeWidget } from "./fso_hub_spoke_widget";

/**
 * FSO Hub-and-Spoke Action
 *
 * Client action that launches the FSO dashboard
 * Includes browser history state tracking for proper back button behavior
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

            // If FSO ID is missing or undefined, try to restore from localStorage
            if (!params.fso_id || params.fso_id === 'undefined') {
                const storedFsoId = localStorage.getItem('current_fso_dashboard_id');
                const storedFsoName = localStorage.getItem('current_fso_dashboard_name');

                if (storedFsoId) {
                    this.state.fsoId = parseInt(storedFsoId);
                    this.state.fsoName = storedFsoName || `Booking #${storedFsoId}`;
                    console.log(`FSO Dashboard: Restored FSO ID from localStorage:`, this.state.fsoId);
                } else {
                    this.state.fsoId = params.fso_id;
                    this.state.fsoName = params.fso_name || `Booking #${params.fso_id}`;
                }
            } else {
                this.state.fsoId = params.fso_id;
                this.state.fsoName = params.fso_name || `Booking #${params.fso_id}`;
            }
        });

        onMounted(() => {
            // Store FSO ID in browser history state and localStorage for back button handling
            const historyState = {
                fsoId: this.state.fsoId,
                fsoName: this.state.fsoName,
                type: 'fso_hub_spoke_dashboard',
            };

            // Push to history to maintain state when user navigates away
            window.history.pushState(historyState, '', window.location.href);

            // Store in localStorage as fallback for browser back navigation
            localStorage.setItem('current_fso_dashboard_id', this.state.fsoId.toString());
            localStorage.setItem('current_fso_dashboard_name', this.state.fsoName);

            console.log(`FSO Dashboard: Stored FSO ID ${this.state.fsoId} in localStorage`);
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
