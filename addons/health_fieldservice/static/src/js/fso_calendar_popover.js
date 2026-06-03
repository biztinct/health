import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { renderToFragment } from "@web/core/utils/render";

const FSO_MODEL = "health.fieldservice.order";
const NON_CANCELLABLE = ["completed", "completed_pending_invoice", "cancelled", "closed"];

const SERVICE_LABELS = {
    home_visit: "Home Visit", clinic_visit: "Clinic Visit", consultation: "Consultation",
    emergency: "Emergency", follow_up: "Follow-up", preventive: "Preventive",
    rehabilitation: "Rehabilitation", telemedicine: "Telemedicine", vaccination: "Vaccination",
    diagnostic: "Diagnostic",
};
const STATE_LABELS = {
    draft: "Draft", confirmed: "Confirmed", assigned: "Assigned", in_progress: "In Progress",
    completed: "Completed", completed_pending_invoice: "Completed", cancelled: "Cancelled", closed: "Closed",
};
const PRIORITY_LABELS = { 2: "High", 3: "Urgent", 4: "Emergency" };

function _initials(name) {
    const parts = (name || "").trim().split(/\s+/);
    return ((parts[0] || "")[0] || "") + (parts.length > 1 ? (parts[parts.length - 1][0] || "") : "");
}
function _durationText(record) {
    if (!record.start || !record.end) return "";
    const mins = Math.round(record.end.diff(record.start, "minutes").minutes);
    if (mins <= 0) return "";
    if (mins < 60) return `${mins}m`;
    const h = Math.floor(mins / 60), m = mins % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
}

patch(CalendarCommonPopover, {
    subTemplates: {
        ...CalendarCommonPopover.subTemplates,
        popover: "health_fieldservice.FSO_CalendarPopover.popover",
        footer: "health_fieldservice.FSO_CalendarPopover.footer",
    },
});

patch(CalendarCommonPopover.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
    },

    get isFsoPopover() {
        return this.props.model.resModel === FSO_MODEL;
    },

    get bkInfo() {
        const raw = this.props.record.rawRecord || {};
        const prio = String(raw.priority || "0");
        return {
            clientName: (raw.patient_id && raw.patient_id[1]) || this.props.record.title || "",
            clientCode: raw.patient_code || "",
            serviceKey: raw.service_type || "default",
            serviceLabel: SERVICE_LABELS[raw.service_type] || "",
            statusKey: raw.state || "draft",
            statusLabel: STATE_LABELS[raw.state] || raw.state || "",
            priorityKey: PRIORITY_LABELS[prio] ? prio : "",
            priorityLabel: PRIORITY_LABELS[prio] || "",
            staffName: (raw.lead_staff_id && raw.lead_staff_id[1]) || "",
            staffInitials: _initials(raw.lead_staff_id && raw.lead_staff_id[1]).toUpperCase(),
            catchment: (raw.catchment_province_id && raw.catchment_province_id[1]) || "",
            hasStaff: !!raw.has_staff_assigned,
        };
    },

    get isBookingCancellable() {
        if (this.props.model.resModel !== FSO_MODEL) return false;
        const state = this.props.record.rawRecord?.state;
        return state && !NON_CANCELLABLE.includes(state);
    },

    get isBookingReschedulable() {
        return this.isBookingCancellable;
    },

    async onRescheduleEvent() {
        const recordId = this.props.record.id;
        const action = await this.orm.call(
            FSO_MODEL, "action_open_reschedule_wizard", [recordId]
        );
        if (action) {
            this.actionService.doAction(action);
        }
        this.props.close();
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
    onEventContent(arg) {
        if (this.props.model.resModel !== FSO_MODEL) {
            return super.onEventContent(arg);
        }
        const record = this.props.model.records[arg.event.id];
        if (!record) {
            return super.onEventContent(arg);
        }
        const raw = record.rawRecord || {};
        const prio = String(raw.priority || "0");
        const ctx = {
            startTime: this.getStartTime(record),
            durationText: _durationText(record),
            clientName: (raw.patient_id && raw.patient_id[1]) || record.title || "",
            clientCode: raw.patient_code || "",
            serviceKey: raw.service_type || "default",
            serviceLabel: SERVICE_LABELS[raw.service_type] || "",
            statusKey: raw.state || "draft",
            statusLabel: STATE_LABELS[raw.state] || raw.state || "",
            priorityKey: PRIORITY_LABELS[prio] ? prio : "",
            priorityLabel: PRIORITY_LABELS[prio] || "",
            staffName: (raw.lead_staff_id && raw.lead_staff_id[1]) || "",
            staffInitials: _initials(raw.lead_staff_id && raw.lead_staff_id[1]).toUpperCase(),
        };
        const fragment = renderToFragment("health_fieldservice.BookingEventCard", ctx);
        return { domNodes: [...fragment.children] };
    },

    eventClassNames(info) {
        const classes = super.eventClassNames(info);
        if (this.props.model.resModel === FSO_MODEL) {
            const record = this.props.model.records[info.event.id];
            const raw = (record && record.rawRecord) || {};
            classes.push("o-bk-event", `o-bk-st-${raw.state || "draft"}`);
            if (!raw.has_staff_assigned) {
                classes.push("o-bk-unassigned");
            }
        }
        return classes;
    },

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
