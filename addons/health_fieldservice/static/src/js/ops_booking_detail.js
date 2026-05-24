/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class OpsBookingDetail extends Component {
    static template = "health_fieldservice.OpsBookingDetailRedirect";

    setup() {
        this.action = useService("action");
        const context = this.props.action && this.props.action.context || {};
        const bookingId = context.active_id || context.default_booking_id || false;
        if (bookingId) {
            const ctx = { form_view_ref: 'health_fieldservice.view_health_fso_form_ops' };
            if (context.active_center) ctx.active_center = context.active_center;
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'health.fieldservice.order',
                res_id: bookingId,
                views: [[false, 'form']],
                target: 'current',
                context: ctx,
            }, { clearBreadcrumbs: true });
        }
    }
}

registry.category("actions").add("ops_booking_detail", OpsBookingDetail);

export default OpsBookingDetail;
