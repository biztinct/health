/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class BiHomeAction extends Component {
    static template = "biz_bi.Home";
    static props = { "*": true };
    static displayName = _t("Analytics");

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            workspaces: [],
            recents: [],
            dashboards: [],
            isCreator: false,
            isModeler: false,
        });

        onWillStart(async () => {
            const home = await this.orm.call("bi.workspace", "get_home_data", []);
            this.state.workspaces = home.workspaces;
            this.state.isCreator = home.is_creator;
            this.state.isModeler = home.is_modeler;
            this.state.recents = await this.orm.call(
                "bi.audit.log", "get_recents", []);
            this.state.dashboards = await this.orm.searchRead(
                "bi.dashboard", [],
                ["name", "description", "workspace_id"],
                { limit: 40 });
        });
    }

    openDashboard(dashboardId) {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_bi.dashboard",
            params: { dashboard_id: dashboardId },
        });
    }

    openExplore() {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_bi.explore",
        });
    }

    async newDashboard() {
        const name = prompt(_t("Dashboard name"));
        if (!name) {
            return;
        }
        const [dashboardId] = await this.orm.create("bi.dashboard", [{ name }]);
        this.openDashboard(dashboardId);
    }

    dashboardsOf(workspaceId) {
        return this.state.dashboards.filter(
            (d) => d.workspace_id && d.workspace_id[0] === workspaceId);
    }
}

registry.category("actions").add("biz_bi.home", BiHomeAction);
