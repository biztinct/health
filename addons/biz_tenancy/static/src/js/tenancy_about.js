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
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
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
        // Subscribed, not merely fetched (ledger F47). This page is open while
        // a release is pushed often enough to matter: it is the page the
        // toast's own button leads to.
        this.state = useState(this.tenancy.state);
        // Read ONCE, from props, never written back. Null when nobody sent us,
        // and the chip is then absent rather than inert.
        this.back = hubBack(this.props);
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
