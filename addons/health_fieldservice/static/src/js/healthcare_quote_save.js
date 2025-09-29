/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

// Patch FormController to handle healthcare quote save behavior
patch(FormController.prototype, {
    async onClickSave(ev) {
        const context = this.props.context;
        const modelName = this.props.resModel;
        
        // Debug logging
        console.log("Save clicked - Model:", modelName);
        console.log("Save clicked - Context:", context);
        console.log("Save clicked - Data:", this.model.root.data);
        
        // Only apply to sale.order forms
        if (modelName !== 'sale.order') {
            return super.onClickSave(ev);
        }
        
        const isHealthcareQuote = context.healthcare_context || 
                                 context.from_catalog ||
                                 context.catalog_source === 'healthcare_quote';
        
        const hasFSO = this.model.root.data.fso_id;
        
        console.log("Is Healthcare Quote:", isHealthcareQuote);
        console.log("Has FSO:", hasFSO);
        
        // If this is a healthcare quote with FSO context, use custom save action
        if (isHealthcareQuote && hasFSO) {
            console.log("Using custom healthcare save action");
            
            // Save the record first
            await this.model.root.save();
            
            // Then execute the custom action to return to FSO
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "health.fieldservice.order", 
                res_id: hasFSO[0], // FSO ID is in array format [id, name]
                view_mode: "form",
                target: "current", // Close modal and go to FSO
                context: {
                    show_notification: true,
                    notification_message: 'Quote saved successfully!',
                    notification_type: 'success'
                }
            });
            return;
        }
        
        // For regular forms, use standard save behavior
        console.log("Using standard save behavior");
        return super.onClickSave(ev);
    }
});