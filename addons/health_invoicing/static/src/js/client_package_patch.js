/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { OpsClientProfileFormController } from "@health_fieldservice/js/ops_client_profile_form";
import { PackageWizardDialog } from "./package_wizard_dialog";

/**
 * Replace the client profile's "Quick Package Purchase" basic wizard with the
 * rich OWL package dialog (the same one used on the booking form), in patient
 * mode: shows the client's current packages with gauges and the purchase cards.
 */
patch(OpsClientProfileFormController.prototype, {
    openPackagePurchase() {
        const resId = this.model.root.resId;
        if (!resId) {
            return;
        }
        this.env.services.dialog.add(PackageWizardDialog, {
            patientId: resId,
            onDone: () => {
                // Refresh the form record and the profile stats (Active Packages)
                // once a package has been purchased.
                this.model.load();
                if (this._loadProfileData) {
                    this._loadProfileData();
                }
            },
        });
    },
});
