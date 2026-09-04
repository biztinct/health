/** @odoo-module **/
/**
 * The navigation protocol — one door in, one door back.
 *
 * Every surface built on this kit is reached the same way, and every hand-off
 * says where it came from, so a screen can never be a dead end. Three context
 * keys carry the whole thing:
 *
 *   `biz_lens`   which lens to raise on arrival
 *   `biz_focus`  what a pinned selection MEANS on arrival — `"queue"` says it
 *                is a FILTER, not a drawer to pop over the thing the reader
 *                came to look at
 *   `biz_back`   `{ label, tag|xmlid, lens, context }` — the return door,
 *                rendered as a <HubBackChip/> by any surface that asks
 *                `hubBack(this.props)` for one
 *
 * A host that reads its arrival lens from another key passes `lensKey`, so one
 * odd consumer never turns into a second protocol for everybody else.
 */
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@biz_kit/js/kit_icons";
import { homeAction } from "@biz_kit/js/kit_registries";

/** The context key a surface reads its arrival lens from. */
export const HUB_LENS_KEY = "biz_lens";

/**
 * Open a client action with the arrival protocol filled in.
 *
 * @param {object} actionService  the "action" service (the caller's, so the
 *                                notification/breadcrumb behaviour is the
 *                                caller's too)
 * @param {object}  opts
 * @param {string} [opts.tag]      client action tag
 * @param {string} [opts.xmlid]    action xmlid — wins over `tag` when both given
 * @param {string} [opts.lens]     lens key to raise on arrival
 * @param {string} [opts.lensKey]  context key for `lens` (default `biz_lens`)
 * @param {string} [opts.focus]    `"queue"` etc.
 * @param {object} [opts.back]     `{ label, tag|xmlid, lens, context }`, the
 *                                 return door. Its own `context` is what a
 *                                 surface needs to be re-opened ON the record
 *                                 it was left on (an id, say) — without it the
 *                                 chip lands on an empty screen.
 * @param {object} [opts.context]  extra context, merged last
 * @param {boolean} [opts.clearBreadcrumbs=true]
 * @returns {Promise} whatever doAction returns
 */
export function openHub(actionService, opts = {}) {
    const {
        tag, xmlid, lens, lensKey = HUB_LENS_KEY, focus, back,
        context = {}, clearBreadcrumbs = true,
    } = opts;
    const target = xmlid || tag;
    if (!target) {
        // A door with no destination is a bug in the CALLER, and swallowing it
        // would make the click look like a slow screen. Never a silent catch.
        throw new Error("openHub: one of `tag` or `xmlid` is required");
    }
    const additionalContext = { ...context };
    if (lens) { additionalContext[lensKey] = lens; }
    if (focus) { additionalContext.biz_focus = focus; }
    // Plain data only: the context crosses `doAction` and may be serialised.
    if (back && (back.tag || back.xmlid)) {
        additionalContext.biz_back = {
            label: back.label || "",
            tag: back.tag || "",
            xmlid: back.xmlid || "",
            lens: back.lens || "",
            // carried so a back door into a surface that reads another key
            // still lands on the right lens
            lensKey: back.lensKey || HUB_LENS_KEY,
            // Plain object or nothing. `_t()` returns a String SUBCLASS, so a
            // lazy translation dropped in here would not survive the JSON round
            // trip a context takes — keep ids and technical keys only.
            context: (back.context && typeof back.context === "object")
                ? { ...back.context } : {},
        };
    }
    return actionService.doAction(target, { additionalContext, clearBreadcrumbs });
}

/**
 * The return door a client action was opened with.
 *
 * A surface that owns its own header asks for it here and renders the same
 * <HubBackChip/>. That is the whole of the one-door law: the door that sent you
 * says how to get back, and the surface does not have to know who that was.
 *
 * THERE IS ALWAYS A DOOR, AND THAT IS THE POINT.
 *
 *   1. the action's own `biz_back`, when it was opened with one;
 *   2. otherwise the product's registered home (`registerHome()`);
 *   3. otherwise `{ history: true }` — a chip labelled "Back" that steps the
 *      browser back one page.
 *
 * The third case is why this never returns `null`. A back chip that is absent
 * on some screens and present on others is a control people stop looking for;
 * a chip that is drawn and inert is worse than both.
 */
export function hubBack(props) {
    const b = (props && props.action && props.action.context
               && props.action.context.biz_back) || null;
    if (b && (b.tag || b.xmlid)) {
        return b;
    }
    const home = homeAction();
    if (home && (home.tag || home.xmlid)) {
        return {
            label: home.label || "",
            tag: home.tag || "",
            xmlid: home.xmlid || "",
            lens: home.lens || "",
            lensKey: home.lensKey || HUB_LENS_KEY,
            context: (home.context && typeof home.context === "object")
                ? { ...home.context } : {},
        };
    }
    return { label: "", history: true };
}

/**
 * The return door, as a chip. It navigates itself — a back chip that needs its
 * host to wire a callback is a back chip somebody will forget to wire.
 *
 * TWO TONES, because the chip has two backgrounds to sit on. `light` (the
 * default) is a white surface header; `dark` is a deep command bar. One
 * component, one modifier class — never two chips that drift apart.
 */
export class HubBackChip extends Component {
    static template = "biz_kit.HubBackChip";
    static props = {
        // { label, tag|xmlid, lens, context } or { history: true }
        back: { type: Object },
        // "light" (a white surface header) | "dark" (a deep command bar)
        tone: { type: String, optional: true },
    };

    setup() {
        this.actionService = useService("action");
    }

    get dark() { return this.props.tone === "dark"; }

    ic(n, s = 12) { return ic(n, s); }

    get label() { return this.props.back.label || _t("Back"); }

    /**
     * Translated here rather than interpolated in the template.
     *
     * A door with a NAME says where it goes; the browser's own back has no name
     * to say, and "Back to Back" is a tooltip written by a machine.
     */
    get title() {
        if (!this.props.back.label) { return _t("Go back to the last screen"); }
        return _t("Back to %s", this.props.back.label);
    }

    /** A CLICK handler, never a lifecycle hook. */
    goBack() {
        const b = this.props.back;
        if (b.history || !(b.tag || b.xmlid)) {
            window.history.back();
            return;
        }
        openHub(this.actionService, {
            tag: b.tag, xmlid: b.xmlid, lens: b.lens, lensKey: b.lensKey,
            context: b.context || {},
        });
    }
}
