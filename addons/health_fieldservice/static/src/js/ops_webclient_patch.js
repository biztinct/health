/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { OpsSidebar } from "@health_fieldservice/js/ops_sidebar";

patch(WebClient, {
    components: {
        ...WebClient.components,
        OpsSidebar,
    },
});
