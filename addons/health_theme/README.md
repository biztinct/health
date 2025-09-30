# Healthcare Theme (Odoo 18 CE)

A professional, AA-accessible healthcare color palette for Odoo 18 CE backend, designed for VAFHS Healthcare System.

## Features

- ✅ **Professional Healthcare Colors**: Calming teal/blue-teal palette optimized for medical workflows
- ✅ **WCAG AA Compliant**: All color combinations meet accessibility standards
- ✅ **Odoo 18 Native**: Uses `web._assets_primary_variables` for proper SCSS variable override
- ✅ **Zero Dependencies**: Only depends on core `web` module
- ✅ **Lightweight**: Minimal CSS footprint, maximum performance

## Color Palette

### Primary Colors
- **Primary**: `#0F6D66` (Teal - calming, medical)
- **Secondary**: `#2E6F89` (Blue-Teal - trust, professionalism)

### State Colors
- **Success**: `#176B47` (Medical green)
- **Info**: `#2A7ABF` (Information blue)
- **Warning**: `#946200` (Caution amber)
- **Danger**: `#C0332A` (Alert red)

### Background Colors
- **Content**: `#F7FAF9` (Light mint - clean, clinical)
- **Surface**: `#ECF5F3` (Soft mint - subtle separation)
- **Border**: `#CFE3E1` (Light teal - soft boundaries)

## Installation

1. Copy `health_theme` to your Odoo addons directory
2. Update app list: **Apps → Update Apps List**
3. Install module: Search "Healthcare Theme" and click **Install**
4. Refresh browser with **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (Mac)

## Technical Architecture

This theme follows Odoo 18's best practices, inspired by the MuK Web Theme architecture:

### SCSS Variable Override
Uses `web._assets_primary_variables` to override Odoo's core variables **before** compilation:

```scss
$o-brand-primary: #0F6D66;
$o-brand-odoo: #0F6D66;
$primary: #0F6D66;
```

### File Structure
```
health_theme/
├── __manifest__.py                      # Module definition
├── views/
│   └── webclient_templates.xml         # Theme color meta tag
└── static/src/scss/
    ├── primary_variables.scss           # Core variable overrides
    └── backend.scss                     # Additional styling
```

## Upgrade from Previous Version

If you're upgrading from an older version:

```bash
./odoo-bin -c odoo.conf -d your_database -u health_theme --stop-after-init
```

Then restart Odoo and hard refresh your browser.

## Troubleshooting

**Colors not applying after installation?**
1. Upgrade the module: `odoo-bin -u health_theme`
2. Restart Odoo server
3. Clear browser cache: **Ctrl+Shift+R** or **Cmd+Shift+R**
4. Check browser console for asset loading errors

**Still not working?**
- Verify module is installed (not just "to install")
- Check Odoo logs for SCSS compilation errors
- Ensure no other theme modules are conflicting

## License

LGPL-3

## Credits

**Author**: VAFHS Healthcare System
**Website**: https://vafhs.com
**Architecture**: Inspired by MuK Web Theme patterns
