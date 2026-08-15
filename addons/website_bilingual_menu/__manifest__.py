# -*- coding: utf-8 -*-
{
    "name": "Website Bilingual Menu",
    "version": "19.0.2.6.16",
    "category": "Website",
    "summary": "Two-line English and Māori website navigation",
    "description": """
Website Bilingual Menu
======================

Displays website menu labels on two lines. Enter a menu name in the form
``English label|Māori label`` and the public website renders the English label
in bold above the Māori label. Menu names without a pipe remain unchanged.
    """,
    "author": "VAFHS",
    "website": "https://vafhs.com",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "views/menu_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_bilingual_menu/static/src/scss/bilingual_menu.scss",
            "website_bilingual_menu/static/src/scss/site_refresh.scss",
            "website_bilingual_menu/static/src/scss/homepage_editorial.scss",
            "website_bilingual_menu/static/src/scss/help_page.scss",
            "website_bilingual_menu/static/src/js/homepage_editorial.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
