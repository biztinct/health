/** @odoo-module **/
/**
 * Switching between English and Vietnamese, from the top bar, on every screen.
 *
 * WHY IT IS IN THE SYSTRAY. This product's navigation is the left rail, but the
 * rail is drawn by one client action and is not on every surface — a form
 * opened from a link, the sign-in landing, a report. The systray is the one
 * strip of chrome that is on all of them, and it is already where somebody
 * looks for "things about me" (their messages, their activities, their
 * account). A language is a thing about them.
 *
 * THE LIST IS NOT WRITTEN DOWN HERE. It comes from `res.lang.get_installed()`,
 * so a clinic that switches a third language on gets it in this menu at the
 * next page load with no code change and no deploy. That also means this
 * control cannot ever offer a language the database cannot actually render.
 *
 * IT HIDES ITSELF WHEN THERE IS NOTHING TO CHOOSE. A dropdown with one item in
 * it is a control that looks like a choice and is not one; on a database with a
 * single language this renders nothing at all.
 *
 * WHAT IT WRITES, AND WHY A RELOAD. The language is a property of the PERSON,
 * not of the tab: `res.users.lang` (which on this framework writes through to
 * their contact record), so the change follows them to their phone, into the
 * field app and onto every email the system sends them. The whole interface —
 * menus, labels, dates, the translations compiled into the assets — is chosen
 * when the page boots, so it takes a reload to reach it. The reload happens
 * ONLY after the write comes back; if the write fails the page is left exactly
 * as it was and the person is told, rather than being reloaded into the
 * language they were trying to leave.
 */

import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { loadLanguages, _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

export class VuLanguageSwitcher extends Component {
    static template = "health_theme.LanguageSwitcher";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ languages: [], switching: false });

        onWillStart(async () => {
            const languages = await loadLanguages(this.orm);
            this.state.languages = languages.map(([code, name]) => ({ code, name }));
        });
    }

    /** Nothing to choose between is not a choice — draw nothing. */
    get hasChoice() {
        return this.state.languages.length > 1;
    }

    get currentCode() {
        return user.context.lang || "en_US";
    }

    get currentLanguage() {
        return this.state.languages.find(({ code }) => code === this.currentCode);
    }

    get currentLabel() {
        return this.currentLanguage?.name || this.currentCode;
    }

    /**
     * "EN", "VI" — the part of the code before the region, which is what a
     * person recognises. `vi_VN` on a button is a setting; `VI` is a language.
     */
    get currentShortCode() {
        return this.currentCode.split(/[_@-]/)[0].toUpperCase();
    }

    get toggleAriaLabel() {
        return _t("Change language. Current language: %s", this.currentLabel);
    }

    async selectLanguage(code) {
        if (this.state.switching || code === this.currentCode) {
            return;
        }
        this.state.switching = true;
        try {
            await this.orm.write("res.users", [user.userId], { lang: code });
            user.updateContext({ lang: code });
            browser.location.reload();
        } catch {
            // Left on the page they were already on, in the language they
            // already had, and told why — never reloaded into a half-applied
            // change.
            this.state.switching = false;
            this.notification.add(
                _t("The language could not be changed. Please try again."),
                { type: "danger" }
            );
        }
    }
}

registry.category("systray").add(
    "health_theme.language_switcher",
    { Component: VuLanguageSwitcher },
    // The navbar draws the systray in REVERSE sequence order, so a number above
    // the messaging and activity entries puts this immediately to their left —
    // beside the other things that are about the person, and left of the
    // account menu.
    { sequence: 30 }
);
