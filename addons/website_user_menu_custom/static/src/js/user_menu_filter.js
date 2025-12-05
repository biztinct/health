/** @odoo-module **/

import { onMounted } from "@odoo/owl";

const ALLOWED_MENUS = ['shortcuts', 'tickets', 'settings', 'logout'];

/**
 * Ensure Tickets entry exists after Shortcuts.
 */
function ensureTicketsEntry() {
    const dropdown = document.querySelector('.o_user_menu .dropdown-menu, .o_popover.o-dropdown--menu, .dropdown-menu.show');
    if (!dropdown) return;

    // Avoid duplicates
    if (dropdown.querySelector('[data-menu="tickets"]')) return;

    const shortcuts = dropdown.querySelector('[data-menu="shortcuts"]');
    const refNode = shortcuts ? shortcuts.nextSibling : dropdown.firstChild;
    const a = document.createElement('a');
    a.className = 'dropdown-item';
    a.setAttribute('href', '/my/tickets');
    a.setAttribute('data-menu', 'tickets');
    a.textContent = 'Tickets';
    dropdown.insertBefore(a, refNode);
}

/**
 * Hide unwanted menu items and keep only allowed entries.
 */
function filterUserMenu() {
    ensureTicketsEntry();

const items = document.querySelectorAll('.o_user_menu [data-menu], .dropdown-menu [data-menu], .o_popover.o-dropdown--menu [data-menu]');
    items.forEach(item => {
        const val = item.getAttribute('data-menu');
        if (!ALLOWED_MENUS.includes(val)) {
            item.style.display = 'none';
        } else {
            item.style.display = '';
        }
    });

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
    document.addEventListener('DOMContentLoaded', filterUserMenu);
} else {
    filterUserMenu();
}

// Also run when user dropdown is shown (for dynamically loaded content)
document.addEventListener('shown.bs.dropdown', filterUserMenu);
document.addEventListener('mouseover', (ev) => {
    if (ev.target && ev.target.closest && ev.target.closest('.o_user_menu')) {
        filterUserMenu();
    }
});

// MutationObserver to catch dynamically added menu items
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.addedNodes.length > 0) {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    if (node.classList && (node.classList.contains('dropdown-menu') ||
                        node.querySelector && node.querySelector('.dropdown-menu'))) {
                        setTimeout(filterUserMenu, 100);
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
