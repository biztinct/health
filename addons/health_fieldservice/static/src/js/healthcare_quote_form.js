/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";

export class HealthcareQuoteFormController extends FormController {

    async onClickSave(ev) {
        const ctx = this.props.context || {};

        // When opened from services/booking wizard — save and close modal
        if (ctx.from_services_wizard || ctx.from_booking_wizard) {
            await this.model.root.save();
            return this.action.doAction({ type: 'ir.actions.act_window_close' });
        }

        // When opened from FSO form — save and navigate to FSO
        const hasFSO = this.model.root.data.fso_id;
        if (hasFSO) {
            await this.model.root.save();
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "health.fieldservice.order",
                res_id: hasFSO[0],
                view_mode: "form",
                target: "current",
            });
            return;
        }

        return super.onClickSave(ev);
    }

    async saveRecord() {
        return this.onClickSave();
    }
}

registry.category("views").add("healthcare_quote_form", {
    ...registry.category("views").get("form"),
    Controller: HealthcareQuoteFormController,
});
