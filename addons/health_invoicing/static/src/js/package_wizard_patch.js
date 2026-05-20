/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { PackageWizardDialog } from "./package_wizard_dialog";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.__pkgDialogService = useService("dialog");
    },

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_open_service_package_wizard") {
            const resId = this.model.root.resId;
            if (resId) {
                const record = this.model.root;
                if (await record.isDirty()) {
                    const saved = await record.save();
                    if (!saved) return false;
                }
                this.__pkgDialogService.add(PackageWizardDialog, {
                    fsoId: resId,
                    onDone: () => this.model.root.load(),
                });
                return false;
            }
        }
        return super.beforeExecuteActionButton(clickParams);
    },
});
