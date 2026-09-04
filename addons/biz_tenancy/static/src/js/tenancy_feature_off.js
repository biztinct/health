/** @odoo-module **/
/**
 * "That part is not switched on here."
 *
 * WHAT THIS PAGE IS FOR, AND WHY IT IS A PAGE. A part of the product that a
 * clinic has not bought has its doors closed: the left-menu entries are gone,
 * and that is most of the work. But a bookmark from before, a tab somebody
 * left open last week and a link in a message all reach the screen directly,
 * and until this existed the answer to all three was a framework error page
 * with a stack trace on it — which reads as "your system is broken" rather
 * than "you do not have this".
 *
 * THE THREE THINGS IT HAS TO SAY, in this order, and nothing else:
 *   1. WHAT is not on, by the name the customer knows it by;
 *   2. WHAT THEY WOULD GET if it were — the product's own sentence about it,
 *      which is the only reason anybody reads a page like this twice;
 *   3. WHO TO ASK, with a real address where there is one.
 *
 * AND ONE DOOR OUT, ALWAYS. Zero dead ends: the button goes back to where they
 * came from, or home if they arrived here cold.
 *
 * NO FRAMEWORK WORD ANYWHERE ON IT (rail R12). The product's name comes from
 * the brand setting; a system with no brand set says "this system".
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@biz_kit/js/kit_icons";
import { HubBackChip, hubBack } from "@biz_kit/js/kit_nav";
import { _t } from "@web/core/l10n/translation";

export class BizTenancyFeatureOff extends Component {
    static template = "biz_tenancy.FeatureOff";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.back = hubBack(this.props);
        this.tenancy = useService("biz_tenancy");
    }

    ic(name, size = 16) { return ic(name, size); }

    get params() { return this.props.action?.params || {}; }

    get brand() {
        return this.params.brand || this.tenancy.state.brand || _t("this system");
    }

    get label() { return this.params.label || _t("This part of the product"); }

    /**
     * The headline, as ONE expression.
     *
     * One `_t()` per sentence and no concatenation inside the template: a
     * template expression is compiled against the component and has no
     * built-ins of its own (ledger F16), and a sentence split across two calls
     * loses its spaces in translation (the R34 family).
     */
    get headline() {
        return _t("%(part)s is not switched on for %(brand)s.",
                  { part: this.label, brand: this.brand });
    }

    /**
     * ⚠ THE ONE CASE WHERE THIS PAGE IS A FAULT RATHER THAN AN ANSWER.
     *
     * If the settings value the platform sent could not be read, the system
     * has deliberately treated everything as off rather than guessing (the
     * fail-closed path). Somebody meeting this page then needs to know it is
     * a fault and not a decision — telling them "you have not bought this"
     * when the truth is "we could not tell" is exactly the kind of confident
     * wrong answer that costs a support call and a customer's trust.
     */
    get unreadable() { return !!this.params.unreadable; }

    get blurb() { return (this.params.blurb || "").trim(); }

    get supportEmail() {
        return this.params.support_email
            || this.tenancy.state.support_email || "";
    }

    get mailto() {
        const addr = this.supportEmail;
        if (!addr) { return ""; }
        const subject = _t("About %(part)s", { part: this.label });
        return `mailto:${addr}?subject=${encodeURIComponent(subject)}`;
    }

    goHome() {
        this.action.doAction("menu", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("biz_tenancy_feature_off", BizTenancyFeatureOff);
