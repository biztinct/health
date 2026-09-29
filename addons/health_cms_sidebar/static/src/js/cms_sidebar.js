/** @odoo-module **/

/**
 * THE MENU SHELL (MENU M1) — rail ⇄ drawer, tab column, page header.
 *
 * WHAT CHANGED AND WHAT DID NOT. This component used to draw the whole menu as
 * one tall list. It now draws the SAME data in three pieces, Payobook-style:
 *
 *   * the RAIL — one entry per section (`section.icon`), 60px wide, widening
 *     over the page on hover, or pinned open as a 240px drawer with «;
 *   * the TAB COLUMN — the root items of the section on screen;
 *   * the PAGE HEADER — the catchment pill, "Section › Tab › Segment", and the
 *     SEGMENT STRIP: the children of the tab on screen.
 *
 * Nothing about what is IN the menu changed: `get_sidebar_data` is read
 * exactly as before, every entry opens exactly the action it always opened
 * (catchment domain included), and "a parent never navigates" is still true —
 * a heading tab opens its first child and shows the rest as segments.
 *
 * ONE COMPONENT, SEVERAL ROOT NODES. The rail, the tab column and the page
 * header are siblings of `.o_action_manager` inside `.ops-layout-wrapper`
 * (health_fieldservice owns that wrapper and its `//ActionContainer` xpath),
 * which lays them out as a CSS grid. None of them is an ANCESTOR of the
 * action, so none of them can trap a form's inline dropdown (ledger §5.96).
 */

import { Component, useState, onMounted, onWillUnmount, onPatched, useExternalListener, useRef } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Domain } from "@web/core/domain";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

export const HOME_KEY = "home";
export const SETTINGS_KEY = "admin";
export const HOME_TAG = "cms_home";

const WIDE_QUERY = "(min-width: 1920px)";
const TABLET_QUERY = "(max-width: 1024px)";
const PHONE_QUERY = "(max-width: 768px)";
const RAIL_MODES = ["auto", "rail", "drawer"];

const SYNTHETIC_HOME = {
    id: "home",
    key: HOME_KEY,
    name: _t("Home"),
    icon: "fa fa-home",
    items: [{ id: "home", name: _t("Home"), icon: "fa fa-home", action_tag: HOME_TAG, children: [] }],
};

// ---------------------------------------------------------------------------
// Per-person memory. EVERY key carries the real user id (`user.userId`).
// The session info carries no uid in this build, so the old fold
// memory fell back to 0 and every account on a browser shared one key.
// ---------------------------------------------------------------------------
export function railModeKey(uid) {
    return `vu.rail.mode.${uid || "anon"}`;
}
export function tabKey(uid, sectionKey) {
    return `vu.tab.${uid || "anon"}.${sectionKey}`;
}
function readStore(key) {
    try {
        return browser.localStorage.getItem(key);
    } catch {
        return null;
    }
}
function writeStore(key, value) {
    try {
        browser.localStorage.setItem(key, value);
    } catch {
        // private mode — the choice just is not remembered
    }
}

/**
 * The rail's words for a section name, WITHOUT changing the data.
 *
 * The sections are stored in capitals ("OPERATIONS MANAGER", "INTEROP &
 * COMPLIANCE"), which read as shouting on a rail. CSS cannot title-case text
 * that is already in capitals without also turning "CRM" into "Crm", so it is
 * done here, for display only: a name written in mixed case is shown as
 * written; in an all-capitals name a short plain-letter word (CRM, EMR, VN) is
 * kept as it is and every other word is capitalised.
 */
export function railLabel(name) {
    const text = String(name || "");
    if (!text || text !== text.toUpperCase()) {
        return text;
    }
    return text
        .split(/(\s+)/)
        .map((word) => {
            if (!/\p{L}/u.test(word) || /^[A-Z]{1,3}$/.test(word)) {
                return word;
            }
            return word.charAt(0) + word.slice(1).toLowerCase();
        })
        .join("");
}

export class CmsSidebar extends Component {
    static template = "health_cms_sidebar.CmsSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.uid = user.userId;

        const name = user.name || window.odoo?.session_info?.name || "";
        this.currentUserName = name || _t("User");
        this.currentUserInitials = this.currentUserName
            .split(" ").filter(Boolean).map((p) => p[0]).join("").substring(0, 2).toUpperCase() || "U";

        const storedMode = readStore(railModeKey(this.uid));
        this.state = useState({
            sections: [],
            loaded: false,
            activeItemId: null,
            activeSectionKey: null,
            railMode: RAIL_MODES.includes(storedMode) ? storedMode : "auto",
            peek: false,
            sheetOpen: false,
            wide: false,
            tablet: false,
            phone: false,
            // Catchment scope. `pick` is the owner's chosen area — "" means
            // "my own area" (the default everyone starts on) and "all" means
            // no catchment filter at all, which only an owner can reach.
            catchment: { current_name: "", can_switch: false, options: [], mine_filter: "" },
            catchmentPick: "",
        });

        this._index = {};           // item id -> { item, sectionKey, rootId }
        this._ownTag = {};
        this._ownXmlid = {};
        this._tagIndex = {};
        this._xmlidIndex = {};
        this._modelIndex = {};
        this._tabXmlids = {};       // cms_tab xml-id -> item id (resolved lazily)

        this._loadCatchmentPick();
        this._forgetSharedFoldKey();
        this._watchViewport();

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveActiveItem());

        // RE-READ WHEN SOMEBODY CHANGES WHO SEES WHAT.
        //
        // The sidebar is read ONCE, on mount. That is right for a menu whose
        // gates only ever change in a settings screen somebody navigates away
        // from — and wrong the moment a screen elsewhere in the same page can
        // change them, because the rail two hundred pixels away would go on
        // showing the answer that screen has just changed.
        //
        // A BUS EVENT AND NOT AN IMPORT. Whatever edits a gate triggers this
        // name; this module knows nothing about it, has no dependency on it,
        // and behaves identically on a database where nothing ever fires it.
        useBus(this.env.bus, "CMS_SIDEBAR:RELOAD", async () => {
            await this._loadSidebarData();
            this._resolveActiveItem();
        });

        // On the DOCUMENT, in the CAPTURE phase: the web client's hotkey
        // service listens on the window and stops the event whenever a screen
        // has claimed the key (a search box claims Escape), so a window
        // listener never sees it. Only an open rail/sheet takes Escape, so the
        // search box keeps its own Escape the rest of the time.
        useExternalListener(document, "keydown", (ev) => this.onWindowKeydown(ev), { capture: true });

        this.tabcolRef = useRef("tabcol");
        onPatched(() => this._fitTabLabels());

        onMounted(async () => {
            await this._loadSidebarData();
            this._resolveActiveItem();
            this._fitTabLabels();
        });
        onWillUnmount(() => this._unwatchViewport());
    }

    // ------------------------------------------------------------------ data
    async _loadSidebarData() {
        const [data, scope] = await Promise.all([
            this.orm.call("cms.sidebar.item", "get_sidebar_data", []),
            this.orm.call("cms.sidebar.item", "get_catchment_scope", []),
        ]);
        this.state.sections = data;
        this.state.catchment = scope;
        if (!scope.can_switch) {
            // A scoped user has exactly one answer. Never let a stale
            // localStorage value from a previous account widen their view.
            this.state.catchmentPick = "";
        }
        this.state.loaded = true;
        this._buildMatchIndex();
    }

    /**
     * Four maps over the WHOLE visible tree, parents and children alike.
     *
     * Pass 0 — the entry whose OWN action this is (`action_tag` /
     * `action_xmlid`). A parent lists its children's actions in its `match_*`
     * so it can stay lit while one is open; without this pass opening Cash In
     * Transit lit AR Management instead of itself (ledger §5.150).
     * Pass 1 — the `match_*` tags and xml-ids. Pass 2 — the model, which is
     * last-wins and belongs to one primary surface per model (§5.94).
     */
    _buildMatchIndex() {
        this._index = {};
        this._ownTag = {};
        this._ownXmlid = {};
        this._tagIndex = {};
        this._xmlidIndex = {};
        this._modelIndex = {};
        const indexOne = (item, sectionKey, rootId) => {
            this._index[item.id] = { item, sectionKey, rootId };
            if (item.action_tag) {
                this._ownTag[item.action_tag] = item.id;
            }
            if (item.action_xmlid) {
                this._ownXmlid[item.action_xmlid] = item.id;
            }
            for (const tag of item.match_action_tags || []) {
                if (tag) {
                    this._tagIndex[tag] = item.id;
                }
            }
            for (const xmlid of item.match_action_xmlids || []) {
                if (xmlid) {
                    this._xmlidIndex[xmlid] = item.id;
                }
            }
            for (const model of item.match_models || []) {
                if (model) {
                    this._modelIndex[model] = item.id;
                }
            }
        };
        for (const section of this.state.sections) {
            for (const item of section.items) {
                indexOne(item, section.key, item.id);
                for (const child of item.children || []) {
                    indexOne(child, section.key, item.id);
                }
            }
        }
    }

    _matchAction(action) {
        const tag = action.tag;
        const xmlId = action.xml_id;
        const model = action.res_model;
        const cmsTab = this._cmsTabOf(action);
        if (cmsTab && this._tabXmlids[cmsTab] && this._index[this._tabXmlids[cmsTab]]) {
            return this._tabXmlids[cmsTab];
        }
        if (tag && this._ownTag[tag] !== undefined) {
            return this._ownTag[tag];
        }
        if (xmlId && this._ownXmlid[xmlId] !== undefined) {
            return this._ownXmlid[xmlId];
        }
        if (tag && this._tagIndex[tag] !== undefined) {
            return this._tagIndex[tag];
        }
        if (xmlId && this._xmlidIndex[xmlId] !== undefined) {
            return this._xmlidIndex[xmlId];
        }
        if (model && this._modelIndex[model] !== undefined) {
            return this._modelIndex[model];
        }
        return undefined;
    }

    _cmsTabOf(action) {
        const ctx = action.context;
        const value = ctx && typeof ctx === "object" ? ctx.cms_tab : null;
        return typeof value === "string" && value ? value : null;
    }

    _resolveActiveItem() {
        const controller = this.actionService.currentController;
        if (!controller || !this.state.loaded) {
            return;
        }
        const action = controller.action || {};
        const cmsTab = this._cmsTabOf(action);
        if (cmsTab && !(cmsTab in this._tabXmlids)) {
            // The deep link names an entry by xml-id; ask once which row that
            // is (only rows this person's own menu draws are answered).
            this._tabXmlids[cmsTab] = false;
            this.orm.call("cms.sidebar.item", "item_id_for_xmlid", [cmsTab]).then((id) => {
                this._tabXmlids[cmsTab] = id || false;
                if (id) {
                    this._resolveActiveItem();
                }
            });
        }
        const found = this._matchAction(action);
        if (found === undefined) {
            // NOTHING ON THE MENU CLAIMS THIS SCREEN. Clear the highlight — a
            // lit entry for a screen that is not on display is a lie — but
            // keep the section, so the tab column does not blank under the
            // person's feet.
            this.state.activeItemId = null;
            return;
        }
        this._setActive(found);
    }

    _setActive(itemId) {
        const entry = this._index[itemId];
        this.state.activeItemId = itemId;
        if (!entry) {
            return;
        }
        if (entry.sectionKey !== HOME_KEY) {
            this.state.activeSectionKey = entry.sectionKey;
            writeStore(tabKey(this.uid, entry.sectionKey), String(entry.rootId));
        }
    }

    // ------------------------------------------------------------- the rail
    /** Home first, then every section by sequence, Settings (ADMIN) last. */
    get railEntries() {
        const sections = this.state.sections;
        // HOME IS NEVER HIDDEN. Should its row be missing or gated away, the
        // rail still draws it, opening the same client action.
        const home = sections.find((s) => s.key === HOME_KEY) || SYNTHETIC_HOME;
        const middle = sections.filter((s) => s.key !== HOME_KEY && s.key !== SETTINGS_KEY);
        const settings = sections.filter((s) => s.key === SETTINGS_KEY);
        return [home, ...middle, ...settings];
    }

    get mainEntries() {
        return this.railEntries.filter((s) => s.key !== SETTINGS_KEY);
    }

    get footEntries() {
        return this.railEntries.filter((s) => s.key === SETTINGS_KEY);
    }

    railNumber(section) {
        const index = this.railEntries.findIndex((s) => s.key === section.key);
        return index >= 0 && index < 9 ? index + 1 : null;
    }

    railTitle(section) {
        const number = this.railNumber(section);
        const label = railLabel(section.name);
        return number ? `${label} (Alt+${number})` : label;
    }

    railLabel(name) {
        return railLabel(name);
    }

    /** The « / » button's words (AR-3: one translatable string each, not an
     *  English ternary inside the template, which no catalogue can reach). */
    get railToggleLabel() {
        return this.isCollapsed ? _t("Keep the menu open") : _t("Show icons only");
    }

    /** "My area (Hà Nội)" as ONE sentence with the area in it. */
    get myAreaLabel() {
        return _t("My area (%s)", this.state.catchment.current_name || "");
    }

    isRailActive(section) {
        if (section.key === HOME_KEY) {
            return false;
        }
        return this.state.activeSectionKey === section.key;
    }

    /** Icons only (hover widens it) — or the pinned 240px drawer. */
    get isCollapsed() {
        if (this.state.phone || this.state.tablet) {
            return true;
        }
        const mode = this.state.railMode;
        return mode === "rail" || (mode === "auto" && !this.state.wide);
    }

    get railClass() {
        return {
            "vu-rail": true,
            "is-collapsed": this.isCollapsed,
            "is-drawer": !this.isCollapsed,
            "is-peek": this.isCollapsed && this.state.peek,
        };
    }

    get showLabels() {
        return !this.isCollapsed || this.state.peek;
    }

    toggleRail() {
        const next = this.isCollapsed ? "drawer" : "rail";
        this.state.railMode = next;
        this.state.peek = false;
        writeStore(railModeKey(this.uid), next);
    }

    onRailEnter() {
        if (this.isCollapsed && !this.state.phone) {
            this.state.peek = true;
        }
    }

    onRailLeave() {
        this.state.peek = false;
    }

    onRailFocusIn() {
        this.onRailEnter();
    }

    onRailFocusOut(ev) {
        const rail = ev.currentTarget;
        if (!ev.relatedTarget || !rail.contains(ev.relatedTarget)) {
            this.state.peek = false;
        }
    }

    onRailClick(section) {
        this.state.peek = false;
        this.state.sheetOpen = false;
        if (section.key === HOME_KEY) {
            this.openHome();
            return;
        }
        this.state.activeSectionKey = section.key;
        const remembered = parseInt(readStore(tabKey(this.uid, section.key)) || "", 10);
        const tab = section.items.find((i) => i.id === remembered) || section.items[0];
        if (tab) {
            this.openTab(tab);
        }
    }

    openHome() {
        const home = this.railEntries[0];
        const item = home.items[0];
        this.navigateTo(item);
    }

    // ------------------------------------------------------- the tab column
    /**
     * Fit every tab label to its box, WITHOUT changing the data.
     *
     * Capitals at 9px/800 are wide: "OBSERVATIONS" is 79px in a 66px box.
     * The browser does not hyphenate capitals, so left to itself it cut such
     * a word in the middle ("OBSERVATIO / NS"), which reads worse than either
     * answer here: a label whose longest word is a little too wide is set
     * smaller, a quarter pixel at a time and never below 7.5px, until the
     * whole word shows; one that still does not fit becomes a single line
     * ending in "…", with the full name as the button's title. Measured on the
     * rendered label, after every render of the column, because only the
     * page knows how wide its own font draws.
     */
    _fitTabLabels() {
        const column = this.tabcolRef.el;
        if (!column) {
            return;
        }
        for (const label of column.querySelectorAll(".vu-tab-label")) {
            // On a phone the strip draws one line with its own ellipsis, and a
            // hidden label (≤1024px) measures as zero: neither is fitted, and
            // the next render that shows the column fits it afresh.
            const mark = `${label.textContent}|${this.state.phone ? "p" : "d"}`;
            if (label.dataset.fitted === mark) {
                continue;
            }
            label.classList.remove("is-long");
            label.style.fontSize = "";
            if (this.state.phone || !label.clientWidth) {
                delete label.dataset.fitted;
                continue;
            }
            label.dataset.fitted = mark;
            let size = 9;
            // A word wider than the box overflows sideways (the label does not
            // break inside words), which is what this looks for.
            while (label.scrollWidth > label.clientWidth + 0.5 && size > 7.5) {
                size -= 0.25;
                label.style.fontSize = `${size}px`;
            }
            if (label.scrollWidth > label.clientWidth + 0.5) {
                label.classList.add("is-long");
            }
        }
    }

    /** `en_US` → `en-US`: the tab labels say which language they are in. */
    get langTag() {
        return String(user.lang || "en_US").replace("_", "-");
    }

    get activeSection() {
        const key = this.state.activeSectionKey;
        if (!key || key === HOME_KEY) {
            return null;
        }
        return this.state.sections.find((s) => s.key === key) || null;
    }

    get activeRootId() {
        const entry = this._index[this.state.activeItemId];
        return entry ? entry.rootId : null;
    }

    get activeRoot() {
        const entry = this._index[this.activeRootId];
        return entry ? entry.item : null;
    }

    get activeChild() {
        const entry = this._index[this.state.activeItemId];
        if (!entry || entry.item.id === entry.rootId) {
            return null;
        }
        return entry.item;
    }

    get segments() {
        const root = this.activeRoot;
        if (!root || !this.activeSection || !(root.children || []).length) {
            return [];
        }
        return root.children;
    }

    isTabActive(item) {
        return this.activeRootId === item.id;
    }

    isSegmentActive(child) {
        return this.state.activeItemId === child.id;
    }

    /**
     * A leaf opens. A parent with a screen of its own (AR Management) opens
     * that screen, with its children as segments; a parent that is only a
     * heading (Phone) opens its first child. The second is the old "a parent
     * never navigates" rule; the first exists because a heading's first child
     * can be a pop-up form (AR Management's is the Account Payment wizard),
     * which is no place to land.
     */
    openTab(item) {
        writeStore(tabKey(this.uid, this._index[item.id]?.sectionKey || this.state.activeSectionKey), String(item.id));
        const children = item.children || [];
        const ownScreen = item.action_xmlid || item.action_tag;
        this.navigateTo(children.length && !ownScreen ? children[0] : item);
    }

    get crumbs() {
        const out = [];
        const section = this.activeSection;
        if (!section) {
            return out;
        }
        out.push(railLabel(section.name));
        const root = this.activeRoot;
        if (root && this._index[root.id]?.sectionKey === section.key) {
            out.push(root.name);
            const child = this.activeChild;
            if (child) {
                out.push(child.name);
            }
        }
        return out;
    }

    // --------------------------------------------------------- navigation
    async navigateTo(item) {
        if (this._index[item.id]) {
            this._setActive(item.id);
        }
        const actionRef = item.action_xmlid || item.action_tag;
        if (!actionRef) {
            return;
        }
        const options = { clearBreadcrumbs: true };
        const scope = this._catchmentDomain(item);
        if (scope) {
            try {
                const action = await this.actionService.loadAction(actionRef, {});
                action.domain = Domain.and([
                    new Domain(action.domain || []),
                    new Domain(scope),
                ]).toString();
                this.actionService.doAction(action, options);
                return;
            } catch {
                // Fall through to plain navigation. Record rules remain the
                // boundary, so the worst case here is an unscoped-looking
                // list, never access to something the rules forbid.
            }
        }
        this.actionService.doAction(actionRef, options);
    }

    /**
     * The catchment scope for this leaf, as a domain — NOT as a
     * `search_default_` facet.
     *
     * A facet was the first design and it was wrong twice over. It is
     * removable, so a scoped user could clear it and widen their own list
     * (on crm.lead the record rules alone let 296 rows through, because the
     * Sales "All Documents" rule ORs the catchment rule away) — and clearing
     * it produced a raw AccessError dialog. It also occupied
     * `searchModel.query`, which silently suppressed the Contacts view's own
     * default "Today" filter (crm_contact_list.js:162 only applies that when
     * the query is empty), so the same screen showed different totals
     * depending on whether an area was selected.
     *
     * As a domain it cannot be removed, cannot collide with the view's own
     * filters, and the pill in the page header remains the visible indication
     * of what is being shown.
     *
     * Returns null when there is nothing to scope: reference-data leaves, the
     * OWL dashboards, or an owner who has chosen "All areas".
     */
    _catchmentDomain(item) {
        const field = item.catchment_field;
        if (!field) {
            return null;
        }
        const scope = this.state.catchment;
        const pick = this.state.catchmentPick;
        if (scope.can_switch && pick === "all") {
            return null;
        }
        if (scope.can_switch && pick) {
            const chosen = (scope.options || []).find((o) => String(o.id) === String(pick));
            if (chosen) {
                return [[field, "=", chosen.id]];
            }
        }
        if (!scope.current_id) {
            // An owner with no area set sees everything; a scoped user with no
            // area set sees nothing, which is the same fail-closed answer the
            // record rules give.
            return scope.can_switch ? null : [[0, "=", 1]];
        }
        return [[field, "=", scope.current_id]];
    }

    /**
     * QWeb expressions run in a restricted context with no access to global
     * builtins — `String(...)` inside the template throws "ctx.String is not a
     * function" and takes the whole sidebar down with it. Comparisons that need
     * coercion belong here, in the component.
     */
    isCatchmentPicked(value) {
        return String(this.state.catchmentPick) === String(value);
    }

    onCatchmentChange(ev) {
        this.state.catchmentPick = ev.target.value;
        this._saveCatchmentPick();
        // Re-open the current screen so the new scope takes effect immediately
        // rather than on the next click. Falls back to doing nothing when the
        // active item cannot be resolved (e.g. arrived via a breadcrumb).
        const entry = this._index[this.state.activeItemId];
        if (entry) {
            this.navigateTo(entry.item);
        }
    }

    _catchmentStorageKey() {
        return `cms_catchment_${user.userId || 0}`;
    }

    _loadCatchmentPick() {
        this.state.catchmentPick = readStore(this._catchmentStorageKey()) || "";
    }

    _saveCatchmentPick() {
        writeStore(this._catchmentStorageKey(), this.state.catchmentPick);
    }

    /** The old shared fold memory (`cms_sidebar_collapse_0`) has no reader now. */
    _forgetSharedFoldKey() {
        try {
            browser.localStorage.removeItem("cms_sidebar_collapse_0");
        } catch {
            // ignore
        }
    }

    // ----------------------------------------------------------- viewport
    _watchViewport() {
        this._queries = [];
        const watch = (query, key) => {
            let mql;
            try {
                mql = browser.matchMedia(query);
            } catch {
                return;
            }
            this.state[key] = mql.matches;
            const onChange = (ev) => {
                this.state[key] = ev.matches;
                if (key === "phone" && !ev.matches) {
                    this.state.sheetOpen = false;
                }
            };
            mql.addEventListener("change", onChange);
            this._queries.push([mql, onChange]);
        };
        watch(WIDE_QUERY, "wide");
        watch(TABLET_QUERY, "tablet");
        watch(PHONE_QUERY, "phone");
    }

    _unwatchViewport() {
        for (const [mql, onChange] of this._queries || []) {
            mql.removeEventListener("change", onChange);
        }
    }

    // ----------------------------------------------------------- the phone
    toggleSheet() {
        this.state.sheetOpen = !this.state.sheetOpen;
    }

    closeSheet() {
        this.state.sheetOpen = false;
    }

    // ------------------------------------------------------------ keyboard
    onWindowKeydown(ev) {
        if (ev.key === "Escape") {
            if (this.state.peek || this.state.sheetOpen) {
                ev.stopPropagation();
                this.state.peek = false;
                this.state.sheetOpen = false;
                const active = document.activeElement;
                if (active && active.closest && active.closest(".vu-rail, .vu-sheet")) {
                    active.blur();
                }
            }
            return;
        }
        // Alt+1 … Alt+9 — jump to that rail entry. `code`, not `key`: on a Mac
        // Alt+1 types "¡". Never while somebody is typing in a field.
        if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) {
            return;
        }
        const match = /^Digit([1-9])$/.exec(ev.code || "");
        if (!match) {
            return;
        }
        const target = ev.target;
        if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName || ""))) {
            return;
        }
        const section = this.railEntries[parseInt(match[1], 10) - 1];
        if (!section) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.onRailClick(section);
    }

    /** ↑ ↓ (and Home / End) move between the buttons of one list. */
    onListKeydown(ev) {
        const keys = ["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"];
        if (!keys.includes(ev.key)) {
            return;
        }
        const list = ev.currentTarget;
        const buttons = [...list.querySelectorAll("button[data-nav]")];
        const index = buttons.indexOf(document.activeElement);
        if (index < 0 || !buttons.length) {
            return;
        }
        let next = index;
        if (ev.key === "ArrowDown" || ev.key === "ArrowRight") {
            next = Math.min(buttons.length - 1, index + 1);
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") {
            next = Math.max(0, index - 1);
        } else if (ev.key === "Home") {
            next = 0;
        } else if (ev.key === "End") {
            next = buttons.length - 1;
        }
        ev.preventDefault();
        buttons[next].focus();
    }
}

// ---------------------------------------------------------------------------
// HOME — a client action that asks the server where this person lands.
//
// `cms.sidebar.item.home_action()` answers with an action xml-id; health_access
// picks the dashboard of the person's own job (owner ruling, MENU IA Q1). The
// answer is kept for the session and dropped whenever somebody changes who
// sees what (`CMS_SIDEBAR:RELOAD`), which is also when a job can have changed.
// ---------------------------------------------------------------------------
let homeAnswer = null;

export function forgetHomeAnswer() {
    homeAnswer = null;
}

async function cmsHomeAction(env, action, options) {
    if (!homeAnswer) {
        homeAnswer = env.services.orm.call("cms.sidebar.item", "home_action", []).catch(() => null);
    }
    const xmlid = await homeAnswer;
    if (!xmlid) {
        homeAnswer = null;
    }
    // Returned, not executed: the action service runs what a function action
    // returns with the options the Home click was made with.
    return xmlid || "health_fieldservice.action_ops_command_center";
}
registry.category("actions").add(HOME_TAG, cmsHomeAction);

// ---------------------------------------------------------------------------
// Registry takeover: remove old per-center sidebars, register unified entry
// ---------------------------------------------------------------------------
const OLD_KEYS = ["crm_center", "ops_center", "finance_center", "admin_center"];
for (const key of OLD_KEYS) {
    try {
        sidebarRegistry.remove(key);
    } catch {
        // key may not exist if that module isn't installed
    }
}

const ALL_ACTION_TAGS = new Set([
    // Home
    HOME_TAG,
    // CRM
    "crm_dashboard", "crm_new_contact", "crm_booking_wizard", "crm_settings",
    // Operations
    "ops_command_center", "ops_booking_queue", "ops_booking_wizard", "ops_booking_detail",
    "ops_client_list", "ops_client_profile", "ops_quick_booking", "ops_reschedule_booking",
    "ops_recurring_booking", "ops_staff_roster", "ops_roster_planning", "ops_calendar",
    "ops_payment_collection", "ops_service_in_progress", "ops_staff_assignment",
    "staff_workload_dashboard",
    // Finance
    "fin_dashboard", "fin_ar_management",
    // Admin
    "admin_dashboard", "admin_settings", "field_requirements_dashboard",
]);

const ALL_XMLIDS = new Set([
    // CRM
    "health_crm.action_crm_contact_list_native",
    "health_crm.action_crm_contact_form_native",
    "health_crm.action_crm_client_list",
    "health_crm.action_crm_bookings_calendar",
    "health_crm.action_crm_followup_calendar",
    "health_crm.action_crm_activity_list",
    // Operations
    "health_fieldservice.action_ops_client_list_native",
    "health_fieldservice.action_ops_booking_list_native",
    "health_fieldservice.action_ops_booking_form",
    "health_fieldservice.action_ops_calendar",
    "health_fieldservice.action_staff_workload_dashboard",
    "health_fieldservice.action_assignment_web_timeline_view",
    "health_fieldservice.action_ops_client_profile_form",
    "health_fieldservice.action_health_staff_schedules",
    "health_fieldservice.action_health_staff_timeoff",
    // Finance
    "health_invoicing.action_fin_invoice_list",
    "health_invoicing.action_fin_package_list",
    "health_invoicing.action_fin_ar_dashboard",
    "health_invoicing.action_fin_payment_list",
    "health_invoicing.action_fin_overdue",
    "health_invoicing.action_fin_cash_collections",
    "health_invoicing.action_fin_vat_log",
    "health_invoicing.action_fin_ar_transactions",
    "health_invoicing.action_fin_account_payment",
    "health_invoicing.action_fin_refund_credit",
    // Admin
    "health_landing.action_admin_users",
    "health_landing.action_admin_facilities",
    "health_landing.action_admin_catchments",
    "health_landing.action_admin_service_types",
    "health_landing.action_admin_symptoms",
    "health_landing.action_admin_referral_sources",
    "health_landing.action_admin_insurance",
    "health_landing.action_admin_urgency",
    "health_landing.action_admin_categories",
    "health_landing.action_admin_specialties",
    "health_landing.action_admin_districts",
    "health_landing.action_admin_provinces",
    "health_landing.action_admin_contact_reasons",
    "health_landing.action_admin_lead_reasons",
    "health_landing.action_admin_lost_reasons",
    "health_landing.action_admin_service_categories",
    "health_landing.action_admin_protocols",
    "health_cms_sidebar.action_admin_medications",
    "health_cms_sidebar.action_admin_observation_types",
    "health_cms_sidebar.action_admin_notgiven_reasons",
    "health_landing.action_admin_booking_stages",
    "health_landing.action_admin_fs_teams",
    "health_landing.action_admin_cancel_reasons",
    "health_landing.action_admin_deletion_reasons",
    "health_landing.action_admin_lookup_values",
    "health_landing.action_admin_lookup_categories",
    "health_landing.action_admin_services",
    "health_landing.action_admin_pricelists",
    "health_landing.action_admin_pricing_rules",
    "health_landing.action_admin_quick_edit_rules",
    "health_landing.action_admin_packages",
    "health_landing.action_admin_staff",
    "health_landing.action_admin_skills",
    "health_landing.action_admin_areas",
    "health_landing.action_admin_equipment",
    "health_landing.action_admin_holidays",
    "health_landing.action_admin_audit",
    // CMS Sidebar Config
    "health_cms_sidebar.action_cms_sidebar_item",
    "health_cms_sidebar.action_cms_sidebar_section",
    // NB: clinical / interop / any future items are added at runtime from
    // cms.sidebar.item data by the cms_sidebar_keys service below — no need
    // to hardcode new action XML IDs here.
]);

const ALL_MODELS = new Set([
    "crm.lead", "res.partner",
    "health.fieldservice.order", "health.staff.assignment",
    "health.payment.transaction", "health.ar.transaction.log",
    "health.service.package", "health.service.billing",
    "account.move", "account.move.line",
    "health.audit.log.view",
    "cms.sidebar.item", "cms.sidebar.section",
    // staff record form (opened from the Staff Roster, Staff Assignment, …)
    // must keep the CMS sidebar like every other CMS record form
    "hr.employee",
    // The dropdown-vocabulary screens: the per-category drill-in is an
    // act_window built in python, so it has no xml_id to match on — the
    // model is the only stable handle that keeps the CMS shell.
    "health.lookup.value", "health.lookup.category",
    // NB: clinical / interop / future record models are added at runtime
    // from cms.sidebar.item.match_models by the cms_sidebar_keys service.
]);

sidebarRegistry.add("cms_unified", {
    actionTags: ALL_ACTION_TAGS,
    actionXmlIds: ALL_XMLIDS,
    windowModels: ALL_MODELS,
    Component: CmsSidebar,
});

// ---------------------------------------------------------------------------
// Data-driven visibility: load the action tags / xml-ids / models declared by
// every cms.sidebar.item and add them to the (shared) registry sets, so a
// newly-wired feature keeps the CMS shell WITHOUT a JS edit. The hardcoded
// sets above are a bootstrap that keeps the core screens shell-y even before
// this RPC resolves (and if it ever fails). SidebarHost reads the sets live
// via .has(), so mutating them here is picked up on the next resolve.
//
// RE-READ ON `CMS_SIDEBAR:RELOAD` (MENU M1). It used to be read once at start,
// so an entry somebody added or switched on from the Access home kept the
// shell only after a full page reload — until then, opening it dropped the
// person into the bare backend. Keys are only ever ADDED: a screen that was
// part of the shell a minute ago stays so for the rest of the session.
// ---------------------------------------------------------------------------
export async function loadMatchKeys(env, orm) {
    try {
        const keys = await orm.call("cms.sidebar.item", "get_match_keys", []);
        (keys.tags || []).forEach((t) => ALL_ACTION_TAGS.add(t));
        (keys.xmlids || []).forEach((x) => ALL_XMLIDS.add(x));
        (keys.models || []).forEach((m) => ALL_MODELS.add(m));
        // Nudge the always-mounted SidebarHost to re-resolve now that the
        // sets include the freshly-loaded keys.
        env.bus.trigger("ACTION_MANAGER:UI-UPDATED");
        return keys;
    } catch {
        // Best-effort: the bootstrap sets still cover the core screens.
        return null;
    }
}

export function shellClaims(kind, value) {
    const set = { tag: ALL_ACTION_TAGS, xmlid: ALL_XMLIDS, model: ALL_MODELS }[kind];
    return Boolean(set && set.has(value));
}

const cmsSidebarKeysService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        env.bus.addEventListener("CMS_SIDEBAR:RELOAD", () => {
            forgetHomeAnswer();
            loadMatchKeys(env, orm);
        });
        loadMatchKeys(env, orm);
        return { reload: () => loadMatchKeys(env, orm), claims: shellClaims };
    },
};
registry.category("services").add("cms_sidebar_keys", cmsSidebarKeysService);
