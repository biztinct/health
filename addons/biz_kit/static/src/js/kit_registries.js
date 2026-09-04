/** @odoo-module **/
/**
 * The kit's soft registries — three keys and one helper.
 *
 * WHY KEYS AND NOT IMPORTS. This module is the bottom of the stack: a product
 * surface depends on the kit, so the kit can never import a product surface
 * back. Everything a product wants to hand the kit therefore arrives through
 * `registry.category(<key>)`, which is a name and not a dependency — a module
 * registers into it at load time and the kit reads whatever is there when it
 * is asked, so a registration made after this file was evaluated still counts.
 *
 * Nothing in the kit CONSUMES the settings or palette categories. They are
 * declared here so that every product spells them the same way; two spellings
 * of one registry key is a card that renders on nobody's screen and no error
 * anywhere.
 */
import { registry } from "@web/core/registry";

/** Cards behind a product's settings cog. */
export const SETTINGS_CATEGORIES = "biz_kit_settings_category";

/** Rows in a product's command palette. */
export const PALETTE = "biz_kit_palette";

/**
 * WHERE "BACK" GOES WHEN NOTHING SAID.
 *
 * A product registers exactly ONE entry here — `{ xmlid }` or `{ tag }` — and
 * it is the screen a back chip returns to when the action it is on carries no
 * return door of its own. A product that registers nothing gets a chip that
 * simply goes back a page, which is still a door; what it never gets is a chip
 * that is drawn and does nothing.
 */
export const HOME_ACTION = "biz_kit_home";

/**
 * Name the screen a back chip falls back to.
 *
 * @param {object|string} target `{ xmlid }`, `{ tag }`, or either as a bare
 *                               string — an xmlid if it has a dot in it.
 */
export function registerHome(target) {
    const entry = typeof target === "string"
        ? (target.includes(".") ? { xmlid: target } : { tag: target })
        : (target || {});
    if (!entry.xmlid && !entry.tag) {
        // A home with no destination is a bug in the CALLER, and swallowing it
        // would make the chip look like a slow screen rather than a mistake.
        throw new Error("registerHome: one of `tag` or `xmlid` is required");
    }
    const home = registry.category(HOME_ACTION);
    // `add` with `force` so a product that re-registers on a hot reload does
    // not throw over its own entry.
    home.add("home", entry, { force: true });
    return entry;
}

/** The registered home, or `null` when the product has named none. */
export function homeAction() {
    const home = registry.category(HOME_ACTION);
    const entries = home.getAll().filter(Boolean);
    return entries.length ? entries[0] : null;
}
