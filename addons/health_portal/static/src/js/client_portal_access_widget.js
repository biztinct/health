/** @odoo-module **/

/**
 * Client profile → "Portal Access" tab.
 *
 * Lazy: the ops client arch is loaded whole by one web_read on page open, so
 * an x2many <field> would cost every open. onWillStart defers the RPC to the
 * click. Clone of health_fieldservice's vu_booking_timeline.
 *
 * SECURITY: the payload carries status only. The token and the derived
 * /my/care URL are capability credentials and are never sent here — read or
 * rotate them on the ops-manager-gated record form.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_BADGE = {
    active: "text-bg-success",
    revoked: "text-bg-danger",
};

export class ClientPortalAccessWidget extends Component {
    static template = "health_portal.ClientPortalAccessWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ access: [], loading: true });

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
                "health.portal.access.ops.tab",
                "get_client_portal_access",
                [resId]
            );
            this.state.access = data.access || [];
        } catch (e) {
            console.error("Portal access load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    openAccess(accessId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.portal.access",
            res_id: accessId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const clientPortalAccessWidget = {
    component: ClientPortalAccessWidget,
};
registry
    .category("view_widgets")
    .add("vu_client_portal_access", clientPortalAccessWidget);
