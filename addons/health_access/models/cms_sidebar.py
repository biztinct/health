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

#: THE PLATFORM'S OWN ENTRIES, drawn for the platform administrator and nobody
#: else (owner ruling 2026-09-29, AR-3 G2). "Google Ads application" is the
#: platform's one Google Ads developer set-up for every clinic on it; its
#: screen is readable by the system administrator only, so on a clinic's menu
#: it was a door that refused everybody who could see it.
#:
#: An entry here carries NO role and is still hidden: "no gate" normally means
#: "everybody", and for these it means "nobody but the administrator short-
#: circuit above". It inherits nothing from its block or its heading either — a
#: block's roles would otherwise draw it for them. Roles somebody deliberately
#: writes on it from the Screens lens still open it, like any other entry.
PLATFORM_ONLY_ITEMS = ('health_google_ads.item_google_ads_platform',)

#: THE MODULES WHOSE OWN HOOKS SWITCH AN ENTRY OFF FOR WANT OF A ROLE.
#:
#: `health_access._gate_new_items` and `biz_bi_cms.apply_role_gates` both put
#: an entry on the menu, ask the permissions table whether any role could open
#: the screen behind it, and switch it off when none can. Those — and only
#: those — are "waiting for a role" on the Screens lens. Everything else that is
#: off (the consolidated staff screens, a feature that is not bought, the
#: switched-off-feature page) was switched off by a DECISION, and the lens must
#: not offer to undo a decision it knows nothing about.
GATE_MANAGED_MODULES = ('health_access', 'biz_bi_cms')

#: WHERE HOME LANDS, BY THE AREA OF THE PERSON'S ROLES (owner ruling, MENU IA
#: Q1). Tried in order within an area; the first screen that can open here
#: wins. An Operations Manager, a Branch Manager, an Admin and an Owner all land
#: on the Operations dashboard; the front desk on Care Command, or the CRM
#: dashboard where Care Command is switched off; an Accountant on the Finance
#: dashboard; a nurse or a doctor on Observations.
HOME_BY_AREA = {
    'admin': ('health_fieldservice.action_ops_command_center',),
    'operations': ('health_fieldservice.action_ops_command_center',),
    'front_desk': ('health_care_command.action_care_command',
                   'health_crm.action_crm_dashboard'),
    'finance': ('health_invoicing.action_fin_dashboard',),
    'clinical': ('health_vitals.action_health_observation',),
}

#: Somebody with roles in several areas lands in the first of these they hold.
HOME_AREA_ORDER = ('admin', 'operations', 'front_desk', 'finance', 'clinical')

#: INSIDE THE CLINICAL AREA, THE JOB DECIDES (owner ruling, MENU M2): a doctor
#: lands on Observations, a nurse on Bookings — the list of the visits she is
#: going out to. Tried in this order, so somebody who is both lands where a
#: doctor lands. Keyed by the role's fixed name.
HOME_BY_CLINICAL_ROLE = (
    ('health_access.role_doctor', 'health_vitals.action_health_observation'),
    ('health_access.role_nurse',
     'health_fieldservice.action_ops_booking_list_native'),
)


def _model_behind(env, item):
    """The model an entry's screen opens, or `''` when it opens no records."""
    if not item.action_xmlid:
        return ''
    action = env.ref(item.action_xmlid, raise_if_not_found=False)
    if not action:
        return ''
    return getattr(action.sudo(), 'res_model', '') or ''


def _awaiting_ids(env, items, models_):
    """The ids of the switched-off entries that are only waiting for a role.

    A LEAF qualifies when it belongs to one of the gate-managed modules, is
    off, and its screen exists and opens records — so "switch it on for a role
    that can read those" is a real offer. A HEADING qualifies when a leaf under
    it does. A leaf whose screen is simply not installed on this database is
    NOT waiting for a role; no role will ever open it here.
    """
    off = items.filtered(lambda i: not i.active)
    if not off:
        return set()
    rows = env['ir.model.data'].sudo().search([
        ('model', '=', 'cms.sidebar.item'),
        ('module', 'in', list(GATE_MANAGED_MODULES)),
        ('res_id', 'in', off.ids)])
    managed = set(rows.mapped('res_id'))
    leaves = {i.id for i in off
              if i.id in managed and i.action_xmlid and models_.get(i.id)}
    headings = {i.id for i in off
                if i.id in managed and not i.action_xmlid
                and any(c.id in leaves for c in env['cms.sidebar.item'].sudo(
                ).with_context(active_test=False).search(
                    [('parent_id', '=', i.id)]))}
    return leaves | headings


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
             'means no gate at all — everybody with a login opens it. A '
             'heading with no screen and no roles of its own is opened by '
             'whoever opens something inside it.')

    #: The entries directly under this one. Not a column — the inverse of
    #: `parent_id` — declared so a heading's derived gate below is recomputed
    #: when a gate inside it changes.
    child_ids = fields.One2many('cms.sidebar.item', 'parent_id',
                                string='Entries inside it')

    # Depends on the parent's RAW roles rather than on its computed effective
    # ones: a field that depended on its own value through `parent_id` would
    # need the ORM's cycle machinery, and the loop below already walks the
    # whole chain.
    @api.depends('biz_role_ids', 'section_id.biz_role_ids',
                 'parent_id.biz_role_ids', 'parent_id.section_id.biz_role_ids',
                 'action_xmlid', 'action_tag',
                 'child_ids.biz_role_ids', 'child_ids.active',
                 'child_ids.section_id.biz_role_ids')
    def _compute_effective_biz_role_ids(self):
        """A gate on a block, or on an entry above, flows down.

        The union, never an override: a leaf can widen who opens it by naming
        a role of its own without being cut off from the people who own the
        block it sits in.

        A HEADING WITH NOTHING WRITTEN ON IT IS OPENED BY WHOEVER OPENS
        SOMETHING INSIDE IT (MENU M2). The consolidated menu has tabs holding
        screens for different people — Settings › Connections holds the front
        desk's channel set-up beside the owner's phone set-up. A gate written
        ON such a heading would flow down and open every screen inside to
        everybody it names; no gate at all would draw the heading for
        everybody. So a heading (no screen of its own) with no roles of its
        own takes the union of what gates the screens inside it, and nothing
        of that flows back down — a child reads its parent's WRITTEN roles,
        which are none. If anything inside it is open to everybody, so is the
        heading. Headings that DO carry roles of their own (Voice, Zalo, Care
        Intelligence…) are unchanged: their gate flows down as before.
        """
        # ARCHIVED ROLES STAY ON THE GATE, and that is the whole reason for
        # the context. A relational read drops inactive records by default, so
        # an entry gated only on a role somebody has since put away would come
        # back with NO gate — and "no gate" means open to everybody. Putting a
        # role away would hand its screens to the whole clinic. The archived
        # role opens nothing (it is absent from the map the rule builds); the
        # entry stays GATED, which is what hides it.
        records = self.with_context(active_test=False)
        platform_only = self._platform_only_ids()
        # Parents before children so a child reads a settled parent value.
        for item in records.sorted(lambda i: bool(i.parent_id)):
            if item.id in platform_only:
                # Only what is written on it: nothing inherited (AR-3 G2).
                item.effective_biz_role_ids = item.biz_role_ids
                continue
            roles = item._chain_biz_roles()
            if item._derives_gate_from_children():
                kids = self.env['cms.sidebar.item'].sudo().with_context(
                    active_test=False).search(
                    [('parent_id', '=', item.id), ('active', '=', True),
                     ('id', 'not in', list(platform_only))])
                kid_roles = [kid._chain_biz_roles() for kid in kids]
                if kid_roles and all(kid_roles):
                    for kid_role in kid_roles:
                        roles |= kid_role
                elif kid_roles:
                    # Something inside is open to everybody: so is the tab.
                    roles = roles.browse()
            item.effective_biz_role_ids = roles

    def _chain_biz_roles(self):
        """Own roles, the block's, and every entry above's WRITTEN roles."""
        self.ensure_one()
        item = self.with_context(active_test=False)
        roles = item.biz_role_ids | item.section_id.biz_role_ids
        parent = item.parent_id
        seen = set()
        while parent and parent.id not in seen:
            seen.add(parent.id)
            roles |= parent.biz_role_ids | parent.section_id.biz_role_ids
            parent = parent.parent_id
        return roles

    @api.model
    def _platform_only_ids(self):
        """The ids of `PLATFORM_ONLY_ITEMS` present on this database."""
        out = set()
        for xmlid in PLATFORM_ONLY_ITEMS:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and rec._name == self._name:
                out.add(rec.id)
        return out

    def _derives_gate_from_children(self):
        """A heading — no screen of its own — with no roles written on it."""
        self.ensure_one()
        return (not self.action_xmlid and not self.action_tag
                and not self.biz_role_ids)

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
        platform_only = self._platform_only_ids()
        drawn = []
        for item in candidates.with_context(active_test=False):
            roles = item.effective_biz_role_ids
            if item.id in platform_only and not roles:
                continue                            # the administrator's alone
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

    # ================================================================ home
    @api.model
    def home_action(self):
        """Home is each role's own dashboard (owner ruling, MENU IA Q1).

        THE AREAS OF THE ROLES THIS PERSON HOLDS IN FULL, and the first of
        `HOME_BY_AREA` among them wins — so somebody who is both an Owner and a
        Nurse lands where an Owner lands. Held "in full" is the same rule the
        menu itself reads (`_held_rows`): a role whose permissions they only
        partly carry is not their job.

        A landing that cannot open here — its module is not installed, or its
        part of the product is switched off — falls to the next thing that can:
        the front desk to the CRM dashboard, everything else to what the menu
        module answers (the Operations dashboard). Nobody is ever sent to a
        screen that answers "switched off".

        MENU M2: inside the clinical area a doctor lands on Observations and a
        nurse on Bookings (`HOME_BY_CLINICAL_ROLE`); every area the person
        holds is tried in order, not only the first; and the answer is always
        a screen this person's own menu draws — failing everything, the first
        one it does.
        """
        fallback = super().home_action()
        user = self.env.user
        # Every area this person holds, highest first: when the first one's
        # landing is not on their menu (a Branch Manager who is also a doctor
        # has no Operations dashboard), the next area's is tried before the
        # generic guard below.
        wanted = []
        for area in self._home_areas(user):
            if area == 'clinical':
                wanted += [action for role, action in HOME_BY_CLINICAL_ROLE
                           if self._holds_role(user, role)]
            wanted += list(HOME_BY_AREA.get(area, ()))
        wanted.append(fallback)
        # NEVER A SCREEN THEY CANNOT FIND AGAIN (MENU M2). A landing that is
        # not on this person's own menu would put them on a page with nothing
        # lit and no way back to it, so the landing must be drawn for them;
        # failing every choice above, the first screen their menu does draw.
        drawn = self._home_drawn_actions()
        for xmlid in wanted:
            if xmlid in drawn and self._home_opens(xmlid):
                return xmlid
        for xmlid in drawn:
            if self._home_opens(xmlid):
                return xmlid
        return fallback

    @api.model
    def _holds_role(self, user, role_xmlid):
        """Does `user` hold every permission of the role with this name?"""
        role = self.env.ref(role_xmlid, raise_if_not_found=False)
        if not role or not role.active or not role.group_ids:
            return False
        return set(role.sudo().group_ids.ids) <= set(user.sudo().all_group_ids.ids)

    @api.model
    def _home_drawn_actions(self):
        """The screens this person's menu draws, in the order it draws them —
        Home itself left out. Asked of `get_sidebar_data`, the one answer."""
        out = []
        for section in self.get_sidebar_data():
            if section.get('key') == 'home':
                continue
            for item in section.get('items') or []:
                for node in [item] + list(item.get('children') or []):
                    xmlid = node.get('action_xmlid')
                    if xmlid and xmlid not in out:
                        out.append(xmlid)
        return out

    @api.model
    def _home_area(self, user):
        """The highest-precedence area among the roles `user` fully holds."""
        areas = self._home_areas(user)
        return areas[0] if areas else ''

    @api.model
    def _home_areas(self, user):
        """Every area among the roles `user` fully holds, highest first."""
        held = set(user.sudo().all_group_ids.ids)
        areas = set()
        for role in self.env['biz.access.role'].sudo().search(
                [('active', '=', True)]):
            groups = set(role.group_ids.ids)
            if groups and groups <= held:
                areas.add(role.area)
        return [area for area in HOME_AREA_ORDER if area in areas]

    @api.model
    def _home_opens(self, xmlid):
        """Does this screen exist here, with its part of the product on?"""
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return False
        if 'biz.tenancy' not in self.env:
            return True
        Tenancy = self.env['biz.tenancy'].sudo()
        try:
            off = Tenancy.features_off()
            if not off:
                return True
            key = Tenancy.feature_of_action(xmlid)
        except Exception:                                    # noqa: BLE001
            _logger.warning('health_access: could not tell whether %s is '
                            'switched on; Home falls back.', xmlid,
                            exc_info=True)
            return False
        return not (key and ('*' in off or key in off))

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
                # Optional in the protocol: the block's own icon, so the
                # Access home's miniature can draw it as the rail draws it
                # (MENU M2 — one rail entry per block).
                'icon': section.icon or '',
                # Optional in the protocol: what is written on the BLOCK, so a
                # lens can say a whole block is gated instead of repeating one
                # chip on fourteen rows. Nothing decides visibility from it.
                'role_ids': section.biz_role_ids.ids,
            })
        return rows

    def labels(self, env=None):
        """What this menu calls its three levels (MENU M2).

        Since the consolidated menu, a block is drawn as an AREA on the rail,
        a root entry as a TAB in the tab column, and a child as a screen
        INSIDE THE TAB. The Access home's generic words ("block", "entry",
        "sub-entry") stay generic in `biz_access`, which exposes no vocabulary
        hook of its own; these are the words to use wherever this product's
        own code talks about its menu, and the ones a future hook would read.
        """
        return {'section': 'Area', 'sections': 'Areas',
                'entry': 'Tab', 'entries': 'Tabs',
                'child': 'Inside the tab'}

    def supports_section_gates(self, env):
        # `cms.sidebar.section.biz_role_ids` — a block's roles flow down.
        return True

    def supports_restricted(self, env):
        # This menu shows an entry or hides it; it has no locked teaser, so the
        # Screens lens must not offer one (owner decision, AR-2: Carejiox's
        # menu hides, it never teases).
        return False

    def entries(self, env, include_inactive=False):
        Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
        domain = [] if include_inactive else [('active', '=', True)]
        items = Item.search(domain, order='section_id, sequence, id')
        models_ = {item.id: _model_behind(env, item) for item in items}
        awaiting = (_awaiting_ids(env, items, models_) if include_inactive
                    else set())
        platform_only = Item._platform_only_ids()
        system = env.ref('base.group_system', raise_if_not_found=False)
        rows = []
        for item in items:
            # A platform-only entry is said to ask for the administrator
            # permission, which is exactly the rule the menu applies to it —
            # so the lens draws "nobody" for it rather than "everybody".
            only = item.id in platform_only and system
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
                'group_ids': [system.id] if only else [],
                'restricted': False,
                'restriction_reason': '',
                # What is WRITTEN on the entry, archived roles included — "is it
                # gated at all" and "who gets through" are different questions.
                'role_ids': item.biz_role_ids.ids,
                # What ACTUALLY gates it — own ∪ block ∪ the entries above it,
                # archived roles kept — from the same computed field the real
                # menu reads, so the lens and the menu cannot disagree about
                # inheritance.
                'effective_role_ids': item.effective_biz_role_ids.ids,
                # The records the screen behind it opens, for "who could open
                # it if it were switched on". Decides nothing about who sees it.
                'model': models_.get(item.id) or '',
                'awaiting_role': item.id in awaiting,
                # No `legacy_note`: it is an OPTIONAL key of the protocol, for a
                # menu part-way between two kinds of gate. This one has one.
            })
        return rows

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

    def set_section_roles(self, env, section_id, role_ids):
        """The roles on a whole block — `biz_role_ids` on the section, which
        every entry inside it inherits (`effective_biz_role_ids`)."""
        section = env['cms.sidebar.section'].sudo().with_context(
            active_test=False).browse(int(section_id or 0)).exists()
        if not section:
            raise UserError(_("That block of the left menu is not here."))
        section.write({'biz_role_ids': [(6, 0, role_ids)]})
        # The inherited gate is a non-stored compute over the section's roles;
        # drop what this transaction already read so the answer handed back
        # to the lens is the new one.
        env['cms.sidebar.item'].invalidate_model(['effective_biz_role_ids'])

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
