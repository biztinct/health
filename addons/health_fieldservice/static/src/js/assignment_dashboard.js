/**
 * VAFHS Healthcare - Assignment Dashboard JavaScript (Odoo 19)
 * Mobile-First Interactive Dashboard for Staff Assignment Management
 * Using simplified approach for compatibility
 */

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// ============================================================================
// Assignment Dashboard Enhancement (Simplified Approach)
// ============================================================================

class AssignmentDashboardEnhancer {
    constructor() {
        this.isInitialized = false;
        this.refreshInterval = null;
    }

    init() {
        if (this.isInitialized) return;
        
        this.initializeDashboard();
        this.isInitialized = true;
    }

    initializeDashboard() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.setupFeatures();
            });
        } else {
            this.setupFeatures();
        }
    }

    setupFeatures() {
        this.initializeRealTimeUpdates();
        this.setupMobileOptimizations();
        this.initializeDragAndDrop();
        this.setupKeyboardShortcuts();
        this.enhanceKanbanCards();
    }

    // ========================================================================
    // Real-time Updates
    // ========================================================================

    initializeRealTimeUpdates() {
        // Auto-refresh every 30 seconds for real-time updates
        this.refreshInterval = setInterval(() => {
            const refreshButton = document.querySelector('.o_cp_buttons .btn[title*="refresh"], .o_cp_buttons .fa-refresh');
            if (refreshButton) {
                refreshButton.click();
            }
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
        const container = document.querySelector('.o_kanban_view, .o_content');
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
            if (e.target.closest('.o_kanban_record')) {
                this.handleDragStart(e);
            }
        });

        document.addEventListener('dragend', (e) => {
            if (e.target.closest('.o_kanban_record')) {
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
        const record = e.target.closest('.o_kanban_record');
        if (!record) return;
        
        const recordId = record.dataset.id;
        e.dataTransfer.setData('text/plain', recordId);
        e.dataTransfer.effectAllowed = 'move';
        
        record.classList.add('dragging');
    }

    handleDragEnd(e) {
        const record = e.target.closest('.o_kanban_record');
        if (record) {
            record.classList.remove('dragging');
        }
        document.querySelectorAll('.o_drag_over').forEach(el => {
            el.classList.remove('o_drag_over');
        });
    }

    handleDrop(e, dropZone) {
        const recordId = e.dataTransfer.getData('text/plain');
        const newState = dropZone.dataset.groupValue;
        
        dropZone.classList.remove('o_drag_over');
        
        if (!recordId || !newState) return;
        
        console.log('Assignment status update:', { recordId, newState });
        // Status update would be handled by standard Odoo mechanisms
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
                        const refreshButton = document.querySelector('.o_cp_buttons .btn[title*="refresh"], .o_cp_buttons .fa-refresh');
                        if (refreshButton) {
                            refreshButton.click();
                        }
                    }
                    break;
                case 'n':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        const createButton = document.querySelector('.o_cp_buttons .btn-primary, .o_list_button_add');
                        if (createButton) {
                            createButton.click();
                        }
                    }
                    break;
            }
        });
    }

    // ========================================================================
    // Kanban Card Enhancement
    // ========================================================================

    enhanceKanbanCards() {
        // Safely setup mutation observer
        this.setupKanbanObserver();

        // Enhance existing cards
        this.enhanceExistingCards();
    }

    setupKanbanObserver() {
        const setupObserver = () => {
            if (!document.body) {
                setTimeout(setupObserver, 100);
                return;
            }

            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1 && (node.classList?.contains('o_kanban_record') || node.querySelector?.('.o_kanban_record'))) {
                            this.enhanceCard(node);
                        }
                    });
                });
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        };

        setupObserver();
    }

    enhanceExistingCards() {
        // Wait for DOM to be ready before enhancing existing cards
        const enhanceCards = () => {
            document.querySelectorAll('.o_kanban_record').forEach(card => {
                this.enhanceCard(card);
            });
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', enhanceCards);
        } else {
            enhanceCards();
        }
    }

    enhanceCard(cardElement) {
        const card = cardElement.classList?.contains('o_kanban_record') ? cardElement : cardElement.querySelector('.o_kanban_record');
        if (!card || card.dataset.enhanced) return;

        // Add priority indicators
        this.addPriorityIndicators(card);
        
        // Add status badges
        this.addStatusBadges(card);
        
        // Add hover effects
        this.addHoverEffects(card);
        
        card.dataset.enhanced = 'true';
    }

    addPriorityIndicators(card) {
        const priorityField = card.querySelector('[name="priority"], .priority');
        if (!priorityField) return;

        const priority = priorityField.textContent?.trim().toLowerCase();
        const priorityClasses = {
            'emergency': 'text-danger',
            'urgent': 'text-warning', 
            'high': 'text-info',
            'normal': 'text-muted',
            'low': 'text-secondary'
        };

        const priorityClass = priorityClasses[priority] || 'text-muted';
        priorityField.className += ` ${priorityClass} font-weight-bold`;
    }

    addStatusBadges(card) {
        const statusField = card.querySelector('[name="state"], .state');
        if (!statusField) return;

        const status = statusField.textContent?.trim().toLowerCase();
        const statusClasses = {
            'completed': 'badge-success',
            'in_progress': 'badge-warning',
            'assigned': 'badge-info',
            'draft': 'badge-secondary',
            'cancelled': 'badge-danger'
        };

        const statusClass = statusClasses[status] || 'badge-secondary';
        statusField.className += ` badge ${statusClass}`;
    }

    addHoverEffects(card) {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-2px)';
            card.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
            card.style.transition = 'all 0.2s ease';
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '';
        });
    }

    // Cleanup
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// ============================================================================
// Safe Dashboard Enhancer Initialization
// ============================================================================

const initializeDashboardEnhancer = () => {
    const dashboardEnhancer = new AssignmentDashboardEnhancer();
    
    // Initialize when the module loads
    dashboardEnhancer.init();
    
    // Make it available globally for debugging
    window.AssignmentDashboardEnhancer = dashboardEnhancer;
    
    // Register utility functions in Odoo registry
    registry.category("assignment_dashboard_utils").add("enhancer", dashboardEnhancer);
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboardEnhancer);
} else {
    // DOM is already ready
    initializeDashboardEnhancer();
}
