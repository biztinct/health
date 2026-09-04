# -*- coding: utf-8 -*-
"""The two settings the top-bar rule reads, and forgetting the old answer.

The framework clears the menu caches when a MENU changes. It has no way of
knowing that this module's rule also depends on two rows in the settings table
— which mode the bar is in, and which entry is the home. Change one of those
and, without this, the bar goes on drawing yesterday's decision until something
else happens to clear the cache: a stale answer nobody can reproduce, because
by the time anybody looks the cache has turned over.

`biz.access.role` already does the same thing for its own fields. This is the
other half of the same promise.
"""

from odoo import api, models

from .access_common import TOPBAR_PARAM_KEYS


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def _biz_access_touches_topbar(self, keys):
        return any(key in TOPBAR_PARAM_KEYS for key in keys if key)

    def _biz_access_forget_if_needed(self, extra_keys=()):
        keys = set(extra_keys or ())
        # `self` may already be gone (unlink), so read the keys defensively.
        for record in self:
            try:
                keys.add(record.key)
            except Exception:                            # noqa: BLE001
                continue
        if self._biz_access_touches_topbar(keys):
            self.env['ir.ui.menu']._biz_access_forget()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._biz_access_forget_if_needed(
            [vals.get('key') for vals in vals_list])
        return records

    def write(self, vals):
        # The keys BEFORE the write matter as much as the ones after it:
        # renaming a row out of the way is the same event as clearing it.
        before = [record.key for record in self]
        result = super().write(vals)
        self._biz_access_forget_if_needed(before + [vals.get('key')])
        return result

    def unlink(self):
        keys = [record.key for record in self]
        result = super().unlink()
        if self._biz_access_touches_topbar(keys):
            self.env['ir.ui.menu']._biz_access_forget()
        return result
