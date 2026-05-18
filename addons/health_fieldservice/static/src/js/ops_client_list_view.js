/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class OpsClientListController extends ListController {
    static template = "health_fieldservice.OpsClientListView";

    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.tabState = useState({ activeTab: "all" });
        this._tabFilterGroupId = null;
    }

    get tabs() {
        return [
            { id: "all", label: "All Clients", icon: "fa-users" },
            { id: "active", label: "Active", icon: "fa-check-circle" },
            { id: "inactive", label: "Inactive", icon: "fa-pause-circle" },
            { id: "recent", label: "Recent Visits", icon: "fa-clock-o" },
        ];
    }

    async setTab(tabId) {
        if (this.tabState.activeTab === tabId) return;
        this.tabState.activeTab = tabId;

        if (this._tabFilterGroupId !== null) {
            this.env.searchModel.deactivateGroup(this._tabFilterGroupId);
            this._tabFilterGroupId = null;
        }

        if (tabId !== "all") {
            let domain;
            let description;
            switch (tabId) {
                case "active":
                    domain = [["patient_status", "=", "active"]];
                    description = "Active";
                    break;
                case "inactive":
                    domain = [["patient_status", "=", "inactive"]];
                    description = "Inactive";
                    break;
                case "recent":
                    domain = [["last_visit_date", "!=", false]];
                    description = "Recent Visits";
                    break;
            }
            const preFilter = { description, domain };
            this.env.searchModel.createNewFilters([preFilter]);
            this._tabFilterGroupId = preFilter.groupId;
        }
    }

    openRecord(record) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: record.resId,
            views: [[false, "form"]],
            target: "current",
            context: { form_view_ref: "health_fieldservice.view_health_patient_form_ops" },
        });
    }
}

export const opsClientListView = {
    ...listView,
    Controller: OpsClientListController,
};

registry.category("views").add("ops_client_list_view", opsClientListView);
