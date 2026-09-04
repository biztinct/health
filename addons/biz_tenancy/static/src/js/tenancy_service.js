/** @odoo-module **/
/**
 * The one place in the browser that knows what the platform has said.
 *
 * SEEDED FROM THE PAGE, NOT FROM A REQUEST. `session_info` already carries the
 * answer, so the bar is correct on the first paint and there is no flash of a
 * page without it. The poll below exists only for a tab that stays open.
 *
 * WHAT IT POLLS, AND WHY IT IS NOT FREE-RUNNING (ledger F14).
 *   * Only while the tab is VISIBLE. A laptop with forty background tabs must
 *     not be asking forty questions a minute about a message that changes twice
 *     a month.
 *   * Immediately when a hidden tab comes back and more than a minute has
 *     passed — that is the case that actually matters, somebody returning to a
 *     screen they left this morning.
 *   * Once a minute otherwise.
 *
 * AND THE CONSEQUENCE TO REMEMBER WHEN VALIDATING THIS: **a background tab does
 * not update.** Driving a browser from a script leaves the customer's tab
 * hidden while the platform's tab is being used, so "the bar did not appear" is
 * the design working. Bring the tab to the front before timing anything.
 *
 * IT WRITES NOTHING. Two things are remembered, both in this browser only:
 * which message this person has closed, and which release they were last told
 * about. Neither leaves the machine, and losing them costs one extra toast.
 */
import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

/** How often an open, visible tab asks. */
export const POLL_MS = 60000;

const LS_DISMISSED = "biz_tenancy.dismissed";
const LS_SEEN_RELEASE = "biz_tenancy.seen_release";

/**
 * The starting point, and every key it has.
 *
 * `apply()` rebuilds the state FROM this object on every read, so a key the
 * server stops sending goes back to its empty answer rather than lingering as
 * something stale that nobody can explain.
 */
const EMPTY = {
    brand: "", release: "", release_notes: "", release_at: "",
    releases: [], notice: null, pushed_at: "",
    platform_url: "", support_email: "", is_platform: false,
};

/** localStorage, but a private window is not an error. */
function lsGet(key) {
    try { return window.localStorage.getItem(key) || ""; } catch { return ""; }
}
function lsSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch { /* private mode */ }
}

/**
 * A stable identity for a message, so that closing one does not close the next.
 *
 * The server builds it from the kind, the start and the text, which is exactly
 * the set of things that make a message a different message.
 */
export function noticeKey(notice) {
    if (!notice) { return ""; }
    return String(notice.id || notice.text || "");
}

export const tenancyService = {
    dependencies: ["notification", "action"],

    start(env, { notification, action }) {
        const state = reactive({
            ...EMPTY,
            ...(session.biz_tenancy || {}),
            // Not from the server: this browser's own answer to "have I closed
            // this one?".
            dismissed: lsGet(LS_DISMISSED),
        });

        let lastFetch = Date.now();

        function apply(data) {
            if (!data) { return; }
            Object.assign(state, EMPTY, data);
        }

        async function refresh() {
            lastFetch = Date.now();
            try {
                apply(await rpc("/biz_tenancy/state", {}, { silent: true }));
            } catch (e) {
                // A dropped connection is not news anybody needs; the bar keeps
                // saying whatever it last knew. Logged, never swallowed in
                // silence.
                console.debug("biz_tenancy: could not refresh the platform state", e);
            }
        }

        function tick() {
            if (document.visibilityState === "visible") { refresh(); }
        }

        /** Hide this message in this browser until a different one arrives. */
        function dismiss() {
            const key = noticeKey(state.notice);
            if (!key) { return; }
            state.dismissed = key;
            lsSet(LS_DISMISSED, key);
        }

        /**
         * "You are now on release 2026.09.04." — once, ever, per browser.
         *
         * Fired for a release this browser has not been told about, INCLUDING
         * the first one it ever sees: a first sighting is genuinely news, and
         * it is the only moment anybody ever discovers there is an About screen
         * at all. The cost of being wrong is one toast.
         */
        function announceRelease() {
            const rel = state.release;
            if (!rel || lsGet(LS_SEEN_RELEASE) === rel) { return; }
            lsSet(LS_SEEN_RELEASE, rel);
            notification.add(
                _t("%(brand)s was updated to release %(name)s.",
                   { brand: state.brand || _t("This system"), name: rel }),
                {
                    type: "success",
                    // Long enough to read a sentence AND reach for the button;
                    // the default four seconds makes the link decorative.
                    autocloseDelay: 12000,
                    sticky: false,
                    buttons: [{
                        name: _t("See what changed"),
                        onClick: () => action.doAction({
                            type: "ir.actions.client",
                            tag: "biz_tenancy_about",
                            target: "current",
                        }),
                    }],
                },
            );
        }

        if (session.biz_tenancy) {
            // After the first paint, never during it: a toast raised while the
            // web client is still assembling itself lands in a notification
            // container that does not exist yet.
            setTimeout(announceRelease, 1500);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible"
                && Date.now() - lastFetch > POLL_MS) {
                refresh();
            }
        });
        const timer = setInterval(tick, POLL_MS);
        // The service lives as long as the page does; the handle is kept only
        // so a test has something to stop.
        return { state, refresh, dismiss, stop: () => clearInterval(timer) };
    },
};

registry.category("services").add("biz_tenancy", tenancyService);
