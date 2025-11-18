/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

/**
 * Customize dialog title for staff assignments
 * Removes "Odoo" prefix and shows only client name
 */
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        // Customize dialog title for staff assignments
        if (this.props.resModel === 'health.staff.assignment') {
            this.updateDialogTitle();
        }
    },

    async updateDialogTitle() {
        // Wait for the component to be mounted
        await this.env.services.ui.block();

        try {
            // Get the current record
            const record = this.model.root;

            if (record && record.data) {
                // Get patient name from the record
                const patientName = record.data.patient_name || record.data.name || 'Assignment';

                // Update dialog title if this form is in a dialog
                if (this.env.dialogData) {
                    this.env.dialogData.title = patientName;
                }

                // Also update browser title
                const titleElement = document.querySelector('.modal-title');
                if (titleElement) {
                    titleElement.textContent = patientName;
                }

                // Update the main browser title (remove "Odoo - " prefix)
                if (document.title.includes('Odoo - ')) {
                    document.title = document.title.replace('Odoo - ', '');
                }
            }
        } finally {
            this.env.services.ui.unblock();
        }
    }
});
