/** @odoo-module **/

// Make the Odoo Field component available inside the ops Client Profile header
// template so we can render an editable "Main Contact" widget in the identity
// row (see ops_client_profile_header.xml). The header markup is added via
// template inheritance in health_crm; here we only widen the component's
// available sub-components.
import { OpsClientProfileFormController } from "@health_fieldservice/js/ops_client_profile_form";
import { Field } from "@web/views/fields/field";

OpsClientProfileFormController.components = {
    ...(OpsClientProfileFormController.components || {}),
    Field,
};
