{
    'name': 'Việt Úc Clinic Official Theme',
    'summary': 'Official Việt Úc Clinic branding for Odoo 19 CE - Professional healthcare theme',
    'description': '''
        Official Việt Úc Clinic Theme
        =============================

        This module implements the official Việt Úc Clinic brand guidelines for Odoo 19 CE,
        providing a professional, modern, and accessible healthcare interface.

        Brand Essence
        -------------
        - Trustworthy, Professional, Compassionate, Modern & Clean

        Official Color Palette (Based on Brandingcompressed.pdf)
        ---------------------------------------------------------

        Primary Logo Colors (Brand Identity):
        - Hibiscus Red: #E53935 (Logo flower - passion, trust, responsibility)
        - Hibiscus Orange: #FB8C00 (Logo flower gradient)
        - Leaf Green: #43A047 (Logo leaf - natural, health-related)

        Secondary UI Colors (Application Theme):
        - Deep Blue: #1565C0 (Primary actions, buttons, navbar - calm & professional)
        - Accent Blue: #42A5F5 (Interactive elements, hover states - modern & engaging)

        State Colors (Healthcare Compliance):
        - Success: #176B47 (Medical green - positive outcomes)
        - Info: #2A7ABF (Information blue - system messages)
        - Warning: #946200 (Caution amber - important notices)
        - Danger: #C0332A (Alert red - critical actions)

        Typography System
        -----------------
        - Primary Headings: Montserrat (Semi Bold 600, Extra Bold 800)
        - Body Text: Segoe UI (Regular 400, Semi Bold 600, Bold 700)
        - Fallback: Arial

        Features
        --------
        - Overrides all Odoo core SCSS variables before compilation
        - Bootstrap-compatible color system
        - Professional shadows and borders for depth
        - Accessible color contrasts (WCAG AA compliant)
        - Modern pill-shaped badges for healthcare workflows
        - Custom navbar and control panel styling
    ''',
    'version': '19.0.3.0.1',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'VAFHS Healthcare System - Vietnam-Australia Family Health Service',
    'website': 'https://vafhs.com',
    'depends': [
        'web',
        'base',
    ],
    'data': [
        'views/webclient_templates.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'health_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            # Core theme
            'health_theme/static/src/scss/backend.scss',
            'health_theme/static/src/scss/loading_spinner.scss',
            # VU Design System — Adaptive Form Framework
            'health_theme/static/src/scss/state_system.scss',
            'health_theme/static/src/scss/three_column.scss',
            'health_theme/static/src/scss/progress_rail.scss',
            'health_theme/static/src/scss/action_card.scss',
            'health_theme/static/src/scss/inline_edit.scss',
            'health_theme/static/src/scss/field_indicators.scss',
            'health_theme/static/src/scss/side_sheet.scss',
            # OWL components — JS
            'health_theme/static/src/js/vu_form_state.js',
            'health_theme/static/src/js/vu_progress_rail.js',
            'health_theme/static/src/js/vu_side_sheet.js',
            'health_theme/static/src/js/vi_translation_terms.js',
            # OWL components — Templates
            'health_theme/static/src/xml/vu_progress_rail.xml',
            'health_theme/static/src/xml/vu_side_sheet.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
