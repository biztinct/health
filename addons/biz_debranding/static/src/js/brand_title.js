/** @odoo-module **/
// Part of the Viet Uc Care white-label layer. License LGPL-3.
//
// THE TAB NEVER READS THE FRAMEWORK'S NAME (white-label rule, ledger §5.236).
//
// The title service joins whatever parts screens have set and, when there are
// none, falls back to the framework's own name. `web_debranding` sets its part
// only after a round trip to the server — and blanks it first — so for a second
// or two after every page load the browser tab said the framework's name. The
// brand now arrives with the page (`session.biz_brand_name`, see
// `models/ir_http.py`) and is set here synchronously, in the same setup, so the
// first title the web client ever writes is the brand's.
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { WebClient } from "@web/webclient/webclient";

export const BRAND_FALLBACK = "Viet Uc Care";

export function brandName() {
    return (session.biz_brand_name || "").trim() || BRAND_FALLBACK;
}

patch(WebClient.prototype, {
    setup() {
        super.setup();
        // The same part `web_debranding` writes (`zopenerp`), so its later
        // answer replaces this one instead of adding a second name beside it.
        this.title.setParts({ zopenerp: odoo.debranding_new_title || brandName() });
    },
});
