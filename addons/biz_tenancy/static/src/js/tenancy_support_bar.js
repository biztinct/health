/** @odoo-module **/
/**
 * The rose bar: somebody from the platform is in this system right now.
 *
 * WHO IT IS FOR. Everybody on the customer's system, not the operator. A nurse
 * who glances at the top of her screen should be able to tell, without asking
 * anybody, that a person from the company that sold them this is looking at it
 * at this moment, why, and for how much longer. That is the whole of the
 * feature: the record afterwards matters, and being able to SEE it while it is
 * happening is what makes the record believable.
 *
 * WHY IT COUNTS DOWN. "Support access is on" is a state somebody stops
 * noticing. "Ends in 12 minutes" is a fact that moves, and a bar that is still
 * there tomorrow is obviously wrong. The clock is drawn from the end time the
 * server sent, recomputed in the browser every ten seconds — so it stays
 * honest between polls without asking the server anything.
 *
 * AND IT REPORTS WHICH SCREENS ARE OPENED (ledger F66). The product's screens
 * are reached without a page load, so the server sees the first address of a
 * session and nothing after it; and the request seam sees an address before
 * the page has a NAME. This watches the document title and the address, and
 * tells the server when either moves — which is what turns a list of paths
 * into a list somebody can read.
 *
 * IT NEVER HIDES. There is no dismiss button, deliberately: a notice about
 * somebody being inside your system that the visitor can close is a notice
 * that will be closed.
 */
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { WebClient } from "@web/webclient/webclient";
import { rpc } from "@web/core/network/rpc";
import { ic } from "@biz_kit/js/kit_icons";
import { _t } from "@web/core/l10n/translation";

/** How often the countdown is redrawn. */
const TICK_MS = 10000;

/**
 * "12 minutes left", "under a minute", "the time is up". PURE.
 *
 * Takes the server's stored spelling (UTC, `YYYY-MM-DD HH:MM:SS`) and the
 * reader's own clock. Converting explicitly, here, is ledger F17/F32: handing
 * a stored string to a browser that reads it as local time moves every one of
 * these by the reader's offset with no error anywhere.
 */
export function remainingWords(endsAt, now = new Date()) {
    if (!endsAt) { return ""; }
    const end = new Date(String(endsAt).replace(" ", "T") + "Z");
    if (isNaN(end.getTime())) { return ""; }
    const secs = Math.round((end.getTime() - now.getTime()) / 1000);
    if (secs <= 0) { return _t("the time is up"); }
    if (secs < 60) { return _t("under a minute left"); }
    const mins = Math.round(secs / 60);
    if (mins < 60) {
        return _t("%(n)s minutes left", { n: mins });
    }
    const hours = Math.floor(mins / 60);
    const rest = mins % 60;
    if (!rest) { return _t("%(n)s hours left", { n: hours }); }
    return _t("%(h)s h %(m)s min left", { h: hours, m: rest });
}

export class BizTenancySupportBar extends Component {
    static template = "biz_tenancy.SupportBar";
    static props = {};

    setup() {
        this.tenancy = useService("biz_tenancy");
        // `useState`'s RETURN VALUE is the subscription (ledger F47). Reading
        // the service's object directly renders once at mount and never again,
        // so the bar would appear only on a page somebody happened to reload.
        this.state = useState(this.tenancy.state);
        this.tick = useState({ now: Date.now() });

        this._timer = setInterval(() => {
            this.tick.now = Date.now();
        }, TICK_MS);
        onWillUnmount(() => clearInterval(this._timer));

        // The screen trail. Watched rather than hooked into the router, so it
        // works for every way a screen can change — a menu click, the back
        // button, a link somebody pasted.
        this._lastSeen = "";
        this._watch = setInterval(() => this.reportScreen(), 2000);
        onWillUnmount(() => clearInterval(this._watch));
    }

    ic(name, size = 15) { return ic(name, size); }

    get session() { return this.state.support || null; }

    get remaining() {
        // `this.tick.now` is READ here on purpose: it is what subscribes this
        // getter to the ten-second timer, so the words move without the whole
        // component being told to re-render by anything else.
        return remainingWords(this.session?.expires_at, new Date(this.tick.now));
    }

    /** One sentence, one expression, so the spaces survive translation. */
    get headline() {
        const s = this.session;
        if (!s) { return ""; }
        return _t("%(who)s is in this system now.",
                  { who: s.who || s.platform || _t("Support") });
    }

    get why() {
        const s = this.session;
        return s && s.reason ? _t("Why: %(reason)s", { reason: s.reason }) : "";
    }

    /**
     * Tell the server which screen is on, when it changes.
     *
     * Silent and best-effort: a trail line that could not be written must
     * never put an error in front of somebody doing their job.
     */
    async reportScreen() {
        if (!this.session) { return; }
        const path = window.location.pathname || "";
        const name = (document.title || "").trim();
        const key = `${path}|${name}`;
        if (key === this._lastSeen) { return; }
        this._lastSeen = key;
        try {
            await rpc("/biz_tenancy/support/seen", { path, name },
                      { silent: true });
        } catch (e) {
            console.debug("biz_tenancy: could not record the screen", e);
        }
    }

    /** Only the person the door was opened for sees this button. */
    async endNow() {
        try {
            await rpc("/biz_tenancy/support/end", {});
        } finally {
            await this.tenancy.refresh();
        }
    }
}

export class BizTenancySupportHost extends Component {
    static template = "biz_tenancy.SupportHost";
    static components = { BizTenancySupportBar };
    static props = {};

    setup() {
        this.tenancy = useService("biz_tenancy");
        this.state = useState(this.tenancy.state);
    }

    get showing() { return !!this.state.support; }
}

// The mount point is declared in `webclient_patch.xml`, beside the notice bar.
patch(WebClient, {
    components: { ...WebClient.components, BizTenancySupportHost },
});
