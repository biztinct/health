/** @odoo-module */
// =============================================================================
// ws_compact_bar — Workspace kit: a slim bar that stays at the top of the
// screen once the big identity block (.ws-hero) has scrolled away.
// -----------------------------------------------------------------------------
// Usage (FIRST child of .ws-main):
//   <widget name="ws_compact_bar"
//           title_fields="name,patient_id"
//           badge_field="state"
//           badge_tones="draft:muted,confirmed:primary,cancelled:danger"
//           fact_fields="scheduled_datetime"/>
//
// Contract:
//  1. Shows the record's title (the listed fields joined with " · "), one
//     status chip (the selection label of `badge_field`, tone from
//     `badge_tones`, default muted) and the listed facts. Fields missing from
//     the record or empty are skipped. Nothing here is a new server read.
//  2. Carries the screen's own Next step button: it mirrors the label of the
//     first `.ws-next .vu-action-btn--primary` in the same form and a click
//     clicks THAT button — so what it does, and when it shows, stays exactly
//     what the arch / the Next step widget already decide. No button → none.
//  3. Shown only while the hero is out of view (IntersectionObserver on the
//     form's own .ws-hero; the scroll box is the observer's root). It is
//     overlaid (zero-height sticky host), so showing it never moves the page.
//  4. Clicking the title scrolls back to the top.
//  5. Publishes its height on the form root as --ws-cbar-h while shown, so the
//     tab strip can stick right under it (ws_workspace.scss §11) — only when
//     the strip is one row (`ws-cbar-tabs`); a wrapped strip scrolls away.
// Product-agnostic: it knows fields, the hero and the Next step banner.
// =============================================================================

import { Component, onMounted, onPatched, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatDateTime, formatDate, formatMany2one, formatSelection } from "@web/views/fields/formatters";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

// the tallest tab strip that is still one row (a row is ~36px)
const TAB_ROW_MAX = 56;

function splitList(value) {
    return (value || "").split(",").map((part) => part.trim()).filter(Boolean);
}

function parseTones(value) {
    const out = {};
    for (const pair of splitList(value)) {
        const [key, tone] = pair.split(":").map((part) => part.trim());
        if (key && tone) {
            out[key] = tone;
        }
    }
    return out;
}

function scrollParent(el) {
    let node = el && el.parentElement;
    while (node && node !== document.body) {
        const overflow = getComputedStyle(node).overflowY;
        if (overflow === "auto" || overflow === "scroll") {
            return node;
        }
        node = node.parentElement;
    }
    return null;
}

export class WsCompactBar extends Component {
    static template = "health_theme.WsCompactBar";
    static props = {
        ...standardWidgetProps,
        titleFields: { type: String, optional: true },
        badgeField: { type: String, optional: true },
        badgeTones: { type: String, optional: true },
        factFields: { type: String, optional: true },
    };

    setup() {
        this.root = useRef("root");
        this.inner = useRef("inner");
        this.state = useState({ shown: false, action: "" });
        onMounted(() => {
            this.observe();
            this.watchNext();
        });
        onPatched(() => this.readAction());
        onWillUnmount(() => {
            this.io?.disconnect();
            this.mo?.disconnect();
            this.setHeight(false);
        });
    }

    // ── record values ──────────────────────────────────────────────────────
    format(name) {
        const { record } = this.props;
        const field = record.fields[name];
        const value = record.data[name];
        if (!field || value === false || value === null || value === undefined || value === "") {
            return "";
        }
        switch (field.type) {
            case "many2one":
                return formatMany2one(value);
            case "selection":
                return formatSelection(value, { field });
            case "datetime":
                return formatDateTime(value, { showSeconds: false });
            case "date":
                return formatDate(value);
            default:
                return typeof value === "object" ? "" : String(value);
        }
    }

    get title() {
        return splitList(this.props.titleFields || "display_name")
            .map((name) => this.format(name))
            .filter(Boolean)
            .join(" · ");
    }

    get badge() {
        const name = this.props.badgeField;
        if (!name || !(name in this.props.record.fields)) {
            return null;
        }
        const text = this.format(name);
        if (!text) {
            return null;
        }
        const tone = parseTones(this.props.badgeTones)[this.props.record.data[name]] || "muted";
        return { text, tone };
    }

    get facts() {
        return splitList(this.props.factFields)
            .map((name) => ({ name, text: this.format(name) }))
            .filter((fact) => fact.text);
    }

    // ── DOM wiring (inside this widget's own form only) ───────────────────
    get form() {
        return this.root.el?.closest(".o_form_renderer") || null;
    }

    nextButton() {
        return this.form?.querySelector(".ws-next .vu-action-btn--primary") || null;
    }

    readAction() {
        const btn = this.nextButton();
        const label = btn && !btn.disabled ? btn.textContent.replace(/\s+/g, " ").trim() : "";
        if (label !== this.state.action) {
            this.state.action = label;
        }
    }

    watchNext() {
        const next = this.form?.querySelector(".ws-next");
        this.readAction();
        if (next) {
            this.mo = new MutationObserver(() => this.readAction());
            this.mo.observe(next, { childList: true, subtree: true, characterData: true });
        }
    }

    observe() {
        const hero = this.form?.querySelector(".ws-hero");
        if (!hero || !window.IntersectionObserver) {
            return;
        }
        this.io = new IntersectionObserver(
            ([entry]) => {
                const shown = !entry.isIntersecting && entry.boundingClientRect.top < (entry.rootBounds?.top ?? 0);
                if (shown !== this.state.shown) {
                    this.state.shown = shown;
                    this.readAction();
                }
                this.setHeight(shown);
            },
            { root: scrollParent(hero), threshold: 0 }
        );
        this.io.observe(hero);
    }

    setHeight(shown) {
        const host = this.root.el?.closest(".o_form_view");
        if (!host) {
            return;
        }
        if (shown) {
            // the bar's height is fixed by CSS; read it once it is laid out
            requestAnimationFrame(() => {
                const h = this.inner.el?.offsetHeight || 0;
                host.style.setProperty("--ws-cbar-h", `${h}px`);
                // tabs stick only while they fit on one row: three rows of
                // tabs (the client screen's 18) under the bar would eat a
                // quarter of the screen
                const tabs = this.form?.querySelector(".ws-main .o_notebook_headers");
                host.classList.toggle("ws-cbar-tabs", !!tabs && tabs.offsetHeight <= TAB_ROW_MAX);
            });
            host.classList.add("ws-cbar-on");
        } else {
            host.style.removeProperty("--ws-cbar-h");
            host.classList.remove("ws-cbar-on", "ws-cbar-tabs");
        }
    }

    // ── actions ────────────────────────────────────────────────────────────
    onAction() {
        this.nextButton()?.click();
    }

    toTop() {
        const hero = this.form?.querySelector(".ws-hero");
        const box = scrollParent(hero);
        if (box) {
            box.scrollTo({ top: 0, behavior: "smooth" });
        }
    }
}

export const wsCompactBar = {
    component: WsCompactBar,
    extractProps: ({ attrs }) => ({
        titleFields: attrs.title_fields,
        badgeField: attrs.badge_field,
        badgeTones: attrs.badge_tones,
        factFields: attrs.fact_fields,
    }),
};

registry.category("view_widgets").add("ws_compact_bar", wsCompactBar);
