/** @odoo-module **/
/**
 * About — the release this system is on, what changed, and who to ask.
 *
 * THE QUESTION IT ANSWERS. "Something looks different this morning. What
 * happened?" Until this screen existed the only answer was to ring somebody.
 * Now every release the platform cuts arrives here with the sentence somebody
 * wrote when they cut it, newest first, with the one being run badged as such.
 *
 * THE NOTES ARE WRITTEN BY A PERSON, IN A TEXT BOX, so they are rendered as a
 * person would type them: a blank line starts a new paragraph, a line beginning
 * `- ` is a bullet. Nothing else — no markup, no links, no pictures. `t-esc`
 * puts every fragment on the page as TEXT, so a note can never carry markup
 * onto somebody's screen, whatever anybody types into the box.
 *
 * ZERO DEAD ENDS. A system that has never been told about a release shows a
 * sentence explaining what will appear here and when, not a blank page. A
 * system with nobody to contact says so rather than drawing an empty row.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ic } from "@biz_kit/js/kit_icons";
import { HubBackChip, hubBack } from "@biz_kit/js/kit_nav";
import { _t } from "@web/core/l10n/translation";
import { longDate } from "./tenancy_range";

/**
 * A note as blocks. PURE.
 *
 * Returns `[{kind: "p", text} | {kind: "ul", items: [...]}]`. A run of `- `
 * lines becomes ONE list rather than one list per line, which is what a person
 * typing three bullets means and never what a naive line-by-line pass gives.
 */
export function noteBlocks(notes) {
    const out = [];
    let para = [];
    let bullets = [];
    const flushPara = () => {
        if (para.length) { out.push({ kind: "p", text: para.join(" ") }); para = []; }
    };
    const flushBullets = () => {
        if (bullets.length) { out.push({ kind: "ul", items: bullets }); bullets = []; }
    };
    for (const raw of String(notes || "").split(/\r?\n/)) {
        const line = raw.trim();
        if (!line) { flushBullets(); flushPara(); continue; }
        if (/^[-*•]\s+/.test(line)) {
            flushPara();
            bullets.push(line.replace(/^[-*•]\s+/, ""));
            continue;
        }
        flushBullets();
        para.push(line);
    }
    flushBullets();
    flushPara();
    return out;
}

export class BizTenancyAbout extends Component {
    static template = "biz_tenancy.About";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.tenancy = useService("biz_tenancy");
        this.notification = useService("notification");
        // Subscribed, not merely fetched (ledger F47). This page is open while
        // a release is pushed often enough to matter: it is the page the
        // toast's own button leads to.
        this.state = useState(this.tenancy.state);
        // Read ONCE, from props, never written back. Null when nobody sent us,
        // and the chip is then absent rather than inert.
        this.back = hubBack(this.props);

        // SUPPORT ACCESS: the customer's own record of it, and their own
        // switch. Fetched on this screen rather than carried on every page,
        // because it is a whole list and nobody needs it until they come here.
        this.support = useState({ loaded: false, allowed: true,
                                  mayChange: false, sessions: [] });
        // PLAN & USAGE: read here rather than carried on every page, for the
        // same reason. It is a whole card and nobody needs it until they open
        // this screen.
        this.plan = useState({ loaded: false, data: null });
        onWillStart(async () => {
            // ⚠ THE ANSWER FIRST, THE RENDER SECOND (ledger H72). Both reads
            // are awaited before anything below them is drawn.
            await this.loadSupport();
            await this.loadPlan();
        });
    }

    /** The plan card's own read. Never raises onto the page. */
    async loadPlan() {
        try {
            this.plan.data = await rpc("/biz_tenancy/plan", {});
        } catch (e) {
            console.debug("biz_tenancy: could not read the plan card", e);
        } finally {
            this.plan.loaded = true;
        }
    }

    /** Is there a plan to draw at all? An empty card is a dead end. */
    get hasPlanCard() {
        return !!(this.plan.data && this.plan.data.plan_name);
    }

    get planRows() {
        const data = this.plan.data;
        return (data && data.usage && data.usage.rows) || [];
    }

    get planTrialPhase() {
        const data = this.plan.data;
        return (data && data.trial && data.trial.phase) || "none";
    }

    /** The bar is only honest where there is a limit to draw it against. */
    get planSeatShown() {
        const data = this.plan.data;
        return !!(data && data.seat && (data.seat.limit || data.seat.count));
    }

    get planSeatWidth() {
        const data = this.plan.data;
        const pct = (data && data.seat && data.seat.pct) || 0;
        return `width:${Math.max(2, Math.min(100, pct))}%`;
    }

    get planSeatTone() {
        const data = this.plan.data;
        return ((data && data.seat && data.seat.verdict) || "ok");
    }

    /** ⚠ THE ANSWER FIRST. Nothing on the support panel renders until the read
     *  comes back; a panel drawn against nothing throws inside the component's
     *  lifecycle and shows a stack trace before recovering (ledger H72). */
    async loadSupport() {
        try {
            const res = await rpc("/biz_tenancy/support/trail", {});
            this.support.allowed = !!res.allowed;
            this.support.mayChange = !!res.may_change;
            this.support.sessions = res.sessions || [];
        } catch (e) {
            console.debug("biz_tenancy: could not read the support record", e);
        } finally {
            this.support.loaded = true;
        }
    }

    get supportSessions() { return this.support.sessions || []; }

    /**
     * "Nobody has been in" is a REASSURING sentence and it has to be said out
     * loud. An empty list with no words under it reads as a screen that has
     * not loaded.
     */
    get supportLede() {
        if (!this.supportSessions.length) {
            return _t("Nobody from %(brand)s has been into this system.",
                      { brand: this.brand });
        }
        return _t("Every time somebody from %(brand)s has been into this " +
                  "system, why, and which screens they opened.",
                  { brand: this.brand });
    }

    supportWords(state) {
        const words = {
            issued: _t("A link was made and has not been used"),
            active: _t("Somebody is in here now"),
            ended: _t("Finished"),
            expired: _t("The time ran out"),
            refused: _t("Refused"),
        };
        return words[state] || state;
    }

    supportTone(state) {
        if (state === "active") { return "warn"; }
        if (state === "refused") { return "err"; }
        if (state === "ended") { return "ok"; }
        return "muted";
    }

    /**
     * The customer's own switch. Turning it OFF is the interesting direction:
     * from then on the platform's door refuses by name, and nobody on the
     * platform can turn it back on.
     */
    async toggleSupportAllowed() {
        const next = !this.support.allowed;
        try {
            const res = await rpc("/biz_tenancy/support/allow",
                                  { allowed: next });
            if (res.ok) {
                this.support.allowed = res.allowed;
            } else {
                this.notification.add(res.message, { type: "warning" });
            }
        } catch (e) {
            console.debug("biz_tenancy: could not change the setting", e);
        }
    }

    /** End a session that is running, from the customer's own side. */
    async endSupport(id) {
        try {
            await rpc("/biz_tenancy/support/end", { session_id: id });
        } finally {
            await this.loadSupport();
            await this.tenancy.refresh();
        }
    }

    ic(name, size = 16) { return ic(name, size); }

    get brand() { return this.state.brand || _t("this system"); }

    get title() { return _t("About %(brand)s", { brand: this.brand }); }

    get currentName() { return this.state.release || ""; }

    get currentDate() { return longDate(this.state.release_at || ""); }

    /** Newest first, each with its notes already broken into blocks. */
    get releases() {
        const rows = this.state.releases || [];
        return rows.map((r) => ({
            name: r.name || "",
            date: longDate(r.date || ""),
            blocks: noteBlocks(r.notes || ""),
            hasNotes: !!(r.notes || "").trim(),
            current: !!r.current,
        }));
    }

    /**
     * The one sentence at the top.
     *
     * Written for somebody who has never heard the word "release": it names the
     * one they are on and says what the list underneath is.
     */
    get lede() {
        if (!this.currentName) {
            return _t("What changed will be listed here after each update.");
        }
        return _t(
            "You are on release %(name)s. Every update is listed below, " +
            "newest first, with what changed in it.",
            { name: this.currentName });
    }

    /** Is there anybody to contact? Never draws an empty row. */
    get hasContact() {
        return !!(this.state.support_email || this.state.platform_url);
    }

    get mailto() {
        return this.state.support_email
            ? `mailto:${this.state.support_email}` : "";
    }
}

registry.category("actions").add("biz_tenancy_about", BizTenancyAbout);
