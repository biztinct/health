# Part of the Viet Uc Care white-label layer.
# License LGPL-3.
{
    "name": "Business Debranding (Viet Uc Care)",
    "version": "19.0.1.0.0",
    "category": "Debranding",
    "summary": "Orchestrates full white-labelling to the configured brand "
               "(default: Viet Uc Care). Seeds debranding params, favicon, "
               "website identity, OdooBot and PWA; SaaS-configurable per database.",
    "author": "Viet Uc Care",
    "website": "https://care.biztinct.com",
    "license": "LGPL-3",
    "depends": [
        "base_setup",
        "web_debranding",
        "mail_debranding",
        "portal_debranding",
        "website_debranding",
        "disable_odoo_online",
        "website",
        "health_pwa",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "data/apply_brand.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "biz_debranding/static/src/xml/notification_alert.xml",
            "biz_debranding/static/src/xml/res_config_edition.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
