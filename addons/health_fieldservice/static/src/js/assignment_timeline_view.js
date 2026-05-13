/** @odoo-module **/

/**
 * Assignment Timeline View Enhancer
 * Adds professional styling to vis.js timeline items used by web_timeline
 */

const TIMELINE_STYLES_ID = 'timeline-enhancements';

function injectTimelineStyles() {
    if (document.getElementById(TIMELINE_STYLES_ID)) return;

    const style = document.createElement('style');
    style.id = TIMELINE_STYLES_ID;
    style.textContent = `
        .vis-item {
            border-radius: 4px;
            font-size: 11px;
            line-height: 1.3;
            padding: 4px 8px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            border-left: 3px solid #90a4ae;
        }
        .vis-item[style*="#f8f9fa"] { border-left-color: #90a4ae; }
        .vis-item[style*="#e3f2fd"] { border-left-color: #42a5f5; }
        .vis-item[style*="#e8f5e8"] { border-left-color: #66bb6a; }
        .vis-item[style*="#fff3e0"] { border-left-color: #ff9800; }
        .vis-item[style*="#ffebee"] { border-left-color: #ef5350; }
        .o_healthcare_assignment_item {
            display: flex;
            align-items: center;
            gap: 6px;
            height: 100%;
        }
        .client_name {
            flex: 1;
            font-weight: 700;
            font-size: 11px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #333;
        }
        .assignment_datetime,
        .assignment_duration {
            flex-shrink: 0;
            font-size: 9px;
            color: #666;
            font-weight: 400;
        }
    `;
    document.head.appendChild(style);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectTimelineStyles);
} else {
    injectTimelineStyles();
}
