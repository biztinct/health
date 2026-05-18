/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class OpsClientProfile extends Component {
    static template = "health_fieldservice.OpsClientProfile";

    setup() {
        this.action = useService("action");

        onMounted(async () => {
            const context = this.props.action?.context || {};
            let partnerId = context.active_id || context.default_partner_id || false;

            if (!partnerId) {
                const parts = window.location.pathname.split("/");
                const idx = parts.indexOf("res.partner");
                if (idx > -1 && parts[idx + 1]) {
                    partnerId = parseInt(parts[idx + 1], 10);
                }
            }

            if (partnerId) {
                const action = await this.action.loadAction(
                    "health_fieldservice.action_ops_client_profile_form"
                );
                action.res_id = partnerId;
                await this.action.doAction(action, { clearBreadcrumbs: true });
            } else {
                await this.action.doAction(
                    "health_fieldservice.action_ops_client_list_native",
                    { clearBreadcrumbs: true }
                );
            }
        });
    }
}

registry.category("actions").add("ops_client_profile", OpsClientProfile);

export default OpsClientProfile;
