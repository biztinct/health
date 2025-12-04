/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ZaloChatHub } from "./zalo_chat_hub";

/**
 * Zalo Chat Hub Service
 *
 * Registers the ZaloChatHub component as a main component
 * that stays visible across all views.
 */
export const zaloChatHubService = {
    dependencies: ["bus_service"],

    start(env, { bus_service }) {
        // Register ZaloChatHub as a main component
        registry.category("main_components").add(
            "ZaloChatHub",
            {
                Component: ZaloChatHub,
                props: {},
            }
        );
    },
};

// Register the service
registry.category("services").add("zalo_chat_hub", zaloChatHubService);
