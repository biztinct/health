/** @odoo-module **/
/**
 * The Form Studio tile on the Settings landing.
 *
 * The tile shows only for somebody Studio would let in: the landing's own
 * "manages access" gate AND Studio's gate, asked of the server through
 * `fs.studio.can_use` (a capability question that never raises, ledger
 * §5.127). The answer arrives after the landing has drawn; the tile appears
 * then.
 */
import { onWillStart, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { AdminSettings } from "@health_landing/js/admin_settings";
import { ic } from "@biz_kit/js/kit_icons";

patch(AdminSettings.prototype, {
    setup() {
        super.setup(...arguments);
        this.fsTile = useState({ ok: false });
        const orm = useService("orm");
        onWillStart(() => {
            orm.silent
                .call("fs.studio", "can_use", [])
                .then((ok) => {
                    this.fsTile.ok = Boolean(ok);
                })
                .catch(() => {});
        });
    },

    get fsTileIcon() {
        return ic("wandSparkles", 22);
    },

    openFormStudio() {
        this.actionService.doAction("biz_form_studio.action_fs_library", {
            clearBreadcrumbs: true,
        });
    },
});
