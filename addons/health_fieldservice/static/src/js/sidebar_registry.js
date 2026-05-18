/** @odoo-module **/

import { registry } from "@web/core/registry";

// Registry for custom sidebar components.
// Each entry: { actionTags: Set<string>, windowModels?: Set<string>, Component: class }
export const sidebarRegistry = registry.category("custom_sidebars");
