/** @odoo-module */
// =============================================================================
// ws_fold_tray — Workspace kit: cards whose fields are ALL empty fold away
// into one "Not filled yet" line of chips; a chip opens its card again.
// -----------------------------------------------------------------------------
// Usage (placed in the same container as the cards it governs):
//   <widget name="ws_fold_tray"
//           options="{'cards': {'care_team_card': ['assigned_staff_ids', …], …}}"/>
//
// Contract:
//  1. A card is EMPTY when every listed field is empty: false/null/'',
//     numeric/monetary 0, x2many with no rows, many2one unset.
//  2. Empty cards get `ws-card--folded` (display: none). Cards are found by
//     `[name="<key>"]` inside the widget's OWN form renderer — never document.
//  3. One chip per folded card: its title (read from the card's
//     `.vu-card__title`, already translated) and "N fields". A click unfolds
//     that card for this record for the rest of the page's life, scrolls it
//     into view and focuses its first input.
//  4. A card that has held a value on this page stays open even if it is
//     emptied again, and a card never hides an invalid field.
//  5. Nothing folded → the tray draws nothing.
//  6. Re-evaluated on every mount and patch, idempotently (classes are only
//     toggled when they change).
//  7. Cards it was not told about are DISCOVERED from the page: any element
//     of the same tab marked `data-fs-fold="1"` with a `name` is a card the
//     tray governs, its fields read from `data-fs-fields="a,b"` (fallback:
//     the field widgets inside it). An element with `data-fs-fields` and no
//     `data-fs-fold` is a configured card that received more fields: those
//     are added to its list, so it never folds while one of them holds a
//     value. (Written by a form layout tool; costs one frame on first mount.)
//     A discovered card with no field this person can read stays folded and
//     draws no chip.
// Product-agnostic: it knows cards, fields and names — nothing else.
// =============================================================================

import { Component, onMounted, onPatched, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const FOLDED = "ws-card--folded";

export function isEmptyValue(value, type) {
    if (value === false || value === null || value === undefined) {
        return true;
    }
    if (type === "one2many" || type === "many2many") {
        const count = value.count ?? value.records?.length ?? value.currentIds?.length ?? 0;
        return count === 0;
    }
    if (type === "many2one" || type === "many2one_reference") {
        return !(value && (value.id || typeof value === "number"));
    }
    if (typeof value === "number") {
        return value === 0;
    }
    if (typeof value === "string") {
        return value.trim() === "";
    }
    return false;
}

export class WsFoldTray extends Component {
    static template = "health_theme.WsFoldTray";
    static props = {
        ...standardWidgetProps,
        cards: { type: Object, optional: true },
    };

    setup() {
        this.root = useRef("root");
        // per-record memory: cards opened by a chip, or seen holding a value
        this.opened = useState({});
        this.seen = new Map();
        this.state = useState({ titles: {} });
        // cards found on the page (contract 7): {cards: {name: [fields]},
        // extra: {configured card: [more fields]}}
        this.discovered = useState({ cards: {}, extra: {} });
        onMounted(() => this.sync());
        onPatched(() => this.sync());
    }

    get cards() {
        const out = {};
        const extra = this.discovered.extra;
        for (const [cardName, fieldNames] of Object.entries(this.props.cards || {})) {
            const more = (extra[cardName] || []).filter((name) => !fieldNames.includes(name));
            out[cardName] = more.length ? fieldNames.concat(more) : fieldNames;
        }
        for (const [cardName, fieldNames] of Object.entries(this.discovered.cards)) {
            if (!(cardName in out)) {
                out[cardName] = fieldNames;
            }
        }
        return out;
    }

    get recordKey() {
        return String(this.props.record.resId || "new");
    }

    _seenSet() {
        const key = this.recordKey;
        if (!this.seen.has(key)) {
            this.seen.set(key, new Set());
        }
        return this.seen.get(key);
    }

    isOpened(cardName) {
        return Boolean(this.opened[`${this.recordKey}:${cardName}`]);
    }

    cardIsEmpty(fieldNames) {
        const record = this.props.record;
        return fieldNames.every((name) => {
            if (!(name in record.fields)) {
                return true; // a field this database does not have holds nothing
            }
            if (record.isFieldInvalid && record.isFieldInvalid(name)) {
                return false; // never hide an invalid field
            }
            return isEmptyValue(record.data[name], record.fields[name].type);
        });
    }

    /** Card names to fold right now. Reads record data, so the tray re-renders
     *  whenever any governed field changes. */
    get foldedNames() {
        const seen = this._seenSet();
        const out = [];
        for (const [cardName, fieldNames] of Object.entries(this.cards)) {
            if (this.isOpened(cardName) || seen.has(cardName)) {
                continue;
            }
            if (this.cardIsEmpty(fieldNames || [])) {
                out.push(cardName);
            } else {
                seen.add(cardName);
            }
        }
        return out;
    }

    get chips() {
        // a discovered card with no readable field folds without a chip
        return this.foldedNames.filter((cardName) => (this.cards[cardName] || []).length).map((cardName) => {
            const count = (this.cards[cardName] || []).length;
            return {
                name: cardName,
                title: this.state.titles[cardName] || "",
                fields: count === 1 ? _t("1 field") : _t("%s fields", count),
            };
        });
    }

    get formRoot() {
        return this.root.el?.closest(".o_form_renderer") || null;
    }

    cardEl(cardName) {
        const form = this.formRoot;
        return form ? form.querySelector(`[name="${cardName}"]`) : null;
    }

    _fieldList(el) {
        const listed = (el.getAttribute("data-fs-fields") || "")
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean);
        const names = listed.length
            ? listed
            : [...el.querySelectorAll(".o_field_widget[name]")].map((w) => w.getAttribute("name"));
        // only fields this person's record holds: one they may not read is
        // not on the page, so it can neither fill the card nor be counted
        const fields = this.props.record.fields;
        return names.filter((name) => name in fields);
    }

    /** Contract 7. Writes `discovered` only when what is on the page changed,
     *  so the re-render it causes finds nothing new and stops. */
    discover() {
        const scope = this.root.el?.closest(".tab-pane") || this.formRoot;
        if (!scope) {
            return;
        }
        const cards = {};
        const extra = {};
        for (const el of scope.querySelectorAll('[data-fs-fold="1"][name]')) {
            cards[el.getAttribute("name")] = this._fieldList(el);
        }
        for (const el of scope.querySelectorAll("[data-fs-fields]:not([data-fs-fold])")) {
            const cardName = el.getAttribute("name");
            if (cardName) {
                extra[cardName] = this._fieldList(el);
            }
        }
        if (JSON.stringify(cards) !== JSON.stringify(this.discovered.cards)) {
            this.discovered.cards = cards;
        }
        if (JSON.stringify(extra) !== JSON.stringify(this.discovered.extra)) {
            this.discovered.extra = extra;
        }
    }

    sync() {
        this.discover();
        const folded = new Set(this.foldedNames);
        const titles = {};
        let titlesChanged = false;
        for (const cardName of Object.keys(this.cards)) {
            const el = this.cardEl(cardName);
            if (!el) {
                continue;
            }
            const shouldFold = folded.has(cardName);
            if (el.classList.contains(FOLDED) !== shouldFold) {
                el.classList.toggle(FOLDED, shouldFold);
            }
            const title = (el.querySelector(".vu-card__title")?.textContent || "").trim();
            titles[cardName] = title;
            if (this.state.titles[cardName] !== title) {
                titlesChanged = true;
            }
        }
        if (titlesChanged) {
            this.state.titles = titles;
        }
    }

    onChipClick(cardName) {
        this.opened[`${this.recordKey}:${cardName}`] = true;
        const el = this.cardEl(cardName);
        if (!el) {
            return;
        }
        el.classList.remove(FOLDED);
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        const input = el.querySelector(
            "input:not([type=hidden]):not([disabled]):not([readonly]), textarea:not([disabled]):not([readonly]), select:not([disabled]), button.o_input"
        );
        if (input) {
            input.focus({ preventScroll: true });
        }
    }
}

export const wsFoldTray = {
    component: WsFoldTray,
    // No fieldDependencies: every governed field lives inside the card it
    // governs, so the arch already loads it.
    extractProps: ({ options }) => ({
        cards: options.cards || {},
    }),
};

registry.category("view_widgets").add("ws_fold_tray", wsFoldTray);
