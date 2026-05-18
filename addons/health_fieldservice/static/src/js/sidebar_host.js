/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

export class SidebarHost extends Component {
    static template = "health_fieldservice.SidebarHost";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.state = useState({ ActiveSidebar: null, registryKey: null });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolve());
        onMounted(() => this._resolve());
        onWillUnmount(() => document.body.classList.remove("has-custom-sidebar"));
    }

    _resolve() {
        const controller = this.actionService.currentController;
        if (!controller) {
            this._clearSidebar();
            return;
        }

        const action = controller.action;
        const tag = action.tag;
        const model = action.res_model;
        const xmlId = action.xml_id;

        for (const [key, config] of sidebarRegistry.getEntries()) {
            if ((tag && config.actionTags?.has(tag)) ||
                (model && config.windowModels?.has(model)) ||
                (xmlId && config.actionXmlIds?.has(xmlId))) {
                this.state.ActiveSidebar = config.Component;
                this.state.registryKey = key;
                document.body.classList.add("has-custom-sidebar");
                return;
            }
        }

        this._clearSidebar();
    }

    _clearSidebar() {
        this.state.ActiveSidebar = null;
        this.state.registryKey = null;
        document.body.classList.remove("has-custom-sidebar");
    }
}
