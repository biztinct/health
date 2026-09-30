/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { browser } from "@web/core/browser/browser";
import { sidebarRegistry } from "@health_fieldservice/js/sidebar_registry";

/** The sidebar that was on screen last, per person: mounted again at boot,
 *  BEFORE the first screen is known, so the menu shell is on display when the
 *  page arrives instead of half a second after it (which pushed the page down
 *  and sideways — the "loads twice" look). `_resolve` corrects it as soon as
 *  the first action is on screen. */
export function sidebarMemoryKey(uid) {
    return `vu.sidebar.${uid || "anon"}`;
}

function readStore(key) {
    try {
        return browser.localStorage.getItem(key);
    } catch {
        return null;
    }
}

function writeStore(key, value) {
    try {
        browser.localStorage.setItem(key, value);
    } catch {
        // private mode — the shell is simply resolved after the first screen
    }
}

export class SidebarHost extends Component {
    static template = "health_fieldservice.SidebarHost";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.state = useState({ ActiveSidebar: null, registryKey: null });
        this.memoryKey = sidebarMemoryKey(user.userId);

        const remembered = readStore(this.memoryKey);
        if (remembered && sidebarRegistry.contains(remembered)) {
            this._setSidebar(sidebarRegistry.get(remembered).Component, remembered);
        }

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolve());
        onMounted(() => this._resolve());
        onWillUnmount(() => document.body.classList.remove("has-custom-sidebar"));
    }

    _resolve() {
        const controller = this.actionService.currentController;
        if (!controller) {
            // Nothing on screen yet: keep the remembered shell (or none) as it
            // is; the first action decides, a moment from now.
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
        writeStore(this.memoryKey, key);
    }

    _clearSidebar() {
        this.state.ActiveSidebar = null;
        this.state.registryKey = null;
        document.body.classList.remove("has-custom-sidebar");
        writeStore(this.memoryKey, "");
    }
}
