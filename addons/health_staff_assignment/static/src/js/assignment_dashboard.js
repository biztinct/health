/**
 * VAFHS Healthcare - Assignment Dashboard JavaScript
 * Mobile-First Interactive Dashboard for Staff Assignment Management
 * Inspired by Monday.com, Asana, and Uber Driver Dashboard
 */

odoo.define('health_staff_assignment.assignment_dashboard', function (require) {
    'use strict';

    const KanbanController = require('web.KanbanController');
    const KanbanView = require('web.KanbanView');
    const viewRegistry = require('web.view_registry');
    const core = require('web.core');
    const Dialog = require('web.Dialog');
    const rpc = require('web.rpc');

    const _t = core._t;

    // ============================================================================
    // Assignment Dashboard Controller
    // ============================================================================

    const AssignmentDashboardController = KanbanController.extend({
        className: 'o_assignment_dashboard_controller',
        
        events: _.extend({}, KanbanController.prototype.events, {
            'click .o_assign_staff_btn': '_onAssignStaffClick',
            'click .o_confirm_assignment_btn': '_onConfirmAssignmentClick',
            'click .o_start_assignment_btn': '_onStartAssignmentClick',
            'click .o_complete_assignment_btn': '_onCompleteAssignmentClick',
            'click .o_ai_suggest_btn': '_onAISuggestClick',
            'click .dropdown-item[data-assignment-id]': '_onDropdownActionClick'
        }),

        /**
         * @override
         */
        start: function () {
            const def = this._super.apply(this, arguments);
            this._initializeRealTimeUpdates();
            this._setupMobileOptimizations();
            return def;
        },

        // ========================================================================
        // Real-time Updates
        // ========================================================================

        /**
         * Initialize real-time updates for assignment status
         */
        _initializeRealTimeUpdates: function () {
            // Set up polling for real-time status updates
            this.realTimeInterval = setInterval(() => {
                this._updateAssignmentStatuses();
            }, 30000); // Update every 30 seconds

            // Listen for browser visibility changes to optimize polling
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this._pauseRealTimeUpdates();
                } else {
                    this._resumeRealTimeUpdates();
                }
            });
        },

        /**
         * Update assignment statuses in real-time
         */
        _updateAssignmentStatuses: function () {
            const assignmentIds = this._getVisibleAssignmentIds();
            
            if (assignmentIds.length === 0) return;

            rpc.query({
                model: 'health.staff.assignment',
                method: 'read',
                args: [assignmentIds, ['id', 'state', 'real_time_status', 'assignment_score']],
            }).then((assignments) => {
                this._updateAssignmentCards(assignments);
            }).catch((error) => {
                console.warn('Failed to update assignment statuses:', error);
            });
        },

        /**
         * Get IDs of currently visible assignment cards
         */
        _getVisibleAssignmentIds: function () {
            const ids = [];
            this.$('.o_assignment_card[data-assignment-id]').each(function () {
                const id = parseInt($(this).data('assignment-id'));
                if (id) ids.push(id);
            });
            return ids;
        },

        /**
         * Update assignment cards with new data
         */
        _updateAssignmentCards: function (assignments) {
            assignments.forEach(assignment => {
                const $card = this.$(`.o_assignment_card[data-assignment-id="${assignment.id}"]`);
                if ($card.length) {
                    this._updateSingleCard($card, assignment);
                }
            });
        },

        /**
         * Update a single assignment card
         */
        _updateSingleCard: function ($card, assignmentData) {
            // Update status indicator
            const $statusIndicator = $card.find('.o_realtime_status .o_status_indicator');
            if ($statusIndicator.length) {
                $statusIndicator.removeClass().addClass(`o_status_indicator o_status_${assignmentData.real_time_status}`);
                $statusIndicator.find('.o_status_text').text(assignmentData.real_time_status.replace('_', ' ').toUpperCase());
            }

            // Update assignment score
            const $scorebadge = $card.find('.o_assignment_score .badge');
            if ($scorebadge.length && assignmentData.assignment_score) {
                $scoreBadge.text(`${Math.round(assignmentData.assignment_score)}%`);
                
                // Update badge color based on score
                $scorebadge.removeClass('badge-success badge-warning badge-danger');
                if (assignmentData.assignment_score >= 80) {
                    $scorebage.addClass('badge-success');
                } else if (assignmentData.assignment_score >= 60) {
                    $scorebage.addClass('badge-warning');
                } else {
                    $scorebage.addClass('badge-danger');
                }
            }

            // Update action buttons based on state
            this._updateCardActions($card, assignmentData.state);
        },

        /**
         * Update action buttons based on assignment state
         */
        _updateCardActions: function ($card, state) {
            const $actions = $card.find('.o_assignment_actions');
            $actions.find('.btn').hide();

            switch (state) {
                case 'draft':
                    $actions.find('.o_assign_staff_btn').show();
                    break;
                case 'assigned':
                    $actions.find('.o_confirm_assignment_btn').show();
                    break;
                case 'confirmed':
                    $actions.find('.o_start_assignment_btn').show();
                    break;
                case 'in_progress':
                    $actions.find('.o_complete_assignment_btn').show();
                    break;
            }

            // AI suggest and more options are always visible
            $actions.find('.o_ai_suggest_btn, .dropdown').show();
        },

        // ========================================================================
        // Button Click Handlers
        // ========================================================================

        /**
         * Handle assign staff button click
         */
        _onAssignStaffClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const assignmentId = parseInt($(ev.currentTarget).data('assignment-id'));
            this._openStaffAssignmentDialog(assignmentId);
        },

        /**
         * Handle confirm assignment button click
         */
        _onConfirmAssignmentClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const assignmentId = parseInt($(ev.currentTarget).data('assignment-id'));
            this._confirmAssignment(assignmentId);
        },

        /**
         * Handle start assignment button click
         */
        _onStartAssignmentClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const assignmentId = parseInt($(ev.currentTarget).data('assignment-id'));
            this._startAssignment(assignmentId);
        },

        /**
         * Handle complete assignment button click
         */
        _onCompleteAssignmentClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const assignmentId = parseInt($(ev.currentTarget).data('assignment-id'));
            this._completeAssignment(assignmentId);
        },

        /**
         * Handle AI suggestion button click
         */
        _onAISuggestClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const assignmentId = parseInt($(ev.currentTarget).data('assignment-id'));
            this._showAISuggestions(assignmentId);
        },

        /**
         * Handle dropdown action clicks
         */
        _onDropdownActionClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            
            const $target = $(ev.currentTarget);
            const assignmentId = parseInt($target.data('assignment-id'));
            const action = $target.text().trim().toLowerCase();
            
            switch (action) {
                case 'edit assignment':
                    this._editAssignment(assignmentId);
                    break;
                case 'optimize route':
                    this._optimizeRoute(assignmentId);
                    break;
                case 'reschedule':
                    this._rescheduleAssignment(assignmentId);
                    break;
                case 'cancel':
                    this._cancelAssignment(assignmentId);
                    break;
            }
        },

        // ========================================================================
        // Assignment Actions
        // ========================================================================

        /**
         * Open staff assignment dialog with AI suggestions
         */
        _openStaffAssignmentDialog: function (assignmentId) {
            const self = this;
            
            // Show loading
            const $btn = this.$(`.o_assign_staff_btn[data-assignment-id="${assignmentId}"]`);
            const originalText = $btn.html();
            $btn.html('<i class="fa fa-spinner fa-spin mr-1"></i>Loading...');
            $btn.prop('disabled', true);

            // Get AI suggestions first
            rpc.query({
                model: 'health.staff.assignment.engine',
                method: 'get_optimal_staff_suggestions',
                args: [assignmentId]
            }).then(function (suggestions) {
                // Restore button
                $btn.html(originalText);
                $btn.prop('disabled', false);
                
                // Show assignment dialog with suggestions
                self._showStaffAssignmentDialog(assignmentId, suggestions);
            }).catch(function (error) {
                // Restore button
                $btn.html(originalText);
                $btn.prop('disabled', false);
                
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Failed to load staff suggestions: ') + error.message.message,
                });
            });
        },

        /**
         * Show staff assignment dialog with AI suggestions
         */
        _showStaffAssignmentDialog: function (assignmentId, suggestions) {
            const self = this;
            
            // Create dialog content
            let dialogContent = `
                <div class="o_staff_assignment_dialog">
                    <h4 class="mb-3">
                        <i class="fa fa-magic text-primary mr-2"></i>
                        AI-Powered Staff Suggestions
                    </h4>
            `;

            if (suggestions && suggestions.length > 0) {
                dialogContent += `
                    <div class="alert alert-info">
                        <i class="fa fa-info-circle mr-2"></i>
                        These suggestions are ranked by our AI based on skills, location, workload, and availability.
                    </div>
                    <div class="staff-suggestions">
                `;

                suggestions.forEach((suggestion, index) => {
                    const scoreColor = suggestion.total_score >= 80 ? 'success' : 
                                     suggestion.total_score >= 60 ? 'warning' : 'danger';
                    
                    dialogContent += `
                        <div class="staff-suggestion-card mb-3 p-3 border rounded ${index === 0 ? 'border-primary' : ''}">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" value="${suggestion.staff_id}" 
                                           id="staff_${suggestion.staff_id}" ${index === 0 ? 'checked' : ''}>
                                    <label class="form-check-label font-weight-bold" for="staff_${suggestion.staff_id}">
                                        ${suggestion.staff_name}
                                        ${index === 0 ? '<span class="badge badge-primary ml-2">Recommended</span>' : ''}
                                    </label>
                                </div>
                                <span class="badge badge-${scoreColor}">${suggestion.total_score}%</span>
                            </div>
                            
                            <div class="suggestion-metrics">
                                <div class="row text-sm">
                                    <div class="col-6">
                                        <div class="metric-item">
                                            <span class="metric-label">Skills:</span>
                                            <span class="metric-value">${suggestion.skill_score}%</span>
                                        </div>
                                        <div class="metric-item">
                                            <span class="metric-label">Location:</span>
                                            <span class="metric-value">${suggestion.proximity_score}%</span>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <div class="metric-item">
                                            <span class="metric-label">Workload:</span>
                                            <span class="metric-value">${suggestion.workload_score}%</span>
                                        </div>
                                        <div class="metric-item">
                                            <span class="metric-label">Available:</span>
                                            <span class="metric-value">${suggestion.availability_score}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="recommendation-reason text-muted small mt-2">
                                <i class="fa fa-lightbulb-o mr-1"></i>
                                ${suggestion.recommendation_reason}
                            </div>
                        </div>
                    `;
                });

                dialogContent += '</div>';
            } else {
                dialogContent += `
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle mr-2"></i>
                        No staff suggestions available. Please assign manually.
                    </div>
                `;
            }

            dialogContent += '</div>';

            // Create and show dialog
            const dialog = new Dialog(this, {
                title: _t('Assign Staff to Appointment'),
                $content: $(dialogContent),
                size: 'large',
                buttons: [{
                    text: _t('Assign Selected Staff'),
                    classes: 'btn-primary',
                    click: function () {
                        const selectedStaff = [];
                        dialog.$('.form-check-input:checked').each(function () {
                            selectedStaff.push(parseInt($(this).val()));
                        });
                        
                        if (selectedStaff.length === 0) {
                            self.displayNotification({
                                type: 'warning',
                                title: _t('Warning'),
                                message: _t('Please select at least one staff member.'),
                            });
                            return;
                        }
                        
                        self._assignStaffToAssignment(assignmentId, selectedStaff);
                        dialog.close();
                    }
                }, {
                    text: _t('Cancel'),
                    close: true
                }]
            });

            dialog.open();
        },

        /**
         * Assign staff to assignment
         */
        _assignStaffToAssignment: function (assignmentId, staffIds) {
            const self = this;
            
            rpc.query({
                model: 'health.staff.assignment',
                method: 'write',
                args: [assignmentId, {
                    'assigned_staff_ids': [[6, 0, staffIds]],
                    'lead_staff_id': staffIds[0], // First selected as lead
                    'state': 'assigned'
                }]
            }).then(function () {
                self.displayNotification({
                    type: 'success',
                    title: _t('Success'),
                    message: _t('Staff successfully assigned to appointment.'),
                });
                self.reload();
            }).catch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: _t('Failed to assign staff: ') + error.message.message,
                });
            });
        },

        /**
         * Confirm assignment
         */
        _confirmAssignment: function (assignmentId) {
            const self = this;
            
            rpc.query({
                model: 'health.staff.assignment',
                method: 'action_confirm_assignment',
                args: [[assignmentId]]
            }).then(function () {
                self.displayNotification({
                    type: 'success',
                    title: _t('Success'),
                    message: _t('Assignment confirmed successfully.'),
                });
                self.reload();
            }).catch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: error.message.message,
                });
            });
        },

        /**
         * Start assignment
         */
        _startAssignment: function (assignmentId) {
            const self = this;
            
            rpc.query({
                model: 'health.staff.assignment',
                method: 'action_start_assignment',
                args: [[assignmentId]]
            }).then(function () {
                self.displayNotification({
                    type: 'success',
                    title: _t('Success'),
                    message: _t('Assignment started successfully.'),
                });
                self.reload();
            }).catch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: error.message.message,
                });
            });
        },

        /**
         * Complete assignment
         */
        _completeAssignment: function (assignmentId) {
            const self = this;
            
            rpc.query({
                model: 'health.staff.assignment',
                method: 'action_complete_assignment',
                args: [[assignmentId]]
            }).then(function () {
                self.displayNotification({
                    type: 'success',
                    title: _t('Success'),
                    message: _t('Assignment completed successfully.'),
                });
                self.reload();
            }).catch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Error'),
                    message: error.message.message,
                });
            });
        },

        /**
         * Show AI suggestions modal
         */
        _showAISuggestions: function (assignmentId) {
            // This would show detailed AI analysis
            this.displayNotification({
                type: 'info',
                title: _t('AI Suggestions'),
                message: _t('Detailed AI analysis feature coming soon!'),
            });
        },

        // ========================================================================
        // Mobile Optimizations
        // ========================================================================

        /**
         * Setup mobile-specific optimizations
         */
        _setupMobileOptimizations: function () {
            // Add touch event handlers for mobile
            if ('ontouchstart' in window) {
                this._setupTouchEvents();
            }

            // Optimize for small screens
            this._setupResponsiveLayout();
        },

        /**
         * Setup touch events for mobile devices
         */
        _setupTouchEvents: function () {
            // Add swipe gestures for cards
            this.$el.on('touchstart', '.o_assignment_card', this._onTouchStart.bind(this));
            this.$el.on('touchmove', '.o_assignment_card', this._onTouchMove.bind(this));
            this.$el.on('touchend', '.o_assignment_card', this._onTouchEnd.bind(this));
        },

        /**
         * Setup responsive layout optimizations
         */
        _setupResponsiveLayout: function () {
            const self = this;
            
            // Adjust layout based on screen size
            function adjustLayout() {
                const isMobile = window.innerWidth < 768;
                self.$el.toggleClass('o_mobile_layout', isMobile);
                
                if (isMobile) {
                    // Stack kanban columns vertically on mobile
                    self.$('.o_kanban_group').addClass('o_mobile_column');
                } else {
                    self.$('.o_kanban_group').removeClass('o_mobile_column');
                }
            }
            
            // Initial adjustment
            adjustLayout();
            
            // Listen for window resize
            $(window).on('resize.assignment_dashboard', _.debounce(adjustLayout, 250));
        },

        // ========================================================================
        // Cleanup
        // ========================================================================

        /**
         * @override
         */
        destroy: function () {
            // Clear real-time update interval
            if (this.realTimeInterval) {
                clearInterval(this.realTimeInterval);
            }
            
            // Remove event listeners
            $(window).off('resize.assignment_dashboard');
            
            return this._super.apply(this, arguments);
        },

        /**
         * Pause real-time updates (when tab is not visible)
         */
        _pauseRealTimeUpdates: function () {
            if (this.realTimeInterval) {
                clearInterval(this.realTimeInterval);
                this.realTimeInterval = null;
            }
        },

        /**
         * Resume real-time updates (when tab becomes visible)
         */
        _resumeRealTimeUpdates: function () {
            if (!this.realTimeInterval) {
                this.realTimeInterval = setInterval(() => {
                    this._updateAssignmentStatuses();
                }, 30000);
            }
        },

        // ========================================================================
        // Touch Event Handlers (for mobile swipe gestures)
        // ========================================================================

        _onTouchStart: function (ev) {
            const touch = ev.originalEvent.touches[0];
            this.touchStartX = touch.clientX;
            this.touchStartY = touch.clientY;
            this.touchStartTime = Date.now();
        },

        _onTouchMove: function (ev) {
            // Prevent default scrolling behavior during swipe
            if (this.touchStartX !== undefined) {
                const touch = ev.originalEvent.touches[0];
                const deltaX = Math.abs(touch.clientX - this.touchStartX);
                const deltaY = Math.abs(touch.clientY - this.touchStartY);
                
                // If horizontal swipe is detected
                if (deltaX > deltaY && deltaX > 20) {
                    ev.preventDefault();
                }
            }
        },

        _onTouchEnd: function (ev) {
            if (this.touchStartX === undefined) return;
            
            const touch = ev.originalEvent.changedTouches[0];
            const deltaX = touch.clientX - this.touchStartX;
            const deltaY = touch.clientY - this.touchStartY;
            const deltaTime = Date.now() - this.touchStartTime;
            
            // Reset touch tracking
            this.touchStartX = undefined;
            this.touchStartY = undefined;
            this.touchStartTime = undefined;
            
            // Check for swipe gesture (horizontal swipe > 50px within 300ms)
            if (Math.abs(deltaX) > 50 && Math.abs(deltaY) < 30 && deltaTime < 300) {
                const $card = $(ev.currentTarget);
                const assignmentId = parseInt($card.data('assignment-id'));
                
                if (deltaX > 0) {
                    // Swipe right - show quick actions
                    this._showQuickActions(assignmentId);
                } else {
                    // Swipe left - show assignment details
                    this._showAssignmentDetails(assignmentId);
                }
            }
        },

        _showQuickActions: function (assignmentId) {
            // Show quick action menu for mobile
            this.displayNotification({
                type: 'info',
                title: _t('Quick Actions'),
                message: _t('Quick actions menu for mobile coming soon!'),
            });
        },

        _showAssignmentDetails: function (assignmentId) {
            // Show assignment details in mobile-optimized view
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'health.staff.assignment',
                res_id: assignmentId,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    });

    // ============================================================================
    // Assignment Dashboard View
    // ============================================================================

    const AssignmentDashboardView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: AssignmentDashboardController,
        }),
    });

    // Register the view
    viewRegistry.add('assignment_dashboard_kanban', AssignmentDashboardView);

    return {
        AssignmentDashboardController: AssignmentDashboardController,
        AssignmentDashboardView: AssignmentDashboardView,
    };
});