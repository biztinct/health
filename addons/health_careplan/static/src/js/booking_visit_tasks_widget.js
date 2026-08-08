/** @odoo-module **/

/**
 * Booking (FSO) → "Visit Tasks" tab.
 *
 * The FSO already has a careplan_task_ids o2m, but the ops booking arch is
 * loaded whole in one web_read, so binding it as a <field> would tax every
 * booking open. onWillStart defers the fetch to the click.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATE_BADGE = {
    pending: "text-bg-secondary",
    done: "text-bg-success",
    not_done: "text-bg-danger",
    skipped: "text-bg-warning",
};

export class BookingVisitTasksWidget extends Component {
    static template = "health_careplan.BookingVisitTasksWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tasks: [], loading: true });

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
                "health.careplan.task", "get_booking_tasks", [resId]
            );
            this.state.tasks = data.tasks || [];
        } catch (e) {
            console.error("Visit tasks load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(state) {
        return STATE_BADGE[state] || "text-bg-secondary";
    }

    get doneCount() {
        return this.state.tasks.filter((t) => t.state === "done").length;
    }

    openCareplan(careplanId) {
        if (!careplanId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.careplan",
            res_id: careplanId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const bookingVisitTasksWidget = {
    component: BookingVisitTasksWidget,
};
registry
    .category("view_widgets")
    .add("vu_booking_visit_tasks", bookingVisitTasksWidget);
