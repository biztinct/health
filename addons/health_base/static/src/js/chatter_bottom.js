/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        const result = super.mailLayout(hasAttachmentContainer);
        if (result === "SIDE_CHATTER") {
            return "BOTTOM_CHATTER";
        }
        if (result === "EXTERNAL_COMBO_XXL") {
            return "EXTERNAL_COMBO";
        }
        return result;
    },
});

const style = document.createElement("style");
style.textContent = `
    .o_form_renderer.flex-nowrap {
        flex-direction: column !important;
        flex-wrap: nowrap !important;
        height: auto !important;
    }
    .o_form_renderer .o_form_sheet_bg {
        width: 100% !important;
        overflow: visible !important;
        flex: none !important;
    }
`;
document.head.appendChild(style);
