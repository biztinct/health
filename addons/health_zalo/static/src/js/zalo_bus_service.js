/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Zalo Bus Service
 *
 * Listens for Zalo message notifications from bus.bus and displays
 * browser notifications + desktop notifications for new messages.
 */
export const zaloBusService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        let notificationSound = null;

        /**
         * Initialize notification sound
         */
        function initNotificationSound() {
            if (!notificationSound) {
                notificationSound = new Audio("/health_zalo/static/src/sounds/notification.mp3");
                notificationSound.volume = 0.5;
            }
        }

        /**
         * Play notification sound
         */
        function playNotificationSound() {
            try {
                initNotificationSound();
                notificationSound.currentTime = 0;
                notificationSound.play().catch((err) => {
                    console.warn("Failed to play notification sound:", err);
                });
            } catch (error) {
                console.warn("Notification sound not available:", error);
            }
        }

        /**
         * Show browser notification
         */
        async function showBrowserNotification(title, body, conversationId) {
            // Request permission if not granted
            if ("Notification" in window && Notification.permission === "default") {
                await Notification.requestPermission();
            }

            // Show notification if permission granted
            if ("Notification" in window && Notification.permission === "granted") {
                const browserNotif = new Notification(title, {
                    body: body,
                    icon: "/health_zalo/static/description/icon.png",
                    tag: `zalo-msg-${conversationId}`,
                    requireInteraction: false,
                });

                // Click handler - open conversation
                browserNotif.onclick = function() {
                    window.focus();
                    browserNotif.close();

                    // Trigger action to open conversation
                    env.services.action.doAction({
                        type: "ir.actions.client",
                        tag: "zalo_chat_window",
                        params: {
                            conversationId: conversationId,
                        },
                    });
                };

                // Auto-close after 5 seconds
                setTimeout(() => browserNotif.close(), 5000);
            }
        }

        /**
         * Handle Zalo message notification from bus
         */
        function handleZaloMessageNotification(message) {
            const { type, conversation_id, from_id, text, message_type } = message;

            if (type !== "zalo_message") return;

            // Play notification sound
            playNotificationSound();

            // Determine notification text
            let notificationText = text;
            if (message_type === "image") {
                notificationText = "📷 Sent an image";
            } else if (message_type === "file") {
                notificationText = "📎 Sent a file";
            } else if (message_type === "sticker") {
                notificationText = "😊 Sent a sticker";
            }

            // Show Odoo notification
            notification.add(`New Zalo message: ${notificationText}`, {
                type: "info",
                title: "Zalo Message",
                sticky: false,
            });

            // Show browser notification
            showBrowserNotification(
                "New Zalo Message",
                notificationText,
                conversation_id
            );

            console.log("📱 Zalo message received:", {
                conversation_id,
                from_id,
                text: notificationText,
            });
        }

        /**
         * Subscribe to bus notifications
         */
        bus_service.addEventListener("notification", ({ detail }) => {
            const notifications = detail;

            // Handle array of notifications
            if (Array.isArray(notifications)) {
                notifications.forEach((notif) => {
                    if (notif.type === "zalo.message") {
                        handleZaloMessageNotification(notif.payload);
                    }
                });
            }
            // Handle single notification
            else if (notifications.type === "zalo.message") {
                handleZaloMessageNotification(notifications.payload);
            }
        });

        console.log("✅ Zalo Bus Service initialized");

        return {
            // Expose public API if needed
            playSound: playNotificationSound,
        };
    },
};

registry.category("services").add("zalo_bus_service", zaloBusService);
