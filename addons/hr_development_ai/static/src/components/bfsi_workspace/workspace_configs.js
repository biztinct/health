/** @odoo-module **/

/**
 * Declarative config for the reusable BfsiWorkspace.
 * One entry per client action (params.workspace = key).
 *
 * Segment shape:
 *   key, label, icon (Lucide), model, fields[] (searchRead),
 *   order, scopeDomains:{ my(uid,eid), team(uid,eid) } -> domain leaves,
 *   chips:[{ key, label, options:[{v,l}] }] | { key, label, kind:'date', field },
 *   search:[fields] (ilike OR), sorts:[{key,l}],
 *   rowKind, drawer (drawerKind), formAction (xmlid escape hatch)
 */

const ST = {
    session: [
        { v: "scheduled", l: "Scheduled" }, { v: "in_progress", l: "In Progress" },
        { v: "completed", l: "Completed" }, { v: "cancelled", l: "Cancelled" },
    ],
    strategy: [
        { v: "draft", l: "Draft" }, { v: "generated", l: "Generated" },
        { v: "in_use", l: "In Use" }, { v: "completed", l: "Completed" },
    ],
    plan: [
        { v: "draft", l: "Draft" }, { v: "committed", l: "Committed" },
        { v: "in_progress", l: "In Progress" }, { v: "completed", l: "Completed" },
        { v: "overdue", l: "Overdue" }, { v: "cancelled", l: "Cancelled" },
    ],
};

export const WORKSPACE_CONFIGS = {
    coaching: {
        title: "Coaching",
        icon: "handshake",
        scope: { enabled: true, default: "team" },
        segments: [
            {
                key: "plans",
                label: "Action Plans",
                icon: "clipboard-check",
                model: "bfsi.action.plan",
                fields: ["name", "employee_id", "manager_id", "state",
                    "progress_percentage", "action_item_count", "completed_items",
                    "target_date", "is_overdue", "commitment_date"],
                order: "create_date desc",
                scopeDomains: {
                    my: (uid) => [["employee_id.user_id", "=", uid]],
                    team: (uid, eid) => [["manager_id", "=", eid]],
                },
                chips: [
                    { key: "state", label: "Status", options: ST.plan },
                    { key: "__date__", label: "Target date", kind: "date", field: "target_date" },
                ],
                search: ["name", "employee_id"],
                sorts: [
                    { key: "create_date desc", l: "Newest" },
                    { key: "target_date asc", l: "Due soonest" },
                    { key: "progress_percentage desc", l: "Most progress" },
                ],
                rowKind: "plan",
                personField: "employee_id",
                drawer: "plan",
                formAction: "hr_development_ai.action_bfsi_action_plan",
            },
            {
                key: "sessions",
                label: "Sessions",
                icon: "messages-square",
                model: "hr.coaching.session",
                fields: ["name", "employee_id", "coach_id", "session_type",
                    "topic", "state", "session_date", "outcome"],
                order: "session_date desc",
                scopeDomains: {
                    my: (uid) => [["employee_id.user_id", "=", uid]],
                    team: (uid, eid) => [["coach_id", "=", eid]],
                },
                chips: [
                    { key: "state", label: "Status", options: ST.session },
                    {
                        key: "session_type", label: "Type", options: [
                            { v: "ai", l: "AI" }, { v: "human", l: "Human" }, { v: "hybrid", l: "Hybrid" }],
                    },
                    { key: "__date__", label: "Date", kind: "date", field: "session_date" },
                ],
                search: ["name", "employee_id"],
                sorts: [
                    { key: "session_date desc", l: "Newest" },
                    { key: "session_date asc", l: "Oldest" },
                ],
                rowKind: "session",
                personField: "employee_id",
                drawer: "session",
                formAction: "hr_development_ai.action_hr_coaching_session",
            },
            {
                key: "strategies",
                label: "Strategies",
                icon: "brain",
                model: "bfsi.coaching.strategy",
                fields: ["name", "banker_id", "manager_id", "state",
                    "ai_confidence", "kpi_snapshot_date"],
                order: "create_date desc",
                scopeDomains: {
                    my: (uid) => [["banker_id.user_id", "=", uid]],
                    team: (uid, eid) => [["manager_id", "=", eid]],
                },
                chips: [
                    { key: "state", label: "Status", options: ST.strategy },
                ],
                search: ["name", "banker_id"],
                sorts: [
                    { key: "create_date desc", l: "Newest" },
                    { key: "ai_confidence desc", l: "Confidence" },
                ],
                rowKind: "strategy",
                personField: "banker_id",
                drawer: "strategy",
                formAction: "hr_development_ai.action_bfsi_coaching_strategy",
            },
        ],
    },

    performance: {
        title: "Performance",
        icon: "chart-column",
        scope: { enabled: true, default: "team" },
        segments: [
            {
                key: "kpis",
                label: "KPIs",
                icon: "gauge",
                model: "bfsi.performance.kpi",
                fields: ["display_name", "employee_id", "branch_id", "period_date",
                    "overall_score", "branch_rank", "coaching_priority", "revenue", "conversions"],
                order: "period_date desc",
                scopeDomains: {
                    my: (uid) => [["employee_id.user_id", "=", uid]],
                    team: (uid, eid, branchId) => branchId ? [["branch_id", "=", branchId]] : [],
                },
                chips: [
                    {
                        key: "coaching_priority", label: "Priority", options: [
                            { v: "critical", l: "Critical" }, { v: "high", l: "High" },
                            { v: "medium", l: "Medium" }, { v: "low", l: "Low" }],
                    },
                    { key: "__date__", label: "Period", kind: "date", field: "period_date" },
                ],
                search: ["employee_id"],
                sorts: [
                    { key: "period_date desc", l: "Newest" },
                    { key: "overall_score desc", l: "Top score" },
                    { key: "overall_score asc", l: "Lowest score" },
                ],
                rowKind: "kpi",
                personField: "employee_id",
                drawer: "kpi",
                formAction: "hr_development_ai.action_bfsi_performance_kpi",
            },
            {
                key: "targets",
                label: "Targets",
                icon: "target",
                model: "bfsi.kpi.target",
                fields: ["name", "period_type", "target_overall_score", "target_revenue",
                    "valid_from", "is_active"],
                order: "valid_from desc",
                scopeDomains: { my: () => [], team: () => [] },
                chips: [
                    {
                        key: "period_type", label: "Period", options: [
                            { v: "daily", l: "Daily" }, { v: "weekly", l: "Weekly" }, { v: "monthly", l: "Monthly" }],
                    },
                ],
                search: ["name"],
                sorts: [{ key: "valid_from desc", l: "Newest" }],
                rowKind: "target",
                drawer: null,   // -> opens the full record form
                formAction: "hr_development_ai.action_bfsi_kpi_target",
            },
        ],
    },

    organization: {
        title: "Organization",
        icon: "building",
        scope: { enabled: false },
        segments: [
            {
                key: "branches",
                label: "Branches",
                icon: "building",
                model: "bfsi.branch",
                fields: ["name", "code", "region_id", "manager_id",
                    "banker_count", "avg_performance_score", "bankers_needing_coaching"],
                order: "name",
                chips: [],
                search: ["name", "code"],
                sorts: [
                    { key: "name", l: "Name" },
                    { key: "avg_performance_score desc", l: "Top score" },
                ],
                rowKind: "branch",
                drawer: "branch",
                formAction: "hr_development_ai.action_bfsi_branch",
            },
            {
                key: "regions",
                label: "Regions",
                icon: "map-pin",
                model: "bfsi.region",
                fields: ["name", "code", "regional_manager_id", "branch_count"],
                order: "name",
                chips: [],
                search: ["name", "code"],
                sorts: [{ key: "name", l: "Name" }],
                rowKind: "region",
                drawer: "region",
                formAction: "hr_development_ai.action_bfsi_region",
            },
        ],
    },
};
