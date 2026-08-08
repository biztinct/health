/** @odoo-module **/

/**
 * Client profile → "Family" tab.
 *
 * The heaviest of the consolidated tabs: every message body is decrypted
 * server-side on read. Fetching in onWillStart means that cost is paid only
 * when someone opens the tab, not on every client-page load. Clone of
 * health_fieldservice's vu_booking_timeline.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class ClientFamilyWidget extends Component {
    static template = "health_family_messages.ClientFamilyWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ threads: [], loading: true });

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
                "health.family.thread", "get_client_threads", [resId]
            );
            this.state.threads = data.threads || [];
        } catch (e) {
            console.error("Family threads load failed:", e);
        }
        this.state.loading = false;
    }

    get totalUnread() {
        return this.state.threads.reduce(
            (n, t) => n + (t.unread_ops_count || 0), 0
        );
    }

    openThread(threadId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.family.thread",
            res_id: threadId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const clientFamilyWidget = {
    component: ClientFamilyWidget,
};
registry.category("view_widgets").add("vu_client_family", clientFamilyWidget);
