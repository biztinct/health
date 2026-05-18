import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

const FSO_MODEL = "health.fieldservice.order";
const NON_CANCELLABLE = ["completed", "completed_pending_invoice", "cancelled", "closed"];

patch(CalendarCommonPopover, {
    subTemplates: {
        ...CalendarCommonPopover.subTemplates,
        footer: "health_fieldservice.FSO_CalendarPopover.footer",
    },
});

patch(CalendarCommonPopover.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
    },

    get isBookingCancellable() {
        if (this.props.model.resModel !== FSO_MODEL) return false;
        const state = this.props.record.rawRecord?.state;
        return state && !NON_CANCELLABLE.includes(state);
    },

    onEditEvent() {
        if (this.props.model.resModel === FSO_MODEL) {
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "ops_booking_detail",
                name: "Booking",
                target: "current",
                context: { active_id: this.props.record.id },
            });
            this.props.close();
            return;
        }
        super.onEditEvent();
    },

    async onCancelEvent() {
        this.props.close();
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Cancel Booking",
            res_model: "health.booking.cancel.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_booking_id: this.props.record.id },
        });
    },
});

patch(CalendarCommonRenderer.prototype, {
    onDblClick(info) {
        const record = this.props.model.records[info.event.id];
        if (this.props.model.resModel === FSO_MODEL && record) {
            this.env.services.action.doAction({
                type: "ir.actions.client",
                tag: "ops_booking_detail",
                name: "Booking",
                target: "current",
                context: { active_id: record.id },
            });
            return;
        }
        super.onDblClick(info);
    },
});
