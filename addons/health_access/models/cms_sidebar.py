# -*- coding: utf-8 -*-
"""The clinic's left menu, gated by role and shown to the Access home.

TWO THINGS LIVE IN THIS FILE, and they are two halves of one idea.

  **The gate on the menu itself.** Every entry and every block names the roles
  that open it. This is now the ONLY gate: there used to be a second one,
  belonging to the previous access application, and for one phase the two were
  read as an OR so that nobody could lose a screen while the first was being
  carried into the second. That has been done, proven person by person, and the
  older lane has gone with the application that owned it.

  **An adapter, so the Access home can read and write it.** `biz_access` owns no
  menu and cannot: it is generic, and every product's menu is a different model.
  It declares what it needs (`access_common.RailProvider`) and this supplies it.

ONE RULE, ASKED ONCE. `visibility_for` — what the Access home draws on a
person's passport and on the Screens lens — and `get_sidebar_data` — what the
real menu draws down the side of the screen — are the SAME code, through
`_sidebar_visible_items`. That is the whole design of this file. A second copy
of a visibility rule drifts, and it drifts by showing an administrator a menu
their colleague does not have, which is precisely the question the passport
exists to answer.

INHERITANCE IS THE MENU'S, NOT THE HOME'S. A gate on a block flows down to
everything in it, and a gate on a parent entry flows down to its children — the
union, never an override. That was true of the older lane and it is true of this
one in exactly the same way, because two inheritance rules on one menu is a menu
nobody can reason about.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.biz_access.models.access_common import (RailProvider,
                                                         rail_state,
                                                         register_rail)

_logger = logging.getLogger(__name__)

#: The bus event the real menu listens for. Handed back with every write the
#: Access home makes, so the rail two hundred pixels from the editor cannot go
#: on showing the answer that editor has just changed.
RELOAD_EVENT = 'CMS_SIDEBAR:RELOAD'

#: The plain table of menu rows, for the administrator who needs the row itself.
ADVANCED_ACTION = 'health_cms_sidebar.action_cms_sidebar_item'

#: Who sees every entry whatever the gates say: the platform's own
#: administrator, and nobody else.
#:
#: There was a second name on this list — the previous access application's
#: admin privilege — while that application was installed. Seven people held it,
#: two of whom were not owners; they now see the menu their own roles open,
#: which is what everybody else has always seen. That is the point of retiring
#: it: one rule, and no privilege that quietly opens the whole menu.
ADMIN_GROUPS = ('base.group_system',)


class CmsSidebarSection(models.Model):
    _inherit = 'cms.sidebar.section'

    biz_role_ids = fields.Many2many(
        'biz.access.role', 'health_access_section_role_rel',
        'section_id', 'role_id', string='Roles that see this block',
        help='Everything in this block is visible to the people who hold one '
             'of these roles in full. An entry inside it may name roles of its '
             'own — those are added to these, never instead of them. Leave it '
             'empty to gate the block entry by entry.')


class CmsSidebarItem(models.Model):
    _inherit = 'cms.sidebar.item'

    biz_role_ids = fields.Many2many(
        'biz.access.role', 'health_access_item_role_rel',
        'item_id', 'role_id', string='Roles that open this entry',
        help='Holding one of these roles IN FULL opens this entry. Empty, and '
             'the entry is open to everybody with a login — unless the block '
             'it sits in, or the entry above it, is gated.')

    effective_biz_role_ids = fields.Many2many(
        'biz.access.role', string='Roles that open it, inherited included',
        compute='_compute_effective_biz_role_ids', compute_sudo=True,
        help='What actually gates this entry: its own roles PLUS everything '
             'inherited from its block and from the entries above it. Empty '
             'means no gate at all — everybody with a login opens it.')

    # Depends on the parent's RAW roles rather than on its computed effective
    # ones: a field that depended on its own value through `parent_id` would
    # need the ORM's cycle machinery, and the loop below already walks the
    # whole chain.
    @api.depends('biz_role_ids', 'section_id.biz_role_ids',
                 'parent_id.biz_role_ids', 'parent_id.section_id.biz_role_ids')
    def _compute_effective_biz_role_ids(self):
        """A gate on a block, or on an entry above, flows down.

        The union, never an override: a leaf can widen who opens it by naming
        a role of its own without being cut off from the people who own the
        block it sits in.
        """
        # ARCHIVED ROLES STAY ON THE GATE, and that is the whole reason for
        # the context. A relational read drops inactive records by default, so
        # an entry gated only on a role somebody has since put away would come
        # back with NO gate — and "no gate" means open to everybody. Putting a
        # role away would hand its screens to the whole clinic. The archived
        # role opens nothing (it is absent from the map the rule builds); the
        # entry stays GATED, which is what hides it.
        records = self.with_context(active_test=False)
        # Parents before children so a child reads a settled parent value.
        for item in records.sorted(lambda i: bool(i.parent_id)):
            roles = item.biz_role_ids | item.section_id.biz_role_ids
            parent = item.parent_id
            seen = set()
            while parent and parent.id not in seen:
                seen.add(parent.id)
                roles |= parent.biz_role_ids | parent.section_id.biz_role_ids
                parent = parent.parent_id
            item.effective_biz_role_ids = roles

    # ================================================================ the rule
    @api.model
    def _sidebar_visible_items(self, all_items):
        """One lane, asked once.

        An entry is drawn when ANY of these is true, tried in this order
        because each is cheaper than the next:

          * this person is the platform administrator;
          * the entry has no gate at all, its block has none, and nothing above
            it in the menu has one;
          * they hold, IN FULL, one of the roles that opens it.

        HOLDING A ROLE MEANS HOLDING ALL OF IT (`rail_state`, the one written
        rule). A bundle is a job, not a shopping list: somebody with three of a
        role's four permissions cannot do the job the sentence describes, so the
        entry does not open for them. And an ARCHIVED role opens nothing — it is
        absent from the map below — while an entry gated only on archived roles
        still counts as GATED, so archiving the last role on an entry hides it
        rather than handing it to the whole company.

        `super()` FIRST, ALWAYS. The menu module draws what there is; this only
        ever narrows it. Anything a module below has already decided somebody
        cannot see does not come back because a role happens to name it.
        """
        user = self.env.user
        candidates = super()._sidebar_visible_items(all_items)
        # THE ONE WAY TO ASK WHAT THIS RULE IS DOING. A before-and-after report
        # has to be able to ask for the answer WITHOUT the role gate, and the
        # only honest way to get it is to run the real code with the gate
        # switched off. Nothing in the product ever sets this; it is read from
        # a report and from a test.
        if self.env.context.get('health_access_no_biz_lane'):
            return candidates
        if self._biz_is_admin(user):
            return candidates

        held = set(user.sudo().all_group_ids.ids)
        role_groups = {
            role.id: set(role.group_ids.ids)
            for role in self.env['biz.access.role'].sudo().search(
                [('active', '=', True)])
        }

        # IDS, NOT RECORDSETS, because the gate has to be read with archived
        # roles included and the answer has to come back in the caller's own
        # environment. Two recordsets from two contexts do not union.
        drawn = []
        for item in candidates.with_context(active_test=False):
            roles = item.effective_biz_role_ids
            if not roles:
                drawn.append(item.id)               # no gate anywhere above it
                continue
            visible, _locked = rail_state(
                {'group_ids': [], 'restricted': False, 'role_ids': roles.ids},
                False, held, role_groups)
            if visible:
                drawn.append(item.id)
        return candidates.filtered(lambda i: i.id in set(drawn))

    @api.model
    def _biz_is_admin(self, user):
        """Who sees the whole menu whatever the gates say.

        Read through `env.ref` with `raise_if_not_found=False` so a name that
        is not on this database is skipped rather than raising — the list used
        to carry a second name, belonging to a module that has since been
        removed, and this is what let that removal be a one-line change.
        """
        for xmlid in ADMIN_GROUPS:
            if not self.env.ref(xmlid, raise_if_not_found=False):
                continue
            try:
                if user.sudo().has_group(xmlid):
                    return True
            except (ValueError, KeyError):          # pragma: no cover
                continue
        return False

    # ------------------------------------------------ the same answer, by id
    @api.model
    def _biz_visible_map(self, user):
        """`({item id: 'on'|'hidden'}, {section id: 'on'|'hidden'})`.

        EXACTLY WHAT `get_sidebar_data` WOULD DRAW FOR THIS PERSON, including
        the two things the rule above does not decide on its own: an entry whose
        PARENT is hidden is not drawn (the menu gathers children under visible
        parents), and a block with nothing visible inside it is not drawn at
        all.

        Same code, one call, so the Access home and the real menu cannot come to
        disagree — which is the only reason this method exists rather than the
        home working it out for itself.
        """
        this = self.with_user(user).sudo()
        items = this.search([('active', '=', True)],
                            order='section_id, sequence, id')
        visible = this._sidebar_visible_items(items)
        visible_ids = set(visible.ids)
        # A child under a hidden parent is not drawn, whatever its own gate.
        drawn = {i.id for i in visible
                 if not i.parent_id or i.parent_id.id in visible_ids}

        item_states = {}
        for item in self.with_context(active_test=False).search([]):
            item_states[item.id] = 'on' if item.id in drawn else 'hidden'

        section_states = {}
        by_section = {}
        for item in items:
            if item.id in drawn:
                by_section[item.section_id.id] = True
        for section in self.env['cms.sidebar.section'].sudo().with_context(
                active_test=False).search([]):
            section_states[section.id] = (
                'on' if section.active and by_section.get(section.id)
                else 'hidden')
        return item_states, section_states


# =============================================================================
# THE ADAPTER
# =============================================================================
class HealthCmsRail(RailProvider):
    """This clinic's left menu, as the Access home is allowed to see it.

    A PLAIN CLASS AND NOT A MODEL, and every method takes `env` rather than
    reading one off `self`: ONE instance of this serves every database the
    registry is loaded for, and an adapter that remembered an environment would
    answer the wrong clinic's question on the second one.
    """

    key = 'cms_sidebar'

    # ------------------------------------------------------------------ reads
    def available(self, env):
        return bool(env['cms.sidebar.item'].sudo().search_count([], limit=1))

    def sections(self, env, include_inactive=False):
        domain = [] if include_inactive else [('active', '=', True)]
        rows = []
        for section in env['cms.sidebar.section'].sudo().with_context(
                active_test=False).search(domain, order='sequence, id'):
            rows.append({
                'id': section.id,
                'name': section.name or '',
                'key': section.technical_key or '',
                'sequence': section.sequence or 0,
                'active': bool(section.active),
                'show_label': True,
                # Optional in the protocol: what is written on the BLOCK, so a
                # lens can say a whole block is gated instead of repeating one
                # chip on fourteen rows. Nothing decides visibility from it.
                'role_ids': section.biz_role_ids.ids,
            })
        return rows

    def entries(self, env, include_inactive=False):
        Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
        domain = [] if include_inactive else [('active', '=', True)]
        rows = []
        for item in Item.search(domain, order='section_id, sequence, id'):
            rows.append({
                'id': item.id,
                'section_id': item.section_id.id,
                'parent_id': item.parent_id.id or 0,
                'name': item.name or '',
                # Whatever the product stores. This menu stores font classes;
                # the miniature draws an `<i>` for those and a glyph for the
                # rest, which is why the protocol never converts them.
                'icon': item.icon or '',
                'sequence': item.sequence or 0,
                'active': bool(item.active),
                # THIS MENU HAS NO PERMISSION LANE AND NO LOCKED TEASER. Said
                # honestly rather than approximated: an entry is shown or it is
                # not, and inventing a middle state the menu cannot draw would
                # make the Screens lens promise something nobody would ever see.
                'group_ids': [],
                'restricted': False,
                'restriction_reason': '',
                # What is WRITTEN on the entry, archived roles included — "is it
                # gated at all" and "who gets through" are different questions.
                'role_ids': item.biz_role_ids.ids,
                'legacy_note': self._legacy_note(env, item),
            })
        return rows

    def _legacy_note(self, env, item):
        """Always empty, and kept rather than deleted.

        While this clinic had two gates on one menu, this said "also opened by
        the older gate: Owner, CRM" wherever the two disagreed — so somebody
        editing a gate could see that an entry was wider than the chips in
        front of them. There is one gate now, so there is nothing it could
        honestly say, and the Screens lens draws no note.

        The method stays because the protocol has the key and the lens reads
        it: a provider that dropped it would work by accident rather than by
        agreement, and the next product to write one would have to find out
        from a traceback that the key is optional.
        """
        return ''

    def visibility_for(self, env, user):
        items, sections = env['cms.sidebar.item']._biz_visible_map(user)
        return {'items': items, 'sections': sections}

    def advanced_action(self, env):
        action = env.ref(ADVANCED_ACTION, raise_if_not_found=False)
        return ADVANCED_ACTION if action else ''

    def reload_event(self):
        return RELOAD_EVENT

    # ----------------------------------------------------------------- writes
    def set_roles(self, env, entry_id, role_ids):
        """The chips on the screen, and nothing else.

        There is one gate on this menu now, so what the lens draws IS what it
        writes. While there were two, this deliberately wrote only the one it
        showed: a screen that can silently change something it does not display
        is a screen nobody can trust.
        """
        self._entry(env, entry_id).write({'biz_role_ids': [(6, 0, role_ids)]})

    def set_active(self, env, entry_id, active):
        self._entry(env, entry_id).write({'active': bool(active)})

    def set_restricted(self, env, entry_id, restricted, reason):
        raise UserError(_(
            "This left menu has no locked preview; an entry is either shown or "
            "hidden."))

    def reorder(self, env, section_id, entry_ids):
        """Numbered in TENS, so the next entry somebody adds by hand has
        somewhere to land between two of them without renumbering the block."""
        for index, entry_id in enumerate(entry_ids):
            self._entry(env, entry_id).write({'sequence': (index + 1) * 10})

    def _entry(self, env, entry_id):
        item = env['cms.sidebar.item'].sudo().with_context(
            active_test=False).browse(int(entry_id or 0)).exists()
        if not item:
            raise UserError(_("That entry is not on the left menu any more."))
        return item


# Registered at import time. Read at CALL time by `biz.access.rail`, so the
# order the two modules happen to be imported in cannot matter.
register_rail(HealthCmsRail())
