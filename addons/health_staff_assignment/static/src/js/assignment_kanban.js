/**
 * VAFHS Healthcare - Assignment Kanban JavaScript
 * Drag-and-Drop Kanban Board for Assignment Workflow Management
 * Inspired by Monday.com and Asana workflow boards
 */

odoo.define('health_staff_assignment.assignment_kanban', function (require) {
    'use strict';

    const KanbanRenderer = require('web.KanbanRenderer');
    const KanbanRecord = require('web.KanbanRecord');
    const core = require('web.core');
    const rpc = require('web.rpc');
    const Dialog = require('web.Dialog');

    const _t = core._t;

    // ============================================================================
    // Enhanced Assignment Kanban Record
    // ============================================================================

    const AssignmentKanbanRecord = KanbanRecord.extend({
        template: 'health_staff_assignment.AssignmentKanbanRecord',

        events: _.extend({}, KanbanRecord.prototype.events, {
            'click .o_assignment_card': '_onCardClick',
            'click .o_assignment_priority': '_onPriorityClick',
            'click .o_assignment_score': '_onScoreClick',
            'mouseenter .o_assignment_card': '_onCardHover',
            'mouseleave .o_assignment_card': '_onCardLeave',
        }),

        /**
         * @override
         */
        init: function (parent, state, options) {
            this._super.apply(this, arguments);
            this.isDragging = false;
            this.dragStartTime = 0;
        },

        /**
         * @override
         */
        start: function () {
            const def = this._super.apply(this, arguments);
            this._setupDragAndDrop();
            this._setupCardAnimations();
            this._setupMobileOptimizations();
            return def;
        },

        // ========================================================================
        // Drag and Drop Setup
        // ========================================================================

        /**
         * Setup drag and drop functionality
         */
        _setupDragAndDrop: function () {
            const self = this;
            
            // Make card draggable
            this.$el.draggable({
                handle: '.o_assignment_card',
                helper: 'clone',
                revert: 'invalid',
                revertDuration: 200,
                opacity: 0.8,
                zIndex: 1000,
                start: function (event, ui) {
                    self._onDragStart(event, ui);
                },
                drag: function (event, ui) {
                    self._onDrag(event, ui);
                },
                stop: function (event, ui) {
                    self._onDragStop(event, ui);
                }
            });

            // Add visual drag indicators
            this.$el.on('dragstart', function () {
                $(this).addClass('o_dragging');
                $('.o_kanban_group').addClass('o_drag_active');
            });

            this.$el.on('dragend', function () {
                $(this).removeClass('o_dragging');
                $('.o_kanban_group').removeClass('o_drag_active');
            });
        },

        /**
         * Handle drag start
         */
        _onDragStart: function (event, ui) {
            this.isDragging = true;
            this.dragStartTime = Date.now();

            // Add dragging class for visual feedback
            ui.helper.addClass('o_assignment_card_dragging');
            
            // Store original data for potential revert
            this.originalState = this.recordData.state && this.recordData.state.data;
            
            // Show drop zones
            this._showDropZones();
            
            // Track drag analytics
            this._trackDragStart();
        },

        /**
         * Handle drag movement
         */
        _onDrag: function (event, ui) {
            // Update helper position for better mobile experience
            if (this._isMobileDevice()) {
                const touch = event.originalEvent.touches && event.originalEvent.touches[0];
                if (touch) {
                    ui.position.left = touch.clientX - ui.helper.width() / 2;
                    ui.position.top = touch.clientY - ui.helper.height() / 2;
                }
            }
        },

        /**
         * Handle drag stop
         */
        _onDragStop: function (event, ui) {
            this.isDragging = false;
            
            // Remove dragging class
            ui.helper.removeClass('o_assignment_card_dragging');
            
            // Hide drop zones
            this._hideDropZones();
            
            // Track drag analytics
            this._trackDragEnd();
        },

        /**
         * Show drop zones for valid state transitions
         */
        _showDropZones: function () {
            const currentState = this.recordData.state && this.recordData.state.data;
            const validTransitions = this._getValidStateTransitions(currentState);
            
            $('.o_kanban_group').each(function () {
                const groupState = $(this).data('id');
                if (validTransitions.includes(groupState)) {
                    $(this).addClass('o_valid_drop_zone');
                } else {
                    $(this).addClass('o_invalid_drop_zone');
                }
            });
        },

        /**
         * Hide drop zones
         */
        _hideDropZones: function () {
            $('.o_kanban_group').removeClass('o_valid_drop_zone o_invalid_drop_zone');
        },

        /**
         * Get valid state transitions for workflow
         */
        _getValidStateTransitions: function (currentState) {
            const transitions = {
                'draft': ['assigned'],
                'assigned': ['confirmed', 'cancelled'],
                'confirmed': ['in_progress', 'cancelled'],
                'in_progress': ['completed', 'deferred'],
                'completed': [], // No transitions from completed
                'cancelled': ['draft'], // Can restart cancelled assignments
                'deferred': ['assigned', 'cancelled']
            };
            
            return transitions[currentState] || [];
        },

        // ========================================================================
        // Card Interactions
        // ========================================================================

        /**
         * Handle card click
         */
        _onCardClick: function (ev) {
            if (this.isDragging) return;
            
            // If click was on action button, don't open card
            if ($(ev.target).closest('.o_assignment_actions, .dropdown').length > 0) {
                return;
            }
            
            // Open assignment form
            this._openAssignmentForm();
        },

        /**
         * Handle priority indicator click
         */
        _onPriorityClick: function (ev) {
            ev.stopPropagation();
            this._showPriorityMenu(ev.currentTarget);
        },

        /**
         * Handle score badge click
         */
        _onScoreClick: function (ev) {
            ev.stopPropagation();
            this._showScoreBreakdown();
        },

        /**
         * Handle card hover
         */
        _onCardHover: function (ev) {
            if (this.isDragging) return;
            
            // Add hover effects
            this.$('.o_assignment_card').addClass('o_hover');
            
            // Show additional info tooltip
            this._showCardTooltip();
        },

        /**
         * Handle card leave
         */
        _onCardLeave: function (ev) {
            // Remove hover effects
            this.$('.o_assignment_card').removeClass('o_hover');
            
            // Hide tooltip
            this._hideCardTooltip();
        },

        // ========================================================================
        // Card Actions
        // ========================================================================

        /**
         * Open assignment form
         */
        _openAssignmentForm: function () {
            this.trigger_up('open_record', {
                id: this.recordData.id,
                mode: 'edit'
            });
        },

        /**
         * Show priority change menu
         */
        _showPriorityMenu: function (target) {
            const self = this;
            const $target = $(target);
            
            const priorities = [
                { key: '0', label: 'Low Priority', class: 'text-muted', icon: 'fa-minus' },
                { key: '1', label: 'Normal', class: 'text-info', icon: 'fa-circle' },
                { key: '2', label: 'High Priority', class: 'text-warning', icon: 'fa-arrow-up' },
                { key: '3', label: 'Urgent', class: 'text-danger', icon: 'fa-exclamation-circle' },
                { key: '4', label: 'Emergency', class: 'text-danger', icon: 'fa-exclamation-triangle' }
            ];
            
            let menuHtml = '<div class="o_priority_menu">';
            priorities.forEach(priority => {
                menuHtml += `
                    <div class="o_priority_option ${priority.class}" data-priority="${priority.key}">
                        <i class="fa ${priority.icon} mr-2"></i>
                        ${priority.label}
                    </div>
                `;
            });
            menuHtml += '</div>';
            
            // Create and show popup
            const $menu = $(menuHtml);
            $menu.css({
                position: 'absolute',
                top: $target.offset().top + $target.height(),
                left: $target.offset().left,
                zIndex: 1050,
                background: 'white',
                border: '1px solid #ddd',
                borderRadius: '4px',
                padding: '8px 0',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
            });
            
            $('body').append($menu);
            
            // Add click handlers
            $menu.find('.o_priority_option').click(function () {
                const newPriority = $(this).data('priority');
                self._updatePriority(newPriority);
                $menu.remove();
            });
            
            // Remove menu on outside click
            setTimeout(() => {
                $(document).one('click', () => $menu.remove());
            }, 100);
        },

        /**
         * Show assignment score breakdown
         */
        _showScoreBreakdown: function () {
            const scoreData = {
                overall: this.recordData.assignment_score || 0,
                skill: this.recordData.skill_match_score || 0,
                proximity: this.recordData.proximity_score || 0,
                workload: this.recordData.workload_score || 0,
                availability: this.recordData.availability_score || 0
            };
            
            const dialog = new Dialog(this, {
                title: _t('Assignment Score Breakdown'),
                $content: $(this._renderScoreBreakdown(scoreData)),
                size: 'medium',
                buttons: [{
                    text: _t('Close'),
                    close: true
                }]
            });
            
            dialog.open();
        },

        /**
         * Render score breakdown content
         */
        _renderScoreBreakdown: function (scoreData) {
            return `
                <div class="o_score_breakdown">
                    <div class="text-center mb-4">
                        <div class="o_overall_score">
                            <span class="o_score_value">${Math.round(scoreData.overall)}%</span>
                            <div class="o_score_label">Overall Assignment Score</div>
                        </div>
                    </div>
                    
                    <div class="o_score_details">
                        <div class="o_score_item">
                            <div class="o_score_info">
                                <span class="o_score_name">Skill Match</span>
                                <span class="o_score_weight">(40% weight)</span>
                            </div>
                            <div class="o_score_bar">
                                <div class="o_score_fill" style="width: ${scoreData.skill}%"></div>
                            </div>
                            <span class="o_score_percent">${Math.round(scoreData.skill)}%</span>
                        </div>
                        
                        <div class="o_score_item">
                            <div class="o_score_info">
                                <span class="o_score_name">Proximity</span>
                                <span class="o_score_weight">(30% weight)</span>
                            </div>
                            <div class="o_score_bar">
                                <div class="o_score_fill" style="width: ${scoreData.proximity}%"></div>
                            </div>
                            <span class="o_score_percent">${Math.round(scoreData.proximity)}%</span>
                        </div>
                        
                        <div class="o_score_item">
                            <div class="o_score_info">
                                <span class="o_score_name">Workload Balance</span>
                                <span class="o_score_weight">(20% weight)</span>
                            </div>
                            <div class="o_score_bar">
                                <div class="o_score_fill" style="width: ${scoreData.workload}%"></div>
                            </div>
                            <span class="o_score_percent">${Math.round(scoreData.workload)}%</span>
                        </div>
                        
                        <div class="o_score_item">
                            <div class="o_score_info">
                                <span class="o_score_name">Availability</span>
                                <span class="o_score_weight">(10% weight)</span>
                            </div>
                            <div class="o_score_bar">
                                <div class="o_score_fill" style="width: ${scoreData.availability}%"></div>
                            </div>
                            <span class="o_score_percent">${Math.round(scoreData.availability)}%</span>
                        </div>
                    </div>
                    
                    <div class="alert alert-info mt-3">
                        <small>
                            <i class="fa fa-info-circle mr-1"></i>
                            This score is calculated by our AI engine based on staff skills, location, 
                            current workload, and availability buffers.
                        </small>
                    </div>
                </div>
            `;
        },

        /**
         * Update assignment priority
         */
        _updatePriority: function (newPriority) {
            const self = this;
            
            rpc.query({
                model: 'health.staff.assignment',
                method: 'write',
                args: [this.recordData.id, { priority: newPriority }]
            }).then(function () {
                // Update local data and re-render
                self.recordData.priority = newPriority;
                self._updateCardPriority(newPriority);
                
                // Show success notification
                self.displayNotification({
                    type: 'success',
                    title: _t('Priority Updated'),
                    message: _t('Assignment priority has been updated.'),
                });
            }).catch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Failed to update priority: ') + error.message.message,
                });
            });
        },

        /**
         * Update card priority visual indicator
         */
        _updateCardPriority: function (priority) {
            const $card = this.$('.o_assignment_card');
            
            // Remove existing priority classes
            $card.removeClass('o_priority_0 o_priority_1 o_priority_2 o_priority_3 o_priority_4');
            
            // Add new priority class
            $card.addClass(`o_priority_${priority}`);
            
            // Update priority indicator
            const priorityIcons = {
                '0': 'fa-minus text-muted',
                '1': 'fa-circle text-info', 
                '2': 'fa-arrow-up text-warning',
                '3': 'fa-exclamation-circle text-danger',
                '4': 'fa-exclamation-triangle text-danger'
            };
            
            const $priorityIcon = this.$('.o_assignment_priority i');
            $priorityIcon.removeClass().addClass(`fa ${priorityIcons[priority] || priorityIcons['1']}`);
        },

        // ========================================================================
        // Card Animations and Visual Effects
        // ========================================================================

        /**
         * Setup card animations
         */
        _setupCardAnimations: function () {
            // Add entrance animation
            this.$el.addClass('o_assignment_card_enter');
            
            // Trigger animation after brief delay
            setTimeout(() => {
                this.$el.addClass('o_assignment_card_entered');
            }, 100);
        },

        /**
         * Show card tooltip
         */
        _showCardTooltip: function () {
            // Implementation for hover tooltip
            // This would show additional assignment details on hover
        },

        /**
         * Hide card tooltip
         */
        _hideCardTooltip: function () {
            // Implementation for hiding tooltip
        },

        // ========================================================================
        // Mobile Optimizations
        // ========================================================================

        /**
         * Setup mobile-specific optimizations
         */
        _setupMobileOptimizations: function () {
            if (this._isMobileDevice()) {
                this._setupMobileDragAndDrop();
                this._setupMobileGestures();
            }
        },

        /**
         * Setup mobile drag and drop
         */
        _setupMobileDragAndDrop: function () {
            // Disable native drag on mobile, use touch events instead
            this.$el.draggable('destroy');
            
            // Setup touch-based drag and drop
            this._setupTouchDragAndDrop();
        },

        /**
         * Setup touch-based drag and drop
         */
        _setupTouchDragAndDrop: function () {
            let dragData = null;
            
            this.$el.on('touchstart', (ev) => {
                const touch = ev.originalEvent.touches[0];
                dragData = {
                    startX: touch.clientX,
                    startY: touch.clientY,
                    startTime: Date.now(),
                    element: this.$el,
                    moved: false
                };
            });
            
            this.$el.on('touchmove', (ev) => {
                if (!dragData) return;
                
                const touch = ev.originalEvent.touches[0];
                const deltaX = Math.abs(touch.clientX - dragData.startX);
                const deltaY = Math.abs(touch.clientY - dragData.startY);
                
                if (deltaX > 10 || deltaY > 10) {
                    dragData.moved = true;
                    ev.preventDefault(); // Prevent scrolling
                    
                    // Create visual drag feedback
                    this._createMobileDragHelper(touch.clientX, touch.clientY);
                }
            });
            
            this.$el.on('touchend', (ev) => {
                if (!dragData) return;
                
                if (dragData.moved) {
                    // Handle drop
                    const touch = ev.originalEvent.changedTouches[0];
                    this._handleMobileDrop(touch.clientX, touch.clientY);
                }
                
                dragData = null;
                this._removeMobileDragHelper();
            });
        },

        /**
         * Setup mobile gestures (swipe, long press, etc.)
         */
        _setupMobileGestures: function () {
            // Long press for context menu
            let longPressTimer = null;
            
            this.$el.on('touchstart', () => {
                longPressTimer = setTimeout(() => {
                    this._showMobileContextMenu();
                }, 800); // 800ms long press
            });
            
            this.$el.on('touchend touchmove', () => {
                if (longPressTimer) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }
            });
        },

        /**
         * Create mobile drag helper
         */
        _createMobileDragHelper: function (x, y) {
            const $helper = this.$el.clone();
            $helper.addClass('o_mobile_drag_helper');
            $helper.css({
                position: 'fixed',
                left: x - $helper.width() / 2,
                top: y - $helper.height() / 2,
                zIndex: 9999,
                opacity: 0.8,
                transform: 'scale(1.1)',
                pointerEvents: 'none'
            });
            
            $('body').append($helper);
            this.mobileDragHelper = $helper;
        },

        /**
         * Remove mobile drag helper
         */
        _removeMobileDragHelper: function () {
            if (this.mobileDragHelper) {
                this.mobileDragHelper.remove();
                this.mobileDragHelper = null;
            }
        },

        /**
         * Handle mobile drop
         */
        _handleMobileDrop: function (x, y) {
            // Find drop target at coordinates
            const $dropTarget = $(document.elementFromPoint(x, y)).closest('.o_kanban_group');
            
            if ($dropTarget.length) {
                const newState = $dropTarget.data('id');
                this._moveToState(newState);
            }
        },

        /**
         * Show mobile context menu
         */
        _showMobileContextMenu: function () {
            // Show mobile-optimized context menu
            this.displayNotification({
                type: 'info',
                title: _t('Context Menu'),
                message: _t('Mobile context menu coming soon!'),
            });
        },

        /**
         * Move assignment to new state
         */
        _moveToState: function (newState) {
            const currentState = this.recordData.state && this.recordData.state.data;
            
            if (currentState === newState) return;
            
            // Validate state transition
            const validTransitions = this._getValidStateTransitions(currentState);
            if (!validTransitions.includes(newState)) {
                this.displayNotification({
                    type: 'warning',
                    title: _t('Invalid Transition'),
                    message: _t('Cannot move assignment from %s to %s.', currentState, newState),
                });
                return;
            }
            
            // Update assignment state
            rpc.query({
                model: 'health.staff.assignment',
                method: 'write',
                args: [this.recordData.id, { state: newState }]
            }).then(() => {
                this.trigger_up('reload');
            }).catch((error) => {
                this.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Failed to update assignment: ') + error.message.message,
                });
            });
        },

        // ========================================================================
        // Utility Methods
        // ========================================================================

        /**
         * Check if device is mobile
         */
        _isMobileDevice: function () {
            return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                   window.innerWidth < 768;
        },

        /**
         * Track drag start for analytics
         */
        _trackDragStart: function () {
            // Analytics tracking implementation
            console.log('Assignment drag started:', this.recordData.id);
        },

        /**
         * Track drag end for analytics
         */
        _trackDragEnd: function () {
            const dragDuration = Date.now() - this.dragStartTime;
            console.log('Assignment drag ended:', this.recordData.id, 'Duration:', dragDuration + 'ms');
        },

        // ========================================================================
        // Cleanup
        // ========================================================================

        /**
         * @override
         */
        destroy: function () {
            // Clean up mobile drag helper
            this._removeMobileDragHelper();
            
            // Call parent destroy
            return this._super.apply(this, arguments);
        }
    });

    return {
        AssignmentKanbanRecord: AssignmentKanbanRecord,
    };
});