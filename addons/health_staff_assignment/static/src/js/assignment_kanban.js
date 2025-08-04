/**
 * VAFHS Healthcare - Assignment Kanban JavaScript (Odoo 18)
 * Drag-and-Drop Kanban Board for Assignment Workflow Management
 * Using OWL Framework and Modern ES6 Modules
 */

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// ============================================================================
// Assignment Kanban Record Helpers (Odoo 18)
// ============================================================================

/**
 * Priority badge color mapping
 */
export function getPriorityBadgeClass(priority) {
    const priorityClasses = {
        'low': 'badge-secondary',
        'normal': 'badge-primary', 
        'high': 'badge-warning',
        'urgent': 'badge-danger'
    };
    return priorityClasses[priority] || 'badge-secondary';
}

/**
 * Assignment score color mapping
 */
export function getScoreColor(score) {
    if (score >= 90) return 'text-success';
    if (score >= 70) return 'text-warning';
    return 'text-danger';
}

/**
 * Format assignment duration
 */
export function formatDuration(minutes) {
    if (!minutes) return '';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (hours > 0) {
        return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
}

/**
 * Get status badge class
 */
export function getStatusBadgeClass(state) {
    const statusClasses = {
        'draft': 'badge-secondary',
        'assigned': 'badge-info',
        'confirmed': 'badge-primary',
        'in_progress': 'badge-warning pulse',
        'completed': 'badge-success',
        'cancelled': 'badge-danger'
    };
    return statusClasses[state] || 'badge-secondary';
}

// Register utility functions for use in templates
registry.category("kanban_utils").add("assignment_priority", getPriorityBadgeClass);
registry.category("kanban_utils").add("assignment_score", getScoreColor);
registry.category("kanban_utils").add("assignment_duration", formatDuration);
registry.category("kanban_utils").add("assignment_status", getStatusBadgeClass);