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
        const centerPin = action.context?.active_center;

        // Pass 0: explicit center pin from action context (highest priority)
        if (centerPin) {
            for (const [key, config] of sidebarRegistry.getEntries()) {
                if (key === centerPin) {
                    this._setSidebar(config.Component, key);
                    return;
                }
            }
        }

        // Pass 1: exact matches (tags + xmlIds) take priority
        for (const [key, config] of sidebarRegistry.getEntries()) {
            if ((tag && config.actionTags?.has(tag)) ||
                (xmlId && config.actionXmlIds?.has(xmlId))) {
                this._setSidebar(config.Component, key);
                return;
            }
        }

        // Pass 2: broad model match
        for (const [key, config] of sidebarRegistry.getEntries()) {
            if (model && config.windowModels?.has(model)) {
                this._setSidebar(config.Component, key);
                return;
            }
        }

        this._clearSidebar();
    }

    _setSidebar(Component, key) {
        this.state.ActiveSidebar = Component;
        this.state.registryKey = key;
        document.body.classList.add("has-custom-sidebar");
    }

    _clearSidebar() {
        this.state.ActiveSidebar = null;
        this.state.registryKey = null;
        document.body.classList.remove("has-custom-sidebar");
    }
}
