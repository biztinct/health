/** @odoo-module **/
/**
 * The trial countdown, on every page, for the last few days only.
 *
 * WHY IT IS NOT ALWAYS THERE. A bar that sits at the top of every page for
 * thirty days is a bar nobody sees on day thirty-one. It appears when the trial
 * has ten days left or fewer, it sharpens in the last three, and it stays after
 * the date has passed — because that is the one moment somebody genuinely needs
 * to know, and because on this platform NOTHING HAPPENS when a trial runs out.
 *
 * ⚠ AND IT SAYS THAT OUT LOUD. Every product that has ever shown a trial
 * countdown has trained people to expect a locked door at the end of it. This
 * one does not lock anything, ever, so the bar says "nothing stops working" in
 * those words. A warning that implies a consequence that will not happen is a
 * warning that costs somebody a bad afternoon.
 *
 * ⚠ `useState(service.state)` AND NOT `service.state` (ledger F47). A service's
 * reactive object only re-renders components that have SUBSCRIBED to it, and
 * `useService` subscribes to nothing — a bar reading it directly renders once at
 * mount and never again.
 */
import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { WebClient } from "@web/webclient/webclient";
import { ic } from "@biz_kit/js/kit_icons";
import { _t } from "@web/core/l10n/translation";

/** The last few days of a trial, and after it. */
export class BizTenancyTrialBar extends Component {
    static template = "biz_tenancy.TrialBar";
    static props = {};

    setup() {
        this.tenancy = useService("biz_tenancy");
        this.action = useService("action");
        this.state = useState(this.tenancy.state);
    }

    ic(name, size = 16) { return ic(name, size); }

    get trial() { return this.state.trial || null; }

    /** Shown only while there is something worth saying. */
    get show() {
        const t = this.trial;
        if (!t) { return false; }
        return t.phase === "ending" || t.phase === "ended";
    }

    get ended() {
        return !!this.trial && this.trial.phase === "ended";
    }

    /** Urgent in the last three days, and after the date. */
    get urgent() {
        const t = this.trial;
        if (!t) { return false; }
        return t.phase === "ended" || t.days_left <= 3;
    }

    get headline() {
        const t = this.trial || {};
        if (t.phase === "ended") {
            return _t("Your trial of %(brand)s has ended.",
                      { brand: this.brand });
        }
        if (t.days_left === 0) {
            return _t("Your trial of %(brand)s ends today.",
                      { brand: this.brand });
        }
        if (t.days_left === 1) {
            return _t("Your trial of %(brand)s ends tomorrow.",
                      { brand: this.brand });
        }
        return _t("Your trial of %(brand)s ends in %(days)s days.",
                  { brand: this.brand, days: t.days_left });
    }

    /** THE SENTENCE THAT STOPS SOMEBODY WORRYING. */
    get reassurance() {
        return _t("Nothing stops working when it does — everything stays " +
                  "exactly where it is.");
    }

    get brand() { return this.state.brand || _t("this system"); }

    openPlan() {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "biz_tenancy_about",
            target: "current",
        });
    }
}

patch(WebClient, {
    components: { ...WebClient.components, BizTenancyTrialBar },
});
