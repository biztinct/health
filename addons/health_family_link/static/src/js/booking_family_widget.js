/** @odoo-module **/

/**
 * Booking (FSO) → "Family Updates" tab.
 *
 * Lazy: the ops booking arch is loaded whole in one web_read on page open, so
 * an x2many <field> would cost every booking open. onWillStart defers the RPC
 * to the click. Clone of health_fieldservice's vu_booking_timeline.
 *
 * SECURITY: the payload carries status only — the family page token is a
 * capability credential and never leaves the server here.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_BADGE = {
    pending: "text-bg-info",
    sent: "text-bg-info",
    viewed: "text-bg-success",
    expired: "text-bg-secondary",
    revoked: "text-bg-danger",
    cancelled: "text-bg-danger",
};

export class BookingFamilyWidget extends Component {
    static template = "health_family_link.BookingFamilyWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ links: [], loading: true });

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
                "health.family.link", "get_booking_links", [resId]
            );
            this.state.links = data.links || [];
        } catch (e) {
            console.error("Family links load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    openLink(linkId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.family.link",
            res_id: linkId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const bookingFamilyWidget = {
    component: BookingFamilyWidget,
};
registry
    .category("view_widgets")
    .add("vu_booking_family", bookingFamilyWidget);
