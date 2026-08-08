/** @odoo-module **/

/**
 * Client profile → "Diagnoses" tab (FHIR Condition problem list).
 *
 * Lazy: the ops client arch is loaded whole by one web_read on page open, so
 * an x2many <field> would cost every client-page open. onWillStart defers the
 * RPC to the click. Clone of health_fieldservice's vu_booking_timeline.
 *
 * This module reaches health_fieldservice transitively (health_condition →
 * health_fhir_terminology → health_fieldservice), so inheriting the ops
 * profile view here is load-order safe and needs no new direct dependency.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const STATUS_BADGE = {
    active: "text-bg-danger",
    inactive: "text-bg-secondary",
    resolved: "text-bg-success",
};

export class ClientDiagnosesWidget extends Component {
    static template = "health_condition.ClientDiagnosesWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ conditions: [], loading: true });

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
                "health.condition", "get_client_conditions", [resId]
            );
            this.state.conditions = data.conditions || [];
        } catch (e) {
            console.error("Diagnoses load failed:", e);
        }
        this.state.loading = false;
    }

    badgeClass(status) {
        return STATUS_BADGE[status] || "text-bg-secondary";
    }

    get activeCount() {
        return this.state.conditions.filter(
            (c) => c.clinical_status === "active"
        ).length;
    }

    openCondition(conditionId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "health.condition",
            res_id: conditionId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const clientDiagnosesWidget = {
    component: ClientDiagnosesWidget,
};
registry
    .category("view_widgets")
    .add("vu_client_diagnoses", clientDiagnosesWidget);
