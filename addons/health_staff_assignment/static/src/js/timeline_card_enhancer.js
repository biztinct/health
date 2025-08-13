/** @odoo-module **/

/**
 * Professional Timeline Card Enhancer
 * Adds icons, badges, and professional styling to web_timeline cards
 * Inspired by Monday.com, Asana Timeline, and Calendly
 */

// Simple utility functions for enhancing timeline cards
function enhanceTimelineCards() {
    // Find all timeline events in the DOM
    const timelineEvents = document.querySelectorAll('.vis-item, .timeline-event');
    
    timelineEvents.forEach(event => {
        if (!event.dataset.enhanced) {
            enhanceEvent(event);
            event.dataset.enhanced = 'true';
        }
    });
}

function enhanceEvent(eventElement) {
    try {
        const content = eventElement.textContent || '';
        const contentDiv = eventElement.querySelector('.vis-item-content, .timeline-event-content');
        
        // Get or parse assignment data
        const data = parseAssignmentData(eventElement, content);
        
        if (data && contentDiv) {
            // Enhance the existing content instead of replacing it
            addIconsToContent(contentDiv, data);
            
            // Add data attributes for CSS styling
            eventElement.setAttribute('data-priority', data.priority);
            eventElement.setAttribute('data-state', data.state);
            eventElement.setAttribute('data-type', data.type);
            eventElement.classList.add('enhanced_timeline_event');
        }
    } catch (error) {
        console.warn('Error enhancing timeline event:', error);
    }
}

function parseAssignmentData(element, content) {
    const data = {
        title: content || element.title || 'Assignment',
        priority: '1',
        state: 'draft',
        type: 'clinic_visit'
    };
    
    // Parse priority from content patterns
    if (content.includes('Emergency') || content.includes('emergency')) {
        data.priority = '4';
        data.type = 'emergency';
    } else if (content.includes('Urgent') || content.includes('urgent')) {
        data.priority = '3';
    } else if (content.includes('High') || content.includes('high')) {
        data.priority = '2';
    }
    
    // Parse type from content
    if (content.includes('Home') || content.includes('home')) data.type = 'home_visit';
    if (content.includes('Clinic') || content.includes('clinic')) data.type = 'clinic_visit';
    if (content.includes('Follow') || content.includes('follow')) data.type = 'follow_up';
    if (content.includes('Consultation') || content.includes('consultation')) data.type = 'consultation';
    
    // Parse state from content
    if (content.includes('completed') || content.includes('Completed')) data.state = 'completed';
    if (content.includes('progress') || content.includes('Progress')) data.state = 'in_progress';
    if (content.includes('confirmed') || content.includes('Confirmed')) data.state = 'confirmed';
    if (content.includes('assigned') || content.includes('Assigned')) data.state = 'assigned';
    if (content.includes('cancelled') || content.includes('Cancelled')) data.state = 'cancelled';
    
    return data;
}

function addIconsToContent(contentDiv, data) {
    const originalHTML = contentDiv.innerHTML;
    
    // Create enhanced content with icons
    const enhancedHTML = `
        <div class="timeline_card_enhanced">
            <div class="card_header_inline">
                <span class="priority_badge priority_${data.priority}">
                    ${getPriorityIcon(data.priority)}
                </span>
                <span class="type_icon">
                    ${getTypeIcon(data.type)}
                </span>
            </div>
            <div class="card_content_inline">
                <div class="assignment_title">${data.title}</div>
                <div class="state_badge_inline">
                    ${getStateIcon(data.state)}
                    <span class="state_text">${data.state.replace('_', ' ')}</span>
                </div>
            </div>
        </div>
    `;
    
    contentDiv.innerHTML = enhancedHTML;
}

function getPriorityIcon(priority) {
    const icons = {
        '4': '<i class="fa fa-exclamation-circle"></i>',
        '3': '<i class="fa fa-exclamation-triangle"></i>',
        '2': '<i class="fa fa-circle"></i>',
        '1': '<i class="fa fa-circle-o"></i>',
        '0': '<i class="fa fa-circle-o"></i>'
    };
    return icons[priority] || icons['1'];
}

function getTypeIcon(type) {
    const icons = {
        'clinic_visit': '<i class="fa fa-hospital-o"></i>',
        'home_visit': '<i class="fa fa-home"></i>',
        'emergency': '<i class="fa fa-ambulance"></i>',
        'follow_up': '<i class="fa fa-stethoscope"></i>',
        'consultation': '<i class="fa fa-user-md"></i>'
    };
    return icons[type] || icons['clinic_visit'];
}

function getStateIcon(state) {
    const icons = {
        'draft': '<i class="fa fa-clock-o"></i>',
        'assigned': '<i class="fa fa-user-plus"></i>',
        'confirmed': '<i class="fa fa-check-circle-o"></i>',
        'in_progress': '<i class="fa fa-play-circle"></i>',
        'completed': '<i class="fa fa-check-circle"></i>',
        'cancelled': '<i class="fa fa-times-circle"></i>'
    };
    return icons[state] || icons['draft'];
}

// Initialize enhancement
function initTimelineEnhancer() {
    // Initial enhancement after short delay
    setTimeout(enhanceTimelineCards, 1000);
    setTimeout(enhanceTimelineCards, 2000);
    setTimeout(enhanceTimelineCards, 3000);
    
    // Monitor for new content
    const observer = new MutationObserver((mutations) => {
        let shouldEnhance = false;
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                shouldEnhance = true;
            }
        });
        
        if (shouldEnhance) {
            setTimeout(enhanceTimelineCards, 100);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Also enhance on scroll and resize events
    window.addEventListener('scroll', () => {
        setTimeout(enhanceTimelineCards, 100);
    });
    
    window.addEventListener('resize', () => {
        setTimeout(enhanceTimelineCards, 100);
    });
}

// Start enhancement when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTimelineEnhancer);
} else {
    initTimelineEnhancer();
}