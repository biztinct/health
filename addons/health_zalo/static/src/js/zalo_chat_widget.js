/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

/**
 * Zalo Chat Widget Component
 *
 * Real-time chat interface for Zalo messaging.
 * Displays conversation messages and allows sending new messages.
 */
export class ZaloChatWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.bus = useService("bus_service");
        this.action = useService("action");

        this.state = useState({
            conversationId: this.props.conversationId || null,
            conversation: null,
            messages: [],
            loading: true,
            sending: false,
            inputText: "",
        });

        this.messagesEndRef = useRef("messagesEnd");
        this.messageInputRef = useRef("messageInput");

        onMounted(() => {
            this.loadConversation();
            this.subscribeToBus();
        });

        onWillUnmount(() => {
            this.unsubscribeFromBus();
        });
    }

    /**
     * Load conversation and messages
     */
    async loadConversation() {
        if (!this.state.conversationId) {
            this.state.loading = false;
            return;
        }

        try {
            const result = await rpc("/zalo/chat/conversation/" + this.state.conversationId + "/messages", {
                limit: 50,
                offset: 0,
            });

            this.state.conversation = result.conversation;
            this.state.messages = result.messages || [];
            this.state.loading = false;

            // Scroll to bottom after loading
            this.scrollToBottom();
        } catch (error) {
            console.error("Failed to load conversation:", error);
            this.notification.add("Failed to load conversation", { type: "danger" });
            this.state.loading = false;
        }
    }

    /**
     * Subscribe to bus notifications for real-time updates
     */
    subscribeToBus() {
        if (!this.state.conversationId) return;

        // Subscribe to bus for new messages
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

        if (type === "zalo.message" && payload.conversation_id === this.state.conversationId) {
            // Add new message to list
            this.state.messages.push({
                id: payload.message_id,
                direction: "incoming",
                message_type: payload.message_type,
                text: payload.text,
                sent_date: payload.sent_date,
                state: "delivered",
            });

            // Scroll to bottom
            this.scrollToBottom();

            // Mark as read
            this.markAsRead();
        }
    }

    /**
     * Send message
     */
    async sendMessage() {
        const text = this.state.inputText.trim();
        if (!text || this.state.sending) return;

        this.state.sending = true;

        try {
            const result = await rpc("/zalo/chat/send_message", {
                conversation_id: this.state.conversationId,
                text: text,
                message_type: "text",
            });

            if (result.error) {
                throw new Error(result.error);
            }

            // Add message to list
            this.state.messages.push(result.message);

            // Clear input
            this.state.inputText = "";

            // Scroll to bottom
            this.scrollToBottom();

            // Focus input
            if (this.messageInputRef.el) {
                this.messageInputRef.el.focus();
            }
        } catch (error) {
            console.error("Failed to send message:", error);
            this.notification.add("Failed to send message: " + error.message, { type: "danger" });
        } finally {
            this.state.sending = false;
        }
    }

    /**
     * Handle Enter key in input
     */
    onKeyDown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    /**
     * Scroll to bottom of messages
     */
    scrollToBottom() {
        setTimeout(() => {
            if (this.messagesEndRef.el) {
                this.messagesEndRef.el.scrollIntoView({ behavior: "smooth" });
            }
        }, 100);
    }

    /**
     * Mark conversation as read
     */
    async markAsRead() {
        try {
            await rpc("/zalo/chat/mark_as_read", {
                conversation_id: this.state.conversationId,
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
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Format date for message grouping
     */
    formatDate(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) {
            return "Today";
        } else if (date.toDateString() === yesterday.toDateString()) {
            return "Yesterday";
        } else {
            return date.toLocaleDateString();
        }
    }

    /**
     * Check if should show date separator
     */
    shouldShowDateSeparator(index) {
        if (index === 0) return true;

        const currentMsg = this.state.messages[index];
        const prevMsg = this.state.messages[index - 1];

        if (!currentMsg.sent_date || !prevMsg.sent_date) return false;

        const currentDate = new Date(currentMsg.sent_date).toDateString();
        const prevDate = new Date(prevMsg.sent_date).toDateString();

        return currentDate !== prevDate;
    }

    /**
     * Close dialog
     */
    closeDialog(ev) {
        console.log('Close dialog clicked');

        // Prevent event bubbling
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }

        try {
            // For client actions, use restore() to go back to previous action
            if (this.action && this.action.restore) {
                this.action.restore();
                console.log('Closed via action.restore()');
                return;
            }

            // Fallback: try standard close
            if (this.action) {
                this.action.doAction({ type: 'ir.actions.act_window_close' });
                console.log('Closed via action service');
                return;
            }

            console.error('No close method available');
        } catch (error) {
            console.error('Error closing dialog:', error);
        }
    }
}

ZaloChatWidget.template = "health_zalo.ZaloChatWidget";
ZaloChatWidget.props = {
    conversationId: { type: Number, optional: true },
    // Standard Odoo action props (optional)
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
};

// Register as a client action
registry.category("actions").add("zalo_chat_window", ZaloChatWidget);
