# -*- coding: utf-8 -*-
"""The clinic's left menu, taught a second gate and shown to the Access home.

TWO THINGS LIVE IN THIS FILE, and they are two halves of one idea.

  **A second lane on the menu itself.** Every entry and every block already
  names the roles that open it, in the previous access application's own model.
  This adds a second list — the same question, asked of a `biz.access.role` — and
  the menu reads the two as an OR. Not a replacement: an OR, so that on the day
  it lands nobody loses a screen they had the day before, whatever state the
  carry-over is in. The old lane goes away in its own step, once the two have
  been proven to agree person by person.

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
union, never an override. That was already true of the old lane and it is true
of the new one in exactly the same way, in a compute written to mirror it line
for line, because two inheritance rules on one menu is a menu nobody can reason
about.
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

#: Who sees every entry whatever the gates say. `base.group_system` is the
#: platform's own administrator; the second is the previous application's admin
#: privilege, read only while that application is still installed, so that the
#: seven people who have it do not lose the whole menu on the day this lands.
ADMIN_GROUPS = ('base.group_system',
                'access_roles.access_role_group_administrator')


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
             'means no gate on this lane at all.')

    # Mirrors `_compute_effective_role_ids` line for line, and depends on the
    # parent's RAW roles for the same reason: a field that depended on its own
    # value through `parent_id` would need the ORM's cycle machinery, and the
    # loop below already walks the whole chain.
    @api.depends('biz_role_ids', 'section_id.biz_role_ids',
                 'parent_id.biz_role_ids', 'parent_id.section_id.biz_role_ids')
    def _compute_effective_biz_role_ids(self):
        """The same inheritance the older lane has, on the newer one.

        Written as a copy of the older compute on purpose. Two lanes with two
        different inheritance rules would make an entry's audience depend on
        WHICH lane somebody had happened to gate it on, and nobody looking at
        the two lists side by side would be able to tell.
        """
        # Parents before children so a child reads a settled parent value.
        for item in self.sorted(lambda i: bool(i.parent_id)):
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
        """The two lanes, read as an OR.

        Visible when ANY of these is true, and they are tried in this order
        because each is cheaper than the next:

          * this person is an administrator;
          * the entry has no gate on EITHER lane;
          * the older lane lets them through — the previous application's rule,
            unchanged, still running, still authoritative for anybody whose
            carry-over has not happened;
          * they hold, IN FULL, one of the roles on the newer lane.

        AN OR AND NOT A REPLACEMENT. This method can only ever return MORE than
        the one it overrides. That is the whole safety argument of this phase:
        whatever state the carry-over is in, and whatever anybody has since
        edited on one lane and not the other, nobody loses a screen they had
        yesterday.

        HOLDING A ROLE MEANS HOLDING ALL OF IT (`rail_state`, the one written
        rule). A bundle is a job, not a shopping list: somebody with three of a
        role's four permissions cannot do the job the sentence describes, so the
        entry does not open for them. And an ARCHIVED role opens nothing — it is
        absent from the map below — while an entry gated only on archived roles
        still counts as GATED, so archiving the last role on an entry hides it
        rather than handing it to the whole company.
        """
        user = self.env.user
        legacy_visible = super()._sidebar_visible_items(all_items)
        # THE ONE WAY TO ASK WHAT THIS LANE IS DOING. A before-and-after report
        # has to be able to ask for the answer WITHOUT the newer lane, and the
        # only honest way to get it is to run the real code with the lane
        # switched off. Nothing in the product ever sets this.
        if self.env.context.get('health_access_no_biz_lane'):
            return legacy_visible
        if legacy_visible == all_items:
            return all_items                       # an administrator, already
        if self._biz_is_admin(user):
            return all_items

        held = set(user.sudo().all_group_ids.ids)
        role_groups = {
            role.id: set(role.group_ids.ids)
            for role in self.env['biz.access.role'].sudo().search(
                [('active', '=', True)])
        }

        extra = all_items.browse()
        for item in all_items - legacy_visible:
            roles = item.effective_biz_role_ids
            if not roles:
                # No gate on this lane. Whether it is open to everybody was
                # already decided by the lane above, which said no.
                continue
            visible, _locked = rail_state(
                {'group_ids': [], 'restricted': False, 'role_ids': roles.ids},
                False, held, role_groups)
            if visible:
                extra |= item
        return legacy_visible | extra

    @api.model
    def _biz_is_admin(self, user):
        """Who sees the whole menu whatever the gates say.

        The previous application's admin privilege is read through `env.ref`
        with `raise_if_not_found=False`, so this file keeps working unchanged on
        the day that application is uninstalled — which is the whole reason this
        module does not depend on it.
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
        """The older gate, in the same plain words, when it says something more.

        Only ever a sentence while this clinic has two lanes. It names the roles
        the older gate lets in that the newer one does not mention — so an
        administrator editing a gate can see that the entry is wider than the
        chips in front of them, rather than discovering it from a colleague.

        Empty everywhere on the day the carry-over runs, because the carry-over
        makes the two lanes say the same thing. It exists for the day after,
        when somebody edits one of them.
        """
        if 'role_ids' not in item._fields:                # pragma: no cover
            return ''
        try:
            old = item.role_ids
            if not old:
                return ''
            covered = {(r.name or '').strip().lower()
                       for r in item.biz_role_ids}
            extra = [r.name or '' for r in old
                     if (r.name or '').strip().lower() not in covered]
            if not extra:
                return ''
            return _("Also opened by the older gate: %s", ', '.join(extra))
        except Exception:                                 # noqa: BLE001
            _logger.warning(
                'health_access: the older gate on left-menu entry %s could not '
                'be read', item.id, exc_info=True)
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
        """The NEW lane only. The older one is never written from this screen.

        Taking a role off the older gate would take a door away from people the
        lens never showed — it draws the new lane's chips — and a screen that
        can silently change something it does not display is a screen nobody can
        trust. The older lane is retired in its own step, deliberately.
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
