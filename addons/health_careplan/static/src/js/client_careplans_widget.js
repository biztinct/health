/** @odoo-module **/

/**
 * Client profile → "Care Plans" tab.
 *
 * Lazy: the ops client arch is loaded whole by a single web_read on page open,
 * so an x2many <field> would cost every client-page open. The Notebook only
 * instantiates the active page's slot, so onWillStart defers the RPC until the
 * tab is clicked. Clone of health_fieldservice's vu_booking_timeline.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_BADGE = {
    draft: "text-bg-secondary",
    active: "text-bg-success",
    on_hold: "text-bg-warning",
    completed: "text-bg-primary",
    revoked: "text-bg-danger",
    cancelled: "text-bg-danger",
};

export class ClientCareplansWidget extends Component {
    static template = "health_careplan.ClientCareplansWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ careplans: [], loading: true });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const resId = this.props.record.resId;
        if (!resId) {
            this.state.loading = false;
            return;
        }
        try {
            const data = await this.orm.call(
                "health.careplan", "get_client_careplans", [resId]
            );
            this.state.careplans = data.careplans || [];
        } catch (e) {
            console.error("Care plans load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    openCareplan(careplanId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.careplan",
            res_id: careplanId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const clientCareplansWidget = {
    component: ClientCareplansWidget,
};
registry
    .category("view_widgets")
    .add("vu_client_careplans", clientCareplansWidget);
