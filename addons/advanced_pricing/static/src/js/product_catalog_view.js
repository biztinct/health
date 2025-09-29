/** @odoo-module **/

import { registry } from "@web/core/registry";
import { productCatalogKanbanView } from "@product/product_catalog/kanban_view";
import { HealthcareProductCatalogController } from "./product_catalog_controller";

// Create healthcare-specific product catalog view
export const healthcareProductCatalogView = {
    ...productCatalogKanbanView,
    Controller: HealthcareProductCatalogController,
};

// Register the healthcare product catalog view with both names
registry.category("views").add("healthcare_product_catalog", healthcareProductCatalogView);

// Also patch the standard product_kanban_catalog for healthcare context
import { patch } from "@web/core/utils/patch";
import { ProductCatalogKanbanController } from "@product/product_catalog/kanban_controller";

patch(ProductCatalogKanbanController.prototype, {
    async backToQuotation() {
        const context = this.props.context;
        const isHealthcareQuote = context.healthcare_context || 
                                 context.catalog_source === 'healthcare_quote' ||
                                 context.quote_order_id;
        
        if (isHealthcareQuote) {
            // Get the correct healthcare quote view ID
            const viewResult = await this.orm.call("sale.order", "get_healthcare_quote_view_id", [this.orderId]);
            
            // For healthcare/FSO quotes, open in modal popup with correct view
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Healthcare Quote",
                res_model: "sale.order",
                res_id: this.orderId,
                view_mode: "form",
                views: [[viewResult, "form"]],
                view_id: viewResult,
                target: "new", // Modal popup like "Recalc Pricing" button
                context: {
                    healthcare_context: true,
                    from_catalog: true,
                    show_notification: false,
                    quote_order_id: this.orderId,
                    catalog_source: 'healthcare_quote'
                }
            });
        } else {
            // For regular quotes, use standard behavior
            await super.backToQuotation();
        }
    },

    async _defineButtonContent() {
        // Call parent to get standard button logic
        await super._defineButtonContent();
        
        // Override button text for healthcare quotes
        const context = this.props.context;
        const isHealthcareQuote = context.healthcare_context || 
                                 context.catalog_source === 'healthcare_quote';
        
        if (isHealthcareQuote) {
            this.buttonString = "Back to Quote";
        }
    }
});