/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

/**
 * BFSI Manager Dashboard - Team Performance Overview
 *
 * Features:
 * - Team ranking with movement indicators
 * - "Needs Coaching" badge count
 * - One-click coaching initiation
 * - Performance trends visualization
 * - Quick strategy generation
 */
export class BfsiManagerDashboard extends Component {
    static template = "hr_development_ai.BfsiManagerDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");

        this.state = useState({
            // Dashboard state
            isLoading: true,
            error: null,

            // Manager info
            managerId: null,
            managerName: '',
            branchId: null,
            branchName: '',

            // Team data
            teamMembers: [],
            needsCoachingCount: 0,

            // Summary metrics
            avgTeamScore: 0,
            totalSessions: 0,
            actionPlanCompletion: 0,

            // Filters
            sortBy: 'rank',
            sortOrder: 'asc',
            filterPriority: 'all',

            // View state
            selectedBanker: null,
        });

        onWillStart(async () => {
            await this.loadManagerContext();
            await this.loadTeamData();
        });

        onMounted(() => {
            this.state.isLoading = false;
        });
    }

    /**
     * Load manager context
     */
    async loadManagerContext() {
        try {
            const userId = this.user.userId;

            // Get manager's employee record
            const employees = await this.orm.searchRead(
                'hr.employee',
                [['user_id', '=', userId]],
                ['id', 'name', 'branch_id', 'banker_type'],
                { limit: 1 }
            );

            if (employees.length > 0 && employees[0].branch_id) {
                this.state.managerId = employees[0].id;
                this.state.managerName = employees[0].name;
                this.state.branchId = employees[0].branch_id[0];
                this.state.branchName = employees[0].branch_id[1];
            }
        } catch (error) {
            console.error('Error loading manager context:', error);
            this.state.error = 'Failed to load manager information';
        }
    }

    /**
     * Load team data with performance metrics
     */
    async loadTeamData() {
        if (!this.state.branchId) {
            this.state.error = 'No branch assigned';
            return;
        }

        try {
            // Get all bankers in the branch
            const bankers = await this.orm.searchRead(
                'hr.employee',
                [
                    ['branch_id', '=', this.state.branchId],
                    ['banker_type', 'not in', ['branch_manager', 'regional_manager']],
                    ['id', '!=', this.state.managerId]
                ],
                ['id', 'name', 'job_id', 'banker_type', 'current_month_rank',
                 'previous_month_rank', 'rank_movement', 'latest_overall_score',
                 'coaching_priority', 'coaching_sessions_received', 'active_action_plan_count',
                 'action_plan_completion_rate'],
                { order: 'current_month_rank asc' }
            );

            // Enhance with latest KPI details
            for (const banker of bankers) {
                const kpis = await this.orm.searchRead(
                    'bfsi.performance.kpi',
                    [['employee_id', '=', banker.id]],
                    ['overall_score', 'deviation_score', 'conversions', 'revenue',
                     'coaching_priority', 'date'],
                    { limit: 1, order: 'date desc' }
                );

                if (kpis.length > 0) {
                    banker.latestKpi = kpis[0];
                }
            }

            this.state.teamMembers = bankers;

            // Calculate summary metrics
            this.state.needsCoachingCount = bankers.filter(
                b => b.coaching_priority === 'high' || b.coaching_priority === 'critical'
            ).length;

            if (bankers.length > 0) {
                this.state.avgTeamScore = bankers.reduce(
                    (sum, b) => sum + (b.latest_overall_score || 0), 0
                ) / bankers.length;

                this.state.totalSessions = bankers.reduce(
                    (sum, b) => sum + (b.coaching_sessions_received || 0), 0
                );

                const withPlans = bankers.filter(b => b.active_action_plan_count > 0);
                if (withPlans.length > 0) {
                    this.state.actionPlanCompletion = withPlans.reduce(
                        (sum, b) => sum + (b.action_plan_completion_rate || 0), 0
                    ) / withPlans.length;
                }
            }

        } catch (error) {
            console.error('Error loading team data:', error);
            this.state.error = 'Failed to load team data';
        }
    }

    /**
     * Get sorted and filtered team members
     */
    get filteredTeam() {
        let team = [...this.state.teamMembers];

        // Filter by priority
        if (this.state.filterPriority !== 'all') {
            team = team.filter(b => b.coaching_priority === this.state.filterPriority);
        }

        // Sort
        team.sort((a, b) => {
            let valA, valB;

            switch (this.state.sortBy) {
                case 'rank':
                    valA = a.current_month_rank || 999;
                    valB = b.current_month_rank || 999;
                    break;
                case 'score':
                    valA = a.latest_overall_score || 0;
                    valB = b.latest_overall_score || 0;
                    break;
                case 'priority':
                    const priorityOrder = { critical: 1, high: 2, medium: 3, low: 4 };
                    valA = priorityOrder[a.coaching_priority] || 5;
                    valB = priorityOrder[b.coaching_priority] || 5;
                    break;
                case 'movement':
                    valA = a.rank_movement || 0;
                    valB = b.rank_movement || 0;
                    break;
                default:
                    valA = a.current_month_rank || 999;
                    valB = b.current_month_rank || 999;
            }

            if (this.state.sortOrder === 'desc') {
                return valB - valA;
            }
            return valA - valB;
        });

        return team;
    }

    /**
     * Get performance badge class
     */
    getScoreBadgeClass(score) {
        if (score >= 90) return 'badge-success';
        if (score >= 75) return 'badge-primary';
        if (score >= 60) return 'badge-warning';
        return 'badge-danger';
    }

    /**
     * Get priority badge class
     */
    getPriorityBadgeClass(priority) {
        switch (priority) {
            case 'critical': return 'badge-danger';
            case 'high': return 'badge-warning';
            case 'medium': return 'badge-info';
            case 'low': return 'badge-success';
            default: return 'badge-secondary';
        }
    }

    /**
     * Get rank movement display
     */
    getRankMovement(movement) {
        if (movement > 0) {
            return { icon: 'fa-arrow-up', class: 'text-success', text: `+${movement}` };
        } else if (movement < 0) {
            return { icon: 'fa-arrow-down', class: 'text-danger', text: movement.toString() };
        }
        return { icon: 'fa-minus', class: 'text-muted', text: '-' };
    }

    /**
     * Sort handlers
     */
    sortBy(field) {
        if (this.state.sortBy === field) {
            this.state.sortOrder = this.state.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.sortBy = field;
            this.state.sortOrder = 'asc';
        }
    }

    /**
     * Filter by priority
     */
    filterByPriority(priority) {
        this.state.filterPriority = priority;
    }

    /**
     * Select banker for coaching
     */
    selectBanker(banker) {
        this.state.selectedBanker = banker;
    }

    /**
     * Start coaching session
     */
    async startCoachingSession(bankerId) {
        try {
            const result = await this.orm.call(
                'hr.employee',
                'action_start_ai_coaching',
                [bankerId]
            );

            this.action.doAction(result);
        } catch (error) {
            console.error('Error starting coaching session:', error);
            this.notification.add('Failed to start coaching session', { type: 'danger' });
        }
    }

    /**
     * Generate coaching strategy
     */
    async generateStrategy(bankerId) {
        try {
            const result = await this.orm.call(
                'hr.employee',
                'action_generate_coaching_strategy',
                [bankerId]
            );

            this.action.doAction(result);
        } catch (error) {
            console.error('Error generating strategy:', error);
            this.notification.add('Failed to generate coaching strategy', { type: 'danger' });
        }
    }

    /**
     * View banker's KPIs
     */
    viewBankerKpis(bankerId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Performance KPIs',
            res_model: 'bfsi.performance.kpi',
            view_mode: 'list,form',
            domain: [['employee_id', '=', bankerId]],
        });
    }

    /**
     * View banker's action plans
     */
    viewBankerActionPlans(bankerId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Action Plans',
            res_model: 'bfsi.action.plan',
            view_mode: 'kanban,list,form',
            domain: [['employee_id', '=', bankerId]],
        });
    }

    /**
     * Refresh dashboard data
     */
    async refresh() {
        this.state.isLoading = true;
        await this.loadTeamData();
        this.state.isLoading = false;
        this.notification.add('Dashboard refreshed', { type: 'success' });
    }

    /**
     * View all strategies
     */
    viewAllStrategies() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Coaching Strategies',
            res_model: 'bfsi.coaching.strategy',
            view_mode: 'list,form',
            domain: [['branch_id', '=', this.state.branchId]],
        });
    }

    /**
     * View all coaching sessions
     */
    viewAllSessions() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Coaching Sessions',
            res_model: 'hr.coaching.session',
            view_mode: 'list,form',
            domain: [['branch_id', '=', this.state.branchId]],
        });
    }
}

// Register as action for menu access
registry.category("actions").add("bfsi_manager_dashboard", BfsiManagerDashboard);
