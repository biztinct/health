/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AdminSettings extends Component {
    static template = "health_landing.AdminSettings";

    setup() {
        this.actionService = useService("action");
    }

    openGeneralSettings() {
        this.actionService.doAction("base_setup.action_general_configuration");
    }

    openCompanyProfile() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.company",
            views: [[false, "form"]],
            res_id: this.env.services.company?.currentCompany?.id || 1,
            target: "current",
        });
    }

    openFieldRequirements() {
        this.actionService.doAction("health_landing.action_admin_field_req", {
            clearBreadcrumbs: true,
        });
    }

    openPricingConfig() {
        this.actionService.doAction("health_landing.action_admin_pricelists", {
            clearBreadcrumbs: true,
        });
    }

    openUserDefaults() {
        this.actionService.doAction("health_landing.action_admin_roles", {
            clearBreadcrumbs: true,
        });
    }
}

registry.category("actions").add("admin_settings", AdminSettings);
