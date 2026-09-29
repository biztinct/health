/** @odoo-module */
// =============================================================================
// Booking workspace — "At a glance", "Needs attention" and the Next step hint.
// -----------------------------------------------------------------------------
//   <widget name="ws_booking_glance" mode="glance"/>     rows for the rail
//   <widget name="ws_booking_glance" mode="attention"/>  its own panel, or nothing
//   <widget name="ws_booking_hint"/>                     one muted line
// Pure display, computed in the browser from the booking's own fields: no
// server call, no write. Money fields that only exist with the invoicing module
// (outstanding_amount, total_paid_amount, is_invoiced) are read only when the
// record has them, and never declared as dependencies.
// Prose is built with concatenation / _t placeholders, never template
// literals (the minifier eats spaces after an interpolation, ledger §5.149).
// =============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const { DateTime } = luxon;

const NATIVE_DEPENDENCIES = [
    { name: "state", type: "selection" },
    { name: "scheduled_datetime", type: "datetime" },
    { name: "scheduled_duration", type: "integer" },
    { name: "has_staff_assigned", type: "boolean" },
    { name: "assigned_staff_ids", type: "many2many" },
    { name: "lead_staff_id", type: "many2one" },
    { name: "total_price", type: "monetary" },
    { name: "service_fee_vnd", type: "monetary" },
    { name: "currency_id", type: "many2one" },
    { name: "sale_order_id", type: "many2one" },
    { name: "invoice_id", type: "many2one" },
    { name: "urgency_level", type: "selection" },
    { name: "deleted", type: "boolean" },
    { name: "active", type: "boolean" },
];

const STAFF_EXPECTED = ["confirmed", "assigned"];
const PRE_VISIT_STATES = ["confirmed", "assigned"];

// What the client pays: the quote total (service_fee_vnd) plus the extra
// charges. total_price is base_price + charges, and base_price is a legacy
// field that is 0 on every booking, so total_price alone reads 0 on almost
// every priced booking.
function bookingPrice(data) {
    return (Number(data.service_fee_vnd) || 0) + (Number(data.total_price) || 0);
}
const PAID_STATES = ["completed", "completed_pending_invoice", "closed"];

/** Calendar-day difference between `dt` and today, in the browser's calendar
 *  (the same clock the form uses to display the date). */
export function dayDiff(dt, now = DateTime.local()) {
    if (!dt || !dt.startOf) {
        return null;
    }
    const a = dt.setZone(now.zone).startOf("day");
    const b = now.startOf("day");
    return Math.round(a.diff(b, "days").days);
}

export function relativeDay(days) {
    if (days === 0) {
        return _t("Today");
    }
    if (days === 1) {
        return _t("Tomorrow");
    }
    if (days === -1) {
        return _t("Yesterday");
    }
    if (days > 1) {
        return _t("In %s days", days);
    }
    return _t("%s days ago", -days);
}

export function durationText(minutes) {
    const m = Math.round(Number(minutes) || 0);
    if (m <= 0) {
        return "—";
    }
    if (m % 60 === 0) {
        return _t("%s h", m / 60);
    }
    return _t("%s min", m);
}

/** Everything both widgets derive from the record, in one place. */
export class BookingFacts {
    constructor(record, now = DateTime.local()) {
        this.record = record;
        this.data = record.data;
        this.now = now;
    }

    has(name) {
        return name in this.record.fields && name in this.data;
    }

    get state() {
        return this.data.state || "";
    }

    get visit() {
        return this.data.scheduled_datetime || null;
    }

    get days() {
        return dayDiff(this.visit, this.now);
    }

    get visitPassed() {
        return Boolean(this.visit && this.visit < this.now);
    }

    get staffNames() {
        const list = this.data.assigned_staff_ids;
        const records = (list && list.records) || [];
        return records.map((r) => r.data.display_name).filter(Boolean);
    }

    get staffCount() {
        const list = this.data.assigned_staff_ids;
        if (!list) {
            return 0;
        }
        return list.count ?? (list.records || []).length;
    }

    get hasStaff() {
        return Boolean(this.data.has_staff_assigned || this.staffCount > 0 || this.data.lead_staff_id);
    }

    get currencyId() {
        const c = this.data.currency_id;
        return (c && c.id) || c || undefined;
    }

    money(value) {
        return formatMonetary(Number(value) || 0, { currencyId: this.currencyId });
    }

    get plannedEnd() {
        if (!this.visit) {
            return null;
        }
        return this.visit.plus({ minutes: Number(this.data.scheduled_duration) || 0 });
    }
}

// ---------------------------------------------------------------------------
// At a glance / Needs attention
// ---------------------------------------------------------------------------
export class WsBookingGlance extends Component {
    static template = "health_fieldservice.WsBookingGlance";
    static props = {
        ...standardWidgetProps,
        mode: { type: String, optional: true },
    };

    get facts() {
        return new BookingFacts(this.props.record);
    }

    get isAttention() {
        return this.props.mode === "attention";
    }

    get rows() {
        const f = this.facts;
        const rows = [];

        // Visit
        let visit = "—";
        let visitClass = "";
        if (f.visit) {
            visit = relativeDay(f.days) + " · " + f.visit.toFormat("HH:mm");
            if (
                ["draft", "confirmed"].includes(f.state) &&
                !f.hasStaff &&
                f.days >= 0 &&
                f.days <= 3
            ) {
                visitClass = "is-warn";
            }
        }
        rows.push({ key: "visit", label: _t("Visit"), value: visit, cls: visitClass });

        // Staff
        const lead = f.data.lead_staff_id;
        let staff = _t("Nobody yet");
        let staffClass = "";
        if (lead && lead.display_name) {
            const leadIsListed = (f.data.assigned_staff_ids?.currentIds || []).includes(lead.id);
            const others = Math.max(0, f.staffCount - (leadIsListed ? 1 : 0));
            staff = others ? lead.display_name + " +" + others : lead.display_name;
        } else if (f.staffCount) {
            const first = f.staffNames[0] || "";
            staff = f.staffCount > 1 ? first + " +" + (f.staffCount - 1) : first;
        } else {
            staffClass = STAFF_EXPECTED.includes(f.state) ? "is-warn" : "is-quiet";
        }
        rows.push({ key: "staff", label: _t("Staff"), value: staff, cls: staffClass });

        // Duration
        rows.push({
            key: "duration",
            label: _t("Duration"),
            value: durationText(f.data.scheduled_duration),
            cls: "",
        });

        // Price
        const price = bookingPrice(f.data);
        rows.push({
            key: "price",
            label: _t("Price"),
            value: f.money(price),
            cls: price ? "" : "is-quiet",
        });

        // Paid — invoicing module only, and only once there is an invoice
        if (f.has("total_paid_amount") && f.has("is_invoiced") && f.data.is_invoiced) {
            const paid = Number(f.data.total_paid_amount) || 0;
            rows.push({
                key: "paid",
                label: _t("Paid"),
                value: f.money(paid),
                cls: paid ? "" : "is-quiet",
            });
        }

        // Outstanding — invoicing module only; hidden when nothing is owed
        if (f.has("outstanding_amount")) {
            const owed = Number(f.data.outstanding_amount) || 0;
            if (owed > 0) {
                rows.push({
                    key: "outstanding",
                    label: _t("Outstanding"),
                    value: f.money(owed),
                    cls: "is-bad",
                });
            }
        }
        return rows;
    }

    get alerts() {
        const f = this.facts;
        const alerts = [];

        // 1. nobody assigned and the visit is close (or already past)
        if (f.state === "confirmed" && !f.hasStaff && f.visit && f.days !== null && f.days <= 3) {
            let text;
            if (f.visitPassed) {
                text = _t("Nobody assigned and the visit time has passed.");
            } else if (f.days <= 0) {
                text = _t("Nobody assigned and the visit is today.");
            } else if (f.days === 1) {
                text = _t("Nobody assigned and the visit is tomorrow.");
            } else {
                text = _t("Nobody assigned and the visit is in %s days.", f.days);
            }
            alerts.push({ key: "staff", tone: "warn", text });
        }

        // 2. a price of zero on a booking whose visit is still ahead
        if (PRE_VISIT_STATES.includes(f.state) && !bookingPrice(f.data)) {
            alerts.push({
                key: "price",
                tone: "warn",
                text: _t("The price is %s. Check the quote before the visit.", f.money(0)),
            });
        }

        // 3. money still owed on a finished visit (invoicing module only)
        if (f.has("outstanding_amount") && PAID_STATES.includes(f.state)) {
            const owed = Number(f.data.outstanding_amount) || 0;
            if (owed > 0) {
                alerts.push({ key: "owed", tone: "bad", text: _t("%s is unpaid.", f.money(owed)) });
            }
        }

        // 4. a visit running more than 30 minutes past its planned end
        if (f.state === "in_progress" && f.plannedEnd && f.now > f.plannedEnd.plus({ minutes: 30 })) {
            alerts.push({
                key: "overrun",
                tone: "warn",
                text: _t("The visit is running past its planned end."),
            });
        }
        return alerts;
    }
}

export const wsBookingGlance = {
    component: WsBookingGlance,
    extractProps: ({ attrs }) => ({ mode: attrs.mode || "glance" }),
    fieldDependencies: NATIVE_DEPENDENCIES,
};

registry.category("view_widgets").add("ws_booking_glance", wsBookingGlance);

// ---------------------------------------------------------------------------
// Next step hint — one muted line inside the Next step card
// ---------------------------------------------------------------------------
export class WsBookingHint extends Component {
    static template = "health_fieldservice.WsBookingHint";
    static props = { ...standardWidgetProps };

    get text() {
        const f = new BookingFacts(this.props.record);
        if (f.state === "confirmed") {
            let visit = "";
            if (f.visit) {
                if (f.visitPassed) {
                    visit = _t("The visit time has passed");
                } else if (f.days <= 0) {
                    visit = _t("Visit today");
                } else if (f.days === 1) {
                    visit = _t("Visit tomorrow");
                } else {
                    visit = _t("Visit in %s days", f.days);
                }
            }
            const parts = [visit];
            if (!f.hasStaff) {
                parts.push(_t("nobody assigned yet"));
            }
            return parts.filter(Boolean).join(" · ");
        }
        if (f.state === "assigned") {
            if (!f.visit) {
                return "";
            }
            const minutes = Math.round(f.visit.diff(f.now, "minutes").minutes);
            if (minutes <= 0) {
                return _t("Due to start now");
            }
            if (minutes < 60) {
                return _t("Starts in %s min", minutes);
            }
            if (minutes < 24 * 60) {
                return _t("Starts in %s h", Math.round(minutes / 60));
            }
            return _t("Starts in %s days", Math.max(1, f.days));
        }
        if (f.state === "draft") {
            const created = f.data.create_date;
            const days = dayDiff(created, f.now);
            if (days === null) {
                return "";
            }
            if (days >= 0) {
                return _t("Created today");
            }
            if (days === -1) {
                return _t("Created yesterday");
            }
            return _t("Created %s days ago", -days);
        }
        return "";
    }
}

export const wsBookingHint = {
    component: WsBookingHint,
    fieldDependencies: [...NATIVE_DEPENDENCIES, { name: "create_date", type: "datetime" }],
};

registry.category("view_widgets").add("ws_booking_hint", wsBookingHint);
