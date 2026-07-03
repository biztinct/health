# Part of the Viet Uc Care white-label layer. License LGPL-3.
import base64
import logging

from odoo import api, fields, models
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

# Default brand for this deployment. Any client database may override
# `biz_debranding.brand_name` (and the web_debranding params) before/after
# install — the seed never clobbers a value that is already customised.
DEFAULT_BRAND = "Viet Uc Care"
DEFAULT_WEBSITE = "https://care.biztinct.com"
DEFAULT_THEME_COLOR = "#1565C0"

# Brand icon reused from health_pwa so we ship no duplicate binary assets.
# (The PWA icon-*.png files are ASCII placeholders, not real images — use the
# valid brand logo instead.)
BRAND_ICON = "health_pwa/static/img/VietLogo.png"


def _read_icon_b64():
    try:
        with file_open(BRAND_ICON, "rb") as f:
            return base64.b64encode(f.read())
    except Exception:
        _logger.warning("biz_debranding: could not read brand icon %s", BRAND_ICON, exc_info=True)
        return None


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Single SaaS brand knob. Kept in sync with the web_debranding params so
    # the whole white-label follows one field, per database.
    biz_brand_name = fields.Char(
        string="Brand Name",
        config_parameter="biz_debranding.brand_name",
        help="Product name shown everywhere in place of Odoo "
             "(browser title, backend, emails, PWA, bot).",
    )
    biz_brand_website = fields.Char(
        string="Brand Website",
        config_parameter="biz_debranding.brand_website",
        help="Replaces odoo.com links across the UI.",
    )
    biz_theme_color = fields.Char(
        string="Brand Theme Color",
        config_parameter="biz_debranding.theme_color",
        help="PWA / mobile theme color (hex, e.g. #1565C0).",
    )

    # ------------------------------------------------------------------
    # Seeding — runs on install AND every upgrade (via data <function>),
    # so the white-label identity is re-applied idempotently.
    # ------------------------------------------------------------------
    @api.model
    def _biz_apply_brand(self):
        icp = self.env["ir.config_parameter"].sudo()

        brand = (icp.get_param("biz_debranding.brand_name") or DEFAULT_BRAND).strip()
        website = (icp.get_param("biz_debranding.brand_website") or DEFAULT_WEBSITE).strip()
        theme_color = (icp.get_param("biz_debranding.theme_color") or DEFAULT_THEME_COLOR).strip()

        # Canonical brand params (source of truth for web_debranding + PWA).
        icp.set_param("biz_debranding.brand_name", brand)
        icp.set_param("biz_debranding.brand_website", website)
        icp.set_param("biz_debranding.theme_color", theme_color)

        # Drive the installed debranding suite; fixes the single-slash
        # `https:/care.biztinct.com` bug that was live.
        icp.set_param("web_debranding.new_name", brand)
        icp.set_param("web_debranding.new_title", brand)
        icp.set_param("web_debranding.new_website", website)
        icp.set_param("web_debranding.new_documentation_website", website + "/documentation/")

        # health_pwa.theme_color is seeded with noupdate=1, so an upgrade never
        # rewrites the stale aubergine value — overwrite it to the brand color.
        icp.set_param("health_pwa.theme_color", theme_color)

        icon_b64 = _read_icon_b64()

        # Favicon: web_debranding only defaults it for NEW companies, so set it
        # explicitly on every existing company. Best-effort.
        if icon_b64:
            for company in self.env["res.company"].sudo().search([]):
                try:
                    company.favicon = icon_b64
                except Exception:
                    _logger.warning("biz_debranding: favicon on %s failed", company.name, exc_info=True)

        # Website identity: the login/portal/website tab title and favicon come
        # from the website record, not the company. Brand every website.
        if "website" in self.env:
            for site in self.env["website"].sudo().search([]):
                try:
                    vals = {"name": brand}
                    if icon_b64:
                        vals["favicon"] = icon_b64
                    site.write(vals)
                except Exception:
                    _logger.warning("biz_debranding: website branding on %s failed", site.name, exc_info=True)

        # OdooBot → brand bot. Name rebrand always runs; avatar best-effort.
        bot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if bot:
            bot.sudo().write({"name": brand})
            if icon_b64:
                try:
                    bot.sudo().write({"image_1920": icon_b64})
                except Exception:
                    _logger.warning("biz_debranding: bot avatar failed", exc_info=True)

        _logger.info("biz_debranding: white-label identity applied as %r", brand)
        return True

    def set_values(self):
        super().set_values()
        # Re-apply the whole identity so a brand change from the settings page
        # propagates to companies, websites, bot and the debranding suite.
        self._biz_apply_brand()
