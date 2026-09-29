# -*- coding: utf-8 -*-
"""The last word on the left menu: a heading with nothing inside it is not drawn.

WHY IT IS NEEDED NOW. Before the consolidation a heading and everything inside
it belonged to one audience, so a heading could only be hidden for the same
reason as its children. The new tabs hold screens for DIFFERENT people (the
Connections tab holds the front desk's channel set-up and the owner's phone
set-up side by side), so for somebody who opens none of them the heading has to
go too. `health_access` already opens such a heading only to people who open
something inside it; this catches the rest — a part of the product switched off
for everybody (`health_tenancy`) takes away every screen inside a tab while the
tab itself belongs to no part of the product.

WHY HERE. This module depends on the menu, the access overlay and the product
switches, so its override runs LAST in the chain, after both of them have had
their say (`super()` first, always — this only ever narrows). The Access home's
miniature asks the same method (`_biz_visible_map`), so it cannot disagree.

`@api.model` IS LOAD-BEARING (ledger F46): the browser calls
`get_sidebar_data` with no ids, and an override without the marker takes the
whole left menu away from everybody.
"""
from odoo import api, models


class CmsSidebarItem(models.Model):
    _inherit = 'cms.sidebar.item'

    @api.model
    def _sidebar_visible_items(self, all_items):
        items = super()._sidebar_visible_items(all_items)
        ids = set(items.ids)
        parents = {i.parent_id.id for i in items if i.parent_id}
        bare = [i for i in items
                if not i.parent_id and not i.action_xmlid
                and not i.action_tag and i.id not in parents]
        if not bare:
            return items
        # Only a real HEADING — one that holds screens, none of which is left
        # for this person. A row with no screen and nothing under it at all
        # is somebody else's business (a placeholder, a test's fixture) and
        # the menu has always drawn it.
        held = set(self.sudo().with_context(active_test=True).search(
            [('parent_id', 'in', [i.id for i in bare])]).mapped('parent_id').ids)
        empty = {i.id for i in bare if i.id in held}
        if not empty:
            return items
        ids -= empty
        return items.filtered(lambda i: i.id in ids)
