/**
 * VAFHS Healthcare - Assignment Dashboard JavaScript (Odoo 18)
 * Mobile-First Interactive Dashboard for Staff Assignment Management
 * Using OWL Framework and Modern ES6 Modules
 */

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// ============================================================================
// Assignment Dashboard Controller (Odoo 18 OWL)
// ============================================================================

export class AssignmentDashboardController extends KanbanController {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        
        // Initialize dashboard features
        this.initializeRealTimeUpdates();
        this.setupMobileOptimizations();
        this.initializeDragAndDrop();
        this.setupKeyboardShortcuts();
    }

    // ========================================================================
    // Real-time Updates
    // ========================================================================

    initializeRealTimeUpdates() {
        // Auto-refresh every 30 seconds for real-time updates
        this.refreshInterval = setInterval(() => {
            this.model.load();
        }, 30000);
    }

    // ========================================================================
    // Mobile Optimizations
    // ========================================================================

    setupMobileOptimizations() {
        // Touch-friendly interactions
        if ('ontouchstart' in window) {
            document.body.classList.add('o_touch_device');
        }
        
        // Responsive columns
        this.updateColumnLayout();
        window.addEventListener('resize', () => this.updateColumnLayout());
    }

    updateColumnLayout() {
        const container = document.querySelector('.o_kanban_dashboard');
        if (!container) return;
        
        const width = window.innerWidth;
        if (width < 768) {
            container.classList.add('o_mobile_view');
            container.classList.remove('o_desktop_view');
        } else {
            container.classList.add('o_desktop_view');
            container.classList.remove('o_mobile_view');
        }
    }

    // ========================================================================
    // Drag and Drop System
    // ========================================================================

    initializeDragAndDrop() {
        // Enable drag and drop for assignment cards
        this.setupDragListeners();
        this.setupDropZones();
    }

    setupDragListeners() {
        document.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('o_draggable_assignment')) {
                this.handleDragStart(e);
            }
        });

        document.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('o_draggable_assignment')) {
                this.handleDragEnd(e);
            }
        });
    }

    setupDropZones() {
        document.addEventListener('dragover', (e) => {
            const dropZone = e.target.closest('.o_kanban_group');
            if (dropZone) {
                e.preventDefault();
                dropZone.classList.add('o_drag_over');
            }
        });

        document.addEventListener('dragleave', (e) => {
            const dropZone = e.target.closest('.o_kanban_group');
            if (dropZone) {
                dropZone.classList.remove('o_drag_over');
            }
        });

        document.addEventListener('drop', (e) => {
            const dropZone = e.target.closest('.o_kanban_group');
            if (dropZone) {
                e.preventDefault();
                this.handleDrop(e, dropZone);
            }
        });
    }

    handleDragStart(e) {
        const assignmentCard = e.target;
        const assignmentId = assignmentCard.dataset.assignmentId;
        
        e.dataTransfer.setData('text/plain', assignmentId);
        e.dataTransfer.effectAllowed = 'move';
        
        assignmentCard.classList.add('dragging');
        
        // Create ghost element
        const ghost = assignmentCard.cloneNode(true);
        ghost.classList.add('drag-ghost');
        document.body.appendChild(ghost);
        e.dataTransfer.setDragImage(ghost, 0, 0);
        
        setTimeout(() => document.body.removeChild(ghost), 0);
    }

    handleDragEnd(e) {
        e.target.classList.remove('dragging');
        document.querySelectorAll('.o_drag_over').forEach(el => {
            el.classList.remove('o_drag_over');
        });
    }

    async handleDrop(e, dropZone) {
        const assignmentId = e.dataTransfer.getData('text/plain');
        const newState = dropZone.dataset.groupValue;
        
        dropZone.classList.remove('o_drag_over');
        
        try {
            await this.rpc("/web/dataset/call_kw/health.staff.assignment/write", {
                model: 'health.staff.assignment',
                method: 'write',
                args: [[parseInt(assignmentId)], {state: newState}],
                kwargs: {}
            });
            
            this.notification.add(_t('Assignment status updated successfully'), {
                type: 'success'
            });
            
            // Refresh the view
            this.model.load();
            
        } catch (error) {
            this.notification.add(_t('Error updating assignment status'), {
                type: 'danger'
            });
        }
    }

    // ========================================================================
    // Keyboard Shortcuts
    // ========================================================================

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            switch(e.key) {
                case 'r':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.model.load();
                    }
                    break;
                case 'n':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.createNewAssignment();
                    }
                    break;
            }
        });
    }

    // ========================================================================
    // Action Handlers
    // ========================================================================

    async onAssignStaffClick(e) {
        const assignmentId = e.target.closest('[data-assignment-id]').dataset.assignmentId;
        // Handle staff assignment logic
        console.log('Assign staff for assignment:', assignmentId);
    }

    async onConfirmAssignmentClick(e) {
        const assignmentId = e.target.closest('[data-assignment-id]').dataset.assignmentId;
        try {
            await this.rpc("/web/dataset/call_kw/health.staff.assignment/action_confirm_assignment", {
                model: 'health.staff.assignment',
                method: 'action_confirm_assignment',
                args: [[parseInt(assignmentId)]],
                kwargs: {}
            });
            this.model.load();
        } catch (error) {
            this.notification.add(_t('Error confirming assignment'), {type: 'danger'});
        }
    }

    async onStartAssignmentClick(e) {
        const assignmentId = e.target.closest('[data-assignment-id]').dataset.assignmentId;
        try {
            await this.rpc("/web/dataset/call_kw/health.staff.assignment/action_start_assignment", {
                model: 'health.staff.assignment',
                method: 'action_start_assignment',
                args: [[parseInt(assignmentId)]],
                kwargs: {}
            });
            this.model.load();
        } catch (error) {
            this.notification.add(_t('Error starting assignment'), {type: 'danger'});
        }
    }

    async onCompleteAssignmentClick(e) {
        const assignmentId = e.target.closest('[data-assignment-id]').dataset.assignmentId;
        try {
            await this.rpc("/web/dataset/call_kw/health.staff.assignment/action_complete_assignment", {
                model: 'health.staff.assignment',
                method: 'action_complete_assignment',
                args: [[parseInt(assignmentId)]],
                kwargs: {}
            });
            this.model.load();
        } catch (error) {
            this.notification.add(_t('Error completing assignment'), {type: 'danger'});
        }
    }

    async onAISuggestClick(e) {
        const assignmentId = e.target.closest('[data-assignment-id]').dataset.assignmentId;
        try {
            const suggestions = await this.rpc("/web/dataset/call_kw/health.staff.assignment/action_get_ai_suggestions", {
                model: 'health.staff.assignment',
                method: 'action_get_ai_suggestions',
                args: [[parseInt(assignmentId)]],
                kwargs: {}
            });
            this.showAISuggestions(suggestions);
        } catch (error) {
            this.notification.add(_t('Error getting AI suggestions'), {type: 'danger'});
        }
    }

    showAISuggestions(suggestions) {
        // Display AI suggestions in a dialog
        console.log('AI Suggestions:', suggestions);
    }

    createNewAssignment() {
        // Handle new assignment creation
        console.log('Create new assignment');
    }

    // Cleanup
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        super.destroy();
    }
}

// ============================================================================
// Assignment Dashboard View (Odoo 18)
// ============================================================================

export class AssignmentDashboardView extends KanbanView {}

AssignmentDashboardView.type = "assignment_dashboard_kanban";
AssignmentDashboardView.Controller = AssignmentDashboardController;

// Register the view in Odoo 18 registry
registry.category("views").add("assignment_dashboard_kanban", AssignmentDashboardView);