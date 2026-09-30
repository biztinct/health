/** @odoo-module */
// =============================================================================
// Client workspace (WS-2) — the panels of the ops client screen.
// -----------------------------------------------------------------------------
//   <widget name="ws_client_next"/>                     the Next step banner
//   <widget name="ws_client_glance" mode="glance"/>     At a glance (rail)
//   <widget name="ws_client_glance" mode="contact"/>    the client's own row in People
//   <widget name="ws_client_glance" mode="attention"/>  Needs attention, or nothing
//   <widget name="ws_client_visits"/>                   Recent visits (Overview card)
//   <widget name="ws_client_shortcuts"/>                Shortcuts, from a registry
//
// ONE loader: `res.partner.get_client_profile_data` is called once per record
// load, memoised by resId + write_date and shared by every panel (an in-flight
// call is shared too). The controller's save hook invalidates it.
//
// Shortcuts come from `registry.category("ws_client_shortcuts")`:
//   { key, label (_t), icon, sequence, run(env, partnerId, ctx), isAvailable?(env) }
// `ctx` = { record, reload } so an entry can refresh the screen after it acts.
// health_fieldservice registers the booking entries here; health_invoicing
// registers its own (package, invoices…) from its module.
//
// Prose is built with concatenation / _t placeholders, never template
// literals (the minifier eats spaces after an interpolation, ledger §5.149).
// =============================================================================

import { Component, onMounted, onPatched, onWillRender, reactive, toRaw, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { dayDiff, relativeDay } from "@health_fieldservice/js/ws_booking_glance";

const { DateTime } = luxon;

export const shortcutRegistry = registry.category("ws_client_shortcuts");

// ---------------------------------------------------------------------------
// The shared loader
// ---------------------------------------------------------------------------
const cache = new Map(); // resId -> { key, promise, data }
const formTags = new WeakMap(); // one tag per opened form (its model instance)
let formSeq = 0;
// bumped by invalidateClientProfile(): every panel reads it, so they all re-key
const bus = reactive({ version: 0 });

function stamp(value) {
    if (!value) {
        return "";
    }
    return value.toISO ? value.toISO() : String(value);
}

/** The memo key: this form + this record + its write_date. A form opened
 *  again (a new model instance) is a new record load and fetches once more. */
export function profileKey(record) {
    // raw objects: every component sees the record through its OWN reactive
    // proxy, so a proxy would give each panel a different tag (and an RPC)
    const model = toRaw(record.model || record);
    if (!formTags.has(model)) {
        formTags.set(model, ++formSeq);
    }
    return bus.version + "/" + formTags.get(model) + ":" + record.resId + "@" + stamp(record.data.write_date);
}

/** Load (or reuse) the profile data of the client on this record. */
export function loadClientProfile(orm, record) {
    const resId = record && record.resId;
    if (!resId) {
        return Promise.resolve(null);
    }
    const key = profileKey(record);
    const hit = cache.get(resId);
    if (hit && hit.key === key) {
        return hit.promise;
    }
    const entry = { key, data: null, promise: null };
    entry.promise = orm
        .call("res.partner", "get_client_profile_data", [resId])
        .then((data) => {
            entry.data = data || {};
            return entry.data;
        })
        .catch(() => {
            if (cache.get(resId) === entry) {
                cache.delete(resId);
            }
            return null;
        });
    cache.set(resId, entry);
    return entry.promise;
}

/** Forget a client's data, so the next render fetches it again. */
export function invalidateClientProfile(resId) {
    if (resId) {
        cache.delete(resId);
    } else {
        cache.clear();
    }
    bus.version++;
}

/** Fields every panel reads from the record itself (no RPC). */
const RECORD_DEPENDENCIES = [
    { name: "write_date", type: "datetime" },
    { name: "patient_status", type: "selection" },
    { name: "registration_date", type: "datetime" },
    { name: "allergies", type: "text" },
    { name: "insurance_expiry", type: "date" },
    { name: "phone", type: "char" },
    { name: "mobile", type: "char" },
    { name: "email", type: "char" },
    { name: "name", type: "char" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function parseUtc(value) {
    return value ? deserializeDateTime(value) : null;
}

function companyCurrencyId(record) {
    const company = user.activeCompany;
    const fromCompany = company && (company.currency_id?.id ?? company.currency_id);
    if (fromCompany) {
        return fromCompany;
    }
    const c = record && record.fields.currency_id && record.data.currency_id;
    return (c && (c.id ?? c)) || undefined;
}

export function money(value, record) {
    return formatMonetary(Number(value) || 0, { currencyId: companyCurrencyId(record) });
}

/** The client's phone as the screen shows it everywhere (hero, Contact card):
 *  the Phone field, falling back to the legacy mobile. */
function recordPhone(data) {
    return (data.phone || data.mobile || "").trim();
}

function visitDateText(dt) {
    return dt ? dt.toFormat("ccc d LLL, HH:mm") : "";
}

/** Run a res.partner method and the action it returns — the old sidebar's
 *  doPartnerAction, with the same friendly warning on failure. */
export async function runPartnerMethod(env, partnerId, method) {
    if (!partnerId) {
        return;
    }
    try {
        const action = await env.services.orm.call("res.partner", method, [partnerId]);
        if (action) {
            await env.services.action.doAction(action);
        }
    } catch {
        env.services.notification.add(
            _t("Action not available. The required module may not be installed."),
            { type: "warning" }
        );
    }
}

/** Open a booking in the ops booking screen (same as the booking list does),
 *  keeping the way back to this client. */
export function openBooking(env, bookingId) {
    return env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "health.fieldservice.order",
        res_id: bookingId,
        views: [[false, "form"]],
        target: "current",
        context: { form_view_ref: "health_fieldservice.view_health_fso_form_ops" },
    });
}

function shortcutEntries(env) {
    return shortcutRegistry
        .getEntries()
        .map(([key, entry]) => ({ ...entry, key: entry.key || key }))
        .filter((entry) => !entry.isAvailable || entry.isAvailable(env))
        .sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
}

// ---------------------------------------------------------------------------
// Base: every panel shares the loader through this component
// ---------------------------------------------------------------------------
class WsClientPanel extends Component {
    static props = {
        ...standardWidgetProps,
        mode: { type: String, optional: true },
    };

    setup() {
        this.profile = useState({ data: null, resId: null });
        this._key = null;
        this.bus = useState(bus); // subscribe: an invalidation re-renders every panel
        // runs inside every render, so a reloaded record (new write_date) or a
        // different record re-keys the panel; the loader shares the call
        onWillRender(() => this.refresh(this.props));
    }

    get data() {
        return this.props.record.data;
    }

    get resId() {
        return this.props.record.resId;
    }

    get loaded() {
        return this.profile.data !== null && this.profile.resId === this.resId;
    }

    get stats() {
        return (this.profile.data && this.profile.data.stats) || {};
    }

    refresh(props) {
        const record = props.record;
        const resId = record.resId;
        if (!resId) {
            this._key = null;
            return;
        }
        void this.bus.version;
        const key = profileKey(record);
        if (key === this._key) {
            return;
        }
        this._key = key;
        loadClientProfile(this.env.services.orm, record).then((data) => {
            if (this._key === key) {
                this.profile.data = data;
                this.profile.resId = resId;
            }
        });
    }

    get reloadCtx() {
        return {
            record: this.props.record,
            reload: async () => {
                await this.props.record.load();
                invalidateClientProfile(this.resId);
            },
        };
    }

    runShortcut(key) {
        const entry = shortcutEntries(this.env).find((e) => e.key === key);
        if (entry) {
            return entry.run(this.env, this.resId, this.reloadCtx);
        }
    }

    hasShortcut(key) {
        return shortcutEntries(this.env).some((e) => e.key === key);
    }

    newBooking() {
        return runPartnerMethod(this.env, this.resId, "action_open_quick_booking_owl");
    }
}

// ---------------------------------------------------------------------------
// At a glance / People (client row) / Needs attention
// ---------------------------------------------------------------------------
export class WsClientGlance extends WsClientPanel {
    static template = "health_fieldservice.WsClientGlance";

    setup() {
        super.setup();
        this.root = useRef("root");
        // the hero's address fact is one line with an ellipsis: give it its
        // full text as a tooltip (a view arch cannot bind a title attribute)
        onMounted(() => this.titleAddress());
        onPatched(() => this.titleAddress());
    }

    titleAddress() {
        if (this.props.mode !== "glance") {
            return;
        }
        const form = this.root.el?.closest(".o_form_renderer");
        const fact = form && form.querySelector(".ws-fact--address");
        if (fact) {
            const text = (fact.textContent || "").trim();
            if (fact.getAttribute("title") !== text) {
                fact.setAttribute("title", text);
            }
        }
    }

    get mode() {
        return this.props.mode || "glance";
    }

    get rows() {
        const s = this.stats;
        const d = this.profile.data || {};
        const rows = [];
        const now = DateTime.local();

        const visits = Number(s.total_visits) || 0;
        rows.push({ key: "visits", label: _t("Visits"), value: String(visits), cls: visits ? "" : "is-quiet" });

        const last = d.last_visit ? parseUtc(d.last_visit.scheduled_datetime) : null;
        rows.push({
            key: "last",
            label: _t("Last visit"),
            value: last ? relativeDay(dayDiff(last, now)) : _t("None yet"),
            cls: last ? "" : "is-quiet",
        });

        const next = d.next_visit ? parseUtc(d.next_visit.scheduled_datetime) : null;
        rows.push({
            key: "next",
            label: _t("Next visit"),
            value: next ? relativeDay(dayDiff(next, now)) + " · " + next.toFormat("HH:mm") : _t("None booked"),
            cls: next ? "" : "is-quiet",
        });

        const since = this.data.registration_date;
        rows.push({
            key: "since",
            label: _t("Client since"),
            value: since && since.toFormat ? since.toFormat("LLL yyyy") : "—",
            cls: since ? "" : "is-quiet",
        });

        const spent = Number(s.total_spent) || 0;
        rows.push({ key: "spent", label: _t("Spent"), value: money(spent, this.props.record), cls: spent ? "" : "is-quiet" });

        const owed = Number(s.outstanding) || 0;
        if (owed > 0) {
            rows.push({ key: "outstanding", label: _t("Outstanding"), value: money(owed, this.props.record), cls: "is-bad" });
        }

        const packages = Number(s.active_packages) || 0;
        rows.push({ key: "packages", label: _t("Packages"), value: String(packages), cls: packages ? "" : "is-quiet" });

        const referrals = Number(s.referrals) || 0;
        rows.push({ key: "referrals", label: _t("Referrals"), value: String(referrals), cls: referrals ? "" : "is-quiet" });
        return rows;
    }

    get alerts() {
        const alerts = [];
        const allergies = (this.data.allergies || "").trim();
        if (allergies) {
            const short = allergies.length > 80 ? allergies.slice(0, 79) + "…" : allergies;
            alerts.push({ key: "allergies", tone: "bad", text: _t("Has allergies: %s", short) });
        }
        const expiry = this.data.insurance_expiry;
        if (expiry && expiry.startOf && expiry < DateTime.local().startOf("day")) {
            alerts.push({
                key: "insurance",
                tone: "warn",
                text: _t("Insurance expired on %s.", expiry.toFormat("d LLL yyyy")),
            });
        }
        const owed = Number(this.stats.outstanding) || 0;
        if (this.loaded && owed > 0) {
            alerts.push({ key: "owed", tone: "bad", text: _t("%s is unpaid.", money(owed, this.props.record)) });
        }
        if (!recordPhone(this.data)) {
            alerts.push({ key: "phone", tone: "warn", text: _t("No phone number.") });
        }
        return alerts;
    }

    get contact() {
        const phone = recordPhone(this.data);
        const email = (this.data.email || "").trim();
        return {
            name: this.data.name || "",
            phone,
            email,
            tel: phone ? "tel:" + phone.replace(/\s+/g, "") : "",
            sms: phone ? "sms:" + phone.replace(/\s+/g, "") : "",
            mail: email ? "mailto:" + email : "",
        };
    }
}

export const wsClientGlance = {
    component: WsClientGlance,
    extractProps: ({ attrs }) => ({ mode: attrs.mode || "glance" }),
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_client_glance", wsClientGlance);

// ---------------------------------------------------------------------------
// Next step
// ---------------------------------------------------------------------------
export class WsClientNext extends WsClientPanel {
    static template = "health_fieldservice.WsClientNext";

    /** First matching rule wins (handover §3). */
    get card() {
        if (!this.resId || !this.loaded) {
            return null;
        }
        const d = this.profile.data || {};
        const owed = Number(this.stats.outstanding) || 0;
        const active = (this.data.patient_status || "active") === "active";
        const newBooking = { key: "new", label: _t("New booking"), primary: true, run: () => this.newBooking() };

        if (owed > 0) {
            const buttons = [];
            if (this.hasShortcut("invoices")) {
                buttons.push({ key: "invoices", label: _t("View invoices"), primary: true, run: () => this.runShortcut("invoices") });
            }
            return {
                kind: "money",
                title: _t("%s is unpaid.", money(owed, this.props.record)),
                hint: _t("Across past visits."),
                buttons,
            };
        }
        if (!d.next_visit && active) {
            const last = d.last_visit ? parseUtc(d.last_visit.scheduled_datetime) : null;
            return {
                kind: "calendar",
                title: _t("No visit is booked."),
                hint: last ? _t("Last visit %s.", relativeDay(dayDiff(last, DateTime.local())).toLowerCase()) : _t("No visits yet."),
                buttons: [newBooking],
            };
        }
        if (d.next_visit) {
            const next = parseUtc(d.next_visit.scheduled_datetime);
            const bookingId = d.next_visit.id;
            return {
                kind: "calendar",
                title: _t("Next visit %s.", visitDateText(next)),
                hint: d.next_visit.name || "",
                buttons: [
                    { key: "open", label: _t("Open booking"), primary: true, run: () => openBooking(this.env, bookingId) },
                    { ...newBooking, primary: false },
                ],
            };
        }
        return {
            kind: "user",
            title: _t("This client is inactive."),
            hint: "",
            buttons: [newBooking],
        };
    }
}

export const wsClientNext = {
    component: WsClientNext,
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_client_next", wsClientNext);

// ---------------------------------------------------------------------------
// Recent visits
// ---------------------------------------------------------------------------
const STATE_TONE = {
    draft: "muted",
    confirmed: "primary",
    assigned: "ok",
    in_progress: "warn",
    completed: "ok",
    completed_pending_invoice: "ok",
    closed: "ok",
    cancelled: "danger",
};

export class WsClientVisits extends WsClientPanel {
    static template = "health_fieldservice.WsClientVisits";

    setup() {
        super.setup();
        this.root = useRef("root");
    }

    get visits() {
        const list = (this.profile.data && this.profile.data.recent_visits) || [];
        return list.map((v) => {
            const dt = parseUtc(v.scheduled_datetime);
            return {
                id: v.id,
                name: v.name,
                // the locale's own short day + month ("3 Apr", "3 thg 4")
                date: dt ? dt.toLocaleString({ day: "numeric", month: "short" }) : "—",
                service: v.service_type_label || "",
                state: v.state_label || "",
                tone: STATE_TONE[v.state] || "muted",
            };
        });
    }

    open(visit) {
        return openBooking(this.env, visit.id);
    }

    allBookings() {
        const form = this.root.el?.closest(".o_form_renderer");
        const tab = form && form.querySelector('.o_notebook_headers a.nav-link[name="bookings_journey"]');
        if (tab) {
            tab.click();
            tab.scrollIntoView({ block: "nearest", behavior: "smooth" });
            return;
        }
        return runPartnerMethod(this.env, this.resId, "action_view_fso_orders");
    }
}

export const wsClientVisits = {
    component: WsClientVisits,
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_client_visits", wsClientVisits);

// ---------------------------------------------------------------------------
// Shortcuts
// ---------------------------------------------------------------------------
export class WsClientShortcuts extends WsClientPanel {
    static template = "health_fieldservice.WsClientShortcuts";

    // Call / Message / Email come first (from the record itself); then the
    // registered shortcuts. "New booking" is the header's own button, so it
    // is not repeated here.
    get entries() {
        const c = this.contact;
        const own = [
            c.tel && { key: "call", label: _t("Call"), icon: "phone", href: c.tel },
            c.sms && { key: "sms", label: _t("Message"), icon: "message-square", href: c.sms },
            c.mail && { key: "mail", label: _t("Email"), icon: "mail", href: c.mail },
        ].filter(Boolean);
        return own.concat(shortcutEntries(this.env).filter((e) => e.key !== "new_booking"));
    }

    get contact() {
        const phone = recordPhone(this.data);
        const email = (this.data.email || "").trim();
        return {
            tel: phone ? "tel:" + phone.replace(/\s+/g, "") : "",
            sms: phone ? "sms:" + phone.replace(/\s+/g, "") : "",
            mail: email ? "mailto:" + email : "",
        };
    }

    run(entry) {
        return entry.run(this.env, this.resId, this.reloadCtx);
    }
}

export const wsClientShortcuts = {
    component: WsClientShortcuts,
    fieldDependencies: RECORD_DEPENDENCIES,
};
registry.category("view_widgets").add("ws_client_shortcuts", wsClientShortcuts);

// health_fieldservice's own entries (the booking side of the old sidebar)
shortcutRegistry.add("new_booking", {
    key: "new_booking",
    label: _t("New booking"),
    icon: "calendar-plus",
    sequence: 10,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_open_quick_booking_owl"),
});
shortcutRegistry.add("recurring", {
    key: "recurring",
    label: _t("Recurring booking"),
    icon: "repeat",
    sequence: 20,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_open_recurring_booking"),
});
shortcutRegistry.add("bookings", {
    key: "bookings",
    label: _t("All bookings"),
    icon: "list",
    sequence: 30,
    run: (env, partnerId) => runPartnerMethod(env, partnerId, "action_view_fso_orders"),
});
