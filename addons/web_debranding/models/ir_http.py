# Copyright 2022 Ivan Yelizariev <https://twitter.com/yelizariev>
# License MIT (https://opensource.org/licenses/MIT).
# License OPL-1 (https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps) for derivative work.
from odoo import api, models

from .ir_translation import debrand


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def _get_translations_for_webclient(self, *args, **kwargs):
        translations_per_module, lang_params = super(
            IrHttp, self
        )._get_translations_for_webclient(*args, **kwargs)

        # Odoo 19 returns ReadonlyDict objects, so we need mutable copies
        mutable_translations = {}
        for module_key, module_vals in translations_per_module.items():
            mutable_vals = dict(module_vals)
            messages = module_vals.get("messages", [])
            mutable_messages = []
            for message in messages:
                mutable_msg = dict(message)
                mutable_msg["id"] = debrand(self.env, mutable_msg.get("id", ""))
                mutable_msg["string"] = debrand(self.env, mutable_msg.get("string", ""))
                mutable_messages.append(mutable_msg)
            mutable_vals["messages"] = mutable_messages
            mutable_translations[module_key] = mutable_vals

        return mutable_translations, lang_params

