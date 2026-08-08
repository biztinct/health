/** @odoo-module **/

/**
 * Client profile → "Booking Links" tab.
 *
 * Lazy by construction: the ops client arch is loaded by a single web_read on
 * page open, so an x2many <field> here would cost every client-page open even
 * for the users who never click this tab. The Notebook only instantiates the
 * active page's slot, so fetching in onWillStart defers the RPC until the tab
 * is opened. Clone of health_fieldservice's vu_booking_timeline.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

// Bootstrap badge utilities — already in web.assets_backend, so this tab ships
// no CSS of its own. Flat single colours only (no gradients), per house style.
const STATE_BADGE = {
    pending: "text-bg-info",
    sent: "text-bg-info",
    accepted: "text-bg-success",
    expired: "text-bg-secondary",
    cancelled: "text-bg-danger",
};

export class ClientBookingLinksWidget extends Component {
    static template = "health_self_booking.ClientBookingLinksWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ invites: [], loading: true });

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
                "health.selfbook.invite", "get_client_invites", [resId]
            );
            this.state.invites = data.invites || [];
        } catch (e) {
            console.error("Booking links load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    openInvite(inviteId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.selfbook.invite",
            res_id: inviteId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openBooking(fsoId) {
        if (!fsoId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.fieldservice.order",
            res_id: fsoId,
            views: [[false, "form"]],
            target: "current",
            context: {
                form_view_ref: "health_fieldservice.view_health_fso_form_ops",
            },
        });
    }
}

export const clientBookingLinksWidget = {
    component: ClientBookingLinksWidget,
};
registry
    .category("view_widgets")
    .add("vu_client_booking_links", clientBookingLinksWidget);
