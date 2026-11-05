# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.fields import Domain
from odoo.tools import SQL


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.readonly
    @api.model
    def _search_for_channel_invite(self, store, search_term, channel_id=None, limit=30):
        """Messages › "Search conversations" offers only the people the user
        may see (UAT round 6, item 5).

        Core lists every internal user's partner, then reads each one's user
        record (``main_user_id`` → ``employee_ids`` for the time-off badge,
        hr_holidays) as the CURRENT user. `rule_res_users_catchment` hides
        staff of another area, so a nurse's search raised "no 'read' access to
        User". Instead of widening that rule, the search is limited to
        partners whose user record the searcher can already read — the same
        people the rule lets them see — and the result is otherwise core's.
        """
        if self.env.su:
            return super()._search_for_channel_invite(
                store, search_term, channel_id=channel_id, limit=limit)
        # Record rules apply here: only the users this person may read.
        visible_users = self.env['res.users'].search(
            [('share', '=', False)]).ids
        domain = Domain.AND([
            Domain('name', 'ilike', search_term) | Domain('email', 'ilike', search_term),
            [('id', '!=', self.env.user.partner_id.id)],
            [('active', '=', True)],
            [('user_ids', 'in', visible_users or [0])],
            [('user_ids.active', '=', True)],
            [('user_ids.share', '=', False)],
        ])
        channel = self.env['discuss.channel']
        if channel_id:
            channel = self.env['discuss.channel'].search([('id', '=', int(channel_id))])
            domain &= Domain('channel_ids', 'not in', channel.id)
            if channel.group_public_id:
                domain &= Domain('user_ids.all_group_ids', 'in', channel.group_public_id.id)
        query = self._search(domain, limit=limit)
        query.order = SQL('LOWER(%s), "res_partner"."id"', self._field_to_sql(self._table, 'name'))
        selectable_partners = self.env['res.partner'].browse(query)
        selectable_partners._search_for_channel_invite_to_store(store, channel)
        return {
            'count': self.env['res.partner'].search_count(domain),
            'partner_ids': selectable_partners.ids,
        }
