/** @odoo-module **/

import { Component, useState, onWillStart, useRef, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

/**
 * BFSI AI Coach Panel - Persistent sidebar component for AI coaching
 *
 * Features:
 * - Always visible on desktop (right sidebar)
 * - Bottom sheet on mobile
 * - Context-aware KPI display
 * - Quick action buttons
 * - Real-time AI coaching chat
 */
export class BfsiAiCoachPanel extends Component {
    static template = "hr_development_ai.BfsiAiCoachPanel";
    static props = {
        isManager: { type: Boolean, optional: true },
        employeeId: { type: Number, optional: true },
        branchId: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.chatEndRef = useRef("chatEnd");
        this.panelRef = useRef("panel");

        this.state = useState({
            // Access control
            hasAccess: false,

            // Panel state
            isOpen: true,
            isMinimized: false,
            isMobile: window.innerWidth < 768,

            // Chat state
            messages: [],
            inputMessage: "",
            isLoading: false,
            isTyping: false,

            // Context data
            employeeData: null,
            kpiData: null,
            actionPlans: [],
            coachingStrategies: [],

            // Quick actions
            showQuickActions: true,

            // Session tracking
            currentSessionId: null,
            sessionType: 'general', // 'general', 'kpi_review', 'action_plan', 'coaching'
        });

        // Check if user is manager
        this.isManager = this.props.isManager || false;

        onWillStart(async () => {
            // Check if user belongs to BFSI coaching groups
            try {
                const hasGroup = await user.hasGroup('hr_development_ai.group_bfsi_banker');
                this.state.hasAccess = hasGroup;
            } catch {
                this.state.hasAccess = false;
            }
            if (!this.state.hasAccess) {
                return; // Skip loading data if no access
            }
            await this.loadUserContext();
            await this.loadKpiData();
            await this.loadInitialGreeting();
        });

        onMounted(() => {
            this.handleResize = this.handleResize.bind(this);
            window.addEventListener('resize', this.handleResize);
            this.scrollToBottom();
        });

        onWillUnmount(() => {
            window.removeEventListener('resize', this.handleResize);
        });
    }

    /**
     * Handle window resize for responsive behavior
     */
    handleResize() {
        const wasMobile = this.state.isMobile;
        this.state.isMobile = window.innerWidth < 768;

        // Auto-minimize on mobile if was open on desktop
        if (!wasMobile && this.state.isMobile && this.state.isOpen) {
            this.state.isMinimized = true;
        }
    }

    /**
     * Load current user context (employee data, role)
     */
    async loadUserContext() {
        try {
            const userId = user.userId;

            // Get employee for current user
            const employees = await this.orm.searchRead(
                'hr.employee',
                [['user_id', '=', userId]],
                ['id', 'name', 'branch_id', 'banker_type', 'job_id', 'department_id',
                    'current_month_rank', 'rank_movement', 'latest_overall_score',
                    'coaching_priority', 'ai_coaching_enabled'],
                { limit: 1 }
            );

            if (employees.length > 0) {
                this.state.employeeData = employees[0];
                this.isManager = employees[0].banker_type === 'branch_manager' ||
                    employees[0].banker_type === 'regional_manager';
            }
        } catch (error) {
            console.error('Error loading user context:', error);
        }
    }

    /**
     * Load KPI data for context display
     */
    async loadKpiData() {
        if (!this.state.employeeData) return;

        try {
            const employeeId = this.props.employeeId || this.state.employeeData.id;

            // Get latest KPI record
            const kpis = await this.orm.searchRead(
                'bfsi.performance.kpi',
                [['employee_id', '=', employeeId]],
                ['period_date', 'overall_score', 'deviation_score', 'coaching_priority',
                    'dials_per_hour', 'meetings_scheduled', 'calls_made',
                    'script_adherence', 'objection_handling_score', 'need_analysis_quality',
                    'conversions', 'products_sold', 'appointments_set',
                    'revenue', 'aum', 'branch_rank', 'rank_movement'],
                { limit: 1, order: 'period_date desc' }
            );

            if (kpis.length > 0) {
                this.state.kpiData = kpis[0];
            }

            // Load action plans
            const actionPlans = await this.orm.searchRead(
                'bfsi.action.plan',
                [['employee_id', '=', employeeId], ['state', 'in', ['committed', 'in_progress']]],
                ['name', 'state', 'progress_percentage', 'target_date'],
                { limit: 3 }
            );
            this.state.actionPlans = actionPlans;

        } catch (error) {
            console.error('Error loading KPI data:', error);
        }
    }

    /**
     * Load initial AI greeting based on context
     */
    async loadInitialGreeting() {
        const greeting = this.generateContextualGreeting();

        this.state.messages.push({
            role: 'assistant',
            content: greeting,
            timestamp: new Date().toISOString(),
            isGreeting: true
        });
    }

    /**
     * Generate context-aware greeting
     */
    generateContextualGreeting() {
        const name = this.state.employeeData?.name || 'there';
        const hour = new Date().getHours();
        let timeGreeting = 'Hello';

        if (hour < 12) timeGreeting = 'Good morning';
        else if (hour < 17) timeGreeting = 'Good afternoon';
        else timeGreeting = 'Good evening';

        let greeting = `${timeGreeting}, ${name}! I'm your AI Performance Coach.`;

        // Add context based on KPI data
        if (this.state.kpiData) {
            const score = this.state.kpiData.overall_score;
            const priority = this.state.kpiData.coaching_priority;

            if (score >= 90) {
                greeting += ` Great job! Your performance score is ${score}%. Keep up the excellent work!`;
            } else if (score >= 70) {
                greeting += ` Your current performance score is ${score}%. I have some suggestions to help you improve.`;
            } else if (score > 0) {
                greeting += ` I notice your performance score is ${score}%. Let's work together on a plan to boost your results.`;
            }

            if (priority === 'high') {
                greeting += ` I have some targeted coaching ready for you.`;
            }
        }

        // Add action plan reminder
        if (this.state.actionPlans.length > 0) {
            const inProgress = this.state.actionPlans.filter(p => p.state === 'in_progress').length;
            if (inProgress > 0) {
                greeting += ` You have ${inProgress} active action plan${inProgress > 1 ? 's' : ''} to work on.`;
            }
        }

        greeting += '\n\nHow can I help you today?';
        return greeting;
    }

    /**
     * Toggle panel open/close
     */
    togglePanel() {
        if (this.state.isMobile) {
            this.state.isMinimized = !this.state.isMinimized;
        } else {
            this.state.isOpen = !this.state.isOpen;
        }
    }

    /**
     * Minimize/maximize panel
     */
    toggleMinimize() {
        this.state.isMinimized = !this.state.isMinimized;
    }

    /**
     * Send message to AI coach
     */
    async sendMessage() {
        if (!this.state.inputMessage.trim() || this.state.isLoading) {
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
        this.state.isTyping = true;

        setTimeout(() => this.scrollToBottom(), 100);

        try {
            // Prepare context for AI
            const context = {
                employee_id: this.state.employeeData?.id,
                is_manager: this.isManager,
                kpi_data: this.state.kpiData,
                action_plans: this.state.actionPlans,
                session_type: this.state.sessionType,
                conversation_history: this.state.messages.slice(-10) // Last 10 messages for context
            };

            const result = await this.orm.call(
                'hr.employee',
                'action_ai_coach_chat',
                [this.state.employeeData?.id || []],
                {
                    message: messageContent,
                    context: context
                }
            );

            this.state.isTyping = false;

            const assistantMessage = {
                role: 'assistant',
                content: result.response || 'I apologize, but I could not generate a response. Please try again.',
                timestamp: new Date().toISOString(),
                actions: result.suggested_actions || [],
                learning_content: result.learning_content || null
            };

            this.state.messages.push(assistantMessage);
            setTimeout(() => this.scrollToBottom(), 100);

        } catch (error) {
            console.error('Error sending message:', error);
            this.state.isTyping = false;

            this.state.messages.push({
                role: 'assistant',
                content: 'I apologize, but there was an error processing your message. Please try again.',
                timestamp: new Date().toISOString(),
                isError: true
            });

            this.notification.add(
                'Failed to send message. Please try again.',
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Handle keyboard events
     */
    onKeydown(ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
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
     * Format timestamp
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Parse markdown content to rich HTML for world-class AI chat display.
     * Handles: headers, bold, italic, code blocks, inline code,
     * numbered lists, bullet lists, blockquotes, horizontal rules.
     */
    formatMarkdown(text) {
        if (!text) return markup('');

        // Escape HTML entities first for safety
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks (``` ... ```)
        html = html.replace(/```([\s\S]*?)```/g, '<pre class="ai-code-block"><code>$1</code></pre>');

        // Inline code (`...`)
        html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');

        // Headers (### h3, ## h2, # h1)
        html = html.replace(/^### (.+)$/gm, '<h4 class="ai-heading">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="ai-heading">$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2 class="ai-heading">$1</h2>');

        // Bold + Italic (***text*** or ___text___)
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');

        // Bold (**text** or __text__)
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

        // Italic (*text* or _text_)
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        html = html.replace(/_([^_]+)_/g, '<em>$1</em>');

        // Blockquotes (> text)
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="ai-blockquote">$1</blockquote>');

        // Horizontal rules (--- or ***)
        html = html.replace(/^(---|\*\*\*)$/gm, '<hr class="ai-divider"/>');

        // Numbered items: each `\d+. text` becomes a CSS-counter div
        // This ensures numbering persists across the entire message
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<div class="ai-numbered-item">$1</div>');

        // Bullet lists: convert consecutive bullet lines into <ul>
        html = html.replace(/((?:^[\-\*•]\s.+$\n?)+)/gm, (match) => {
            const items = match.trim().split('\n').map(line => {
                const content = line.replace(/^[\-\*•]\s/, '');
                return `<li>${content}</li>`;
            }).join('');
            return `<ul class="ai-list ai-bullet-list">${items}</ul>`;
        });

        // Paragraphs: double newlines become paragraph breaks
        html = html.replace(/\n\n+/g, '</p><p class="ai-paragraph">');
        // Single newlines become line breaks (but not inside lists/code)
        html = html.replace(/\n/g, '<br/>');

        // Wrap in paragraph
        html = `<p class="ai-paragraph">${html}</p>`;

        // Clean up empty paragraphs
        html = html.replace(/<p class="ai-paragraph">\s*<\/p>/g, '');

        return markup(html);
    }

    /**
     * Quick action handlers
     */
    async onQuickAction(actionType) {
        let message = '';

        switch (actionType) {
            case 'check_kpis':
                message = 'Show me my current KPIs and performance metrics';
                this.state.sessionType = 'kpi_review';
                break;
            case 'action_plan':
                message = 'Help me review my action plan progress';
                this.state.sessionType = 'action_plan';
                break;
            case 'get_coaching':
                message = 'I need coaching advice for improving my performance';
                this.state.sessionType = 'coaching';
                break;
            case 'log_activity':
                message = 'I want to log my sales activity for today';
                break;
            case 'difficult_scenario':
                message = 'I need help handling a difficult customer scenario';
                break;
            case 'micro_learning':
                message = 'Suggest some quick learning content based on my performance gaps';
                break;
        }

        if (message) {
            this.state.inputMessage = message;
            await this.sendMessage();
        }
    }

    /**
     * Manager-specific quick actions
     */
    async onManagerQuickAction(actionType) {
        let message = '';

        switch (actionType) {
            case 'team_overview':
                message = 'Show me my team\'s performance overview';
                break;
            case 'needs_coaching':
                message = 'Who on my team needs coaching attention today?';
                break;
            case 'generate_strategy':
                message = 'Help me prepare a coaching strategy for my team';
                break;
            case 'practice_roleplay':
                message = 'I want to practice a coaching conversation';
                break;
        }

        if (message) {
            this.state.inputMessage = message;
            await this.sendMessage();
        }
    }

    /**
     * Open full dashboard
     */
    openDashboard() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'My Performance',
            res_model: 'bfsi.performance.kpi',
            view_mode: 'list,form',
            domain: [['employee_id', '=', this.state.employeeData?.id]],
            context: { default_employee_id: this.state.employeeData?.id }
        });
    }

    /**
     * Open action plans
     */
    openActionPlans() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'My Action Plans',
            res_model: 'bfsi.action.plan',
            view_mode: 'kanban,list,form',
            domain: [['employee_id', '=', this.state.employeeData?.id]],
        });
    }

    /**
     * Clear chat history
     */
    async clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            this.state.messages = [];
            this.state.showQuickActions = true;
            await this.loadInitialGreeting();
            this.notification.add('Chat history cleared', { type: 'info' });
        }
    }

    /**
     * Get performance badge class
     */
    getPerformanceBadgeClass(score) {
        if (score >= 90) return 'bg-success';
        if (score >= 70) return 'bg-warning';
        if (score >= 50) return 'bg-danger';
        return 'bg-secondary';
    }

    /**
     * Get rank movement icon
     */
    getRankMovementIcon(movement) {
        if (movement > 0) return 'fa-arrow-up text-success';
        if (movement < 0) return 'fa-arrow-down text-danger';
        return 'fa-minus text-muted';
    }
}

// Register as a systray item for persistent access
// Note: Access control is handled inside the component's onWillStart
// because systray isDisplayed is called synchronously and cannot be async.
registry.category("systray").add("bfsi_ai_coach", {
    Component: BfsiAiCoachPanel,
}, { sequence: 100 });
