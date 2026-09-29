/** @odoo-module */
// =============================================================================
// Contact workspace (WS-3) — the panels of the CRM contact screen.
// -----------------------------------------------------------------------------
//   <widget name="ws_contact_next"/>                     the Next step banner
//   <widget name="ws_contact_glance" mode="glance"/>     At a glance (rail)
//   <widget name="ws_contact_glance" mode="attention"/>  Needs attention, or nothing
//   <widget name="ws_contact_glance" mode="avatar"/>     the hero's initials circle
//
// ONE loader, built on the client screen's (health_fieldservice
// ws_client_panels.js — its memo key and helpers are imported, not copied).
// Everything the contact panels show is on the contact record itself, so the
// loader makes NO server call: it derives the "facts" (status label, days
// since first contact, follow-up, duplicates…) once per record load, memoised
// on the client loader's key (this form + resId + write_date, ledger §5.250),
// and every panel reads the same object.
//
// The actions run the SAME crm.lead methods the header buttons run (Book =
// action_convert_to_booking, Log activity = action_log_as_lead); after the
// action the record reloads, like an arch button.
//
// Prose is built with _t placeholders, never template literals (the minifier
// eats spaces after an interpolation, ledger §5.149).
// =============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { dayDiff, relativeDay } from "@health_fieldservice/js/ws_booking_glance";
import { profileKey } from "@health_fieldservice/js/ws_client_panels";

const { DateTime } = luxon;

/** Statuses still being worked (the "Following up" step). */
const FOLLOWING = ["lead", "thinking", "recontact"];
/** A New contact with no outcome for this many days is flagged. */
const STALE_DAYS = 7;

/** Fields every panel reads from the record (no RPC). */
const RECORD_DEPENDENCIES = [
    { name: "write_date", type: "datetime" },
    { name: "name", type: "char" },
    { name: "contact_status", type: "selection" },
    { name: "contact_outcome", type: "selection" },
    { name: "contact_datetime", type: "datetime" },
    { name: "next_follow_up_date", type: "datetime" },
    { name: "last_booking_date", type: "date" },
    { name: "duplicate_lead_count", type: "integer" },
    { name: "clinical_priority", type: "selection" },
    { name: "patient_id", type: "many2one", relation: "res.partner" },
];

// ---------------------------------------------------------------------------
// The shared loader — one facts object per record load
// ---------------------------------------------------------------------------
const cache = new Map(); // resId -> { key, facts }

function selectionLabel(record, name) {
    const value = record.data[name];
    if (!value) {
        return "";
    }
    const field = record.fields[name];
    const pair = ((field && field.selection) || []).find(([v]) => v === value);
    return (pair && pair[1]) || String(value);
}

/** The initials of a name: first letter of the first two words. */
export function initialsOf(name) {
    const words = (name || "").trim().split(/\s+/).filter(Boolean);
    const letters = words.slice(0, 2).map((w) => w[0]).join("");
    return letters.toUpperCase() || "?";
}

function buildFacts(record) {
    const d = record.data;
    const now = DateTime.local();
    const status = d.contact_status || "active";
    const first = d.contact_datetime && d.contact_datetime.startOf ? d.contact_datetime : null;
    const follow = d.next_follow_up_date && d.next_follow_up_date.startOf ? d.next_follow_up_date : null;
    const lastBooking = d.last_booking_date && d.last_booking_date.startOf ? d.last_booking_date : null;
    const daysSinceFirst = first ? Math.max(0, -dayDiff(first, now)) : null;
    const following = FOLLOWING.includes(status);
    return {
        status,
        statusLabel: selectionLabel(record, "contact_status"),
        outcome: d.contact_outcome || "",
        first,
        daysSinceFirst,
        follow,
        followOverdue: Boolean(following && follow && follow < now),
        lastBooking,
        duplicates: Number(d.duplicate_lead_count) || 0,
        priorityLabel: selectionLabel(record, "clinical_priority"),
        clientId: (d.patient_id && (d.patient_id.id ?? d.patient_id[0])) || false,
        following,
        staleNew: Boolean(status === "active" && !d.contact_outcome && daysSinceFirst !== null && daysSinceFirst >= STALE_DAYS),
    };
}

/** The facts of the contact on this record (memoised per record load). */
export function contactFacts(record) {
    const resId = record.resId || 0;
    const key = profileKey(record);
    const hit = cache.get(resId);
    if (hit && hit.key === key) {
        return hit.facts;
    }
    const facts = buildFacts(record);
    // an unsaved edit changes the facts without a new write_date: memoise only
    // a clean record
    if (!record.dirty) {
        cache.set(resId, { key, facts });
    }
    return facts;
}

function daysText(n) {
    return n === 1 ? _t("1 day") : _t("%s days", n);
}

/** Run a crm.lead method and the action it returns, then reload the record
 *  (what an arch object button does). */
export async function runLeadMethod(env, record, method) {
    if (!record.resId) {
        return;
    }
    // like an arch button: save pending edits first (a no-op when clean)
    const saved = await record.save();
    if (saved === false) {
        return;
    }
    const reload = () => record.load();
    const action = await env.services.orm.call("crm.lead", method, [[record.resId]]);
    if (action) {
        await env.services.action.doAction(action, { onClose: reload });
    } else {
        await reload();
    }
}

/** Open the linked client in the client screen (keeps the way back here). */
export function openClient(env, clientId) {
    return env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "res.partner",
        res_id: clientId,
        views: [[false, "form"]],
        target: "current",
        context: { form_view_ref: "health_fieldservice.view_health_patient_form_ops" },
    });
}

// ---------------------------------------------------------------------------
// Base
// ---------------------------------------------------------------------------
class WsContactPanel extends Component {
    static props = {
        ...standardWidgetProps,
        mode: { type: String, optional: true },
    };

    get record() {
        return this.props.record;
    }

    get facts() {
        return contactFacts(this.props.record);
    }

    book() {
        return runLeadMethod(this.env, this.props.record, "action_convert_to_booking");
    }

    logActivity() {
        return runLeadMethod(this.env, this.props.record, "action_log_as_lead");
    }

    openClient() {
        const id = this.facts.clientId;
        return id && openClient(this.env, id);
    }
}

// ---------------------------------------------------------------------------
// At a glance / Needs attention / avatar
// ---------------------------------------------------------------------------
export class WsContactGlance extends WsContactPanel {
    static template = "health_crm.WsContactGlance";

    get mode() {
        return this.props.mode || "glance";
    }

    get initials() {
        return initialsOf(this.props.record.data.name);
    }

    get rows() {
        const f = this.facts;
        const now = DateTime.local();
        const rows = [];

        rows.push({
            key: "since",
            label: _t("Since first contact"),
            value: f.daysSinceFirst === null ? "—" : daysText(f.daysSinceFirst),
            cls: f.daysSinceFirst === null ? "is-quiet" : f.staleNew ? "is-warn" : "",
        });

        rows.push({ key: "status", label: _t("Status"), value: f.statusLabel || "—", cls: f.statusLabel ? "" : "is-quiet" });

        rows.push({
            key: "follow",
            label: _t("Follow-up"),
            value: f.follow ? relativeDay(dayDiff(f.follow, now)) : _t("None"),
            cls: f.follow ? (f.followOverdue ? "is-warn" : "") : "is-quiet",
        });

        rows.push({
            key: "booking",
            label: _t("Last booking"),
            value: f.lastBooking ? relativeDay(dayDiff(f.lastBooking, now)) : _t("None"),
            cls: f.lastBooking ? "" : "is-quiet",
        });

        rows.push({
            key: "duplicates",
            label: f.duplicates > 0 ? _t("Possible duplicates") : _t("Duplicates"),
            value: String(f.duplicates),
            cls: f.duplicates > 0 ? "is-warn" : "is-quiet",
        });

        rows.push({ key: "priority", label: _t("Priority"), value: f.priorityLabel || "—", cls: f.priorityLabel ? "" : "is-quiet" });
        return rows;
    }

    get alerts() {
        const f = this.facts;
        const alerts = [];
        if (f.staleNew) {
            alerts.push({
                key: "no_outcome",
                tone: "warn",
                text: _t("No outcome recorded %s after the first contact.", daysText(f.daysSinceFirst)),
            });
        }
        if (f.followOverdue) {
            alerts.push({
                key: "follow",
                tone: "warn",
                text: _t("Follow-up was due %s.", relativeDay(dayDiff(f.follow, DateTime.local())).toLowerCase()),
            });
        }
        if (f.duplicates > 0) {
            // duplicate_lead_count = other enquiries with the same email, the
            // same phone or the same name (crm_lead._compute_duplicate_lead_count)
            alerts.push({
                key: "duplicates",
                tone: "warn",
                text: f.duplicates === 1
                    ? _t("1 other contact has the same name, phone or email.")
                    : _t("%s other contacts have the same name, phone or email.", f.duplicates),
            });
        }
        if (f.status === "spam") {
            alerts.push({ key: "spam", tone: "info", text: _t("This contact was marked as spam.") });
        }
        return alerts;
    }
}

export const wsContactGlance = {
    component: WsContactGlance,
    extractProps: ({ attrs }) => ({ mode: attrs.mode || "glance" }),
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_contact_glance", wsContactGlance);

// ---------------------------------------------------------------------------
// Next step
// ---------------------------------------------------------------------------
export class WsContactNext extends WsContactPanel {
    static template = "health_crm.WsContactNext";

    /** First matching rule wins (handover WS-3 §3). */
    get card() {
        if (!this.props.record.resId) {
            return null;
        }
        const f = this.facts;
        const now = DateTime.local();
        const book = { key: "book", label: _t("Book"), primary: true, run: () => this.book() };
        const log = { key: "log", label: _t("Log activity"), primary: true, run: () => this.logActivity() };
        const openClient = { key: "client", label: _t("Open client"), primary: true, run: () => this.openClient() };

        if (f.status === "active" && !f.outcome) {
            return {
                kind: "phone",
                title: _t("No outcome recorded yet."),
                hint: f.first ? _t("First contact %s.", relativeDay(dayDiff(f.first, now)).toLowerCase()) : "",
                buttons: [book, { ...log, primary: false }],
            };
        }
        if (f.following && f.followOverdue) {
            return {
                kind: "phone",
                title: _t("Follow-up was due %s.", relativeDay(dayDiff(f.follow, now)).toLowerCase()),
                hint: _t("Call back, then record what they need."),
                buttons: [log],
            };
        }
        if (f.following) {
            return {
                kind: "calendar",
                title: _t("Following up."),
                hint: f.follow
                    ? _t("Next follow-up %s.", relativeDay(dayDiff(f.follow, now)).toLowerCase())
                    : _t("No follow-up date set."),
                buttons: [book],
            };
        }
        if (f.status === "booking") {
            return {
                kind: "calendar",
                title: _t("Appointment scheduled."),
                hint: f.lastBooking
                    ? _t("Last booking %s.", relativeDay(dayDiff(f.lastBooking, now)).toLowerCase())
                    : "",
                buttons: f.clientId ? [openClient] : [],
            };
        }
        if (f.status === "service_used" || f.status === "existing") {
            return {
                kind: "user",
                title: _t("Existing client."),
                hint: "",
                buttons: f.clientId ? [openClient] : [],
            };
        }
        if (f.status === "lost_booking") {
            return { kind: "stop", title: _t("Booking cancelled."), hint: "", buttons: [] };
        }
        if (f.status === "spam") {
            return { kind: "spam", title: _t("Marked as spam."), hint: "", buttons: [] };
        }
        // New with an outcome recorded: still to be followed up
        return {
            kind: "calendar",
            title: _t("Following up."),
            hint: _t("No follow-up date set."),
            buttons: [book],
        };
    }
}

export const wsContactNext = {
    component: WsContactNext,
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_contact_next", wsContactNext);
