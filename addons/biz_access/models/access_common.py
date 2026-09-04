# -*- coding: utf-8 -*-
"""The words, the caps, the switches and the small helpers this module shares.

ONE MODULE, ONE VOCABULARY. An area is spelled the same on the model, on the
board and in the audit trail, because three spellings of one idea is how a
filter quietly matches nothing.

THIS FILE IS PRODUCT-NEUTRAL ON PURPOSE. Nothing here names a product, an
industry or a screen that belongs to one application. Everything an application
wants to add — the areas roles are grouped under, the permission groups that
count as "may manage access here" — arrives through a REGISTRATION CALL made by
the application's own module at import time. A registry rather than an import,
because the dependency only ever runs one way: the application knows about
access management, and access management knows nothing about the application.

Two rules carried over from the module this was extracted from:

  * **A cap that is right for a SCREEN is a bug in a CRON.** Every cap below is
    a DEFAULT, every reader takes it as a PARAMETER, and the jobs pass `None`.
  * **A swallowed exception logged at DEBUG is invisible on a live server.**
    `safe()` returns its default and says so at WARNING with the traceback.
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# =============================================================================
# THE AREAS ROLES ARE GROUPED UNDER — A REGISTRY, NOT A LIST.
#
# An area is a word from the application's own left menu ("Clinical", "Money &
# budgets"), so this module cannot know them and must not invent them. It ships
# ONE neutral area so that a database with nothing but this module installed has
# a working board rather than a Selection field with no options, and an
# application replaces that list wholesale by registering its own.
# =============================================================================
#: What a database with no application on top of it offers.
NEUTRAL_AREA = ('general', 'General')

_AREAS = []
_DEFAULT_AREA = None


def register_areas(pairs, default=None):
    """An application says which areas its roles are grouped under.

    Called at import time from the application's own module. The first
    registration REPLACES the neutral default rather than adding to it: an
    application that has said "Clinical, People, Money" does not also want a
    stray "General" on its board. Registering the same key twice keeps the first
    label, so two modules of one product cannot fight over a word.
    """
    global _DEFAULT_AREA
    seen = {key for key, _label in _AREAS}
    for key, label in pairs or ():
        if key not in seen:
            _AREAS.append((key, label))
            seen.add(key)
    if default and default in seen:
        _DEFAULT_AREA = default
    return list(_AREAS)


def profile_areas():
    """Every area a role or an ability may belong to, in registration order."""
    return list(_AREAS) if _AREAS else [NEUTRAL_AREA]


def default_area():
    """The one a new role starts in."""
    if _DEFAULT_AREA:
        return _DEFAULT_AREA
    return profile_areas()[0][0]


def area_label(key, env=None):
    """The word for an area, translated where there is an env to ask.

    Module-level `_()` has no language to work in and logs "no translation
    language detected" on every call, so the environment is passed rather than
    assumed — `env._()` is the framework's own form for exactly this.
    """
    for k, lbl in profile_areas():
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


# =============================================================================
# WHO MAY MANAGE SOMEBODY ELSE'S ACCESS — ALSO A REGISTRY.
#
# This module ships its own "access team" permission and nothing else. An
# application whose own administrator tier should also be able to give and take
# roles registers that permission here; it is never hard-coded, because the next
# application will have a different one and a gate that drifts from the facade's
# produces a door that can only make an access dialog.
# =============================================================================
#: Who may open the board at all. Everybody with a login, because the "hand my
#: access over" half is for everybody by requirement — somebody going on leave
#: should not have to ask an administrator to arrange cover.
BOARD_GROUPS = ['base.group_user']

#: Who may grant and remove on somebody else's behalf.
MANAGE_GROUPS = ['biz_access.group_access_manager']


def register_manager_groups(*xmlids):
    """An application adds its own administrator tier to the manage gate."""
    for xmlid in xmlids:
        if xmlid and xmlid not in MANAGE_GROUPS:
            MANAGE_GROUPS.append(xmlid)
    return list(MANAGE_GROUPS)


def register_board_groups(*xmlids):
    """An application widens who may open the board at all. Rarely needed."""
    for xmlid in xmlids:
        if xmlid and xmlid not in BOARD_GROUPS:
            BOARD_GROUPS.append(xmlid)
    return list(BOARD_GROUPS)


# ------------------------------------------------------------------ the words
DELEGATION_KINDS = [
    ('temporary', 'For a while'),
    ('permanent', 'For good'),
]

DELEGATION_STATES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('expired', 'Ended'),
    ('revoked', 'Taken back'),
]

# =============================================================================
# THE ABSOLUTE. Nothing in this module may ever put anybody into one of these.
#
# `base.group_system` and `base.group_erp_manager` are the keys to the whole
# database — the settings screens, every model's ACL, the ability to install
# code. A "temporary hand-over" of one of those is not a hand-over, it is a
# permanent change of who owns the system, and a screen that makes it a
# two-click action is a screen that will eventually be used for that.
#
# Belt AND braces: no catalogue an application seeds may contain them (there is
# a test that walks the whole implied closure and fails if one is reachable),
# `biz.access.role` and `biz.access.ability` refuse to be created or written
# pointing at one, and the facade checks again before it applies anything.
# =============================================================================
FORBIDDEN_GROUP_XMLIDS = (
    'base.group_system',
    'base.group_erp_manager',
)

# ------------------------------------------------------------------- the caps
DELEGATION_ROW_CAP = 500
#: Holders shown per profile on the roles board. A profile held by four
#: thousand people is a fact, not a list, and the board says the number.
HOLDER_CAP = 40
PICKER_CAP = 20
#: People listed in the People lens at once. A list of two hundred colleagues
#: is already longer than anybody scrolls; past it, the search box is the
#: answer, and the lens says so rather than truncating in silence.
PEOPLE_CAP = 200

# --------------------------------------------------------------- the switches
#: Defaults live in CODE, never in a `noupdate="1"` record — a shipped record
#: freezes whatever value a test run left behind, because the next upgrade
#: never corrects it.
DEFAULTS = {
    #: Are the hand-over mails switched on?
    'biz_access.delegation_mail': '1',
    #: How long a hand-over runs for when nobody says otherwise.
    'biz_access.default_window_days': '14',
    #: Is developer mode kept for the system administrator alone? `off` puts
    #: the framework's own behaviour back; anything else, including this row
    #: being absent, means the block is on. See `models/ir_http.py`.
    'biz_access.debug_block': 'on',
    #: HOW THE TOP BAR IS DECIDED.
    #:
    #: `by_role` — the default and the general case: every role names the
    #: applications the people who hold it do not see, and the lists are
    #: reconciled by intersection (`models/ir_ui_menu.py`).
    #:
    #: `admin_only` — the whole bar belongs to the platform administrator and
    #: nobody else sees anything on it but the home named below. A product
    #: whose own left menu IS the navigation chooses this: two menus over one
    #: screen is two answers to "where do I go", and the second one was never
    #: curated by anybody.
    'biz_access.topbar_mode': 'by_role',
    #: In `admin_only`, the top-level entries everybody keeps — comma-separated
    #: menu xml-ids. ROOTS ONLY: what is inside them is the product's own
    #: navigation to draw, not this bar's. Empty means "work one out", never
    #: "show nobody anything" — see `_biz_access_home_menu_ids`.
    'biz_access.topbar_home_xmlids': '',
}

#: The settings above that the menu rule reads. Writing one of them has to
#: clear the cached answer, or the bar goes on showing yesterday's decision
#: until something else happens to clear it.
TOPBAR_PARAM_KEYS = ('biz_access.topbar_mode', 'biz_access.topbar_home_xmlids')


def param(env, key, default=None, defaults=None):
    """A config parameter, with the calling module's own default behind it."""
    raw = env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, False, ''):
        raw = (DEFAULTS if defaults is None else defaults).get(key, default)
    return raw


def param_raw(env, key):
    """The row's own value, `None` when there is no row — F24.

    `get_param` cannot tell "not set" from "deliberately empty": it answers
    `False` for a missing key and its body ends in `or default`, so a value
    somebody has cleared on purpose comes back as the default they cleared it
    from. Any setting where EMPTY is a real answer has to read the row.
    """
    row = env['ir.config_parameter'].sudo().search(
        [('key', '=', key)], limit=1)
    if not row:
        return None
    return row.value or ''


def param_int(env, key, default=0, defaults=None):
    try:
        return int(str(param(env, key, default, defaults)).strip())
    except (TypeError, ValueError):
        return default


def flag(env, key, defaults=None):
    return str(param(env, key, '0', defaults)).strip().lower() in (
        '1', 'true', 'yes', 'on')


def counted(n, one, many):
    """"1 role" / "4 roles" — never "1 role(s)"."""
    return one if n == 1 else many % n


def fold(text):
    """Accents folded, never stripped.

    Not every database has an `unaccent` extension and plenty of people carry an
    accent in their name, so every match this module makes on a name is made in
    Python over folded text.
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(c for c in out if not unicodedata.combining(c))
    # Vietnamese `đ` carries no combining mark, so NFKD leaves it alone.
    out = out.replace('đ', 'd').replace('Đ', 'D')
    return out.strip().lower()


def safe(fn, default=None, what='a piece of this screen'):
    """Every independent probe gets its OWN try/except — never a shared one.

    And it says so at WARNING with the traceback: a swallowed failure logged at
    DEBUG is invisible on a live server, which is how a job that half worked
    came to report a cheerful small number.
    """
    try:
        return fn()
    except Exception:                           # noqa: BLE001
        _logger.warning('biz_access: %s could not be read', what, exc_info=True)
        return default


def forbidden_group_ids(env):
    """The ids of the groups nothing here may ever hand out.

    Resolved by xmlid and tolerant of one being absent — a database without
    `base.group_erp_manager` is not a database where the refusal should stop
    working for the other one.
    """
    out = set()
    for xmlid in FORBIDDEN_GROUP_XMLIDS:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            out.add(rec.id)
    return out


def implied_closure(groups):
    """Every permission these permissions actually carry, themselves included.

    A group that IMPLIES the administrator permission hands over the same
    database as the administrator permission does, so every check in this module
    that used to look at one group now looks at the whole closure. On this build
    `res.groups.all_implied_ids` is that closure and it is REFLEXIVE — it
    contains the group itself — so the field answers the question directly. The
    hand walk below is there for a build where the field is not, because a rail
    that silently stops checking is worse than no rail.
    """
    if not groups:
        return groups
    groups = groups.sudo()
    if 'all_implied_ids' in groups._fields:
        try:
            return groups | groups.all_implied_ids
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'biz_access: all_implied_ids could not be read — walking '
                'implied_ids by hand instead', exc_info=True)
    seen = groups
    frontier = groups
    while frontier:
        frontier = frontier.implied_ids - seen
        seen |= frontier
    return seen


def forbidden_in_closure(groups, env):
    """The forbidden permissions these permissions reach, if any.

    Returns a `res.groups` recordset so the caller can name them in the refusal
    — "it would carry X" is a sentence somebody can act on, and "no" is not.
    """
    empty = env['res.groups'].browse()
    forbidden = forbidden_group_ids(env)
    if not forbidden or not groups:
        return empty
    try:
        return implied_closure(groups).filtered(lambda g: g.id in forbidden)
    except Exception:                           # noqa: BLE001
        # And this one is load-bearing: a check that cannot be made must be
        # reported, never treated as a pass.
        _logger.warning(
            'biz_access: the forbidden-permission check could not be made '
            'for %s', groups.ids, exc_info=True)
        return env['res.groups'].browse(
            [gid for gid in groups.ids if gid in forbidden])


# =============================================================================
# THE LEFT MENU — A PROVIDER, NOT AN INHERIT.
#
# This module needs to know four things about a product's left menu: what is on
# it, who can see each entry, which roles are written on an entry, and how to
# change that. It cannot INHERIT a menu model, because every product's menu is a
# different model with a different shape, and a generic module that names one is
# a generic module that installs on exactly one database.
#
# So it declares WHAT IT NEEDS and a product supplies it — the same
# soft-registration pattern this module already uses for its areas, its manager
# groups and its catalogue. Registered at import time, read at CALL time, so a
# registration made after this file was imported still counts.
#
# A DATABASE WITH NO PROVIDER IS A DATABASE WITH NO LEFT MENU, and that is an
# honest answer rather than a failure: the Screens lens says so in words, the
# mini rail is empty, and every write refuses with a sentence.
# =============================================================================
_RAIL_PROVIDER = [None]


def register_rail(provider):
    """A product says how to read and write its left menu.

    Passing `None` clears the registration — which is what a test does in its
    own cleanup, and the only reason this takes a falsy value at all.
    """
    _RAIL_PROVIDER[0] = provider or None
    return _RAIL_PROVIDER[0]


def rail_provider():
    """The registered provider, or `None`."""
    return _RAIL_PROVIDER[0]


class RailProvider:
    """The protocol a product implements to put its left menu on this home.

    THIS IS A PLAIN CLASS AND NOT A MODEL, on purpose. A product's menu already
    lives in a model of its own; making the provider a model too would be a
    second row of state to keep in step with the first. A provider is a thin
    adapter over what the product already has, and it holds nothing.

    Every method takes `env` rather than reading one off `self`, because ONE
    provider instance serves every database this registry is loaded for, and an
    adapter that remembered an environment would answer the wrong database's
    question on the second tenant.

    A subclass need only override what its menu can actually do. Everything is
    given a safe default here: the reads answer empty and the writes refuse, so
    a half-written provider produces an honest screen rather than a traceback.
    """

    #: A short name for the product's menu, used only in logs.
    key = 'none'

    # ------------------------------------------------------------------ reads
    def available(self, env):
        """Is there a left menu on this database at all?"""
        return False

    def sections(self, env, include_inactive=False):
        """The blocks of the menu, in their own order.

        `[{'id', 'name', 'sequence', 'active'}]`, and two OPTIONAL keys a
        product may add: `'key'` (its own short name for the block) and
        `'role_ids'` — the roles written on the BLOCK, for a menu where a gate
        on a block flows down to everything inside it. Nothing in this module
        decides anything from `role_ids` on a section: `visibility_for` is the
        product's own answer and has already taken it into account. It is here
        so a lens can SAY that a whole block is gated, rather than repeating the
        same chip on fourteen rows.
        """
        return []

    def entries(self, env, include_inactive=False):
        """The rows of the menu, in their own order.

        `[{'id', 'section_id', 'parent_id' (0 for a top-level row), 'name',
           'icon', 'sequence', 'active', 'group_ids': [int],
           'restricted': bool, 'restriction_reason': str,
           'role_ids': [int]}]`

        `role_ids` is what is WRITTEN on the entry, archived roles INCLUDED.
        "Is this entry gated at all" and "who gets through the gate" are two
        different questions, and answering the first with the active list makes
        archiving the last role on an entry open it to the whole company.

        `icon` is whatever the product stores. A key this kit's icon set knows
        is drawn as that glyph; anything else that starts with `fa ` is drawn as
        the font class it is; anything else is a plain dot.

        One OPTIONAL key: `'legacy_note'`, a plain sentence for a product that
        is part-way through moving its menu from one kind of gate to another.
        While both are live an entry can be opened by a gate this lens does not
        edit, and a lens that showed only the half it can change would be
        describing the entry wrongly. Empty on a product with one lane — which
        is every product that never had two.
        """
        return []

    def visibility_for(self, env, user):
        """What THIS PERSON sees, decided by the product's own menu code.

        `{'items': {id: 'on'|'locked'|'hidden'}, 'sections': {...}}`

        This module keeps NO copy of that rule and must not: a copy drifts, and
        it drifts by telling somebody they can open a screen they cannot. Where
        a product's menu has no rule of its own, `rail_state()` below is the one
        to build this from — it is the rule, written once.
        """
        return {'items': {}, 'sections': {}}

    def advanced_action(self, env):
        """The xmlid of the product's own plain table of menu rows, or `''`.

        The Screens lens offers it as a quiet link for the administrator who
        needs the row itself. A product with no such screen returns nothing and
        the link is simply not drawn — never drawn and inert.
        """
        return ''

    def reload_event(self):
        """The bus event the product's menu listens for, or `None`.

        Returned to the browser after every write so the REAL menu two hundred
        pixels from the editor re-reads itself. A product whose menu cannot be
        told to reload returns `None`, and the browser triggers nothing.
        """
        return None

    # ----------------------------------------------------------------- writes
    def set_roles(self, env, entry_id, role_ids):
        raise NotImplementedError

    def set_active(self, env, entry_id, active):
        raise NotImplementedError

    def set_restricted(self, env, entry_id, restricted, reason):
        raise NotImplementedError

    def reorder(self, env, section_id, entry_ids):
        raise NotImplementedError


def rail_state(entry, is_admin, held_group_ids, role_groups):
    """(visible, locked) — who can see one entry on a left menu.

    THE RULE, WRITTEN ONCE, AS A FUNCTION OF NOTHING BUT ITS ARGUMENTS. Every
    surface in this module — the Screens lens, a person's passport, the
    builder's miniature — has to give the SAME answer as the real menu, and the
    only way to guarantee that is for there to be one answer. A provider whose
    product has no visibility rule of its own builds `visibility_for` out of
    this; the fake provider the tests run against does exactly that, so the
    tests exercise the rule the product will run.

    Arguments:
      `entry`            one row from `RailProvider.entries()`
      `is_admin`         does this person hold the system-administrator tier
      `held_group_ids`   every permission they hold, TRANSITIVELY
      `role_groups`      `{role_id: set(group_ids)}` for ACTIVE roles only

    The branches, in order, and each is load-bearing:

      * **no permissions and no roles written on it → open to everybody.** The
        default state of a menu row nobody has gated.
      * **an administrator → open.** Every gate short-circuits for them, exactly
        as the real menu does, or the passport would show them a menu their
        colleague has and they do not.
      * **the permission lane, ANY.** Holding any one of the permissions named
        on the entry is enough. This is the lane that existed before roles, and
        it stays so that re-gating a live menu takes nobody's door away.
      * **the role lane, ALL.** A role is a BUNDLE — a job, not a shopping list.
        Somebody with two of its three permissions cannot do the job its
        sentence describes, so the entry does not open for them. A role with NO
        permissions is held by nobody, never by everybody, which is what an
        empty subset test would otherwise say.
      * **a teaser → shown, locked.** The entry is visible with a note about
        what it is. "Off" would be a lie about what they see.
      * **otherwise → not on their menu.**

    AN ARCHIVED ROLE OPENS NOTHING. It is absent from `role_groups`, so an entry
    gated ONLY on archived roles is reachable by nobody but an administrator —
    and, because the FIRST branch counts what is WRITTEN rather than what is
    active, it does not quietly fall back to "open to everybody" either. A gate
    that widened when its role was archived would be a gate that fails open.
    """
    groups = set(entry.get('group_ids') or ())
    roles = list(entry.get('role_ids') or ())
    if not groups and not roles:
        return True, False
    if is_admin:
        return True, False
    held = set(held_group_ids or ())
    if groups & held:
        return True, False
    for role_id in roles:
        needed = role_groups.get(role_id)
        if needed and needed <= held:
            return True, False
    if entry.get('restricted'):
        return True, True
    return False, False
