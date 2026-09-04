# -*- coding: utf-8 -*-
"""Which parts of the product this clinic has, applied to the left menu.

ONE RULE, IN THE ONE PLACE THAT ALREADY ANSWERS IT. `_sidebar_visible_items` is
the single seam the menu module leaves for "who may see this row"; the access
overlay narrows it by role and this narrows it again by whether the clinic has
that part of the product at all. A second rule somewhere else is how a screen
comes to promise somebody a page they cannot open, so there is not one.

⚠ AND IT NARROWS FOR EVERYBODY, INCLUDING WHOEVER RUNS THE CLINIC. The role
lane lets an administrator past every gate, which is right: a gate there is
about permission. This is not a permission — a part the clinic has not got is
not there for anybody, and an administrator seeing Telehealth on their menu
while nobody else can is worse than not having it.

⚠ A CHILD INHERITS ITS PARENT'S ANSWER, exactly as the role gate does. Hiding
"Care Intelligence" and leaving its three children on the menu would be worse
than doing nothing.

⚠ `@api.model` IS ON EVERY OVERRIDE HERE AND IT IS LOAD-BEARING (ledger F46).
The browser calls `get_sidebar_data` with no ids, and the framework decides how
to call a method by reading the marker off the function it is ABOUT TO INVOKE
(`odoo/service/model.py`). An override without it takes the whole left menu
away from everybody — and no Python test can see it, because a test calls the
method directly and both shapes work. `health_access` asserts the marker; this
module asserts its own.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CmsSidebarItem(models.Model):
    _inherit = 'cms.sidebar.item'

    feature_key = fields.Char(
        string="Part of the product",
        index=True,
        help="Which part of the product this entry belongs to. When that part "
             "is not switched on for this clinic, the entry is not drawn and "
             "the screen behind it says so. Empty means the entry is always "
             "there.")

    # =====================================================================
    #  THE RULE
    # =====================================================================
    @api.model
    def _feature_key_of(self, item, by_id=None):
        """This entry's own key, or the nearest one above it. `''` for none."""
        seen = set()
        node = item
        while node and node.id not in seen:
            seen.add(node.id)
            if node.feature_key:
                return node.feature_key.strip()
            if node.section_id and node.section_id.feature_key:
                return node.section_id.feature_key.strip()
            node = node.parent_id
        return ''

    @api.model
    def _sidebar_visible_items(self, all_items):
        """`super()` first, always. This only ever narrows.

        THE HOT PATH IS ONE SETTINGS READ. With nothing switched off — which is
        every clinic, every day, until somebody decides otherwise — this costs
        a cached read of one `ir.config_parameter` row and a return.
        """
        items = super()._sidebar_visible_items(all_items)
        try:
            off = self.env['biz.tenancy'].features_off()
        except Exception:                                    # noqa: BLE001
            # The left menu is the whole product's navigation. A fault here
            # must leave it drawn, and must SAY so rather than fail quietly
            # (ledger F53) — a menu that silently lost half its entries is a
            # support call nobody can diagnose.
            _logger.warning("health_tenancy: could not read which parts of "
                            "the product are switched on; the whole left menu "
                            "is drawn.", exc_info=True)
            return items
        if not off:
            return items
        # `'*'` means the setting could not be read at all, so nothing gated is
        # drawn. Everything ungated stays — a clinic must never be left staring
        # at an empty menu because one settings row is damaged.
        blocked = []
        for item in items.with_context(active_test=False):
            key = self._feature_key_of(item)
            if key and ('*' in off or key in off):
                blocked.append(item.id)
        if not blocked:
            return items
        return items.filtered(lambda i: i.id not in set(blocked))

    # =====================================================================
    #  THE DOOR BEHIND THE ENTRY
    # =====================================================================
    @api.model
    def feature_action_map(self):
        """`{'xmlids': {...}, 'tags': {...}}` — which screen belongs to what.

        Built from the menu itself rather than written down twice: the entry
        that opens a screen is the thing that knows which part of the product
        it belongs to, and a second list would drift from it on the first
        change nobody remembered to make in both places.
        """
        xmlids, tags = {}, {}
        items = self.with_context(active_test=False).search([])
        for item in items:
            key = self._feature_key_of(item)
            if not key:
                continue
            if item.action_xmlid:
                xmlids[item.action_xmlid] = key
            if item.action_tag:
                tags[item.action_tag] = key
            for extra in (item.match_action_xmlids or '').split(','):
                if extra.strip():
                    xmlids.setdefault(extra.strip(), key)
            for extra in (item.match_action_tags or '').split(','):
                if extra.strip():
                    tags.setdefault(extra.strip(), key)
        return {'xmlids': xmlids, 'tags': tags}


class CmsSidebarSection(models.Model):
    _inherit = 'cms.sidebar.section'

    feature_key = fields.Char(
        string="Part of the product",
        help="When a whole block of the menu belongs to one part of the "
             "product — the reporting block, for instance — it is said here "
             "once instead of on every entry inside it.")


class BizTenancyProduct(models.AbstractModel):
    """What the generic platform link knows about THIS product's screens."""
    _inherit = 'biz.tenancy'

    #: Who, on one of THIS product's systems, runs it. Named by fixed id and
    #: read with `env.ref(..., raise_if_not_found=False)` so a system without
    #: the access overlay skips the name rather than raising.
    ADMIN_GROUPS = ('health_access.group_clinic_admin',
                    'health_base.group_healthcare_admin')

    @api.model
    def may_change_support(self):
        """⚠ THE CUSTOMER'S OWN ADMINISTRATOR, NOT THE PLATFORM'S.

        Found on a live customer's screen: the generic gate is the framework's
        administrator permission, and the two-ring rule deliberately withholds
        that from a customer's administrator — so the one setting a customer
        OWNS was refused to the only person who should be able to change it,
        with a message telling them they were not an administrator of their own
        system. Widened here, where the product knows what it calls them.
        """
        if super().may_change_support():
            return True
        user = self.env.user
        for xmlid in self.ADMIN_GROUPS:
            if not self.env.ref(xmlid, raise_if_not_found=False):
                continue
            try:
                if user.sudo().has_group(xmlid):
                    return True
            except (ValueError, KeyError):               # pragma: no cover
                continue
        return False

    @api.model
    def feature_of_action(self, action_id, action=None):
        """Which part of the product this screen belongs to. `''` = none.

        Called only when something IS switched off (the generic side checks
        that first), so the cost of building the map is paid by the clinics
        that have a switch off and by nobody else.
        """
        amap = self.env['cms.sidebar.item'].sudo().feature_action_map()
        # 1. The name the browser asked for, if it asked by name.
        if isinstance(action_id, str) and action_id in amap['xmlids']:
            return amap['xmlids'][action_id]
        # 2. A client action asked for by its tag.
        tag = (action or {}).get('tag') if isinstance(action, dict) else None
        if tag and tag in amap['tags']:
            return amap['tags'][tag]
        # 3. A numeric id — resolve it back to a name. Done last because it is
        #    the only branch that costs a query.
        try:
            ident = int(action_id)
        except (TypeError, ValueError):
            return ''
        if not amap['xmlids']:
            return ''
        data = self.env['ir.model.data'].sudo().search([
            ('model', 'like', 'ir.actions.%'), ('res_id', '=', ident)])
        for row in data:
            name = '%s.%s' % (row.module, row.name)
            if name in amap['xmlids']:
                return amap['xmlids'][name]
        return ''


# =============================================================================
# THE MINIATURE THE PLATFORM'S MATRIX DRAWS BESIDE THE SWITCHES.
#
# ⚠ IT TAKES `env` AS AN ARGUMENT AND HOLDS NOTHING (ledger H6). One
# registration is made at import time and serves every database this process
# ever loads; a function that remembered an environment would draw the wrong
# customer's menu the second time it was called.
#
# IT ANSWERS FOR SOMEBODY WHO CAN OPEN EVERYTHING, on purpose. The question the
# matrix asks is "what does this switch do to their menu", and answering it for
# one particular person would put a role question inside a sales screen.
# =============================================================================
def menu_preview(env, off_keys):
    """`[{key, label, items: [{id, label, icon, state, children}]}]`."""
    Item = env['cms.sidebar.item'].sudo()
    off = set(off_keys or ())
    sections = env['cms.sidebar.section'].sudo().search(
        [('active', '=', True)], order='sequence, id')
    items = Item.search([('active', '=', True)],
                        order='section_id, sequence, id')

    def state_of(item):
        key = Item._feature_key_of(item)
        if key and ('*' in off or key in off):
            return 'hidden'
        return 'on'

    def draw(item):
        return {'id': item.id, 'label': item.name, 'icon': item.icon or '',
                'state': state_of(item), 'feature': Item._feature_key_of(item),
                'children': []}

    out = []
    for section in sections:
        mine = items.filtered(lambda i, s=section: i.section_id == s)
        tops = mine.filtered(lambda i: not i.parent_id)
        rows = []
        for top in tops:
            row = draw(top)
            row['children'] = [draw(k) for k in
                               mine.filtered(lambda c, p=top: c.parent_id == p)]
            rows.append(row)
        if not rows:
            continue
        out.append({'key': section.technical_key or str(section.id),
                    'label': section.name, 'show_label': True,
                    'restricted': False, 'items': rows})
    return out
