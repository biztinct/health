/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Shows existing clients matching a contact's name/phone/email so the user can
 * pick the right one (avoiding duplicates) or choose to create a new client.
 */
export class ClientMatchDialog extends Component {
    static template = "health_fieldservice.ClientMatchDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        clients: { type: Array },
        clientName: { type: String, optional: true },
        onPick: Function,        // (clientId) => void
        onCreateNew: Function,   // () => void
    };

    pick(client) {
        this.props.onPick(client.id);
        this.props.close();
    }

    createNew() {
        this.props.onCreateNew();
        this.props.close();
    }
}
