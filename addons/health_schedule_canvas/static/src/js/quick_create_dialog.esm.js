/** @odoo-module **/
/**
 * ScheduleQuickCreateDialog — the draw-to-create booking dialog (§2.1).
 *
 * Why an owned minimal dialog rather than the shipped `ops_quick_booking`
 * client action: `ops_quick_booking` is a full-page ACTION (registered under
 * "actions", target=current) with its own in-page confirmation screen. Opening
 * it navigates away from the schedule and cannot call back into the timeline
 * renderer to reload it in place — which §2.1 step 5 requires ("on save → toast
 * + reload"). This lightweight dialog collects patient + service, forwards the
 * pre-filled staff / facility / date / time to the SAME shipped builder
 * (`action_create_from_quick_booking_owl`), then hands control back so the
 * controller reloads the timeline. (Reported as the chosen §2.1 path.)
 */
import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

/** Small, honest service menu for a quick draw-create; the builder maps each to a
 *  service_location. Ops can refine the booking (products, doctor…) on the form. */
const SERVICE_TYPES = [
    {value: "home_visit", label: _t("Home visit")},
    {value: "clinic_visit", label: _t("Clinic visit")},
    {value: "consultation", label: _t("Consultation")},
    {value: "follow_up", label: _t("Follow-up")},
    {value: "telemedicine", label: _t("Telemedicine")},
];

export class ScheduleQuickCreateDialog extends Component {
    static template = "health_schedule_canvas.QuickCreateDialog";
    static components = {Dialog};
    static props = {
        close: Function, // injected by the dialog service
        staffId: Number,
        staffName: {type: String, optional: true},
        facilityId: [Number, Boolean],
        facilityName: {type: String, optional: true},
        date: String,
        timeHour: Number,
        dateLabel: {type: String, optional: true},
        timeLabel: {type: String, optional: true},
        warning: {type: String, optional: true},
        onCreated: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.serviceTypes = SERVICE_TYPES;
        this.state = useState({
            query: "",
            results: [],
            searching: false,
            patientId: false,
            patientName: "",
            serviceType: "home_visit",
            durationHours: 1,
            notes: "",
            saving: false,
        });
    }

    get title() {
        return _t("New booking");
    }

    async onSearchInput(ev) {
        const q = (ev.target.value || "").trim();
        this.state.query = q;
        this.state.patientId = false;
        if (q.length < 2) {
            this.state.results = [];
            return;
        }
        this.state.searching = true;
        try {
            this.state.results = await this.orm.call("res.partner", "search_read", [
                [
                    "&",
                    ["is_patient", "=", true],
                    "|",
                    "|",
                    ["name", "ilike", q],
                    ["mobile", "ilike", q],
                    ["patient_code", "ilike", q],
                ],
                ["id", "name", "mobile", "patient_code"],
            ], {limit: 8, order: "name asc"});
        } catch {
            this.state.results = [];
        }
        this.state.searching = false;
    }

    pickPatient(p) {
        this.state.patientId = p.id;
        this.state.patientName = p.name;
        this.state.query = p.name;
        this.state.results = [];
    }

    clearPatient() {
        this.state.patientId = false;
        this.state.patientName = "";
        this.state.query = "";
        this.state.results = [];
    }

    get canCreate() {
        return Boolean(this.state.patientId) && !this.state.saving;
    }

    async create() {
        if (!this.canCreate) {
            return;
        }
        this.state.saving = true;
        let res;
        try {
            res = await this.orm.call(
                "health.fieldservice.order",
                "action_create_from_quick_booking_owl",
                [
                    {
                        patient_id: this.state.patientId,
                        staff_id: this.props.staffId,
                        facility_id: this.props.facilityId || false,
                        date: this.props.date,
                        time_hour: this.props.timeHour,
                        duration_hours: Number(this.state.durationHours) || 1,
                        service_type: this.state.serviceType,
                        notes: this.state.notes || "",
                    },
                ]
            );
        } catch {
            res = {success: false, error: _t("Could not create the booking.")};
        }
        this.state.saving = false;
        if (!res || !res.success) {
            this.notification.add((res && res.error) || _t("Could not create the booking."), {
                type: "danger",
            });
            return;
        }
        this.props.close();
        this.props.onCreated(res);
    }

    cancel() {
        this.props.close();
    }
}
