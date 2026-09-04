# -*- coding: utf-8 -*-
"""`biz.access.rail` — the left menu, as this module is allowed to see it.

WHY THIS EXISTS AT ALL. The Access home answers three questions and two of them
are about a LEFT MENU: "which screens does this role open" and "what does this
person actually see". Neither can be answered without reading the product's own
menu — and this module is generic, so it cannot name one.

The module the Access home was extracted from taught the menu model a `role_ids`
column and overrode its visibility rule. That works when there is exactly one
menu model and this module is allowed to depend on it. Here there is not: the
next product's menu is a different model with a different shape, its gates may
be rows of a third-party table, its sub-entries may inherit their gates, and it
may have no permission lane and no locked teaser at all. A generic module cannot
inherit a model it does not know the name of.

So this is a SEAM. The module says what it needs from a left menu
(`access_common.RailProvider`), a product registers something that provides it,
and everything else in this module goes through this one abstract model. The
facade never touches a provider directly — one place asks, so there is one place
where "there is no menu here" is answered.

AND WITH NO PROVIDER, EVERY ANSWER IS HONEST AND EMPTY. `available()` is False,
the reads hand back nothing, and every write refuses with a sentence a person
can act on. That is not a degraded mode to apologise for: a database with this
module and nothing else has no left menu, and a screen that said otherwise would
be inventing one. It is also the proof that the seam works — the Screens lens on
such a database draws its own empty state rather than a traceback.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .access_common import rail_provider, safe

_logger = logging.getLogger(__name__)


class BizAccessRail(models.AbstractModel):
    _name = 'biz.access.rail'
    _description = 'The left menu, through the registered provider'

    # ------------------------------------------------------------- the seam
    @api.model
    def _provider(self):
        return rail_provider()

    @api.model
    def _no_menu(self):
        """The one refusal, said once.

        A write that cannot happen has to say WHY it cannot, and "this system
        has no left menu" is a fact somebody can act on — where a bare "not
        allowed" would send them looking for a permission they do not lack.
        """
        raise UserError(_(
            "This system has no left menu the Access home can edit."))

    # ------------------------------------------------------------------ reads
    @api.model
    def available(self):
        provider = self._provider()
        if not provider:
            return False
        return bool(safe(lambda: provider.available(self.env), False,
                         'whether this system has a left menu'))

    @api.model
    def sections(self, include_inactive=False):
        """The blocks of the menu — `[{'id', 'name', 'sequence', 'active'}]`.

        Every probe gets its OWN guard and says so at WARNING with the
        traceback: a provider that half works must not take the whole Access
        home down with it, and a swallowed failure logged at DEBUG is invisible
        on a live server.
        """
        provider = self._provider()
        if not provider:
            return []
        rows = safe(lambda: provider.sections(self.env, include_inactive),
                    None, 'the blocks of the left menu')
        return list(rows or [])

    @api.model
    def entries(self, include_inactive=False):
        """The rows of the menu. See `RailProvider.entries` for the shape."""
        provider = self._provider()
        if not provider:
            return []
        rows = safe(lambda: provider.entries(self.env, include_inactive),
                    None, 'the entries on the left menu')
        return list(rows or [])

    @api.model
    def visibility_for(self, user):
        """What one person sees — the product's OWN answer, never a copy."""
        provider = self._provider()
        empty = {'items': {}, 'sections': {}}
        if not provider:
            return empty
        seen = safe(lambda: provider.visibility_for(self.env, user), None,
                    'what somebody sees on the left menu')
        if not isinstance(seen, dict):
            return empty
        return {
            'items': dict(seen.get('items') or {}),
            'sections': dict(seen.get('sections') or {}),
        }

    @api.model
    def advanced_action(self):
        """The product's own plain table of menu rows, or `''`."""
        provider = self._provider()
        if not provider:
            return ''
        return safe(lambda: provider.advanced_action(self.env) or '', '',
                    'the advanced left-menu screen') or ''

    @api.model
    def reload_event(self):
        """The bus event that makes the REAL menu re-read itself, or `False`.

        Handed back with every write so the rail down the side of the screen
        cannot go on showing the answer the editor beside it has just changed.
        `False` rather than `None` because it crosses to the browser as JSON.
        """
        provider = self._provider()
        if not provider:
            return False
        return safe(lambda: provider.reload_event(), None,
                    'the left menu reload event') or False

    # --------------------------------------------------------------- helpers
    @api.model
    def entry(self, entry_id, include_inactive=True):
        """One row, by id — or the refusal, in words."""
        entry_id = int(entry_id or 0)
        for row in self.entries(include_inactive=include_inactive):
            if row.get('id') == entry_id:
                return row
        raise UserError(_("That entry is not on the left menu any more."))

    @api.model
    def role_groups(self):
        """`{role_id: set(group_ids)}` for the ACTIVE roles, worked out once.

        The one input `rail_state` needs that this module owns. Asked here so
        every caller gets the same map rather than each building its own, and
        so an ARCHIVED role is absent from it — which is what makes an archived
        role open nothing.
        """
        out = {}
        for role in self.env['biz.access.role'].sudo().search(
                [('active', '=', True)]):
            out[role.id] = set(role.group_ids.ids)
        return out

    @api.model
    def role_groups_all(self):
        """The same map, archived roles INCLUDED.

        Only the Screens lens wants this: it names a role that has been put away
        so somebody can see WHY an entry has become unreachable. Nothing that
        decides visibility may use it.
        """
        out = {}
        for role in self.env['biz.access.role'].sudo().with_context(
                active_test=False).search([]):
            out[role.id] = set(role.group_ids.ids)
        return out

    # ----------------------------------------------------------------- writes
    @api.model
    def set_roles(self, entry_id, role_ids):
        provider = self._provider()
        if not provider:
            self._no_menu()
        provider.set_roles(self.env, int(entry_id or 0),
                           [int(r) for r in (role_ids or []) if r])
        return True

    @api.model
    def set_active(self, entry_id, active):
        provider = self._provider()
        if not provider:
            self._no_menu()
        provider.set_active(self.env, int(entry_id or 0), bool(active))
        return True

    @api.model
    def set_restricted(self, entry_id, restricted, reason=None):
        provider = self._provider()
        if not provider:
            self._no_menu()
        provider.set_restricted(self.env, int(entry_id or 0), bool(restricted),
                                reason or '')
        return True

    @api.model
    def reorder(self, section_id, entry_ids):
        provider = self._provider()
        if not provider:
            self._no_menu()
        provider.reorder(self.env, int(section_id or 0),
                         [int(i) for i in (entry_ids or []) if i])
        return True
