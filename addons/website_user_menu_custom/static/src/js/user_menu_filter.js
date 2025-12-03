/** @odoo-module **/

import { onMounted } from "@odoo/owl";

/**
 * Hide unwanted menu items from the user dropdown
 * This handles items that may not be caught by CSS selectors
 */
function hideUnwantedMenuItems() {
    // List of data-menu attribute values to hide
    const unwantedDataMenus = [
        'documentation',
        'support',
        'shortcuts',
        'web_tour.tour_enabled', // Onboarding
        'account' // My Odoo.com account
    ];

    // Hide items by data-menu attribute (most reliable)
    unwantedDataMenus.forEach(menuValue => {
        const items = document.querySelectorAll(`[data-menu="${menuValue}"]`);
        items.forEach(item => {
            item.style.display = 'none';
        });
    });

    // Fallback: Also hide by text content
    const unwantedMenuTexts = [
        'Documentation',
        'Support',
        'Shortcuts',
        'Onboarding',
        'My Odoo.com account'
    ];

    const dropdownItems = document.querySelectorAll('.o-dropdown-item, .dropdown-item');

    dropdownItems.forEach(item => {
        const itemText = item.textContent.trim();

        // Check if this item matches any unwanted text
        const shouldHide = unwantedMenuTexts.some(unwantedText =>
            itemText.toLowerCase().includes(unwantedText.toLowerCase())
        );

        if (shouldHide) {
            item.style.display = 'none';
        }
    });

    // Clean up consecutive dividers
    cleanupDividers();
}

/**
 * Remove consecutive or trailing dividers in dropdown menus
 */
function cleanupDividers() {
    const dropdowns = document.querySelectorAll('.dropdown-menu');

    dropdowns.forEach(dropdown => {
        const items = Array.from(dropdown.children);
        let previousWasDivider = false;

        items.forEach((item, index) => {
            const isDivider = item.classList.contains('dropdown-divider') ||
                             item.tagName === 'HR';

            if (isDivider) {
                // Hide if previous was also a divider, or if it's the first/last item
                const isVisible = getComputedStyle(item).display !== 'none';
                if (isVisible && (previousWasDivider || index === 0 || index === items.length - 1)) {
                    item.style.display = 'none';
                }
                previousWasDivider = true;
            } else {
                const isVisible = getComputedStyle(item).display !== 'none';
                if (isVisible) {
                    previousWasDivider = false;
                }
            }
        });
    });
}

/**
 * Initialize the menu filter when DOM is ready
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hideUnwantedMenuItems);
} else {
    hideUnwantedMenuItems();
}

// Also run when user dropdown is shown (for dynamically loaded content)
document.addEventListener('shown.bs.dropdown', hideUnwantedMenuItems);

// MutationObserver to catch dynamically added menu items
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.addedNodes.length > 0) {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    if (node.classList && (node.classList.contains('dropdown-menu') ||
                        node.querySelector && node.querySelector('.dropdown-menu'))) {
                        setTimeout(hideUnwantedMenuItems, 100);
                    }
                }
            });
        }
    });
});

// Start observing
if (document.body) {
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
} else {
    document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
}
