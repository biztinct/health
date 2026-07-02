from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose the VU Form Engine kill-switch to the web client.

        Set ``health_theme.vu_form_engine = off`` (ir.config_parameter) to
        instantly revert every form to stock Odoo rendering without a deploy.
        """
        info = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        info["vu_form_engine"] = icp.get_param("health_theme.vu_form_engine", "on")
        # Published theme version — cache-busting handle for /vu_theme/tokens.css
        info["vu_theme_version"] = icp.get_param("health_theme.theme_version", "0")
        return info
