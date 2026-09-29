/** @odoo-module */
// =============================================================================
// Workspace kit — header "More" menu.
// -----------------------------------------------------------------------------
// A header <button> whose arch class carries `ws-more` is drawn inside ONE
// "More" dropdown on desktop instead of inline. Everything else is core:
//  - compileHeader wraps each compiled header button in a
//    <t t-set-slot="button_N" isVisible="…"> handed to StatusBarButtons; we
//    only add `wsMore="true"` to the slots whose button carries the class.
//  - StatusBarButtons splits its visible slots into inline / more.
//  - The template extension renders the inline slots, then the dropdown —
//    ONLY when at least one visible slot is a `ws-more` one, so every form
//    without the class renders exactly what core renders. Small screens keep
//    core's own "first button + ⋮" behaviour untouched.
// The compiled ViewButton keeps its confirm=, context and groups handling, so
// a button inside the menu behaves exactly like the inline one.
// =============================================================================

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";
import { StatusBarButtons } from "@web/views/form/status_bar_buttons/status_bar_buttons";

export const WS_MORE_CLASS = "ws-more";

export function markWsMoreSlots(statusBar) {
    const bar = statusBar && statusBar.querySelector ? statusBar : null;
    if (!bar) {
        return 0;
    }
    let marked = 0;
    for (const slot of bar.querySelectorAll("StatusBarButtons > t[t-set-slot]")) {
        const button = slot.firstElementChild;
        if (!button) {
            continue;
        }
        // the arch class survives as a quoted string EXPRESSION in className
        const classExpr = button.getAttribute("className") || button.getAttribute("class") || "";
        if (new RegExp(`(^|[^\\w-])${WS_MORE_CLASS}([^\\w-]|$)`).test(classExpr)) {
            slot.setAttribute("wsMore", "true");
            marked++;
        }
    }
    return marked;
}

patch(FormCompiler.prototype, {
    compileHeader(el, params) {
        const res = super.compileHeader(...arguments);
        try {
            markWsMoreSlots(res);
        } catch (error) {
            // fail closed: the stock header, every button inline
            console.warn("ws_statusbar_more: header left stock", error);
        }
        return res;
    },
});

patch(StatusBarButtons.prototype, {
    get inlineSlotNames() {
        const slots = this.props.slots || {};
        return this.visibleSlotNames.filter((name) => !slots[name].wsMore);
    },
    get moreSlotNames() {
        const slots = this.props.slots || {};
        return this.visibleSlotNames.filter((name) => slots[name].wsMore);
    },
});
