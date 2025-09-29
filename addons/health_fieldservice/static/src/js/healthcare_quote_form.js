/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";

export class HealthcareQuoteFormController extends FormController {
    
    setup() {
        super.setup();
        console.log("HealthcareQuoteFormController setup called");
        console.log("Setup - Context:", this.props.context);
        console.log("Setup - Model:", this.props.resModel);
    }
    
    async onClickSave(ev) {
        console.log("Healthcare Quote Save clicked");
        console.log("Context:", this.props.context);
        console.log("Data:", this.model.root.data);
        
        // Check if this is a healthcare quote with FSO
        const hasFSO = this.model.root.data.fso_id;
        
        if (hasFSO) {
            console.log("FSO detected, using custom save action");
            
            // Save the record first
            await this.model.root.save();
            
            // Then navigate to FSO
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "health.fieldservice.order",
                res_id: hasFSO[0], // FSO ID is in array format [id, name]
                view_mode: "form",
                target: "current", // Replace current view (close modal and go to FSO)
                context: {
                    show_notification: true,
                    notification_message: 'Quote saved successfully!',
                    notification_type: 'success'
                }
            });
            return;
        }
        
        // For regular quotes, use standard save behavior
        console.log("No FSO detected, using standard save");
        return super.onClickSave(ev);
    }
    
    // Also override keyboard shortcuts
    async saveRecord() {
        console.log("Healthcare Quote saveRecord called (Ctrl+S)");
        return this.onClickSave();
    }
}

// Register the custom controller
registry.category("views").add("healthcare_quote_form", {
    ...registry.category("views").get("form"),
    Controller: HealthcareQuoteFormController,
});

// Additional DOM-based approach for modal dialogs
document.addEventListener('DOMContentLoaded', function() {
    console.log("Healthcare Quote: DOM ready, setting up modal save interceptors");
    
    // Function to intercept modal save buttons
    function interceptModalSave() {
        // Find all modal dialogs with healthcare quote forms
        const modals = document.querySelectorAll('.modal .o_sale_order');
        
        modals.forEach(modal => {
            const saveButtons = modal.querySelectorAll('.o_form_button_save, .btn[data-hotkey="s"]');
            
            saveButtons.forEach(button => {
                if (!button.hasAttribute('data-healthcare-intercepted')) {
                    button.setAttribute('data-healthcare-intercepted', 'true');
                    
                    button.addEventListener('click', function(e) {
                        console.log("Modal save button clicked - checking for healthcare context");
                        
                        // Check if this modal has FSO context
                        const fsoFields = modal.querySelectorAll('[name="fso_id"]');
                        if (fsoFields.length > 0) {
                            console.log("FSO field found in modal - this is a healthcare quote");
                            // Let the custom controller handle it
                        }
                    });
                }
            });
        });
    }
    
    // Run initially and on DOM changes
    interceptModalSave();
    
    // Watch for new modals
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                interceptModalSave();
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});