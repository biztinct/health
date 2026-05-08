/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * Zalo Chat Hub Component
 *
 * Persistent floating chat widget that stays visible across all views.
 * Shows Zalo conversation list and notifications for incoming messages.
 */
export class ZaloChatHub extends Component {
    setup() {
        this.orm = useService("orm");
        this.bus = useService("bus_service");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            isOpen: false,              // Panel expanded or collapsed
            conversations: [],          // List of active conversations
            unreadCount: 0,             // Total unread messages
            activeConversationId: null, // Currently open chat
            loading: false,             // Loading state
        });

        // Audio notification
        this.notificationSound = null;

        onMounted(() => {
            this.loadConversations();
            this.subscribeToBus();
            this.initNotificationSound();
        });

        onWillUnmount(() => {
            this.unsubscribeFromBus();
        });
    }

    t(text) {
        return _t(text);
    }

    /**
     * Initialize notification sound
     */
    initNotificationSound() {
        // Create audio element for notifications
        // Using a simple beep - can be replaced with custom sound file
        this.notificationSound = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZQQ0PVqzn7q1aGAc+ltzy0HwrBSl+zO/aizsJEmS66+ihUBQKRaXh8bllHgU2jdXyzn0vBSh+y+/cizsJEmS56+mjUhYLRaXi8bZkHQU3jdXy0HwwBSh9y+/dilAKEmW56+mjUhYKRaXi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8bZkHAU3jdXyzn0vBSh/zO/cizsJEmS66+mjUhYKRKTi8Q==');
    }

    /**
     * Toggle chat panel open/closed
     */
    togglePanel() {
        this.state.isOpen = !this.state.isOpen;

        // Mark all as read when opening panel
        if (this.state.isOpen && this.state.unreadCount > 0) {
            this.markAllAsRead();
        }
    }

    /**
     * Load active conversations
     */
    async loadConversations() {
        this.state.loading = true;
        try {
            const result = await rpc("/zalo/chat/conversations/active", {
                limit: 50,
            });

            this.state.conversations = result.conversations || [];
            this.state.unreadCount = result.total_unread || 0;
        } catch (error) {
            console.error("Failed to load conversations:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Subscribe to bus notifications for real-time updates
     */
    subscribeToBus() {
        this.busSubscription = this.bus.addEventListener(
            "notification",
            this.onBusNotification.bind(this)
        );
    }

    /**
     * Unsubscribe from bus
     */
    unsubscribeFromBus() {
        if (this.busSubscription) {
            this.bus.removeEventListener("notification", this.busSubscription);
        }
    }

    /**
     * Handle bus notifications (new messages)
     */
    onBusNotification(notification) {
        const { type, payload } = notification.detail;

        if (type === "zalo.message") {
            // Reload conversations to get updated data
            this.loadConversations();

            // Play notification sound
            this.playNotificationSound();

            // Show browser notification
            this.showBrowserNotification(payload);

            // Auto-expand on first message (optional)
            // Commented out - users can manually open
            // if (this.state.unreadCount === 1 && !this.state.isOpen) {
            //     this.state.isOpen = true;
            // }
        }
    }

    /**
     * Play notification sound
     */
    playNotificationSound() {
        if (this.notificationSound) {
            try {
                this.notificationSound.play().catch(err => {
                    console.log("Could not play notification sound:", err);
                });
            } catch (error) {
                console.log("Notification sound error:", error);
            }
        }
    }

    /**
     * Show browser notification
     */
    showBrowserNotification(payload) {
        if ("Notification" in window && Notification.permission === "granted") {
            try {
                new Notification("New Zalo Message", {
                    body: payload.text || "You have a new message",
                    icon: "/health_zalo/static/description/icon.png",
                    tag: `zalo-${payload.conversation_id}`,
                });
            } catch (error) {
                console.log("Browser notification error:", error);
            }
        }
    }

    /**
     * Open a conversation in full chat widget
     */
    openConversation(conversation) {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "zalo_chat_window",
            name: conversation.name || "Zalo Chat",
            params: {
                conversationId: conversation.id,
            },
        });

        // Close panel after opening chat
        this.state.isOpen = false;
    }

    /**
     * Open related record (Client/Patient or Lead)
     */
    async openRelatedRecord(conversation) {
        try {
            // Priority 1: Search for Client/Patient
            const partners = await this.orm.searchRead(
                "res.partner",
                [["zalo_user_id", "=", conversation.zalo_user_id]],
                ["id", "name"],
                { limit: 1 }
            );

            if (partners.length > 0) {
                return this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "res.partner",
                    res_id: partners[0].id,
                    views: [[false, "form"]],
                    target: "current",
                });
            }

            // Priority 2: Search for CRM Lead
            const leads = await this.orm.searchRead(
                "crm.lead",
                [["zalo_user_id", "=", conversation.zalo_user_id]],
                ["id", "name"],
                { limit: 1 }
            );

            if (leads.length > 0) {
                return this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "crm.lead",
                    res_id: leads[0].id,
                    views: [[false, "form"]],
                    target: "current",
                });
            }

            // Priority 3: Create New Lead
            this.showCreateLeadDialog(conversation);

        } catch (error) {
            console.error("Failed to open related record:", error);
            this.notification.add("Failed to open related record", { type: "danger" });
        }
    }

    /**
     * Show dialog to create new lead from conversation
     */
    showCreateLeadDialog(conversation) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_name: conversation.name || "Zalo Lead",
                default_zalo_user_id: conversation.zalo_user_id,
                default_mobile: conversation.zalo_phone_number || "",
                default_contact_type: "zalo",
            },
        });
    }

    /**
     * Mark all conversations as read
     */
    async markAllAsRead() {
        try {
            await rpc("/zalo/chat/mark_all_read", {});
            this.state.unreadCount = 0;

            // Update conversation unread counts
            this.state.conversations.forEach(conv => {
                conv.unread_count = 0;
            });
        } catch (error) {
            console.error("Failed to mark as read:", error);
        }
    }

    /**
     * Format timestamp for display
     */
    formatTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return "Just now";
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    /**
     * Request browser notification permission
     */
    async requestNotificationPermission() {
        if ("Notification" in window && Notification.permission === "default") {
            try {
                await Notification.requestPermission();
            } catch (error) {
                console.log("Notification permission error:", error);
            }
        }
    }
}

ZaloChatHub.template = "health_zalo.ZaloChatHub";
ZaloChatHub.props = {};
