/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class RelationshipAddressWidget extends Component {
    static template = "health_crm.RelationshipAddressWidget";
    static props = {
        record: Object,
        name: String,
    };

    setup() {
        this.action = useService("action");
    }

    get address() {
        return this.props.record.data[this.props.name] || "";
    }

    get hasRepresentative() {
        const representative = this.props.record.data.representative_id;
        return representative && representative[0];
    }

    async onEditAddress() {
        if (!this.hasRepresentative) {
            return;
        }
        const representativeId = this.props.record.data.representative_id[0];
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Edit Address",
                res_model: "res.partner",
                res_id: representativeId,
                view_mode: "form",
                target: "new",
                context: {
                    form_view_ref: "health_base.view_health_patient_address_form",
                    form_view_initial_mode: "edit",
                },
            },
            {
                onClose: async () => {
                    await this.props.record.load();
                },
            }
        );
    }
}

registry.category("fields").add("relationship_address", {
    component: RelationshipAddressWidget,
});
