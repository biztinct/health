/** @odoo-module **/

import { Component, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormRenderer } from "@web/views/form/form_renderer";

/**
 * Notebook Icon Replacer
 *
 * Automatically replaces emoji icons in notebook tabs with Font Awesome icons
 * for a more professional appearance.
 */

// Icon mapping: Unicode emoji → Font Awesome class
const ICON_MAPPING = {
    // Emoji Unicode → FA icon class
    '📍': 'fa-map-marker',
    '🏥': 'fa-heartbeat',
    '💳': 'fa-credit-card',
    '📋': 'fa-list-alt',
    '📦': 'fa-gift',
    '👥': 'fa-users',
    '🚀': 'fa-road',
    '📝': 'fa-file-text-o',
    '🗺️': 'fa-map',
    '💊': 'fa-medkit',
    '🔬': 'fa-flask',
    '📊': 'fa-bar-chart',
    '⚙️': 'fa-cogs',
    '📞': 'fa-phone',
    '✉️': 'fa-envelope',
    '🏦': 'fa-building',
    '💰': 'fa-money',
    '📈': 'fa-line-chart',
    '🔔': 'fa-bell',
    '⭐': 'fa-star',
};

/**
 * Replace emoji with Font Awesome icons in notebook tabs
 */
function replaceNotebookIcons() {
    // Find all notebook tab links
    const tabs = document.querySelectorAll('.o_notebook .nav-tabs .nav-link');

    tabs.forEach(tab => {
        const text = tab.textContent.trim();

        // Check if tab contains any emoji from our mapping
        for (const [emoji, faClass] of Object.entries(ICON_MAPPING)) {
            if (text.includes(emoji)) {
                // Replace emoji with FA icon + text
                const cleanText = text.replace(emoji, '').trim();
                tab.innerHTML = `<i class="fa ${faClass} me-2"></i>${cleanText}`;
                break;
            }
        }
    });
}

/**
 * Enhanced Form Renderer with Notebook Icon Support
 */
class NotebookIconFormRenderer extends FormRenderer {
    setup() {
        super.setup();

        onMounted(() => {
            // Replace icons after form is mounted
            replaceNotebookIcons();

            // Watch for dynamic tab changes (e.g., switching views)
            try {
                const observer = new MutationObserver(() => {
                    replaceNotebookIcons();
                });

                // Find notebook in the document
                const notebookContainer = document.querySelector('.o_notebook');
                if (notebookContainer) {
                    observer.observe(notebookContainer, {
                        childList: true,
                        subtree: true,
                    });
                }
            } catch (error) {
                console.warn('Notebook icon observer setup failed:', error);
            }
        });
    }
}

// Don't force override - just extend if needed
// Comment this out to avoid conflicts
/*
registry.category("views").add("form", {
    ...formView,
    Renderer: NotebookIconFormRenderer,
}, { force: true });
*/

/**
 * Alternative: Standalone initialization for backward compatibility
 * This runs on page load to replace icons immediately
 */
document.addEventListener('DOMContentLoaded', () => {
    replaceNotebookIcons();

    // Also run after a short delay to catch dynamically loaded content
    setTimeout(replaceNotebookIcons, 500);
    setTimeout(replaceNotebookIcons, 1500);
});

// Export for use in other modules if needed
export { replaceNotebookIcons, ICON_MAPPING };
