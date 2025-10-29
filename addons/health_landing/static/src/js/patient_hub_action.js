/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { HubSpokeWidget } from "./hub_spoke_widget";
import { PatientSpokeModal } from "./patient_spoke_modal";

/**
 * Patient Hub Client Action
 *
 * Standalone client action that displays hub-and-spoke for a specific patient
 * Launched from patient list view "Hub & Spoke" button
 * Includes browser history state tracking for proper back button behavior
 */
class PatientHubAction extends Component {
    static template = "health_landing.PatientHubActionTemplate";
    static components = { HubSpokeWidget, PatientSpokeModal };

    setup() {
        this.state = useState({
            selectedSpoke: null,
        });

        // Get patient info from action params
        this.patientId = this.props.action.params?.patient_id;
        this.patientName = this.props.action.params?.patient_name;

        onWillStart(async () => {
            // If patient ID is missing or undefined, try to restore from localStorage
            if (!this.patientId || this.patientId === 'undefined') {
                const storedPatientId = localStorage.getItem('current_patient_dashboard_id');
                const storedPatientName = localStorage.getItem('current_patient_dashboard_name');

                if (storedPatientId) {
                    this.patientId = parseInt(storedPatientId);
                    this.patientName = storedPatientName || `Patient #${storedPatientId}`;
                    console.log(`Patient Dashboard: Restored Patient ID from localStorage:`, this.patientId);
                }
            }
        });

        onMounted(() => {
            // Store patient ID in browser history state and localStorage for back button handling
            if (this.patientId) {
                const historyState = {
                    patientId: this.patientId,
                    patientName: this.patientName,
                    type: 'patient_hub_dashboard',
                };

                // Push to history to maintain state when user navigates away
                window.history.pushState(historyState, '', window.location.href);

                // Store in localStorage as fallback for browser back navigation
                localStorage.setItem('current_patient_dashboard_id', this.patientId.toString());
                localStorage.setItem('current_patient_dashboard_name', this.patientName);

                console.log(`Patient Dashboard: Stored Patient ID ${this.patientId} in localStorage`);
            }
        });
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
     * Back to patient kanban
     */
    onBack() {
        // Go back to the patient registry kanban view
        this.env.services.action.doAction("health_base.action_health_patient");
    }
}

PatientHubAction.template = "health_landing.PatientHubActionTemplate";

// Register as client action
registry.category("actions").add("health_landing_patient_hub", PatientHubAction);
