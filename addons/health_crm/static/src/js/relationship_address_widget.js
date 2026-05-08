/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class RelationshipAddressWidget extends Component {
    static template = "health_crm.RelationshipAddressWidget";
    static props = {
        record: Object,
        name: String,
    };

    setup() {
        this.action = useService("action");
    }

    t(text) {
        return _t(text);
    }

    get address() {
        return this.props.record.data[this.props.name] || "";
    }

    get hasRepresentative() {
        return Boolean(this.representativeId);
    }

    get representativeId() {
        const representative = this.props.record.data.representative_id;
        if (!representative) {
            return null;
        }
        if (typeof representative === "number") {
            return representative;
        }
        if (Array.isArray(representative)) {
            return representative[0];
        }
        if (typeof representative === "object" && representative.id) {
            return representative.id;
        }
        return null;
    }

    async onEditAddress() {
        const representativeId = this.representativeId;
        if (!representativeId) {
            return;
        }
        await this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Edit Address",
                res_model: "res.partner",
                res_id: representativeId,
                view_mode: "form",
                views: [[false, "form"]],
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
