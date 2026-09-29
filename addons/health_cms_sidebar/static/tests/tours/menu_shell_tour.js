/** @odoo-module **/

/**
 * MENU M1 — the shell, driven the way a person drives it.
 *
 * `cms_menu_shell_tour` (test 5 + 6 + 8, as an Owner): Home first and Settings
 * last on the rail; a rail entry opens its section's tabs; a heading tab opens
 * its first child and shows the rest as segments; the child pill, its tab and
 * its area are all lit; a reload comes back to the same place and the area
 * reopens on the tab last used; the memory keys carry the real user id; hover
 * widens the rail and Esc closes it; « pins the drawer and it survives a
 * reload; Alt+3 jumps to the third rail entry; a screen the menu does not
 * claim clears the lit tab but keeps the area; Home lands on the dashboard.
 *
 * `cms_menu_allowlist_tour` (test 4, as the platform administrator): an entry
 * added while the page is open keeps the shell as soon as the menu is told to
 * re-read (`CMS_SIDEBAR:RELOAD`), without a page reload.
 *
 * NOTE: these only execute where a Chrome/Chromium binary exists. On a server
 * without one Odoo's ChromeBrowser raises SkipTest and the test is reported as
 * SKIPPED, never as passed (ledger §5.83).
 */

import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { shellClaims } from "@health_cms_sidebar/js/cms_sidebar";

const PROBE_UNCLAIMED = "health_cms_sidebar.m1_probe_unclaimed_action";
const PROBE_NEW = "health_cms_sidebar.m1_probe_new_action";
const PROBE_NEW_NAME = "M1 new entry";
// A heading with no screen of its own. (Not Phone: an Owner does not hold the
// phone permission on every database, and the tour is about the menu.)
const HEADING = "Medications (eMAR)";

function env() {
    return odoo.__WOWL_DEBUG__.root.env;
}

function fail(message) {
    throw new Error(message);
}

function railEntries() {
    return [...document.querySelectorAll(".vu-rail-nav .vu-rail-entry")];
}

function peek() {
    document.querySelector(".vu-rail").dispatchEvent(new MouseEvent("mouseenter"));
}

/** Wait until the screen a lit tab or segment opens is really on display. */
async function screenOf(selector) {
    for (let i = 0; i < 100; i++) {
        const lit = document.querySelector(selector);
        const expected = lit && lit.dataset.action;
        const action = env().services.action.currentController?.action || {};
        if (expected && (action.xml_id === expected || action.tag === expected)) {
            return;
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    fail(`the screen behind ${selector} never opened`);
}

function key(init) {
    document.body.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }));
}

registry.category("web_tour.tours").add("cms_menu_shell_tour", {
    steps: () => [
        {
            content: "the shell is on screen, Home first",
            trigger: ".vu-rail .vu-rail-nav .vu-rail-entry:first-child[data-section='home']",
            run() {
                // Start every run in the icon rail, whatever a previous run left.
                localStorage.setItem(`vu.rail.mode.${user.userId}`, "rail");
                const entries = railEntries();
                if (entries.length < 3) {
                    fail(`expected Home, the areas and Settings; got ${entries.length} entries`);
                }
                const last = entries[entries.length - 1];
                if (last.dataset.section !== "admin") {
                    fail(`Settings must be the last rail entry, got ${last.dataset.section}`);
                }
            },
        },
        {
            content: "open Clinical",
            trigger: ".vu-rail-entry[data-section='clinical']",
            run: "click",
        },
        {
            content: "the tab column lists Clinical's own entries",
            trigger: `.vu-tabcol[data-section='clinical'] .vu-tab[title='${HEADING}']`,
            run: "click",
        },
        {
            content: "a heading opens its first child; child, tab and area are lit",
            trigger: ".vu-segments .vu-segment:first-child.is-active",
            run() {
                if (!document.querySelector(`.vu-tab.is-active[title='${HEADING}']`)) {
                    fail("the heading's tab is not lit while its first child is open");
                }
                if (!document.querySelector(".vu-rail-entry.is-active[data-section='clinical']")) {
                    fail("the Clinical rail entry is not lit");
                }
                if (document.querySelectorAll(".vu-segments .vu-segment").length < 2) {
                    fail("the segment strip does not show the heading's children");
                }
            },
        },
        {
            content: "open the second segment",
            trigger: ".vu-segments .vu-segment:nth-child(2)",
            run: "click",
        },
        {
            content: "the second segment is lit and its screen has opened; reload the page",
            trigger: ".vu-segments .vu-segment:nth-child(2).is-active",
            async run() {
                // The pill lights on the click; the address only changes once
                // the screen has loaded. Reload after that, not before.
                const expected = document.querySelector(".vu-segments .vu-segment:nth-child(2)").dataset.action;
                for (let i = 0; i < 100; i++) {
                    const action = env().services.action.currentController?.action || {};
                    if ((action.xml_id === expected || action.tag === expected) && location.pathname.includes("action-")) {
                        await new Promise((resolve) => setTimeout(resolve, 300));
                        window.location.reload();
                        return;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                fail(`the second segment's screen (${expected}) never opened`);
            },
            expectUnloadPage: true,
        },
        {
            content: "after the reload the same screen is lit again",
            trigger: ".vu-segments .vu-segment:nth-child(2).is-active",
        },
        {
            content: "go to Operations",
            trigger: ".vu-rail-entry[data-section='ops']",
            run: "click",
        },
        {
            content: "Operations' tabs are on screen",
            trigger: ".vu-tabcol[data-section='ops'] .vu-tab.is-active",
        },
        {
            content: "back to Clinical",
            trigger: ".vu-rail-entry[data-section='clinical']",
            run: "click",
        },
        {
            content: "Clinical reopens on the tab last used, and the memory is this person's",
            trigger: `.vu-tabcol[data-section='clinical'] .vu-tab.is-active[title='${HEADING}']`,
            run() {
                const uid = user.userId;
                if (!localStorage.getItem(`vu.tab.${uid}.clinical`)) {
                    fail(`no tab memory under vu.tab.${uid}.clinical`);
                }
                const shared = Object.keys(localStorage).filter(
                    (k) => k.startsWith("vu.tab.anon.") || k.startsWith("vu.tab.0.") || k === "cms_sidebar_collapse_0");
                if (shared.length) {
                    fail(`memory stored under a shared key: ${shared.join(", ")}`);
                }
                peek();
            },
        },
        {
            content: "hover widens the rail over the page; Esc closes it",
            trigger: ".vu-rail.is-collapsed.is-peek",
            run() {
                key({ key: "Escape", code: "Escape" });
            },
        },
        {
            content: "closed again",
            trigger: ".vu-rail.is-collapsed:not(.is-peek)",
            run() {
                peek();
            },
        },
        {
            content: "« keeps the menu open",
            trigger: ".vu-rail.is-peek .vu-rail-toggle",
            run: "click",
        },
        {
            content: "the drawer is pinned and remembered; reload",
            trigger: ".vu-rail.is-drawer",
            run() {
                if (localStorage.getItem(`vu.rail.mode.${user.userId}`) !== "drawer") {
                    fail("the drawer choice was not remembered");
                }
                window.location.reload();
            },
            expectUnloadPage: true,
        },
        {
            content: "still a drawer after the reload; back to icons only",
            trigger: ".vu-rail.is-drawer .vu-rail-toggle",
            run: "click",
        },
        {
            content: "icons only again; Alt+3",
            trigger: ".vu-rail.is-collapsed",
            run() {
                key({ key: "3", code: "Digit3", altKey: true });
            },
        },
        {
            content: "Alt+3 opened the third rail entry",
            trigger: ".vu-rail-nav .vu-rail-entry:nth-child(3).is-active",
            async run() {
                await screenOf(".vu-tabcol .vu-tab.is-active");
                env().services.action.doAction(PROBE_UNCLAIMED, { clearBreadcrumbs: true });
            },
        },
        {
            content: "a screen no entry claims: no tab lit, the area kept",
            trigger: ".o_control_panel .o_breadcrumb:contains('M1 unclaimed')",
            async run() {
                // The menu redraws on the frame after the screen's title.
                for (let i = 0; i < 30 && document.querySelector(".vu-tab.is-active"); i++) {
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                if (!document.querySelector(".vu-rail")) {
                    fail("the shell left the screen");
                }
                if (document.querySelector(".vu-tab.is-active, .vu-segment.is-active")) {
                    fail("a tab is still lit for a screen the menu does not claim");
                }
                if (!document.querySelector(".vu-tabcol") ||
                        !document.querySelector(".vu-rail-nav .vu-rail-entry:nth-child(3).is-active")) {
                    fail("the area was dropped along with the highlight");
                }
            },
        },
        {
            content: "Home",
            trigger: ".vu-rail-entry[data-section='home']",
            run: "click",
        },
        {
            content: "Home lands an Owner on the Operations dashboard",
            trigger: ".vu-rail-entry.is-active[data-section='ops']",
        },
    ],
});

registry.category("web_tour.tours").add("cms_menu_allowlist_tour", {
    steps: () => [
        {
            content: "the shell is on screen",
            trigger: ".vu-rail .vu-rail-entry[data-section='admin']",
            run: "click",
        },
        {
            content: "Settings' tabs are on screen; add an entry while the page is open",
            trigger: ".vu-tabcol[data-section='admin'] .vu-tab",
            async run() {
                if (shellClaims("xmlid", PROBE_NEW)) {
                    fail("the probe screen was already part of the shell before the test");
                }
                const e = env();
                const [section] = await e.services.orm.search("cms.sidebar.section", [["technical_key", "=", "admin"]]);
                await e.services.orm.create("cms.sidebar.item", [{
                    name: PROBE_NEW_NAME,
                    section_id: section,
                    sequence: 1,
                    icon: "fa fa-flask",
                    action_xmlid: PROBE_NEW,
                }]);
                e.bus.trigger("CMS_SIDEBAR:RELOAD");
            },
        },
        {
            content: "the new entry is drawn without a page reload",
            trigger: `.vu-tabcol .vu-tab[title='${PROBE_NEW_NAME}']`,
            run: "click",
        },
        {
            content: "and its screen keeps the shell, lit",
            trigger: `.vu-rail ~ .vu-tabcol .vu-tab.is-active[title='${PROBE_NEW_NAME}']`,
            async run() {
                await screenOf(".vu-tabcol .vu-tab.is-active");
                for (let i = 0; i < 30 && !document.querySelector(".o_action_manager .o_list_view"); i++) {
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                if (!document.querySelector(".vu-rail")) {
                    fail("the shell left the screen");
                }
                if (!shellClaims("xmlid", PROBE_NEW)) {
                    fail("the allowlist was not refreshed");
                }
                if (!document.querySelector(".o_action_manager .o_list_view")) {
                    fail("the new entry's screen did not open");
                }
            },
        },
    ],
});
