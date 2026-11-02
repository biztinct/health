/** @odoo-module **/
/**
 * T44 — a fresh load of the address Studio writes for a screen shows that
 * screen again (what a browser reload does). Started by
 * `TestFsEditorAddress.test_44_a_reload_opens_the_same_screen` at
 * `/odoo/action-biz_form_studio.studio?fs_model=…&fs_view=…&fs_res=…`.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("biz_form_studio_reload", {
    steps: () => [
        {
            content: "The editor names the screen it was given in the address",
            trigger: ".fs-studio .fs-bar .fs-tag--soft:contains(Partner sheet)",
        },
        {
            content: "and draws it, not the notice for an empty Studio",
            trigger: ".fs-studio .fs-work .fs-canvas",
            run: () => {
                if (document.querySelector(".fs-studio .fs-error")) {
                    throw new Error("Studio showed the empty notice after a reload");
                }
            },
        },
    ],
});
