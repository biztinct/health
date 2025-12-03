# Website User Menu Customization

This module customizes the website user dropdown menu to show only essential menu items.

## Features

### Hidden Menu Items
- Documentation
- Support
- Shortcuts
- Onboarding
- My Odoo.com account

### Visible Menu Items
- My Profile
- Log out

## Installation

1. **Update Apps List**
   - Go to Apps
   - Click "Update Apps List"
   - Search for "Website User Menu Customization"

2. **Install the Module**
   - Click Install

3. **Refresh the Website**
   - Clear browser cache
   - Refresh the website page
   - The user dropdown should now show only Profile and Logout

## Technical Details

This module uses two complementary approaches to hide menu items:

1. **CSS Hiding** ([user_menu.css](static/src/css/user_menu.css)): Hides menu items based on href patterns, classes, and data attributes
2. **JavaScript Filtering** ([user_menu_filter.js](static/src/js/user_menu_filter.js)): Dynamically hides menu items based on text content and handles dynamically loaded content

This dual approach ensures maximum compatibility across different Odoo configurations and versions.

## Dependencies

- `website`
- `portal`

## Compatibility

- Odoo 18.0
