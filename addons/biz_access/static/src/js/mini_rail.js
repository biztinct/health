/** @odoo-module **/
/**
 * `BizMiniRail` — the left menu, drawn small, showing what somebody would see.
 *
 * WHY A MINIATURE AND NOT A LIST. "This role opens Records and People" is a
 * sentence somebody has to translate before they can check it. The left menu
 * drawn as the left menu is the thing they already look at forty times a day,
 * so a picture of it needs no translating at all — and the moment a tick box
 * lights a row up, the promise the dialog is making has been SHOWN rather than
 * described. That is the whole reason the Role Composer has a right-hand side.
 *
 * IT DECIDES NOTHING. Every state on every row — on, locked, hidden, and which
 * rows are newly lit — is worked out on the server by the same code that
 * answers for it afterwards (`biz.access._rail_states`). This component draws
 * what it is handed and nothing else. A second copy of the visibility rule
 * living in a browser is a copy that will one day disagree, and it would
 * disagree by promising somebody a screen they cannot open.
 *
 * IT IS A COMPONENT, NOT A LUMP OF MARKUP, BECAUSE IT IS USED TWICE. The
 * composer's preview is the first place; the person passport is the second.
 *
 * THE ICONS, AND THE THREE THINGS A LEFT MENU MIGHT STORE. The rail arrives
 * across a provider seam, so the icon on a row is whatever the PRODUCT keeps —
 * this module is not allowed to have an opinion about it. Three cases, in this
 * order:
 *
 *   1. a name this kit's `ic()` registry knows, directly or through the small
 *      alias map below (the hyphenated Lucide spellings a menu is likely to
 *      have stored);
 *   2. anything beginning `fa ` — a font class the product's own menu already
 *      draws with, rendered as exactly that;
 *   3. anything else — a plain dot, which is what the real menu does with a
 *      name it does not recognise.
 *
 * A miniature drawing a wrong-but-confident icon would be worse than one
 * drawing a dot, so there is no guessing anywhere in here.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic, IC } from "@biz_kit/js/kit_icons";

/** Left-menu icon name -> shared registry key. */
const RAIL_ICONS = {
    "home": "home",
    "calendar": "calendar",
    "clock": "clock",
    "receipt": "receipt",
    "zap": "zap",
    "download": "download",
    "users": "users",
    "user": "user",
    "file": "file",
    "file-text": "fileText",
    "calculator": "calculator",
    "layers": "layers",
    "shield": "shield",
    "percent": "percent",
    "trending-up": "trendingUp",
    "trending-down": "trendingDown",
    "clipboard-check": "checkCircle",
    "lock": "lock",
    "building": "building",
    "database": "database",
    "compass": "compass",
    "settings": "settings",
    "map-pin": "mapPin",
    "truck": "truck",
    "table": "table",
    "plane": "plane",
    "scan": "scan",
    "send": "send",
    "landmark": "landmark",
    "activity": "activity",
    "umbrella": "umbrella",
    "inbox": "inbox",
    "book-open": "bookOpen",
    "scroll-text": "scrollText",
    "refresh-cw": "refresh",
    "award": "award",
    "briefcase": "briefcase",
    "list": "list",
    "search": "search",
    "sparkles": "sparkles",
};

/** Does this row's icon belong to a font the product already loads? */
export function isFontIcon(name) {
    return /^fa\s/.test((name || "").trim());
}

/**
 * A left-menu icon, drawn.
 *
 * Never throws and never renders nothing: an icon that cannot be identified
 * becomes a dot, because a gap where a glyph should be reads as a broken screen
 * and a dot reads as "this row has no picture", which is the truth.
 */
export function railIcon(name, size = 14) {
    const raw = (name || "").trim();
    const key = RAIL_ICONS[raw] || (raw in IC ? raw : null);
    if (key) {
        return ic(key, size);
    }
    return ic("circle", size);
}

export class BizMiniRail extends Component {
    static template = "biz_access.MiniRail";
    static props = {
        sections: { type: Array },
        legend: { type: Boolean, optional: true },
        // FOLDED PARENTS (AR-2). On a person's passport a parent entry is
        // drawn folded with "3 of 5" on it — how many of the screens inside it
        // they can open — and unfolds into its sub-entries, each with its own
        // state. The builder's preview leaves this off and keeps every
        // sub-entry drawn, because there the point is to watch them light up.
        expandable: { type: Boolean, optional: true },
        // THE SHELL LAYOUT (MENU M2). The product's menu is drawn as a rail of
        // areas, a column of the chosen area's tabs, and the chosen tab's
        // screens as a strip — so the passport draws it the same way: press an
        // area, then a tab, and read what is inside. Read-only, like the rest.
        shell: { type: Boolean, optional: true },
    };
    static defaultProps = { legend: true, expandable: false, shell: false };

    setup() {
        this.state = useState({ open: {}, sec: null, tab: null });
    }

    // ------------------------------------------------------- shell layout
    /** An area is "on" when anything in it opens for them. */
    sectionState(sec) {
        const any = (sec.items || []).some((i) => i.state === "on"
            || (i.children || []).some((c) => c.state === "on"));
        return any ? "on" : "off";
    }

    /** A tab is "on" when it, or any screen inside it, opens for them. */
    tabState(item) {
        if ((item.children || []).length) {
            return item.children.some((c) => c.state === "on") ? "on"
                : (item.children.some((c) => c.state === "locked") ? "locked" : "off");
        }
        return item.state;
    }

    get activeSection() {
        const sections = this.props.sections || [];
        return sections.find((s) => (s.key || s.label) === this.state.sec)
            // Home is a door, not an area: start on the first real area
            // somebody opens something in.
            || sections.find((s) => s.key !== "home" && this.sectionState(s) === "on")
            || sections.find((s) => this.sectionState(s) === "on")
            || sections[0] || null;
    }

    get activeTab() {
        const sec = this.activeSection;
        const items = (sec && sec.items) || [];
        return items.find((i) => i.id === this.state.tab)
            || items.find((i) => this.tabState(i) === "on")
            || items[0] || null;
    }

    pickSection(sec) {
        this.state.sec = sec.key || sec.label;
        this.state.tab = null;
    }

    pickTab(item) {
        this.state.tab = item.id;
    }

    isActiveSection(sec) {
        const active = this.activeSection;
        return Boolean(active) && (active.key || active.label) === (sec.key || sec.label);
    }

    ic(n, s = 13) { return ic(n, s); }

    railIcon(name, s = 14) { return railIcon(name, s); }

    /** True when the row's icon is a font class the product already loads —
     *  the template draws an `<i>` for those and inline SVG for the rest. */
    isFontIcon(name) { return isFontIcon(name); }

    /** ONE expression per sentence, so the spaces survive (R34). */
    title(item) {
        if (item.state === "on") { return _t("They can open this."); }
        if (item.state === "locked") {
            return _t("They see this, locked, with a note about what it is.");
        }
        return _t("This is not on their menu at all.");
    }

    stateIcon(item) {
        if (item.state === "on") { return ic("check", 12); }
        if (item.state === "locked") { return ic("lock", 12); }
        return ic("eyeOff", 12);
    }

    /**
     * Is anything on this miniature drawn locked? The legend explains only
     * what is on the picture: a menu that shows or hides and never teases
     * (AR-2) has no locked entry, and a key for one would describe a state
     * nobody can ever see.
     */
    get hasLocked() {
        return (this.props.sections || []).some((s) => (s.items || []).some(
            (i) => i.state === "locked"
                || (i.children || []).some((c) => c.state === "locked")));
    }

    canExpand(item) {
        return this.props.expandable && (item.children || []).length > 0;
    }

    isOpen(item) {
        return !this.props.expandable || Boolean(this.state.open[item.id]);
    }

    toggle(item) {
        if (!this.canExpand(item)) { return; }
        this.state.open[item.id] = !this.state.open[item.id];
    }

    /** Enter and Space unfold a parent, as they would any button. */
    onKey(ev, item) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.toggle(item);
        }
    }

    /**
     * "3 of 5" — how many of the screens inside a parent they can open.
     *
     * The server counts it (`kids_on` / `kids_total`) off the same states the
     * sub-entries carry; the count below is only for a miniature that arrives
     * without one, and it counts the same thing.
     */
    childSummary(item) {
        const children = item.children || [];
        const on = item.kids_on !== undefined
            ? item.kids_on : children.filter((c) => c.state === "on").length;
        const total = item.kids_total !== undefined
            ? item.kids_total : children.length;
        return _t("%s of %s", on, total);
    }

    summaryTitle(item) {
        return _t("They can open %s screens inside this. Press to see which.",
                  this.childSummary(item));
    }
}
