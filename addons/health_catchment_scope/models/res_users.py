# -*- coding: utf-8 -*-
from odoo import api, models, _

from .catchment_scope import FILTER_MINE, FILTER_PER_AREA, OWNER_GROUP


class ResUsers(models.Model):
    """`catchment_enforced`, which the global rules read, lives in health_base
    — health_base's own rules need it and this module depends on health_base,
    so defining it here would be a loop. See health_base/models/res_users.py."""
    _inherit = 'res.users'

    def _catchment_can_switch(self):
        """True for the one role allowed to look at another area."""
        self.ensure_one()
        return self.has_group(OWNER_GROUP)

    @api.model
    def _catchment_scope_info(self):
        """Payload for the CMS sidebar's scope pill.

        `options` is empty for everyone but an owner, so the sidebar has no way
        to draw another area's name for a scoped user even by accident.
        """
        user = self.env.user
        can_switch = user._catchment_can_switch()
        options = []
        if can_switch:
            # Their own area is already the first entry in the picker as
            # "My area (X)" — listing it again below would be the same choice
            # twice. Mirrors the injector, which for the same reason emits the
            # owner's own area only as `catchment_mine`.
            others = self.env['health.catchment.province'].sudo().search(
                [('id', '!=', user.catchment_province_id.id)]
                if user.catchment_province_id else [])
            options = [
                {'id': p.id, 'name': p.name, 'filter': FILTER_PER_AREA % p.id}
                for p in others
            ]
        return {
            'current_id': user.catchment_province_id.id or False,
            'current_name': user.catchment_province_id.name or _('Not set'),
            'can_switch': can_switch,
            'options': options,
            'mine_filter': FILTER_MINE,
        }

    @api.model
    def action_users_missing_catchment(self):
        """The data-quality list that pays for the fail-closed choice.

        A scoped user with no catchment area sees nothing. That is deliberate,
        but it is only safe if somebody can find those accounts — hence this.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': _('Staff Without a Catchment Area'),
            'res_model': 'res.users',
            'view_mode': 'list,form',
            'domain': [('share', '=', False),
                       ('catchment_province_id', '=', False)],
            'context': {'search_default_no_catchment': 1},
        }
