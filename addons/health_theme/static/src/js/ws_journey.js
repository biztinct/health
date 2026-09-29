/** @odoo-module */
// =============================================================================
// ws_journey — Workspace kit: a segmented journey bar with stage dates.
// -----------------------------------------------------------------------------
// Usage (any form that opts into the Workspace kit):
//   <widget name="ws_journey"
//           steps="draft,confirmed,assigned,in_progress,completed,closed"
//           labels="Created,Confirmed,Assigned,In progress,Completed,Closed"
//           date_fields="create_date,confirmation_date,assignment_date,,,"
//           aliases="completed_pending_invoice:completed"/>
//
// - `labels` are English source strings, translated with _t at render (the
//   catalogue carries them as code terms of this module).
// - `date_fields` runs parallel to `steps`; an empty entry = no date for it.
// - `aliases` maps states that have no segment of their own onto one that does
//   (any number of `from:to` pairs, comma-separated — several states may map to
//   the same step, e.g. "thinking:lead,recontact:lead,service_used:existing")
//   (vu_progress_rail's bug: `completed_pending_invoice` matched no step, so
//   every step read "done" — never copy that).
// - `cancelled` is not a step: every segment greys and a chip says so.
// - `terminal` (optional, comma states) names the states that end the journey
//   off the path (a contact marked spam, a cancelled booking-to-be). They
//   render like `cancelled` — every segment grey — and the chip reads that
//   state's own selection label. Without `terminal` the widget behaves exactly
//   as before (`cancelled` only, chip text "Cancelled").
// Product-agnostic on purpose: it knows nothing about bookings.
// =============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

function splitList(value) {
    return (value || "").split(",").map((part) => part.trim());
}

function parseAliases(value) {
    const out = {};
    for (const pair of splitList(value)) {
        if (!pair) {
            continue;
        }
        const [from, to] = pair.split(":").map((part) => (part || "").trim());
        if (from && to) {
            out[from] = to;
        }
    }
    return out;
}

export class WsJourney extends Component {
    static template = "health_theme.WsJourney";
    static props = {
        ...standardWidgetProps,
        steps: { type: String, optional: true },
        labels: { type: String, optional: true },
        dateFields: { type: String, optional: true },
        stateField: { type: String, optional: true },
        aliases: { type: String, optional: true },
        terminal: { type: String, optional: true },
    };

    get stateField() {
        return this.props.stateField || "state";
    }

    get rawState() {
        return this.props.record.data[this.stateField] || "";
    }

    /** The default stop (no `terminal` attr): a cancelled record. */
    get isCancelled() {
        return !this.props.terminal && this.rawState === "cancelled";
    }

    /** A state listed in `terminal`: its selection label, or "" when the
     *  record is not in one. */
    get terminalLabel() {
        if (!this.props.terminal) {
            return "";
        }
        const state = this.rawState;
        if (!state || !splitList(this.props.terminal).includes(state)) {
            return "";
        }
        const field = this.props.record.fields[this.stateField];
        const pair = ((field && field.selection) || []).find(([value]) => value === state);
        return (pair && pair[1]) || state;
    }

    /** Off the path: every segment grey, a chip instead of the step count. */
    get isStopped() {
        return this.isCancelled || Boolean(this.terminalLabel);
    }

    get currentState() {
        const aliases = parseAliases(this.props.aliases);
        return aliases[this.rawState] || this.rawState;
    }

    formatDate(value) {
        if (!value || !value.toLocaleString) {
            return "";
        }
        return value.toLocaleString({ month: "short", day: "numeric" });
    }

    get segments() {
        const steps = splitList(this.props.steps).filter(Boolean);
        const labels = splitList(this.props.labels);
        const dateFields = splitList(this.props.dateFields);
        const data = this.props.record.data;
        const currentIndex = steps.indexOf(this.currentState);
        const cancelled = this.isStopped;
        return steps.map((state, index) => {
            let status = "future";
            if (!cancelled && currentIndex >= 0) {
                if (index < currentIndex) {
                    status = "done";
                } else if (index === currentIndex) {
                    status = "current";
                }
            }
            const dateField = dateFields[index];
            let sub = "";
            if (dateField && data[dateField]) {
                sub = this.formatDate(data[dateField]);
            } else if (!cancelled && currentIndex >= 0 && index === currentIndex + 1) {
                sub = _t("Next");
            }
            return {
                key: state,
                label: _t(labels[index] || state),
                status,
                sub,
            };
        });
    }

    get stepText() {
        const steps = splitList(this.props.steps).filter(Boolean);
        const index = steps.indexOf(this.currentState);
        if (this.isStopped || index < 0) {
            return "";
        }
        return _t("Step %s of %s", index + 1, steps.length);
    }
}

export const wsJourney = {
    component: WsJourney,
    extractProps: ({ attrs }) => ({
        steps: attrs.steps,
        labels: attrs.labels,
        dateFields: attrs.date_fields,
        stateField: attrs.state_field,
        aliases: attrs.aliases,
        terminal: attrs.terminal,
    }),
    fieldDependencies: ({ attrs }) => {
        const deps = [{ name: attrs.state_field || "state", type: "selection" }];
        for (const name of splitList(attrs.date_fields)) {
            if (name) {
                deps.push({ name, type: "datetime" });
            }
        }
        return deps;
    },
};

registry.category("view_widgets").add("ws_journey", wsJourney);
