/** @odoo-module **/

/**
 * Booking (FSO) → "Telehealth" tab.
 *
 * One session per FSO (unique index on health_telehealth_session), so this
 * renders a single session, not a list. Lazy: the ops booking arch is loaded
 * whole in one web_read on page open, so onWillStart defers this RPC to the
 * click. Clone of health_fieldservice's vu_booking_timeline.
 *
 * SECURITY: the payload carries status only. The patient token and the derived
 * room URL are capability credentials; joining goes through the FSO's
 * action_tele_join object method, which re-checks access server-side.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_BADGE = {
    pending: "text-bg-info",
    open: "text-bg-success",
    closed: "text-bg-secondary",
    cancelled: "text-bg-danger",
};

export class BookingTelehealthWidget extends Component {
    static template = "health_telehealth.BookingTelehealthWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ session: null, loading: true });

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
                "health.telehealth.session", "get_booking_session", [resId]
            );
            this.state.session = data.session || null;
        } catch (e) {
            console.error("Telehealth session load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    async joinVideo() {
        // Server-side re-check lives in action_tele_join / _tele_join_url.
        const action = await this.orm.call(
            "health.fieldservice.order",
            "action_tele_join",
            [this.props.record.resId]
        );
        if (action) {
            this.action.doAction(action);
        }
    }

    openSession() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.telehealth.session",
            res_id: this.state.session.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const bookingTelehealthWidget = {
    component: BookingTelehealthWidget,
};
registry
    .category("view_widgets")
    .add("vu_booking_telehealth", bookingTelehealthWidget);
