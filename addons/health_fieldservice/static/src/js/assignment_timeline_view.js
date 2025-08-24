/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * Assignment Timeline View Enhancer
 * Professional timeline enhancements without complex inheritance
 */
class AssignmentTimelineEnhancer {
    constructor() {
        this.isInitialized = false;
    }

    init() {
        if (this.isInitialized) return;
        
        this.setupTimelineEnhancements();
        this.isInitialized = true;
    }

    setupTimelineEnhancements() {
        console.log('🔧 DEBUG: Assignment Timeline Enhancer - Setting up enhancements');
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            console.log('🔧 DEBUG: DOM still loading, waiting...');
            document.addEventListener('DOMContentLoaded', () => {
                console.log('🔧 DEBUG: DOM loaded, enhancing timeline views');
                this.enhanceTimelineViews();
            });
        } else {
            console.log('🔧 DEBUG: DOM ready, enhancing timeline views immediately');
            this.enhanceTimelineViews();
        }

        // Watch for new timeline views - safely check if document.body exists
        this.setupMutationObserver();
    }

    setupMutationObserver() {
        // Safely setup mutation observer when DOM is ready
        const setupObserver = () => {
            if (!document.body) {
                // Retry after a short delay if document.body is not ready
                setTimeout(setupObserver, 100);
                return;
            }

            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1 && (node.classList?.contains('o_timeline_view') || node.querySelector?.('.o_timeline_view'))) {
                            this.enhanceTimelineViews();
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

    enhanceTimelineViews() {
        console.log('🔧 DEBUG: Enhancing timeline views...');
        
        // Check for web_timeline assignments (the actual ones being used)
        const webTimelineItems = document.querySelectorAll('.vis-item, .o_healthcare_assignment_item');
        console.log('🔧 DEBUG: Found web_timeline items:', webTimelineItems.length);
        
        // Enhance web_timeline items
        webTimelineItems.forEach((item, index) => {
            console.log(`🔧 DEBUG: Processing web_timeline item ${index}:`, item);
            if (!item.dataset.enhanced) {
                this.enhanceWebTimelineItem(item);
                item.dataset.enhanced = 'true';
                console.log('🔧 DEBUG: Enhanced web_timeline item');
            }
        });
        
        // Check for our custom timeline assignments (in case both exist)
        const customAssignments = document.querySelectorAll('.o_timeline_assignment');
        console.log('🔧 DEBUG: Found custom timeline assignments:', customAssignments.length);
        
        // Enhance custom timeline assignments  
        customAssignments.forEach((assignment, index) => {
            console.log(`🔧 DEBUG: Processing assignment ${index}:`, assignment);
            if (!assignment.dataset.enhanced) {
                this.enhanceCustomAssignment(assignment);
                assignment.dataset.enhanced = 'true';
                assignment.classList.add('DEBUG_FORCE_MINIMAL'); // Add debug class
                console.log('🔧 DEBUG: Enhanced assignment with debug class');
            }
        });

        // Add professional styling
        this.addProfessionalStyling();
        
        // Start continuous monitoring for timeline items
        this.startContinuousMonitoring();
    }

    startContinuousMonitoring() {
        console.log('🔧 DEBUG: Starting continuous timeline monitoring...');
        
        // Monitor every 500ms for new or changed timeline items
        setInterval(() => {
            const visItems = document.querySelectorAll('.vis-item:not([data-enhanced])');
            if (visItems.length > 0) {
                console.log(`🔧 DEBUG: Found ${visItems.length} new timeline items to enhance`);
                visItems.forEach(item => {
                    this.enhanceWebTimelineItem(item);
                    item.dataset.enhanced = 'true';
                });
            }
            
        }, 500);
    }


    enhanceWebTimelineItem(timelineItem) {
        console.log('🔧 DEBUG: Found web_timeline item (no styling applied):', timelineItem);
        
        // No styling modifications - preserve original web_timeline appearance
        try {
            const assignmentItem = timelineItem.querySelector('.o_healthcare_assignment_item');
            if (assignmentItem) {
                console.log('🔧 DEBUG: Found healthcare assignment item (no modifications)');
            }
            
            console.log('🔧 DEBUG: Web timeline item preserved as original');
            
        } catch (error) {
            console.warn('🔧 DEBUG: Error processing web_timeline item:', error);
        }
    }


    minimizeAssignmentContent(assignmentItem) {
        // No modifications - preserve original healthcare assignment item styling
        console.log('🔧 DEBUG: Healthcare assignment item preserved as original');
    }

    enhanceCustomAssignment(assignmentElement) {
        console.log('🔧 DEBUG: Enhancing custom assignment:', assignmentElement);
        
        try {
            // Force apply minimal styling
            assignmentElement.style.height = '16px';
            assignmentElement.style.fontSize = '8px';
            assignmentElement.style.minWidth = '80px';
            
            // Add drag functionality if missing
            if (!assignmentElement.draggable) {
                assignmentElement.draggable = true;
                console.log('🔧 DEBUG: Made assignment draggable');
            }
            
            // Add event listeners for drag
            this.addDragListeners(assignmentElement);
            
        } catch (error) {
            console.warn('🔧 DEBUG: Error enhancing custom assignment:', error);
        }
    }

    addDragListeners(element) {
        element.addEventListener('dragstart', (e) => {
            console.log('🔧 DEBUG: Drag started for assignment:', element);
            e.dataTransfer.setData('text/plain', element.dataset.assignmentId);
            element.classList.add('o_dragging');
        });
        
        element.addEventListener('dragend', (e) => {
            console.log('🔧 DEBUG: Drag ended for assignment:', element);
            element.classList.remove('o_dragging');
        });
    }

    enhanceTimelineEvent(eventElement) {
        try {
            // Add priority indicators
            this.addPriorityToEvent(eventElement);
            
            // Add status indicators  
            this.addStatusToEvent(eventElement);
            
            // Add hover effects
            this.addHoverToEvent(eventElement);
            
        } catch (error) {
            console.warn('Error enhancing timeline event:', error);
        }
    }

    addPriorityToEvent(event) {
        const content = event.textContent || '';
        const priority = this.extractPriority(content);
        
        if (priority) {
            const indicator = document.createElement('span');
            indicator.className = `priority-indicator priority-${priority}`;
            indicator.innerHTML = this.getPriorityIcon(priority);
            event.appendChild(indicator);
        }
    }

    addStatusToEvent(event) {
        const content = event.textContent || '';
        const status = this.extractStatus(content);
        
        if (status) {
            event.classList.add(`status-${status}`);
        }
    }

    addHoverToEvent(event) {
        event.addEventListener('mouseenter', () => {
            event.style.transform = 'scale(1.02)';
            event.style.zIndex = '1000';
            event.style.transition = 'all 0.2s ease';
        });

        event.addEventListener('mouseleave', () => {
            event.style.transform = 'scale(1)';
            event.style.zIndex = '';
        });
    }

    extractPriority(content) {
        if (content.includes('Emergency') || content.includes('emergency')) return 'emergency';
        if (content.includes('Urgent') || content.includes('urgent')) return 'urgent';
        if (content.includes('High') || content.includes('high')) return 'high';
        if (content.includes('Low') || content.includes('low')) return 'low';
        return 'normal';
    }

    extractStatus(content) {
        if (content.includes('Complete') || content.includes('complete')) return 'completed';
        if (content.includes('Progress') || content.includes('progress')) return 'in_progress';
        if (content.includes('Assigned') || content.includes('assigned')) return 'assigned';
        if (content.includes('Draft') || content.includes('draft')) return 'draft';
        return 'unknown';
    }

    getPriorityIcon(priority) {
        const icons = {
            'emergency': '🚨',
            'urgent': '⚡',
            'high': '🔴',
            'normal': '🔵',
            'low': '🟡'
        };
        return icons[priority] || '🔵';
    }

    addProfessionalStyling() {
        console.log('🔧 DEBUG: Adding professional styling...');
        
        // Add custom CSS for timeline enhancements
        const style = document.createElement('style');
        style.id = 'timeline-debug-styles';
        style.textContent = `
            /* Minimal vis.js timeline styling - following vis.js best practices */
            
            /* Timeline Item Enhancements */
            .vis-item {
                border-radius: 4px;
                font-size: 11px;
                line-height: 1.3;
                padding: 4px 8px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                border-left: 3px solid #90a4ae;
            }
            
            /* Professional State Color Accents */
            .vis-item[style*="#f8f9fa"] { border-left-color: #90a4ae; }  /* Draft - Gray */
            .vis-item[style*="#e3f2fd"] { border-left-color: #42a5f5; }  /* Assigned - Blue */
            .vis-item[style*="#e8f5e8"] { border-left-color: #66bb6a; }  /* Confirmed/Completed - Green */
            .vis-item[style*="#fff3e0"] { border-left-color: #ff9800; }  /* In Progress - Orange */
            .vis-item[style*="#ffebee"] { border-left-color: #ef5350; }  /* Cancelled - Red */
            
            /* Healthcare Assignment Item */
            .o_healthcare_assignment_item {
                display: flex;
                align-items: center;
                gap: 6px;
                height: 100%;
            }
            
            /* Client Name - Bold */
            .client_name {
                flex: 1;
                font-weight: 700;
                font-size: 11px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                color: #333;
            }
            
            /* Date/Time and Duration */
            .assignment_datetime,
            .assignment_duration {
                flex-shrink: 0;
                font-size: 9px;
                color: #666;
                font-weight: 400;
            }
            
            /* DEBUG: Custom Timeline Assignment (for custom timeline if exists) */
            .o_timeline_assignment {
                height: 16px !important;
                background: #ff0000 !important;
                color: white !important;
                font-size: 8px !important;
                border: 2px solid yellow !important;
                border-radius: 3px !important;
            }
        `;
        
        if (!document.getElementById('timeline-enhancements')) {
            style.id = 'timeline-enhancements';
            document.head.appendChild(style);
            console.log('🔧 DEBUG: Added timeline enhancement styles to head');
        } else {
            console.log('🔧 DEBUG: Timeline enhancement styles already exist');
        }
        
        // Add global debug function
        window.debugTimeline = () => {
            console.log('🔧 TIMELINE DEBUG INFO:');
            console.log('- Assignment elements:', document.querySelectorAll('.o_timeline_assignment').length);
            console.log('- Healthcare assignment items:', document.querySelectorAll('.o_healthcare_assignment_item').length);
            console.log('- Timeline view elements:', document.querySelectorAll('.o_assignment_timeline_view').length);
            console.log('- Vis items:', document.querySelectorAll('.vis-item').length);
            console.log('- Debug styles applied:', !!document.getElementById('timeline-enhancements'));
            
            // Check for any timeline-related elements
            console.log('🔍 ALL TIMELINE-RELATED ELEMENTS:');
            console.log('- .o_timeline_*:', document.querySelectorAll('[class*="timeline"]').length);
            console.log('- .vis-*:', document.querySelectorAll('[class*="vis-"]').length);
            console.log('- .assignment*:', document.querySelectorAll('[class*="assignment"]').length);
            console.log('- .healthcare*:', document.querySelectorAll('[class*="healthcare"]').length);
            console.log('- .o_action_*:', document.querySelectorAll('[class*="o_action"]').length);
            console.log('- .o_view_*:', document.querySelectorAll('[class*="o_view"]').length);
            
            // List all vis.js items
            const visItems = document.querySelectorAll('.vis-item');
            visItems.forEach((el, i) => {
                console.log(`Vis Item ${i}:`, {
                    className: el.className,
                    innerHTML: el.innerHTML.substring(0, 100),
                    height: el.style.height,
                    computedHeight: window.getComputedStyle(el).height
                });
            });
            
            // List all healthcare assignment items  
            const healthcareItems = document.querySelectorAll('.o_healthcare_assignment_item');
            healthcareItems.forEach((el, i) => {
                console.log(`Healthcare Item ${i}:`, {
                    className: el.className,
                    innerHTML: el.innerHTML.substring(0, 100),
                    parentHeight: el.parentElement.style.height
                });
            });
            
            const assignments = document.querySelectorAll('.o_timeline_assignment');
            assignments.forEach((el, i) => {
                console.log(`Assignment ${i}:`, {
                    height: el.style.height,
                    computedHeight: window.getComputedStyle(el).height,
                    classes: el.className,
                    draggable: el.draggable
                });
            });
        };
    }
}

// Safe initialization - ensure DOM is ready
const initializeTimelineEnhancer = () => {
    console.log('🔧 DEBUG: Initializing Timeline Enhancer...');
    
    const timelineEnhancer = new AssignmentTimelineEnhancer();
    timelineEnhancer.init();

    // Make available globally
    window.AssignmentTimelineEnhancer = timelineEnhancer;
    console.log('🔧 DEBUG: Timeline Enhancer available globally');

    // Register in Odoo registry
    try {
        registry.category("timeline_utils").add("enhancer", timelineEnhancer);
        console.log('🔧 DEBUG: Timeline Enhancer registered in Odoo registry');
    } catch (error) {
        console.warn('🔧 DEBUG: Could not register in Odoo registry:', error);
    }
    
    // Add immediate debug check
    setTimeout(() => {
        console.log('🔧 DEBUG: Running initial timeline check...');
        window.debugTimeline && window.debugTimeline();
    }, 1000);
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTimelineEnhancer);
} else {
    // DOM is already ready
    initializeTimelineEnhancer();
}