from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose the Staff Schedule grid timezone (the operator's facility tz)
        so the timeline front-end can render in it synchronously at startup —
        independent of the user's physical/browser timezone."""
        info = super().session_info()
        try:
            info["schedule_tz"] = self.env[
                "health.staff.assignment"
            ]._schedule_tz_name()
        except Exception:
            info["schedule_tz"] = self.env.user.tz or "Asia/Ho_Chi_Minh"
        return info
