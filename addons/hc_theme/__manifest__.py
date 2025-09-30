{
    "name": "Healthcare Theme (Backend + Website)",
    "summary": "Calm, AA-accessible healthcare palette for Odoo 18 CE (backend + website)",
    "version": "18.0.1.0.0",
    "category": "Theme",
    "author": "ChatGPT Assistant",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": ["web", "website"],
    "assets": {
        "web.assets_backend": [
            "hc_theme/static/src/scss/variables.scss",
            "hc_theme/static/src/scss/backend.scss"
        ],
        "web.assets_frontend": [
            "hc_theme/static/src/scss/variables.scss",
            "hc_theme/static/src/scss/frontend.scss"
        ]
    },
    "installable": true,
    "application": false
}