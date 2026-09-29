/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// "ACCESS & ROLES" ON THE SETTINGS TAB STRIP, BESIDE USERS.
//
// The strip belongs to health_landing; the screen this tab opens belongs to the
// Access home. So the tab is contributed through the strip's own extension
// registry rather than written into health_landing's list (AR-2) — the same
// seam health_cms_sidebar uses for its lookup tabs.
//
// `group: "people"` is the Users strip. That group declares its tabs flat, so
// it has one unnamed section, which is what an absent `section` means. Users
// carries no sequence (0), so 20 puts this straight after it.
//
// NOT A LIST OF ROWS: it opens the Access home, which is a screen rather than a
// table, hence `model: false`. Who may see it is decided where the strip is
// drawn (`ACCESS_TAB_IDS` in admin_model_navigator.js, keyed on this id) — the
// people who manage access and the platform administrator.
registry.category("health_landing.admin_tabs").add("access", {
    group: "people",
    sequence: 20,
    label: _t("Access & roles"),
    icon: "fa-key",
    model: false,
    action: "biz_access.action_biz_access_home",
});
