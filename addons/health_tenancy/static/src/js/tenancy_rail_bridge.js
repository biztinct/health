/** @odoo-module **/
/**
 * One line of glue, and the reason it is a separate file.
 *
 * ⚠ A BROWSER-SIDE REACTIVE CANNOT UPDATE A MENU THE SERVER DREW (ledger F48).
 * The platform link notices — once a minute, on a tab somebody is actually
 * looking at — that which parts of the product are switched on has CHANGED,
 * and fires an event of its own. It cannot fire this product's menu-reload
 * event itself: that event belongs to the module that wrote the menu, and the
 * platform link is meant to be lifted into the next product unchanged (rail
 * R11). So the overlay — the one module that knows about both — listens for
 * one and re-fires the other.
 *
 * IT IS NOT FIRED ON THE FIRST READ. The platform link only fires when the
 * signature MOVES, and it seeds that signature from the answer the page was
 * painted with, so signing in does not redraw the menu a minute later for
 * nothing (F47's second half).
 */
import { registry } from "@web/core/registry";
import { FEATURES_CHANGED } from "@biz_tenancy/js/tenancy_service";

/** The event this product's own left menu listens for. */
const RAIL_RELOAD = "CMS_SIDEBAR:RELOAD";

export const railBridgeService = {
    // The platform link has to have started, or there would be nothing to
    // listen to and nothing to seed the signature from.
    dependencies: ["biz_tenancy"],

    start(env) {
        env.bus.addEventListener(FEATURES_CHANGED, (ev) => {
            const detail = ev.detail || {};
            console.debug(
                "health_tenancy: which parts of the product are switched on "
                + `moved ("${detail.was || ""}" -> "${detail.now || ""}"); `
                + "asking the left menu to draw itself again.");
            env.bus.trigger(RAIL_RELOAD);
        });
        return {};
    },
};

registry.category("services").add("health_tenancy_rail_bridge",
                                  railBridgeService);
