# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""The empty-list help of every screen, without the framework's name.

Stock actions ship help such as "Odoo helps you track all activities related
to your contacts." (Contacts, Customers, Vendors, CRM Opportunities). Every
action's help goes through `get_empty_list_help` of its model when the web
client reads the action, so this one seam covers them all, in every language,
using the same word rule as the mail layer (UAT round 10, item 4).
"""
import logging

from markupsafe import Markup

from odoo import api, models

from .brand_words import debrand_value, names_the_framework

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def get_empty_list_help(self, help_message):
        help_message = super().get_empty_list_help(help_message)
        if not help_message or not names_the_framework(help_message):
            return help_message
        brand = self.env["mail.render.mixin"]._biz_brand()
        if not brand:
            return help_message
        try:
            text = debrand_value(str(help_message), brand)
        except Exception:  # noqa: BLE001
            _logger.warning("biz_debranding: could not debrand an empty-list "
                            "help", exc_info=True)
            return help_message
        return Markup(text) if isinstance(help_message, Markup) else text
