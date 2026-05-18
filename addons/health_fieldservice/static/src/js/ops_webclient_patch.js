/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { SidebarHost } from "@health_fieldservice/js/sidebar_host";

patch(WebClient, {
    components: {
        ...WebClient.components,
        SidebarHost,
    },
});
