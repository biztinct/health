/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart } from "@odoo/owl";
import { LeadHubSpokeWidget } from "./lead_hub_spoke_widget";

/**
 * Lead Hub Client Action
 *
 * Displays hub-and-spoke for a specific lead.
 */
class LeadHubAction extends Component {
    static template = "health_landing.LeadHubActionTemplate";
    static components = { LeadHubSpokeWidget };

    setup() {
        this.leadId = this.props.action.params?.lead_id;
        this.leadName = this.props.action.params?.lead_name;

        onWillStart(async () => {
            if (!this.leadId || this.leadId === "undefined") {
                const storedLeadId = localStorage.getItem("current_lead_dashboard_id");
                const storedLeadName = localStorage.getItem("current_lead_dashboard_name");
                if (storedLeadId) {
                    this.leadId = parseInt(storedLeadId, 10);
                    this.leadName = storedLeadName || `Lead #${storedLeadId}`;
                }
            }
        });

        onMounted(() => {
            if (this.leadId) {
                const historyState = {
                    leadId: this.leadId,
                    leadName: this.leadName,
                    type: "lead_hub_dashboard",
                };
                window.history.pushState(historyState, "", window.location.href);
                localStorage.setItem("current_lead_dashboard_id", this.leadId.toString());
                localStorage.setItem("current_lead_dashboard_name", this.leadName || "");
            }
        });
    }

    onBack() {
        this.env.services.action.doAction("health_crm.action_healthcare_opportunities");
    }
}

registry.category("actions").add("health_landing_lead_hub", LeadHubAction);

