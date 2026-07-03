# Part of the Viet Uc Care white-label layer. License LGPL-3.
import re

from odoo.http import request
from odoo.addons.web.controllers.database import Database

# Server-level fallback brand (the database manager lists ALL databases on the
# server, so it is inherently not per-database).
FALLBACK_BRAND = "Viet Uc Care"
FALLBACK_WEBSITE = "https://care.biztinct.com"
BRAND_LOGO = "/health_pwa/static/img/VietLogo.png"


class BizDatabase(Database):
    """Debrand the /web/database/{manager,selector} pages.

    The page is served pre-login (auth='none') by reading static qweb.html
    files, so it bypasses the normal translation/debranding pipeline. We
    post-process the rendered HTML instead of forking the core template.
    """

    def _brand(self):
        try:
            icp = request.env["ir.config_parameter"].sudo()
            return (
                icp.get_param("web_debranding.new_name") or FALLBACK_BRAND,
                icp.get_param("web_debranding.new_website") or FALLBACK_WEBSITE,
            )
        except Exception:
            # No database selected (multi-db) → config params unavailable.
            return FALLBACK_BRAND, FALLBACK_WEBSITE

    def _render_template(self, **d):
        html = super()._render_template(**d)
        if not isinstance(html, str):
            return html
        brand, website = self._brand()
        # Brand logo + favicon (static, public paths that need no database).
        html = html.replace("/web/static/img/logo2.png", BRAND_LOGO)
        html = html.replace("/web/static/img/favicon.ico", BRAND_LOGO)
        # odoo.com links first, then any standalone "Odoo" word.
        html = re.sub(r"https?://(www\.)?odoo\.com[^\"'> ]*", website, html, flags=re.IGNORECASE)
        html = re.sub(r"\bOdoo\b", brand, html)
        return html
