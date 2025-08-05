/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Assignment Timeline View
 * Professional timeline/Gantt-style view for assignment management
 * Inspired by Monday.com, Asana Timeline, and Microsoft Project
 */
export class AssignmentTimelineView extends Component {
    static template = "health_staff_assignment.AssignmentTimelineView";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");
        
        this.timelineRef = useRef("timeline");
        
        this.state = useState({
            staffMembers: [],
            assignments: [],
            isLoading: true,
            selectedTimeRange: 'week',
            viewMode: 'day', // day, week, month
            currentDate: new Date(),
            draggedAssignment: null,
            selectedAssignment: null,
            timeSlots: [],
            zoomLevel: 1,
            // PROFESSIONAL: Reactive position state (OWL can track changes)
            assignmentLayout: {
                positions: {},      // Reactive object for assignment positions
                staffLanes: {},     // Staff lane assignments
                timeSlotGrid: {}    // Time slot pixel mapping
            }
        });
        
        // Debounce variables to prevent multiple operations
        this.moveTimeoutId = null;
        this.clickTimeoutId = null;
        this.isDragging = false;
        this.isProcessingMove = false;
        
        // Professional click vs drag detection
        this.mouseDownTime = 0;
        this.mouseDownTarget = null;
        this.mouseDownX = 0;
        this.mouseDownY = 0;
        this.actuallyDragging = false;
        
        // Timeline configuration
        this.timelineConfig = {
            hourWidth: 60,  // pixels per hour
            rowHeight: 120,  // pixels per staff row (increased for stacking)
            headerHeight: 50,
            leftPanelWidth: 250,
            minDuration: 15, // minimum assignment duration in minutes
            snapToGrid: 15,  // snap to 15-minute intervals
        };
        
        onWillStart(this.loadData);
        onMounted(this.initializeTimeline);
    }

    /**
     * Load timeline data
     */
    async loadData() {
        try {
            // Load staff and assignments
            const timelineData = await this.orm.call(
                'health.staff',
                'get_timeline_data',
                [],
                {
                    date: this.state.currentDate.toISOString().split('T')[0],
                    view_mode: this.state.viewMode,
                    include_assignments: true
                }
            );
            
            this.state.staffMembers = timelineData.staff_members || [];
            this.state.assignments = timelineData.assignments || [];
            this.state.timeSlots = this.generateTimeSlots();
            
            // CRITICAL: Pre-compute all positions professionally
            this.computeAllPositions();
            
            this.state.isLoading = false;
            
            // Reset drag setup flag for new data
            this._dragSetupComplete = false;
            
            // Re-setup drag and drop after data loads
            setTimeout(() => {
                this.setupDragAndDrop();
            }, 100);
            
        } catch (error) {
            console.error('Error loading timeline data:', error);
            this.notification.add(_t("Failed to load timeline data"), {
                type: "danger"
            });
            this.state.isLoading = false;
        }
    }

    /**
     * Initialize timeline interactions
     */
    initializeTimeline() {
        if (!this.timelineRef.el) return;
        
        this.setupTimelineScrolling();
        this.setupZoomControls();
        this.setupTimelineResize();
        
        // Setup drag and drop after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.setupDragAndDrop();
        }, 200);
    }

    /**
     * PROFESSIONAL: Compute reactive positions (Monday.com/Asana pattern)
     * Uses reactive state so OWL automatically re-renders when positions change
     */
    computeAllPositions() {
        console.log('🚀 Computing reactive positions for', this.state.assignments.length, 'assignments');
        
        // Clear reactive state
        this.state.assignmentLayout.positions = {};
        this.state.assignmentLayout.staffLanes = {};
        this.state.assignmentLayout.timeSlotGrid = {};
        
        // Build staff lane mapping (reactive)
        this.state.assignments.forEach(assignment => {
            const staffIds = assignment.assigned_staff_ids || [];
            if (assignment.lead_staff_id) staffIds.push(assignment.lead_staff_id);
            
            staffIds.forEach(staffId => {
                if (!this.state.assignmentLayout.staffLanes[staffId]) {
                    this.state.assignmentLayout.staffLanes[staffId] = [];
                }
                this.state.assignmentLayout.staffLanes[staffId].push(assignment.id);
            });
        });
        
        // Pre-compute time slot grid (reactive)
        this.state.timeSlots.forEach((timeSlot, index) => {
            this.state.assignmentLayout.timeSlotGrid[index] = {
                left: index * this.timelineConfig.hourWidth * this.state.zoomLevel,
                width: this.timelineConfig.hourWidth * this.state.zoomLevel,
                datetime: timeSlot.datetime
            };
        });
        
        // Calculate positions for each assignment (reactive)
        this.state.assignments.forEach(assignment => {
            const primaryStaffId = assignment.lead_staff_id || assignment.assigned_staff_ids[0];
            if (primaryStaffId) {
                const position = this.calculatePositionReactive(assignment, primaryStaffId);
                this.state.assignmentLayout.positions[assignment.id] = position;
                console.log(`📍 Assignment ${assignment.id}: left=${position.left}px, top=${position.top}px`);
            }
        });
        
        console.log('✅ Reactive position computation complete');
    }

    /**
     * Generate time slots for the current view
     */
    generateTimeSlots() {
        const slots = [];
        const startDate = new Date(this.state.currentDate);
        
        if (this.state.viewMode === 'day') {
            // Generate hourly slots for the day
            for (let hour = 0; hour < 24; hour++) {
                slots.push({
                    time: `${hour.toString().padStart(2, '0')}:00`,
                    datetime: new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate(), hour),
                    type: 'hour'
                });
            }
        } else if (this.state.viewMode === 'week') {
            // Generate daily slots for the week
            startDate.setDate(startDate.getDate() - startDate.getDay()); // Start of week
            for (let day = 0; day < 7; day++) {
                const slotDate = new Date(startDate);
                slotDate.setDate(startDate.getDate() + day);
                slots.push({
                    time: slotDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
                    datetime: slotDate,
                    type: 'day'
                });
            }
        } else if (this.state.viewMode === 'month') {
            // Generate weekly slots for the month
            const startOfMonth = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
            const endOfMonth = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0);
            
            for (let week = 0; week < 6; week++) {
                const weekStart = new Date(startOfMonth);
                weekStart.setDate(1 + (week * 7));
                if (weekStart <= endOfMonth) {
                    slots.push({
                        time: `Week ${week + 1}`,
                        datetime: weekStart,
                        type: 'week'
                    });
                }
            }
        }
        
        return slots;
    }

    /**
     * Setup timeline scrolling synchronization
     */
    setupTimelineScrolling() {
        const headerRight = this.timelineRef.el.querySelector('.o_timeline_header_right');
        const bodyRight = this.timelineRef.el.querySelector('.o_timeline_body_right');
        
        if (headerRight && bodyRight) {
            // Sync header and body horizontal scrolling
            bodyRight.addEventListener('scroll', () => {
                headerRight.scrollLeft = bodyRight.scrollLeft;
                
                // Update assignment positions when scrolling
                this.updateAssignmentPositions();
            });
            
            // Also sync when header is scrolled
            headerRight.addEventListener('scroll', () => {
                bodyRight.scrollLeft = headerRight.scrollLeft;
                this.updateAssignmentPositions();
            });
        }
    }

    /**
     * Update assignment positions after scroll or data changes
     */
    updateAssignmentPositions() {
        const assignments = this.timelineRef.el.querySelectorAll('.o_timeline_assignment');
        assignments.forEach(element => {
            const assignmentId = parseInt(element.dataset.assignmentId);
            const assignment = this.state.assignments.find(a => a.id === assignmentId);
            if (assignment) {
                // Find the staff row this assignment belongs to
                const staffRow = element.closest('.o_timeline_staff_row');
                const staffId = staffRow ? parseInt(staffRow.dataset.staffId) : assignment.assigned_staff_ids[0];
                
                const position = this.getAssignmentPosition(assignment, staffId);
                element.style.left = position.left + 'px';
                element.style.width = position.width + 'px';
                element.style.top = position.top + 'px';
                element.style.height = position.height + 'px';
            }
        });
    }

    /**
     * Setup drag and drop for timeline
     */
    setupDragAndDrop() {
        // Prevent multiple setups
        if (this._dragSetupComplete) {
            console.log('Drag setup already completed, skipping');
            return;
        }
        
        this.setupAssignmentDragging();
        this.setupTimelineDropZones();
        
        this._dragSetupComplete = true;
        console.log('Drag setup completed');
    }

    /**
     * PROFESSIONAL: Setup event delegation (Monday.com/Asana pattern)
     * Single event listener for all assignments - more reliable and performant
     */
    setupAssignmentDragging() {
        if (!this.timelineRef.el) {
            console.warn('Timeline element not found for drag setup');
            return;
        }
        
        const timelineContainer = this.timelineRef.el.querySelector('.o_timeline_grid_container');
        if (!timelineContainer) {
            console.warn('Timeline grid container not found');
            return;
        }
        
        // Remove existing listeners to prevent duplicates
        timelineContainer.removeEventListener('mousedown', this.handleMouseDown);
        timelineContainer.removeEventListener('dragstart', this.handleDragStart);
        timelineContainer.removeEventListener('dragend', this.handleDragEnd);
        timelineContainer.removeEventListener('click', this.handleClick);
        
        // Professional event delegation - single listeners for all assignments
        this.handleMouseDown = this.handleMouseDown.bind(this);
        this.handleDragStart = this.handleDragStart.bind(this);
        this.handleDragEnd = this.handleDragEnd.bind(this);
        this.handleClick = this.handleClick.bind(this);
        this.handleDoubleClick = this.handleDoubleClick.bind(this);
        this.handleMouseMove = this.handleMouseMove.bind(this);
        
        timelineContainer.addEventListener('mousedown', this.handleMouseDown);
        timelineContainer.addEventListener('mousemove', this.handleMouseMove);
        timelineContainer.addEventListener('dragstart', this.handleDragStart);
        timelineContainer.addEventListener('dragend', this.handleDragEnd);
        timelineContainer.addEventListener('click', this.handleClick);
        timelineContainer.addEventListener('dblclick', this.handleDoubleClick);
        
        // Ensure all assignment elements are draggable
        const assignmentElements = timelineContainer.querySelectorAll('.o_timeline_assignment');
        assignmentElements.forEach(element => {
            element.draggable = true;
            element.style.cursor = 'move';
        });
        
        console.log(`✅ Professional drag setup complete for ${assignmentElements.length} assignments`);
        
        // ENHANCED DEBUG: Check assignment element properties and positioning
        console.log('🔍 ASSIGNMENT DEBUGGING START');
        console.log('🔍 State assignments count:', this.state.assignments.length);
        console.log('🔍 DOM assignment elements found:', assignmentElements.length);
        
        assignmentElements.forEach((element, index) => {
            const rect = element.getBoundingClientRect();
            const computedStyle = window.getComputedStyle(element);
            const assignmentId = element.dataset.assignmentId;
            const assignment = this.state.assignments.find(a => a.id == assignmentId);
            
            console.log(`🔍 Assignment ${index + 1} (ID: ${assignmentId}):`, {
                visible: rect.width > 0 && rect.height > 0,
                dimensions: `${rect.width}x${rect.height}`,
                position: `${element.style.left}, ${element.style.top}`,
                inlineStyle: element.getAttribute('style'),
                zIndex: computedStyle.zIndex,
                pointerEvents: computedStyle.pointerEvents,  
                display: computedStyle.display,
                opacity: computedStyle.opacity,
                assignmentData: assignment ? {
                    name: assignment.name,
                    state: assignment.state,
                    staffIds: assignment.assigned_staff_ids,
                    leadStaff: assignment.lead_staff_id
                } : 'NOT FOUND'
            });
            
            // Check if assignment is positioned outside visible area
            if (rect.left > window.innerWidth || rect.top > window.innerHeight) {
                console.warn(`⚠️ Assignment ${assignmentId} positioned outside viewport!`);
            }
            
            // Check if assignment has zero dimensions
            if (rect.width === 0 || rect.height === 0) {
                console.warn(`⚠️ Assignment ${assignmentId} has zero dimensions!`);
            }
        });
        
        // Also debug the reactive position data
        console.log('🔍 Reactive position data:', this.state.assignmentLayout.positions);
        console.log('🔍 ASSIGNMENT DEBUGGING END');
        
        // CRITICAL: Also setup drop zones (was missing!)
        this.setupTimelineDropZones();
    }

    /**
     * Setup timeline drop zones
     */
    setupTimelineDropZones() {
        if (!this.timelineRef.el) {
            console.warn('Timeline element not found for drop zone setup');
            return;
        }
        
        // Setup drop zones on time slots
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        console.log(`Setting up drop zones for ${timeSlots.length} time slots`);
        
        timeSlots.forEach(slot => {
            slot.addEventListener('dragover', this.onTimeSlotDragOver.bind(this));
            slot.addEventListener('drop', this.onTimeSlotDrop.bind(this));
            slot.addEventListener('dragenter', this.onTimeSlotDragEnter.bind(this));
            slot.addEventListener('dragleave', this.onTimeSlotDragLeave.bind(this));
            
            // Visual indication for drop zones
            slot.style.minHeight = '60px';
        });
        
        // Also setup staff row drop zones for staff reassignment
        const staffRows = this.timelineRef.el.querySelectorAll('.o_timeline_staff_row');
        console.log(`Setting up staff drop zones for ${staffRows.length} staff rows`);
        
        staffRows.forEach(element => {
            element.addEventListener('dragover', this.onStaffDragOver.bind(this));
            element.addEventListener('drop', this.onStaffDrop.bind(this));
            element.addEventListener('dragenter', this.onStaffDragEnter.bind(this));
            element.addEventListener('dragleave', this.onStaffDragLeave.bind(this));
        });
    }

    /**
     * PROFESSIONAL: Mouse down handler for click vs drag detection
     */
    handleMouseDown(event) {
        console.log('🔍 Mouse down event details:', {
            target: event.target.className,
            targetTag: event.target.tagName,
            targetId: event.target.id,
            targetDataset: event.target.dataset,
            clientX: event.clientX,
            clientY: event.clientY
        });
        
        const assignmentElement = event.target.closest('.o_timeline_assignment');
        if (!assignmentElement) {
            console.log('🔍 Mouse down - no assignment element found');
            console.log('🔍 Searching for assignments in DOM...');
            
            // Debug: Find all assignment elements in the DOM
            const allAssignments = document.querySelectorAll('.o_timeline_assignment');
            console.log(`🔍 Found ${allAssignments.length} assignment elements in DOM`);
            
            allAssignments.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                const isUnderMouse = event.clientX >= rect.left && event.clientX <= rect.right && 
                                   event.clientY >= rect.top && event.clientY <= rect.bottom;
                console.log(`🔍 Assignment ${index + 1}:`, {
                    id: el.dataset.assignmentId,
                    rect: `${rect.left},${rect.top} ${rect.width}x${rect.height}`,
                    underMouse: isUnderMouse,
                    visible: rect.width > 0 && rect.height > 0
                });
            });
            
            return;
        }
        
        this.mouseDownTime = Date.now();
        this.mouseDownTarget = assignmentElement;
        this.mouseDownX = event.clientX;
        this.mouseDownY = event.clientY;
        console.log('🖱️ Mouse down on assignment', assignmentElement.dataset.assignmentId);
    }

    /**
     * PROFESSIONAL: Mouse move handler to detect actual dragging
     */
    handleMouseMove(event) {
        if (!this.mouseDownTarget || !this.mouseDownTime) return;
        
        const deltaX = Math.abs(event.clientX - this.mouseDownX);
        const deltaY = Math.abs(event.clientY - this.mouseDownY);
        const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        
        // Consider it actual dragging if moved more than 5 pixels
        if (distance > 5) {
            this.actuallyDragging = true;
            console.log('🔄 Mouse movement detected, actuallyDragging = true');
        }
    }

    /**
     * PROFESSIONAL: Click handler with improved element detection
     */
    handleClick(event) {
        // Try multiple ways to find the assignment element
        let assignmentElement = event.target.closest('.o_timeline_assignment');
        
        // If not found, check if we're clicking on the container and use stored target
        if (!assignmentElement && this.mouseDownTarget) {
            assignmentElement = this.mouseDownTarget;
        }
        
        console.log('🔍 Click event - assignment found:', !!assignmentElement, 'target:', event.target.className);
        console.log('🔍 Mouse down target:', this.mouseDownTarget?.dataset?.assignmentId);
        
        if (!assignmentElement) {
            console.log('🔍 Click ignored - no assignment element found');
            this.mouseDownTarget = null;
            this.mouseDownTime = 0;
            return;
        }
        
        const clickDuration = Date.now() - (this.mouseDownTime || 0);
        console.log('🔍 Click duration:', clickDuration, 'ms, isDragging:', this.isDragging, 'actuallyDragging:', this.actuallyDragging);
        
        // Improved click detection using actual mouse movement
        if (!this.actuallyDragging && clickDuration < 2000) {
            // Click without significant mouse movement
            event.preventDefault();
            event.stopPropagation();
            
            const assignmentId = parseInt(assignmentElement.dataset.assignmentId);
            console.log('✅ Assignment clicked successfully:', assignmentId);
            this.openAssignmentDetails(assignmentId);
        } else if (this.actuallyDragging) {
            console.log('🔍 Click ignored - user was actually dragging the element');
        } else {
            console.log('🔍 Click ignored - duration too long:', clickDuration, 'ms');
        }
        
        // Reset state
        this.mouseDownTarget = null;
        this.mouseDownTime = 0;
        this.actuallyDragging = false;
    }

    /**
     * PROFESSIONAL: Double-click handler for quick assignment access
     */
    handleDoubleClick(event) {
        const assignmentElement = event.target.closest('.o_timeline_assignment');
        if (!assignmentElement) {
            console.log('🔍 Double-click - no assignment element found');
            return;
        }
        
        event.preventDefault();
        event.stopPropagation();
        
        const assignmentId = parseInt(assignmentElement.dataset.assignmentId);
        console.log('✅ Assignment double-clicked:', assignmentId);
        this.openAssignmentDetails(assignmentId);
    }

    /**
     * PROFESSIONAL: Drag start handler
     */
    handleDragStart(event) {
        const assignmentElement = event.target.closest('.o_timeline_assignment');
        console.log('🔍 Drag start - assignment found:', !!assignmentElement, 'target:', event.target.className);
        
        if (!assignmentElement) {
            console.log('🔍 Drag start ignored - no assignment element');
            return;
        }
        
        console.log('✅ Drag started on assignment:', assignmentElement.dataset.assignmentId);
        this.isDragging = true;
        this.onAssignmentDragStart(event);
    }

    /**
     * PROFESSIONAL: Drag end handler
     */
    handleDragEnd(event) {
        this.onAssignmentDragEnd(event);
        
        // No delay needed - drag state is already reset in onAssignmentDragEnd
        console.log('🔄 HandleDragEnd completed');
    }

    /**
     * Handle assignment drag start
     */
    onAssignmentDragStart(event) {
        if (this.isProcessingMove) {
            event.preventDefault();
            return;
        }
        
        this.isDragging = true;
        console.log('Drag start event triggered', event.target);
        
        // Try to get assignment ID from the dragged element or its closest assignment parent
        let assignmentElement = event.target.closest('.o_timeline_assignment');
        if (!assignmentElement) {
            assignmentElement = event.target;
        }
        
        const assignmentId = parseInt(assignmentElement.dataset.assignmentId);
        console.log('Assignment ID from element:', assignmentId, 'element:', assignmentElement);
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        console.log('Found assignment:', assignment ? assignment.name : 'NOT FOUND');
        
        if (!assignment) {
            console.warn('Assignment not found for ID:', assignmentId);
            this.isDragging = false;
            return;
        }
        
        console.log('✅ Assignment found, continuing with drag setup...');
        
        this.state.draggedAssignment = assignment;
        console.log('✅ Set draggedAssignment state:', this.state.draggedAssignment.id, this.state.draggedAssignment.name);
        
        // DEBUGGING: Check if drop zones can receive events
        setTimeout(() => {
            const dropZones = document.querySelectorAll('.o_timeline_slot');
            console.log(`🔍 Found ${dropZones.length} drop zones after drag start`);
            dropZones.forEach((zone, index) => {
                if (index < 3) { // Check first 3 zones
                    const style = window.getComputedStyle(zone);
                    const rect = zone.getBoundingClientRect();
                    console.log(`🔍 Drop zone ${index}:`, {
                        pointerEvents: style.pointerEvents,
                        zIndex: style.zIndex,
                        position: style.position,
                        dimensions: `${rect.width}x${rect.height}`,
                        visible: rect.width > 0 && rect.height > 0,
                        staffId: zone.dataset.staffId,
                        timeSlot: zone.dataset.timeSlot
                    });
                }
            });
        }, 100);
        
        // Create drag ghost with assignment info
        const dragGhost = document.createElement('div');
        dragGhost.className = 'o_timeline_drag_ghost';
        dragGhost.innerHTML = `
            <div class="o_drag_ghost_content">
                <i class="fa fa-arrows-alt"></i>
                <span>${assignment.name}</span>
            </div>
        `;
        document.body.appendChild(dragGhost);
        event.dataTransfer.setDragImage(dragGhost, 10, 10);
        
        // Clean up ghost after drag
        setTimeout(() => document.body.removeChild(dragGhost), 0);
        
        event.dataTransfer.setData('text/plain', assignmentId.toString());
        event.dataTransfer.setData('application/json', JSON.stringify({
            assignmentId: assignmentId,
            assignmentName: assignment.name
        }));
        event.dataTransfer.effectAllowed = 'move';
        
        console.log('✅ Drag data set:', { assignmentId, name: assignment.name });
        
        // Add visual feedback
        event.target.classList.add('o_dragging');
        this.timelineRef.el.classList.add('o_timeline_dragging');
        
        // CRITICAL: During drag, hide the dragged assignment so drop zones can receive events
        event.target.style.opacity = '0.1';
        event.target.style.pointerEvents = 'none';
        console.log('🔄 Made dragged assignment transparent for drop zone access');
        
        // Optionally reduce assignments layer z-index  
        const assignmentsLayer = this.timelineRef.el.querySelector('.o_timeline_assignments_layer');
        if (assignmentsLayer) {
            assignmentsLayer.style.zIndex = '2';
            console.log('🔄 Reduced assignments layer z-index for drag operation');
        }
        
        // Highlight valid drop zones
        this.highlightValidDropZones(assignment);
    }

    /**
     * Handle assignment drag
     */
    onAssignmentDrag(event) {
        // Update drag preview position if needed
        this.updateDragPreview(event);
    }

    /**
     * Handle assignment drag end
     */
    onAssignmentDragEnd(event) {
        // Clean up visual feedback
        event.target.classList.remove('o_dragging');
        this.timelineRef.el.classList.remove('o_timeline_dragging');
        
        // CRITICAL: Restore dragged assignment appearance
        event.target.style.opacity = '1';
        event.target.style.pointerEvents = 'auto';
        console.log('🔄 Restored dragged assignment appearance');
        
        // CRITICAL: Restore assignment layer z-index after drag
        const assignmentsLayer = this.timelineRef.el.querySelector('.o_timeline_assignments_layer');
        if (assignmentsLayer) {
            assignmentsLayer.style.zIndex = '20';
            console.log('🔄 Restored assignments layer z-index after drag');
        }
        
        // Remove drop zone highlights
        this.removeDropZoneHighlights();
        
        // Reset state
        this.state.draggedAssignment = null;
        
        // Reset drag flag immediately - don't delay clicks unnecessarily
        this.isDragging = false;
        console.log('🔄 Drag ended, isDragging reset to false');
    }

    /**
     * Handle time slot drag over
     */
    onTimeSlotDragOver(event) {
        if (!this.state.draggedAssignment) {
            console.log('🔄 Drag over slot but no draggedAssignment:', event.currentTarget.dataset.timeSlot);
            return;
        }
        
        console.log('🔄 Drag over slot:', event.currentTarget.dataset.timeSlot, 'with assignment:', this.state.draggedAssignment.id);
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }

    /**
     * Handle time slot drag enter
     */
    onTimeSlotDragEnter(event) {
        if (!this.state.draggedAssignment) return;
        
        const slot = event.currentTarget;
        const staffId = parseInt(slot.dataset.staffId);
        const timeSlot = slot.dataset.timeSlot;
        
        // Validate drop
        if (this.validateTimeSlotDrop(staffId, timeSlot, this.state.draggedAssignment)) {
            slot.classList.add('o_valid_drop_target');
        } else {
            slot.classList.add('o_invalid_drop_target');
        }
    }

    /**
     * Handle time slot drag leave
     */
    onTimeSlotDragLeave(event) {
        event.currentTarget.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
    }

    /**
     * Handle time slot drop
     */
    async onTimeSlotDrop(event) {
        console.log('🎯 DROP EVENT TRIGGERED!', event.type);
        event.preventDefault();
        
        if (this.isProcessingMove) {
            console.log('⚠️ Already processing a move, ignoring drop');
            return;
        }
        
        this.isProcessingMove = true;
        
        const slot = event.currentTarget;
        const staffId = parseInt(slot.dataset.staffId);
        const timeSlot = slot.dataset.timeSlot;
        const slotDatetime = slot.dataset.slotDatetime;
        const slotIndex = parseInt(slot.dataset.slotIndex);
        const assignmentId = parseInt(event.dataTransfer.getData('text/plain'));
        
        console.log('🎯 Drop data:', { staffId, timeSlot, slotDatetime, slotIndex, assignmentId });
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        if (!assignment) {
            console.log('❌ Assignment not found for drop:', assignmentId);
            this.isProcessingMove = false;
            return;
        }
        
        console.log('✅ Processing drop for assignment:', assignment.name);
        
        // Clean up visual states
        slot.classList.remove('o_valid_drop_target', 'o_invalid_drop_target');
        
        // Validate and execute the move
        if (this.validateTimeSlotDrop(staffId, timeSlot, assignment)) {
            await this.moveAssignmentToTimeSlot(assignment, staffId, timeSlot, slotDatetime, slotIndex);
        } else {
            this.notification.add(_t("Cannot move assignment to this time slot"), {
                type: "warning"
            });
        }
        
        // Reset processing flag
        setTimeout(() => {
            this.isProcessingMove = false;
        }, 500);
    }

    /**
     * Validate if assignment can be dropped in time slot
     */
    validateTimeSlotDrop(staffId, timeSlot, assignment) {
        // Check if staff exists and is active
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        if (!staff || staff.employment_status !== 'active') {
            return false;
        }
        
        // Check for time conflicts
        // In full implementation, this would check for overlapping assignments
        
        // Check staff availability for the time slot
        // In full implementation, this would check staff working hours
        
        return true;
    }

    /**
     * Move assignment to new time slot (debounced)
     */
    async moveAssignmentToTimeSlot(assignment, staffId, timeSlot, slotDatetime = null, slotIndex = null) {
        // Clear any existing timeout to prevent multiple calls
        if (this.moveTimeoutId) {
            clearTimeout(this.moveTimeoutId);
        }
        
        // Debounce the move operation
        this.moveTimeoutId = setTimeout(async () => {
            try {
                console.log('Moving assignment:', assignment.name, 'to staff:', staffId, 'at:', timeSlot);
                
                // Calculate new assignment time - prioritize slot datetime from DOM
                let newDateTime;
                
                // First priority: use the datetime from the DOM slot element
                if (slotDatetime && slotDatetime !== '') {
                    try {
                        newDateTime = new Date(slotDatetime);
                        if (this.state.viewMode !== 'day') {
                            // For week/month view, set to 9 AM
                            newDateTime.setHours(9, 0, 0, 0);
                        }
                        console.log('Using slot datetime from DOM:', newDateTime);
                    } catch (e) {
                        console.warn('Invalid slot datetime:', slotDatetime, e);
                        newDateTime = null;
                    }
                }
                
                // Second priority: calculate from slot index
                if (!newDateTime && slotIndex !== null) {
                    newDateTime = this.calculateDateTimeFromSlotIndex(slotIndex);
                    console.log('Calculated from slot index:', slotIndex, '->', newDateTime);
                }
                
                // Third priority: parse from time slot string
                if (!newDateTime) {
                    newDateTime = this.calculateAssignmentDateTime(timeSlot);
                    console.log('Calculated from timeSlot string:', timeSlot, '->', newDateTime);
                }
                
                // Validate final datetime
                if (!newDateTime || isNaN(newDateTime.getTime())) {
                    console.error('Failed to calculate valid datetime, using fallback');
                    newDateTime = new Date();
                    newDateTime.setHours(9, 0, 0, 0);
                }
                
                // Update assignment with correct fields (assignment_date is datetime, not date)
                await this.orm.write('health.staff.assignment', [assignment.id], {
                    assigned_staff_ids: [[6, 0, [staffId]]],
                    lead_staff_id: staffId,
                    assignment_date: newDateTime.toISOString(), // This is the main datetime field
                });
                
                // Update local state immediately for visual feedback
                const assignmentIndex = this.state.assignments.findIndex(a => a.id === assignment.id);
                if (assignmentIndex !== -1) {
                    this.state.assignments[assignmentIndex].assigned_staff_ids = [staffId];
                    this.state.assignments[assignmentIndex].lead_staff_id = staffId;
                    this.state.assignments[assignmentIndex].assignment_date = newDateTime.toISOString();
                    
                    // PROFESSIONAL: Recompute positions after assignment move
                    console.log('🔄 Recomputing positions after assignment move');
                    this.computeAllPositions();
                    
                    // Force re-render to update positions immediately
                    console.log('🔄 Forcing re-render after position update');
                    this.render();
                }
                
                // Show success notification (only one)
                const staff = this.state.staffMembers.find(s => s.id === staffId);
                const dateStr = newDateTime.toLocaleDateString();
                this.notification.add(
                    _t("Assignment moved to %s on %s", staff ? staff.name : 'new position', dateStr),
                    { type: "success" }
                );
                
                // Reload data to get fresh positions
                await this.loadData();
                
            } catch (error) {
                console.error('Error moving assignment:', error);
                this.notification.add(_t("Failed to move assignment"), {
                    type: "danger"
                });
            } finally {
                this.moveTimeoutId = null;
            }
        }, 300); // 300ms debounce
    }

    /**
     * Calculate datetime from slot index
     */
    calculateDateTimeFromSlotIndex(slotIndex) {
        if (slotIndex !== null && this.state.timeSlots[slotIndex]) {
            const slot = this.state.timeSlots[slotIndex];
            if (slot.datetime) {
                const date = new Date(slot.datetime);
                
                // Set appropriate time based on view mode
                if (this.state.viewMode === 'day') {
                    // For day view, keep the hour from slot
                    return date;
                } else {
                    // For week/month view, set to 9 AM
                    date.setHours(9, 0, 0, 0);
                    return date;
                }
            }
        }
        
        // Fallback to current date with 9 AM
        const fallback = new Date();
        fallback.setHours(9, 0, 0, 0);
        return fallback;
    }

    /**
     * Calculate assignment date/time from time slot
     */
    calculateAssignmentDateTime(timeSlot) {
        console.log('Calculating date from time slot:', timeSlot, 'in view mode:', this.state.viewMode);
        
        if (this.state.viewMode === 'day') {
            // For day view, timeSlot represents hours (e.g., "09:00")
            const [hours, minutes] = timeSlot.split(':').map(Number);
            const newDate = new Date(this.state.currentDate);
            newDate.setHours(hours, minutes || 0, 0, 0);
            return newDate;
            
        } else if (this.state.viewMode === 'week') {
            // For week view, timeSlot represents day (e.g., "Mon Jan 15" or index)
            const weekStart = new Date(this.state.currentDate);
            const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1;
            weekStart.setDate(weekStart.getDate() - daysFromMonday);
            weekStart.setHours(9, 0, 0, 0); // Default to 9 AM
            
            // Find which time slot index this corresponds to
            const timeSlotIndex = this.state.timeSlots.findIndex(slot => slot.time === timeSlot);
            if (timeSlotIndex !== -1) {
                const targetDate = new Date(weekStart);
                targetDate.setDate(weekStart.getDate() + timeSlotIndex);
                targetDate.setHours(9, 0, 0, 0); // Ensure 9 AM time
                console.log('Calculated week date:', targetDate);
                return targetDate;
            }
            
            // Fallback: try to parse the timeSlot as a date string
            try {
                const parsedDate = new Date(timeSlot);
                if (!isNaN(parsedDate.getTime())) {
                    parsedDate.setHours(9, 0, 0, 0);
                    return parsedDate;
                }
            } catch (e) {
                console.warn('Could not parse timeSlot as date:', timeSlot);
            }
            
            return weekStart; // Fallback to week start
            
        } else if (this.state.viewMode === 'month') {
            // For month view, timeSlot represents weeks
            const monthStart = new Date(this.state.currentDate.getFullYear(), this.state.currentDate.getMonth(), 1);
            const timeSlotIndex = this.state.timeSlots.findIndex(slot => slot.time === timeSlot);
            
            if (timeSlotIndex !== -1) {
                const targetDate = new Date(monthStart);
                targetDate.setDate(1 + (timeSlotIndex * 7));
                targetDate.setHours(9, 0, 0, 0);
                return targetDate;
            }
            
            return monthStart; // Fallback
        }
        
        // Fallback to current date with 9 AM time
        const fallback = new Date();
        fallback.setHours(9, 0, 0, 0);
        return fallback;
    }

    /**
     * Highlight valid drop zones
     */
    highlightValidDropZones(assignment) {
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        
        timeSlots.forEach(slot => {
            const staffId = parseInt(slot.dataset.staffId);
            const timeSlot = slot.dataset.timeSlot;
            
            if (this.validateTimeSlotDrop(staffId, timeSlot, assignment)) {
                slot.classList.add('o_potential_drop_zone');
            } else {
                slot.classList.add('o_invalid_drop_zone');
            }
        });
    }

    /**
     * Remove drop zone highlights
     */
    removeDropZoneHighlights() {
        const timeSlots = this.timelineRef.el.querySelectorAll('.o_timeline_slot');
        timeSlots.forEach(slot => {
            slot.classList.remove('o_potential_drop_zone', 'o_invalid_drop_zone');
        });
    }

    /**
     * Setup zoom controls
     */
    setupZoomControls() {
        // This would handle timeline zoom in/out
    }

    /**
     * Setup timeline resize
     */
    setupTimelineResize() {
        // This would handle timeline panel resizing
    }

    /**
     * Handle staff drag over
     */
    onStaffDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }

    /**
     * Handle staff drag enter
     */
    onStaffDragEnter(event) {
        if (!this.state.draggedAssignment) return;
        
        const staffRow = event.currentTarget;
        const staffId = parseInt(staffRow.dataset.staffId);
        
        // Validate drop on staff
        if (this.validateStaffDrop(staffId, this.state.draggedAssignment)) {
            staffRow.classList.add('o_valid_staff_drop_target');
        } else {
            staffRow.classList.add('o_invalid_staff_drop_target');
        }
    }

    /**
     * Handle staff drag leave  
     */
    onStaffDragLeave(event) {
        event.currentTarget.classList.remove('o_valid_staff_drop_target', 'o_invalid_staff_drop_target');
    }

    /**
     * Handle staff drop
     */
    async onStaffDrop(event) {
        event.preventDefault();
        
        const staffRow = event.currentTarget;
        const staffId = parseInt(staffRow.dataset.staffId);
        const assignmentId = parseInt(event.dataTransfer.getData('text/plain'));
        
        const assignment = this.state.assignments.find(a => a.id === assignmentId);
        if (!assignment) return;
        
        // Clean up visual states
        staffRow.classList.remove('o_valid_staff_drop_target', 'o_invalid_staff_drop_target');
        
        // Validate and execute the staff reassignment
        if (this.validateStaffDrop(staffId, assignment)) {
            await this.reassignToStaff(assignment, staffId);
        } else {
            this.notification.add(_t("Cannot reassign assignment to this staff member"), {
                type: "warning"
            });
        }
    }

    /**
     * Validate if assignment can be dropped on staff
     */
    validateStaffDrop(staffId, assignment) {
        // Check if staff exists and is active
        const staff = this.state.staffMembers.find(s => s.id === staffId);
        if (!staff || staff.employment_status !== 'active') {
            return false;
        }
        
        // Check if assignment is already assigned to this staff
        if (assignment.assigned_staff_ids.includes(staffId)) {
            return false;
        }
        
        // Additional validation can be added here
        return true;
    }

    /**
     * Reassign assignment to different staff
     */
    async reassignToStaff(assignment, staffId) {
        try {
            // Update assignment
            await this.orm.write('health.staff.assignment', [assignment.id], {
                assigned_staff_ids: [[6, 0, [staffId]]],
                lead_staff_id: staffId,
            });
            
            // Update local state
            assignment.assigned_staff_ids = [staffId];
            assignment.lead_staff_id = staffId;
            
            // Show success notification
            const staff = this.state.staffMembers.find(s => s.id === staffId);
            this.notification.add(
                _t("Assignment '%s' reassigned to %s", assignment.name, staff.name),
                { type: "success" }
            );
            
            // Refresh timeline
            await this.loadData();
            
        } catch (error) {
            console.error('Error reassigning assignment:', error);
            this.notification.add(_t("Failed to reassign assignment"), {
                type: "danger"
            });
        }
    }

    /**
     * Update drag preview
     */
    updateDragPreview(event) {
        // Update visual drag preview position
    }

    /**
     * PROFESSIONAL: Calculate position with reactive state (DHTMLX/Monday.com pattern)
     */
    calculatePositionReactive(assignment, staffId) {
        console.log(`🧮 Calculating position for assignment ${assignment.id} on staff ${staffId}`);
        
        const assignmentDate = new Date(assignment.start_datetime || assignment.assignment_date);
        const duration = assignment.estimated_duration || 60;
        
        console.log(`🧮 Assignment date: ${assignmentDate}, duration: ${duration}min`);
        
        // Calculate horizontal position based on view mode
        let left = 0;
        let width = this.durationToPixels(duration);
        
        if (this.state.viewMode === 'week') {
            // Week view: position by day
            const weekStart = new Date(this.state.currentDate);
            const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1;
            weekStart.setDate(weekStart.getDate() - daysFromMonday);
            weekStart.setHours(0, 0, 0, 0);
            
            const dayIndex = Math.floor((assignmentDate - weekStart) / (1000 * 60 * 60 * 24));
            left = Math.max(0, dayIndex) * this.timelineConfig.hourWidth * this.state.zoomLevel;
            width = Math.max(width, this.timelineConfig.hourWidth * this.state.zoomLevel * 0.8);
            
            console.log(`🧮 Week view: dayIndex=${dayIndex}, weekStart=${weekStart}, left=${left}, width=${width}`);
            
        } else if (this.state.viewMode === 'day') {
            // Day view: position by hour
            left = this.dateToPixels(assignmentDate);
            console.log(`🧮 Day view: left=${left}, width=${width}`);
            
        } else if (this.state.viewMode === 'month') {
            // Month view: position by week
            const monthStart = new Date(this.state.currentDate.getFullYear(), this.state.currentDate.getMonth(), 1);
            const dayIndex = Math.floor((assignmentDate - monthStart) / (1000 * 60 * 60 * 24));
            const weekIndex = Math.floor(dayIndex / 7);
            left = weekIndex * this.timelineConfig.hourWidth * this.state.zoomLevel;
            width = Math.max(width, this.timelineConfig.hourWidth * this.state.zoomLevel * 0.6);
            
            console.log(`🧮 Month view: weekIndex=${weekIndex}, left=${left}, width=${width}`);
        }
        
        // Calculate vertical position using reactive state
        const staffIndex = this.state.staffMembers.findIndex(s => s.id === staffId);
        const rowTop = staffIndex * this.timelineConfig.rowHeight;
        const cardTop = this.calculateVerticalPositionReactive(assignment, staffId, left, width);
        
        const finalPosition = {
            left: Math.max(0, left),
            width: Math.max(50, width),
            top: rowTop + cardTop,
            height: 25
        };
        
        console.log(`🧮 Final position for assignment ${assignment.id}:`, finalPosition);
        console.log(`🧮 Staff index: ${staffIndex}, rowTop: ${rowTop}, cardTop: ${cardTop}`);
        
        return finalPosition;
    }

    /**
     * PROFESSIONAL: Calculate vertical position with reactive overlap detection
     */
    calculateVerticalPositionReactive(assignment, staffId, left, width) {
        const staffAssignmentIds = this.state.assignmentLayout.staffLanes[staffId] || [];
        const cardHeight = 25;
        const cardSpacing = 2;
        
        // Find the lowest available level using reactive state
        let level = 0;
        let levelFound = false;
        
        while (!levelFound && level < 6) { // Max 6 levels
            const testTop = 5 + (level * (cardHeight + cardSpacing));
            let hasConflict = false;
            
            // Check for conflicts with other assignments at this level
            for (const otherAssignmentId of staffAssignmentIds) {
                if (otherAssignmentId === assignment.id) continue;
                
                const otherPosition = this.state.assignmentLayout.positions[otherAssignmentId];
                if (otherPosition && (otherPosition.top % this.timelineConfig.rowHeight) === testTop) {
                    // Check horizontal overlap
                    if (this.hasHorizontalOverlap(left, width, otherPosition.left, otherPosition.width)) {
                        hasConflict = true;
                        break;
                    }
                }
            }
            
            if (!hasConflict) {
                levelFound = true;
            } else {
                level++;
            }
        }
        
        return 5 + (level * (cardHeight + cardSpacing));
    }

    /**
     * PROFESSIONAL: Get reactive assignment position (eliminates template recalculation)
     */
    getAssignmentPosition(assignment, staffId = null) {
        const reactivePosition = this.state.assignmentLayout.positions[assignment.id];
        if (reactivePosition) {
            return reactivePosition;
        }
        
        // Fallback: calculate on demand (should rarely happen)
        console.warn(`⚠️ Position not cached for assignment ${assignment.id}, calculating on demand`);
        const targetStaffId = staffId || assignment.lead_staff_id || assignment.assigned_staff_ids[0];
        return this.calculatePositionReactive(assignment, targetStaffId);
    }

    /**
     * NEW: Get assignment style string for template (single call optimization)
     */
    getAssignmentStyle(assignment) {
        const position = this.getAssignmentPosition(assignment);
        return `left: ${position.left}px; width: ${position.width}px; height: ${position.height}px; top: ${position.top}px;`;
    }

    /**
     * Calculate vertical position to avoid overlapping assignments
     */
    calculateVerticalPosition(assignment, staffId, left, width) {
        console.log(`Calculating vertical position for assignment ${assignment.id} on staff ${staffId}`);
        
        // Get all assignments for this staff that might overlap
        const staffAssignments = this.state.assignments.filter(a => 
            (a.assigned_staff_ids.includes(staffId) || a.lead_staff_id === staffId) && 
            a.id !== assignment.id
        );
        
        console.log(`Found ${staffAssignments.length} other assignments for staff ${staffId}`);
        
        const cardHeight = 25;
        const cardSpacing = 2;
        const usedLevels = new Set();
        
        // Calculate which levels are occupied by overlapping assignments
        for (const otherAssignment of staffAssignments) {
            const otherDate = new Date(otherAssignment.start_datetime || otherAssignment.assignment_date);
            const otherDuration = otherAssignment.estimated_duration || 60;
            
            // Calculate other assignment's position using simple logic (no recursion)
            let otherLeft = 0;
            let otherWidth = this.durationToPixels(otherDuration);
            
            if (this.state.viewMode === 'week') {
                const weekStart = new Date(this.state.currentDate);
                const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1;
                weekStart.setDate(weekStart.getDate() - daysFromMonday);
                weekStart.setHours(0, 0, 0, 0);
                
                const dayIndex = Math.floor((otherDate - weekStart) / (1000 * 60 * 60 * 24));
                otherLeft = dayIndex * this.timelineConfig.hourWidth * this.state.zoomLevel;
                otherWidth = Math.max(otherWidth, this.timelineConfig.hourWidth * this.state.zoomLevel * 0.8);
            }
            
            console.log(`Other assignment ${otherAssignment.id}: left=${otherLeft}, width=${otherWidth}`);
            console.log(`Current assignment: left=${left}, width=${width}`);
            
            // Check if there's horizontal overlap
            if (this.hasHorizontalOverlap(left, width, otherLeft, otherWidth)) {
                // Simple level assignment for consistent stacking
                const level = Math.abs(otherAssignment.id) % 4; // Use assignment ID for consistency
                usedLevels.add(level);
                console.log(`Horizontal overlap detected, used level: ${level} for assignment ${otherAssignment.id}`);
            }
        }
        
        // Find first free level
        let level = 0;
        while (usedLevels.has(level) && level < 4) {
            level++;
        }
        
        // If all levels are taken, use assignment ID modulo for consistency
        if (level >= 4) {
            level = Math.abs(assignment.id) % 4;
        }
        
        const topPosition = 5 + (level * (cardHeight + cardSpacing));
        console.log(`Final vertical position for assignment ${assignment.id}: level=${level}, top=${topPosition}px`);
        
        return topPosition; // Start 5px from top
    }

    /**
     * Get basic assignment position without vertical calculation (to avoid recursion)
     */
    getAssignmentPositionBasic(assignment) {
        const assignmentDate = new Date(assignment.start_datetime || assignment.assignment_date);
        const duration = assignment.estimated_duration || 60;
        
        let left = 0;
        let width = this.durationToPixels(duration);
        
        if (this.state.viewMode === 'week') {
            const weekStart = new Date(this.state.currentDate);
            const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1;
            weekStart.setDate(weekStart.getDate() - daysFromMonday);
            weekStart.setHours(0, 0, 0, 0);
            
            const dayIndex = Math.floor((assignmentDate - weekStart) / (1000 * 60 * 60 * 24));
            left = dayIndex * this.timelineConfig.hourWidth * this.state.zoomLevel;
            width = Math.max(width, this.timelineConfig.hourWidth * this.state.zoomLevel * 0.8);
        }
        
        return { left: Math.max(0, left), width: Math.max(50, width), top: 5 };
    }

    /**
     * Check if two horizontal ranges overlap
     */
    hasHorizontalOverlap(left1, width1, left2, width2) {
        const right1 = left1 + width1;
        const right2 = left2 + width2;
        return left1 < right2 && left2 < right1;
    }

    /**
     * Convert date to pixel position
     */
    dateToPixels(date) {
        // Convert date/time to horizontal pixel position based on view mode
        if (this.state.viewMode === 'day') {
            // For day view, calculate position within 24 hours
            const dayStart = new Date(this.state.currentDate);
            dayStart.setHours(0, 0, 0, 0);
            
            const diffHours = (date - dayStart) / (1000 * 60 * 60);
            return Math.max(0, diffHours * this.timelineConfig.hourWidth * this.state.zoomLevel);
            
        } else if (this.state.viewMode === 'week') {
            // For week view, calculate position within the week
            const weekStart = new Date(this.state.currentDate);
            const daysFromMonday = weekStart.getDay() === 0 ? 6 : weekStart.getDay() - 1; // Make Monday = 0
            weekStart.setDate(weekStart.getDate() - daysFromMonday);
            weekStart.setHours(0, 0, 0, 0);
            
            const diffDays = (date - weekStart) / (1000 * 60 * 60 * 24);
            return Math.max(0, diffDays * this.timelineConfig.hourWidth * this.state.zoomLevel);
            
        } else if (this.state.viewMode === 'month') {
            // For month view, calculate position within the month
            const monthStart = new Date(this.state.currentDate.getFullYear(), this.state.currentDate.getMonth(), 1);
            
            const diffDays = (date - monthStart) / (1000 * 60 * 60 * 24);
            const daysPerWeek = 7;
            const weekPosition = Math.floor(diffDays / daysPerWeek);
            return Math.max(0, weekPosition * this.timelineConfig.hourWidth * this.state.zoomLevel);
        }
        
        return 0;
    }

    /**
     * Convert duration to pixel width
     */
    durationToPixels(minutes) {
        if (this.state.viewMode === 'day') {
            // For day view, duration in hours
            const hours = minutes / 60;
            return hours * this.timelineConfig.hourWidth * this.state.zoomLevel;
        } else if (this.state.viewMode === 'week') {
            // For week view, minimum width is partial day
            const days = minutes / (60 * 24); // Convert to days
            return Math.max(
                this.timelineConfig.hourWidth * this.state.zoomLevel * 0.5, // Minimum half-day width
                days * this.timelineConfig.hourWidth * this.state.zoomLevel
            );
        } else if (this.state.viewMode === 'month') {
            // For month view, minimum width spans some portion of a week
            const days = minutes / (60 * 24);
            const weeks = days / 7;
            return Math.max(
                this.timelineConfig.hourWidth * this.state.zoomLevel * 0.3, // Minimum width
                weeks * this.timelineConfig.hourWidth * this.state.zoomLevel
            );
        }
        
        return this.timelineConfig.hourWidth * this.state.zoomLevel * 0.5; // Default minimum width
    }

    /**
     * Handle view mode change
     */
    async onViewModeChange(newMode) {
        this.state.viewMode = newMode;
        this.state.isLoading = true;
        await this.loadData();
    }

    /**
     * Navigate timeline
     */
    async onNavigate(direction) {
        const currentDate = new Date(this.state.currentDate);
        
        if (this.state.viewMode === 'day') {
            currentDate.setDate(currentDate.getDate() + (direction === 'next' ? 1 : -1));
        } else if (this.state.viewMode === 'week') {
            currentDate.setDate(currentDate.getDate() + (direction === 'next' ? 7 : -7));
        } else if (this.state.viewMode === 'month') {
            currentDate.setMonth(currentDate.getMonth() + (direction === 'next' ? 1 : -1));
        }
        
        this.state.currentDate = currentDate;
        this.state.isLoading = true;
        await this.loadData();
    }

    /**
     * Handle zoom change
     */
    onZoomChange(newZoom) {
        this.state.zoomLevel = newZoom;
        // Redraw timeline with new zoom level
        this.redrawTimeline();
    }

    /**
     * Redraw timeline
     */
    redrawTimeline() {
        // Recalculate positions and redraw
        this.state.timeSlots = this.generateTimeSlots();
    }

    /**
     * Open assignment details
     */
    async openAssignmentDetails(assignmentId) {
        try {
            console.log('Opening assignment details for ID:', assignmentId);
            
            // Get assignment data from state
            const assignment = this.state.assignments.find(a => a.id === assignmentId);
            if (!assignment) {
                console.error('Assignment not found in state:', assignmentId);
                this.notification.add('Assignment not found', { type: 'danger' });
                return;
            }
            
            // Create and show assignment details popup
            this.state.selectedAssignment = assignment;
            console.log('✅ Assignment details opened for:', assignment.name);
            
            // Show notification for now (will be replaced with proper modal later)
            this.notification.add(`Assignment: ${assignment.name} (${assignment.state})`, {
                type: 'info',
                title: 'Assignment Details',
                sticky: true
            });
            
        } catch (error) {
            console.error('Error opening assignment details:', error);
            this.notification.add('Error opening assignment details', { type: 'danger' });
        }
    }

    /**
     * Close assignment details popup
     */
    closeAssignmentDetails() {
        this.state.selectedAssignment = null;
        console.log('✅ Assignment details popup closed');
    }
}

// Register the component
registry.category("actions").add("assignment_timeline_view", AssignmentTimelineView);