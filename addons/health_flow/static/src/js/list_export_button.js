/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

/**
 * Patch ListController to add an "Export All" button in the control panel.
 * This uses the same mechanism as Odoo's built-in "Export All" from the
 * gear/cog menu — triggers the "direct-export-data" event on searchModel.
 */
patch(ListController.prototype, {
    /**
     * Called by the Export All button click.
     * Triggers the same export event as Odoo's built-in Export All.
     */
    onExportAll() {
        this.env.searchModel.trigger("direct-export-data");
    },
});
