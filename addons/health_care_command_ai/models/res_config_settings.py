# -*- coding: utf-8 -*-
"""Settings for the optional Care Command AI layer (handover §2.1).

Sovereignty defaults ship OFF: ``care_ai_enabled`` and ``care_ai_allow_cloud``
are both False, so installing the module changes nothing until a manager flips
the master on, and a non-Ollama provider is refused unless cloud is explicitly
allowed. The two capability toggles default True but only matter when the
master is on.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    care_ai_enabled = fields.Boolean(
        string="Enable Care Command AI",
        config_parameter="health_care_command_ai.enabled")
    care_ai_allow_cloud = fields.Boolean(
        string="Allow Cloud AI Providers",
        config_parameter="health_care_command_ai.allow_cloud",
        help="When off (default) only an Ollama (local) provider is called; a "
             "cloud provider is refused. Data-sovereignty control.")
    care_ai_provider_id = fields.Many2one(
        "bi.ai.provider", string="AI Provider",
        config_parameter="health_care_command_ai.provider_id")
    care_ai_drafts = fields.Boolean(
        string="AI Reply Drafts",
        config_parameter="health_care_command_ai.drafts", default=True)
    care_ai_brief = fields.Boolean(
        string="AI Continuity Brief",
        config_parameter="health_care_command_ai.brief", default=True)

    def set_values(self):
        # Core set_param() UNLINKS a parameter whose value is falsy, and a
        # get_param-with-default helper then falls back to the hardcoded default
        # (True) — so a default-True toggle saved as False would silently snap
        # back on (§5.36). Persist explicit strings for every boolean.
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("health_care_command_ai.enabled",
                      "True" if self.care_ai_enabled else "False")
        icp.set_param("health_care_command_ai.allow_cloud",
                      "True" if self.care_ai_allow_cloud else "False")
        icp.set_param("health_care_command_ai.drafts",
                      "True" if self.care_ai_drafts else "False")
        icp.set_param("health_care_command_ai.brief",
                      "True" if self.care_ai_brief else "False")
