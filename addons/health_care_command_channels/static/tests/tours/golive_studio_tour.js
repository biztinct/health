/** @odoo-module **/

/**
 * T188 — the Go-Live Studio opens, maps both providers, and reaches step one.
 *
 * Deliberately minimal: it proves the client action resolves, the journey map
 * renders a card per provider, "Start" opens the milestone rail with all seven
 * Meta milestones, and the first canvas asks for the App ID. Everything past
 * that writes to `channel.platform.app`, which belongs in the model suite (and
 * in the browser QA pack) rather than in a tour.
 *
 * NOTE: this tour only executes where a Chrome/Chromium binary exists. On a
 * server without one, Odoo's `ChromeBrowser` raises `unittest.SkipTest` and
 * the test is reported as skipped, never as passed (ledger §5.83's rule — a
 * test that can fail to RUN must be visible when it does).
 */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("channel_golive_studio_tour", {
    steps: () => [
        {
            content: "the Studio's own root is on screen",
            trigger: ".o_golive_studio .gl-home",
        },
        {
            content: "both providers are mapped",
            trigger: ".gl-provider-card[data-provider='zalo']",
        },
        // GL-4: the map is four providers plus the Calls truth card, which is
        // a statement rather than a journey — it carries no Start button.
        {
            content: "google is mapped too",
            trigger: ".gl-provider-card[data-provider='google']",
        },
        {
            content: "microsoft is mapped too",
            trigger: ".gl-provider-card[data-provider='microsoft']",
        },
        {
            content: "calls tells the truth instead of pretending to be a flow",
            trigger: ".gl-truth-card[data-provider='call'] .gl-truth-center",
        },
        {
            content: "start the Meta journey",
            trigger: ".gl-provider-card[data-provider='meta'] .gl-start",
            run: "click",
        },
        {
            content: "the rail carries all seven Meta milestones",
            trigger: ".gl-rail-list li:nth-child(7) .gl-rail-item[data-step='done']",
        },
        {
            content: "step one asks for the App ID",
            trigger: ".gl-canvas[data-step='create_app'] input[name='client_id']",
        },
        {
            content: "and the console link for step one is live",
            trigger: ".gl-canvas[data-step='create_app'] a.gl-console",
        },
        // GL-3: the delegation affordance is offered on a do step, and it
        // opens in place. The tour stops at the revealed field — pressing Send
        // would post a real email to a real SMTP server.
        {
            content: "the step can be handed to whoever has the console",
            trigger: ".gl-canvas[data-step='create_app'] .gl-invite-open",
            run: "click",
        },
        {
            content: "the address box opens in place, with no dialog",
            trigger: ".gl-canvas[data-step='create_app'] .gl-invite-email",
        },
    ],
});
