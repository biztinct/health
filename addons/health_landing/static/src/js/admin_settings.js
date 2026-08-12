/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export class AdminSettings extends Component {
    static template = "health_landing.AdminSettings";

    setup() {
        this.actionService = useService("action");
        // Ring 0 only: role/permission design is platform-admin work.
        // Tenant admins assign predefined roles from Users — they never see
        // the Access Roles tile (and the ACL denies the action regardless).
        // Odoo's own General Settings is ring-0 too: tenant admins/owners must
        // never reach system-wide configuration. base.group_system is the
        // platform-admin marker (see the two-ring model).
        this.state = useState({ isRoleAdmin: false, isSystemAdmin: false });
        onWillStart(async () => {
            const [isRoleAdmin, isSystemAdmin] = await Promise.all([
                user.hasGroup("access_roles.access_role_group_administrator"),
                user.hasGroup("base.group_system"),
            ]);
            this.state.isRoleAdmin = isRoleAdmin;
            this.state.isSystemAdmin = isSystemAdmin;
        });
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
