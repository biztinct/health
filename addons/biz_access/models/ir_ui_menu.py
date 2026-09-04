# -*- coding: utf-8 -*-
"""The top bar, decided by the roles somebody holds.

WHY A SECOND SURFACE AT ALL. This module's Screens lens is about the product's
own LEFT MENU — the rail a product draws down the side of its shell. Above that
shell there is still the framework's own bar of applications, and on a database
where a product has built its whole vocabulary into the rail, that bar is a
second, unwritten menu nobody curated. A role that says "this is the job" and
then leaves eleven applications on the top bar is a role that has not finished
its sentence.

THE RULE, AND WHY IT IS AN INTERSECTION.

A role names the top-bar screens the people who hold it do NOT see. Somebody who
holds two roles is therefore described twice, and the two descriptions have to be
reconciled. The reconciliation is the INTERSECTION: a screen is hidden only when
EVERY role that person holds hides it.

That is the only direction that is safe. With a union, being given a second role
would take screens away — a promotion that removes doors, which is the one
outcome nobody expects and nobody would think to test for. With an intersection,
holding more can only ever show more, which is the same monotonic promise the
left-menu rule makes (`access_common.rail_state`: another role is another way
IN, never a way out).

A ROLE WITH AN EMPTY LIST HIDES NOTHING, and that is a statement rather than a
gap. It empties the intersection for everybody who holds it, so somebody who
holds one job that hides half the bar and another that hides none of it sees the
whole bar.

THIS WAS WRITTEN THE OTHER WAY ROUND FIRST, AND A REAL PERSON FOUND IT. The
first version read an empty list as "this role was never asked" and left it out
of the reckoning. On the clinic's own data that took 489 top-bar screens away
from one doctor: their job hides nothing, they also happen to carry the one
permission that makes them a branch manager, and a branch manager's bar is
short. Reading "hides nothing" as "no opinion" is what let a role they were
never given decide what they see — and it broke the promise two paragraphs up,
because holding the doctor job on top of the branch-manager one showed them
less rather than more.

The cost of the other reading is real and is the safe direction: a role somebody
writes without saying anything about the top bar will, for the people who hold
it, show more of the bar rather than less. That is visible on the role's own
form, and it can only ever open a door.

WHAT IS NEVER TOUCHED. The system administrator, always: this is a tidying rule
for a product's shell, not a security boundary, and locking the person who owns
the box out of Settings on the strength of it would be absurd. And a menu that
arrives with a module installed tomorrow is visible by default, because a role
can only name what existed when somebody wrote it down.

THE SECOND MODE, AND WHY A PRODUCT WOULD WANT IT. Everything above describes a
bar that is CURATED role by role. A product whose own left menu is the whole of
its navigation does not want a curated second bar; it wants no second bar at
all. `biz_access.topbar_mode = admin_only` says exactly that: the framework's
bar belongs to the platform administrator, and everybody else keeps the one
home entry the product names and nothing else above their left menu.

That is subtraction, and subtraction has a floor. NOBODY IS EVER LEFT WITH AN
EMPTY BAR — if the setting names nothing, or names nothing this person could
see anyway, the rule keeps the first entry they could see and says so in the
log. A tidy shell is worth having; a colleague signing in to a blank screen
never is.

SECURITY, STATED PLAINLY. Hiding a menu is not a permission. Everything behind
the menu is still governed by `ir.model.access` and the record rules, exactly as
before. This makes a product's shell coherent; it does not make it safe, and
nothing here should ever be relied on as though it did.
"""

import logging

from odoo import api, models, tools

from .access_common import DEFAULTS, param, param_raw

_logger = logging.getLogger(__name__)

#: The mode in which the whole bar belongs to the platform administrator.
TOPBAR_ADMIN_ONLY = 'admin_only'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """The framework's answer, minus what this product's rule takes off it.

        `super()` first and always: this subtracts, it never adds. A menu that
        the framework has already decided this person cannot see does not come
        back because a role forgot to mention it — or because a setting named
        it as the home.
        """
        visible = super()._visible_menu_ids(debug=debug)
        # THE ONE WAY TO ASK WHAT THIS RULE IS DOING. A before-and-after report
        # has to be able to ask for the answer WITHOUT this rule, and the only
        # honest way to get it is to run the real code with the rule switched
        # off — a report that reconstructed "before" from a copy of the rule it
        # is checking would be marking its own homework. Nothing in the product
        # ever sets this; it is read only from a report and from a test.
        if self.env.context.get('biz_access_no_menu_rule'):
            return visible
        if self._biz_access_topbar_mode() == TOPBAR_ADMIN_ONLY:
            return self._biz_access_home_only(visible)
        hidden = self._biz_access_hidden_menu_ids()
        if not hidden:
            return visible
        return visible - set(hidden)

    # -------------------------------------------------- administrator-only
    @api.model
    def _biz_access_topbar_mode(self):
        """`by_role` or `admin_only`. Anything unrecognised means `by_role`.

        An unreadable setting must not be able to take the bar away: the mode
        that removes things is opted INTO by name and never arrived at by a
        typo.
        """
        mode = (param(self.env, 'biz_access.topbar_mode') or '').strip().lower()
        return TOPBAR_ADMIN_ONLY if mode == TOPBAR_ADMIN_ONLY else 'by_role'

    @api.model
    def _biz_access_home_only(self, visible):
        """Everything the framework would draw, cut down to the home entries.

        THE ADMINISTRATOR IS NEVER CUT. Same rule as the role lists above and
        for the same reason: this is a tidying rule for a product's shell, not
        a security boundary, and locking the person who owns the box out of
        Settings on the strength of it would be absurd.

        ROOTS ONLY, DELIBERATELY. The children of the home entry are not added
        back: the product draws its own navigation underneath, and a bar that
        re-listed it would be the second answer to "where do I go" that this
        mode exists to remove.
        """
        user = self.env.user
        if not user or self._biz_access_is_untouchable(user):
            return visible
        home = self._biz_access_home_menu_ids() & set(visible)
        if home:
            return frozenset(home)
        # NOBODY IS LEFT WITH NOTHING. Either the setting named no entry, or it
        # named entries this person cannot see anyway; keeping the first one
        # they could see is the only answer that is both honest and openable.
        fallback = self._biz_access_first_root(visible)
        _logger.warning(
            'biz_access: the top bar is in administrator-only mode and '
            '`biz_access.topbar_home_xmlids` names no entry %s can open, so '
            'they keep "%s" and nothing else. Set that parameter to the menu '
            'this product calls home.',
            user.login or user.id,
            self.sudo().browse(sorted(fallback)[:1]).name if fallback else '—')
        return frozenset(fallback)

    @api.model
    def _biz_access_home_menu_ids(self):
        """The menu ids named by `biz_access.topbar_home_xmlids`.

        Read through `param_raw` (F24) so that a value somebody has CLEARED on
        purpose reads as empty rather than as the shipped default — the two
        mean different things here, and only one of them means "work one out".
        """
        raw = param_raw(self.env, 'biz_access.topbar_home_xmlids')
        if raw is None:
            raw = DEFAULTS.get('biz_access.topbar_home_xmlids', '')
        ids = set()
        for xmlid in [x.strip() for x in (raw or '').split(',') if x.strip()]:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu and menu._name == 'ir.ui.menu':
                ids.add(menu.id)
            else:
                _logger.warning(
                    'biz_access: `biz_access.topbar_home_xmlids` names "%s", '
                    'which is not a menu on this database — ignored.', xmlid)
        return ids

    @api.model
    def _biz_access_first_root(self, visible):
        """One entry: the first ROOT of what this person could see anyway.

        Sorted the way the bar itself is sorted (`sequence, id`), so "the
        first one" means the same thing here as it does on the screen.
        """
        if not visible:
            return set()
        roots = self.sudo().with_context({}).search(
            [('id', 'in', list(visible)), ('parent_id', '=', False)],
            order='sequence, id', limit=1)
        if roots:
            return {roots.id}
        return {sorted(visible)[0]}

    # ------------------------------------------------------------------ the rule
    @api.model
    @tools.ormcache('frozenset(self.env.user.all_group_ids.ids)')
    def _biz_access_hidden_menu_ids(self):
        """The top-bar menus this person's roles agree they do not see.

        Cached on the PERMISSIONS the person holds rather than on their user id,
        for the same reason the framework caches its own answer that way: the
        rule is a function of what somebody holds, so two colleagues with the
        same access are one cache entry, and somebody who is given a role gets a
        different key rather than a stale answer.

        Returned as a `frozenset` because a cached mutable is a defect waiting
        for its first caller with a `.discard()` in it.
        """
        empty = frozenset()
        user = self.env.user
        if not user or self._biz_access_is_untouchable(user):
            return empty
        if 'biz.access.role' not in self.env:            # pragma: no cover
            return empty

        try:
            held = set(user.sudo().all_group_ids.ids)
            # EVERY ACTIVE ROLE, not only the ones with a list. A role that
            # hides nothing is saying so, and leaving it out of the search is
            # exactly the bug the module note describes.
            roles = self.env['biz.access.role'].sudo().search(
                [('active', '=', True)])
        except Exception:                                # noqa: BLE001
            # A rule that cannot be worked out must not take the top bar with
            # it. It says so at WARNING with the traceback, because a swallowed
            # failure logged at DEBUG is invisible on a live server.
            _logger.warning(
                'biz_access: the top-bar rule could not be worked out; the '
                'menu is left exactly as the framework drew it', exc_info=True)
            return empty

        lists = []
        for role in roles:
            # HOLDING A ROLE MEANS HOLDING ALL OF IT — the same test the roles
            # board, the passport and the left menu use. Somebody with three of
            # a role's four permissions is not doing that job, so its opinion
            # about the top bar is not about them.
            if not role.group_ids or not set(role.group_ids.ids) <= held:
                continue
            menus = role.hidden_menu_ids
            if not menus:
                # HIDES NOTHING, WHICH IS A STATEMENT. It goes into the
                # reckoning as the empty set and takes the intersection with it
                # — see the module note; a real doctor paid for the other
                # reading.
                return empty
            lists.append(self._biz_access_with_descendants(menus))
        if not lists:
            return empty

        hidden = set(lists[0])
        for other in lists[1:]:
            hidden &= other
            if not hidden:
                break
        return frozenset(hidden)

    @api.model
    def _biz_access_is_untouchable(self, user):
        """Whose top bar this rule never edits."""
        try:
            return bool(user.sudo().has_group('base.group_system'))
        except Exception:                                # noqa: BLE001
            _logger.warning(
                'biz_access: could not tell whether somebody is a system '
                'administrator — leaving their top bar alone', exc_info=True)
            return True

    @api.model
    def _biz_access_with_descendants(self, menus):
        """A menu named on a role stands for its WHOLE branch.

        Somebody writing "this role does not see Invoicing" means the
        application, not the one row labelled with its name — and storing every
        descendant instead would be a list that goes stale the day a module adds
        a screen underneath. So the list holds the top-most rows and the branch
        is worked out here, at read time, against the menu as it is today.

        `parent_path` is the framework's own materialised path (`'12/45/78/'`),
        so one `=like` per named row finds every descendant in a single search.
        """
        menus = menus.sudo()
        ids = set(menus.ids)
        paths = [m.parent_path for m in menus if m.parent_path]
        if not paths:
            return ids
        domain = ['|'] * (len(paths) - 1)
        for path in paths:
            domain.append(('parent_path', '=like', path + '%'))
        ids |= set(self.sudo().search(domain).ids)
        return ids

    # ------------------------------------------------------------ invalidation
    #
    # The framework clears this cache whenever a MENU changes. What it cannot
    # know about is the two things this rule also depends on: which menus a role
    # hides, and which roles a person holds. Both clear it from their own model,
    # because a cached answer that outlives the fact it was computed from is the
    # one bug nobody can reproduce.
    @api.model
    def _biz_access_forget(self):
        self.env.registry.clear_cache()
