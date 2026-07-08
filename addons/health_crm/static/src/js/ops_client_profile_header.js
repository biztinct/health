/** @odoo-module **/

// Render an editable "Main Contact" widget inside the ops Client Profile
// header (see ops_client_profile_header.xml). We expose the Field component and
// a getter that returns the parsed arch fieldInfo for main_contact_id, so the
// header <Field> inherits the arch domain ([('id','in',allowed_main_contact_ids)])
// and options (no_create) — without fieldInfo, Field applies neither.
import { OpsClientProfileFormController } from "@health_fieldservice/js/ops_client_profile_form";
import { Field } from "@web/views/fields/field";
import { patch } from "@web/core/utils/patch";

OpsClientProfileFormController.components = {
    ...(OpsClientProfileFormController.components || {}),
    Field,
};

patch(OpsClientProfileFormController.prototype, {
    get mainContactFieldInfo() {
        const archInfo = this.archInfo || this.props.archInfo || {};
        const nodes = archInfo.fieldNodes || {};
        return Object.values(nodes).find((fn) => fn.name === "main_contact_id");
    },
});
