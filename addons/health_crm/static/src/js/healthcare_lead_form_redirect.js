/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Healthcare Lead Form Controller
 * 
 * This controller automatically redirects to the hub-spoke dashboard
 * when opening an existing CRM lead record.
 * 
 * For new records (create mode), it shows the normal form.
 */
class HealthcareLeadFormController extends FormController {

    setup() {
        super.setup();

        // Get services
        this.orm = useService("orm");
        this.action = useService("action");

        // Check if we're opening an existing record and redirect
        this._checkAndRedirect();
    }

    async _checkAndRedirect() {
        // Wait a tick for the props to be fully available
        await Promise.resolve();

        const resId = this.props.resId;

        // Check if we should skip the redirect (e.g., when clicking central node of hub-spoke)
        // The skip_hub_redirect flag is passed in the action context
        const context = this.props.context || {};
        if (context.skip_hub_redirect) {
            // Don't redirect - user intentionally wants to see the form
            return;
        }

        if (resId) {
            // This is an existing record - redirect to hub-spoke dashboard
            this._redirectToHubSpoke(resId);
        }
    }

    async onRecordSaved(record) {
        // After saving a new record, redirect to hub-spoke dashboard
        const result = await super.onRecordSaved(record);

        if (record && record.resId) {
            this._redirectToHubSpoke(record.resId);
        }

        return result;
    }

    /**
     * Redirect to the hub-spoke dashboard for the given lead ID
     */
    async _redirectToHubSpoke(leadId) {
        try {
            // Call the Python method to get the hub-spoke action
            const result = await this.orm.call(
                'crm.lead',
                'action_open_lead_hub',
                [[leadId]]  // Pass as array for multi-record API
            );

            if (result) {
                // Execute the client action to open hub-spoke dashboard
                await this.action.doAction(result, {
                    clearBreadcrumbs: false,
                });
            }
        } catch (error) {
            console.error("Failed to redirect to hub-spoke dashboard:", error);
            // Don't break the form if redirect fails
        }
    }
}

// Register the custom form view
const HealthcareLeadFormView = {
    ...formView,
    Controller: HealthcareLeadFormController,
};

registry.category("views").add("healthcare_lead_form_redirect", HealthcareLeadFormView);
