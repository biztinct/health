/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Lists the mandatory fields a user still needs to fill before continuing.
 * Used by the New Contact wizard instead of a cryptic top-right notification.
 */
export class RequiredFieldsDialog extends Component {
    static template = "health_crm.RequiredFieldsDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        message: { type: String, optional: true },
        fields: { type: Array },        // array of field labels (strings)
    };
}
