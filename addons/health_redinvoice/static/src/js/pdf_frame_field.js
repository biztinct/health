/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Minimal field widget that embeds a URL (the Red Invoice PDF) in an iframe,
 * so the browser's native PDF viewer renders it inside the modal.
 */
export class RedinvoicePdfFrame extends Component {
    static template = "health_redinvoice.PdfFrame";
    static props = { ...standardFieldProps };

    get src() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("redinvoice_pdf_frame", {
    component: RedinvoicePdfFrame,
    supportedTypes: ["char"],
});
