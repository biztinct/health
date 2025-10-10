/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { HubSpokeWidget } from "./hub_spoke_widget";
import { PatientSpokeModal } from "./patient_spoke_modal";

/**
 * Patient Hub Client Action
 *
 * Standalone client action that displays hub-and-spoke for a specific patient
 * Launched from patient list view "Hub & Spoke" button
 */
class PatientHubAction extends Component {
    static template = "health_landing.PatientHubActionTemplate";
    static components = { HubSpokeWidget, PatientSpokeModal };

    setup() {
        this.state = useState({
            selectedSpoke: null,
        });

        // Get patient info from action params
        this.patientId = this.props.action.params.patient_id;
        this.patientName = this.props.action.params.patient_name;
    }

    /**
     * Handle spoke click - open modal
     */
    onSpokeClick(spoke, patientId) {
        this.state.selectedSpoke = spoke;
    }

    /**
     * Close spoke modal
     */
    closeSpokeModal() {
        this.state.selectedSpoke = null;
    }

    /**
     * Handle spoke modal edit button
     */
    onSpokeEdit(spokeId) {
        // Close modal
        this.closeSpokeModal();
    }

    /**
     * Handle item click in spoke modal (e.g., booking card)
     */
    onSpokeItemClick(item, itemType, spokeId) {
        if (itemType === "booking" && item.id) {
            // TODO: Show nested hub-and-spoke for booking
            console.log("Show booking hub-and-spoke for:", item.id);
        }
    }

    /**
     * Back to patient list
     */
    onBack() {
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            name: "Patients",
            res_model: "res.partner",
            domain: [["is_patient", "=", true]],
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            target: "current",
        });
    }
}

PatientHubAction.template = "health_landing.PatientHubActionTemplate";

// Register as client action
registry.category("actions").add("health_landing_patient_hub", PatientHubAction);
