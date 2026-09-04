/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
// The one list that says who may change who-can-do-what. Read, never restated:
// two copies of a gate is one copy that will be out of date, and the copy that
// is wrong is the one that shows somebody a tile they will be refused on.
import { ACCESS_MANAGE_GATE } from "@biz_access/js/access_palette";

export class AdminSettings extends Component {
    static template = "health_landing.AdminSettings";

    setup() {
        this.actionService = useService("action");
        // TWO DIFFERENT QUESTIONS, AND THEY ARE NOT THE SAME PERSON.
        //
        // "Who can do what" is the clinic's own administrators' work, and the
        // tile that opens it is theirs. The settings for the box itself —
        // Odoo's General Settings — belong to the platform administrator
        // alone, which is the two-ring model: `base.group_system` never leaves
        // the one account that owns the machine.
        this.state = useState({ canManageAccess: false, isSystemAdmin: false });
        onWillStart(async () => {
            const [manage, isSystemAdmin] = await Promise.all([
                Promise.all(ACCESS_MANAGE_GATE.map((g) => user.hasGroup(g))),
                user.hasGroup("base.group_system"),
            ]);
            this.state.canManageAccess = manage.some(Boolean) || isSystemAdmin;
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

    openAccessHome() {
        this.actionService.doAction("biz_access.action_biz_access_home", {
            clearBreadcrumbs: true,
        });
    }
}

registry.category("actions").add("admin_settings", AdminSettings);
