/** @odoo-module **/

import { ProductCatalogKanbanController } from "@product/product_catalog/kanban_controller";
import { _t } from "@web/core/l10n/translation";

export class HealthcareProductCatalogController extends ProductCatalogKanbanController {
    
    async backToQuotation() {
        const context = this.props.context;
        const isHealthcareQuote = context.healthcare_context || 
                                 context.catalog_source === 'healthcare_quote' ||
                                 context.quote_order_id;
        
        if (isHealthcareQuote) {
            const actionService = this.action || this.env.services.action;
            // For healthcare/FSO quotes, open in modal popup
            await actionService.doAction({
                type: "ir.actions.act_window",
                name: _t("Healthcare Quote"),
                res_model: "sale.order",
                res_id: this.orderId,
                view_mode: "form",
                views: [[false, "form"]],
                view_id: "health_fieldservice.view_healthcare_quote_form_custom",
                target: "new", // Modal popup like "Recalc Pricing" button
                context: {
                    healthcare_context: true,
                    from_catalog: true,
                    show_notification: false
                }
            });
        } else {
            // For regular quotes, use standard behavior
            await super.backToQuotation();
        }
    }

    async _defineButtonContent() {
        // Call parent to get standard button logic
        await super._defineButtonContent();
        
        // Override button text for healthcare quotes
        const context = this.props.context;
        const isHealthcareQuote = context.healthcare_context || 
                                 context.catalog_source === 'healthcare_quote';
        
        if (isHealthcareQuote) {
            this.buttonString = _t("Back to Quote");
        }
    }
}
