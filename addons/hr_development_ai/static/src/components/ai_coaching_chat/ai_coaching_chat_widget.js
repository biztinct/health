/** @odoo-module **/

import { Component, useState, onWillStart, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class AiCoachingChatWidget extends Component {
    static template = "hr_development_ai.AiCoachingChatWidget";
    static props = {
        ...standardFieldProps,
    };
    static supportedTypes = ["text"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.chatEndRef = useRef("chatEnd");

        this.state = useState({
            messages: [],
            inputMessage: "",
            isLoading: false,
            isExpanded: false,
            recordId: null,
        });

        onWillStart(async () => {
            await this.loadChatHistory();
        });

        onMounted(() => {
            this.scrollToBottom();
        });
    }

    /**
     * Get record from props (field widgets automatically receive record)
     */
    get record() {
        return this.props.record;
    }

    /**
     * Get record ID
     */
    get recordId() {
        const record = this.record;
        if (!record) return null;
        return record.resId || record.data?.id || null;
    }

    /**
     * Load chat history from ai_transcript field
     */
    async loadChatHistory() {
        const record = this.record;
        if (!record || !record.data) {
            return;
        }

        const transcript = record.data.ai_transcript;
        if (!transcript) {
            return;
        }

        try {
            // Parse ai_transcript if it's JSON
            const parsed = JSON.parse(transcript);
            this.state.messages = parsed.messages || [];
        } catch (e) {
            // If not JSON, treat as plain text message
            if (transcript.trim()) {
                this.state.messages = [{
                    role: 'assistant',
                    content: transcript,
                    timestamp: new Date().toISOString()
                }];
            }
        }
    }

    /**
     * Send message to AI
     */
    async sendMessage() {
        if (!this.state.inputMessage.trim() || this.state.isLoading) {
            return;
        }

        const recordId = this.recordId;
        if (!recordId) {
            this.notification.add('Cannot send message: No record ID available', { type: 'danger' });
            return;
        }

        const userMessage = {
            role: 'user',
            content: this.state.inputMessage.trim(),
            timestamp: new Date().toISOString()
        };

        this.state.messages.push(userMessage);
        const messageContent = this.state.inputMessage;
        this.state.inputMessage = "";
        this.state.isLoading = true;

        setTimeout(() => this.scrollToBottom(), 100);

        try {
            const result = await this.orm.call(
                'hr.coaching.session',
                'action_send_ai_message',
                [recordId],
                {
                    message: messageContent
                }
            );

            const assistantMessage = {
                role: 'assistant',
                content: result.response || 'No response received',
                timestamp: new Date().toISOString()
            };

            this.state.messages.push(assistantMessage);

            // Save updated transcript
            await this.saveTranscript();

            setTimeout(() => this.scrollToBottom(), 100);
        } catch (error) {
            console.error('Error sending message:', error);
            this.notification.add(
                'Failed to send message to AI coach. Please try again.',
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Save transcript back to record
     */
    async saveTranscript() {
        const recordId = this.recordId;
        if (!recordId) {
            console.warn('Cannot save transcript: No record ID');
            return;
        }

        const transcript = JSON.stringify({
            messages: this.state.messages,
            updated_at: new Date().toISOString()
        });

        await this.orm.write(
            'hr.coaching.session',
            [recordId],
            { ai_transcript: transcript }
        );
    }

    /**
     * Generate AI summary
     */
    async generateSummary() {
        const recordId = this.recordId;
        if (!recordId) {
            this.notification.add('Cannot generate summary: No record ID', { type: 'danger' });
            return;
        }

        this.state.isLoading = true;
        try {
            const result = await this.orm.call(
                'hr.coaching.session',
                'action_generate_ai_summary',
                [recordId]
            );

            this.notification.add(
                result.message || 'Summary generated successfully',
                { type: 'success' }
            );

            // Reload the record to show updated summary
            const record = this.record;
            if (record && record.load) {
                await record.load();
            }
        } catch (error) {
            console.error('Error generating summary:', error);
            this.notification.add(
                'Failed to generate summary. Please try again.',
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Handle Enter key in input
     */
    onKeydown(ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    /**
     * Toggle expanded view
     */
    toggleExpanded() {
        this.state.isExpanded = !this.state.isExpanded;
        setTimeout(() => this.scrollToBottom(), 100);
    }

    /**
     * Scroll chat to bottom
     */
    scrollToBottom() {
        if (this.chatEndRef.el) {
            this.chatEndRef.el.scrollIntoView({ behavior: 'smooth' });
        }
    }

    /**
     * Format timestamp for display
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Clear chat history
     */
    async clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            this.state.messages = [];
            await this.saveTranscript();
            this.notification.add('Chat history cleared', { type: 'info' });
        }
    }
}

registry.category("fields").add("ai_coaching_chat", AiCoachingChatWidget);
