# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""The brand name, handed to the web client before it draws anything.

WHY IT HAS TO ARRIVE WITH THE PAGE. The web client's title service falls back to
the framework's own name whenever no screen has set a title yet, and the
debranding suite only fills its part in after a round trip to the server. For
the second or two in between, every browser tab read the framework's name
(ledger §5.236). The name therefore travels in the session information the page
is rendered with, so `brand_title.js` can set it synchronously, on the very
first paint, with no call to wait for.
"""
from odoo import models

from .res_config_settings import DEFAULT_BRAND

BRAND_PARAM = "biz_debranding.brand_name"


def brand_name(env):
    """The configured brand name, or the default one — never empty."""
    value = env["ir.config_parameter"].sudo().get_param(BRAND_PARAM) or ""
    return value.strip() or DEFAULT_BRAND


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        info["biz_brand_name"] = brand_name(self.env)
        return info
