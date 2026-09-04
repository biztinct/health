# -*- coding: utf-8 -*-
"""What this module offers an application, and what it does the day it lands.

THE CATALOGUE REGISTRY. This module seeds NOTHING. It knows nothing about
clinics, or ledgers, or budgets, or what an ability should be called — those are
the application's words, and a generic module that shipped somebody else's
vocabulary would put the wrong words on the next product's screen. An
application registers a seeding callable and `ensure_catalogue()` runs whatever
is registered. A database with only this module on it has a working, EMPTY
Access home, which is the honest answer.

`ensure_bundles()` is here rather than in an application because it is not about
any catalogue: it gives a role somebody made BY HAND an ability of its own, so
nothing is left with an empty bundle. That is a fact about the model, not about
a product.
"""

import logging
import re
import unicodedata

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# =============================================================================
# THE CATALOGUE REGISTRY.
#
# An application registers ONE callable that seeds its own roles and abilities.
# It is called with an env and must be safe to run again — every seeding routine
# in this family is idempotent by construction rather than by a stamp, because
# it runs on a fresh install, on an upgrade, and on a database somebody restored
# from a backup taken in between.
# =============================================================================
_PROVIDERS = []


def register_catalogue(fn, name=None):
    """An application says how to seed its own roles and abilities."""
    key = name or getattr(fn, '__module__', '') + '.' + getattr(
        fn, '__name__', repr(fn))
    for existing_key, _existing in _PROVIDERS:
        if existing_key == key:
            return _PROVIDERS
    _PROVIDERS.append((key, fn))
    return _PROVIDERS


def catalogue_providers():
    return list(_PROVIDERS)


def ensure_catalogue(env):
    """Seed whatever the applications on this database have registered.

    On a database with nothing but this module installed there is nothing
    registered, and an EMPTY Access home is the right answer: this module has no
    vocabulary of its own to offer and inventing one would put words on somebody
    else's screen.

    EVERY PROVIDER GETS ITS OWN GUARD. One application whose catalogue cannot be
    read must not stop the next one's from being read — and the failure is
    logged at WARNING with its traceback, because a swallowed failure logged at
    DEBUG is invisible on a live server.
    """
    ran = []
    for key, fn in _PROVIDERS:
        try:
            fn(env)
            ran.append(key)
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the "%s" catalogue could not be seeded', key,
                exc_info=True)
    linked = ensure_bundles(env)
    _logger.info(
        'biz_access: catalogue — %s application catalogue(s) run, %s role(s) '
        'written down as bundles of what they already carried',
        len(ran), linked)
    return {'providers': ran, 'linked': linked}


def _slug(text, fallback='ability'):
    """A stable key out of a name an administrator typed.

    Accents folded rather than stripped: "Chế độ" must not become "ch-", which
    is a key that collides with the next three roles like it.
    """
    raw = unicodedata.normalize('NFKD', str(text or ''))
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    raw = raw.replace('đ', 'd').replace('Đ', 'D')
    raw = re.sub(r'[^a-zA-Z0-9]+', '-', raw).strip('-').lower()
    return raw or fallback


def ensure_bundles(env):
    """Give every remaining role an ability, so nothing is left unbundled.

    An application's catalogue covers the roles it seeded. An administrator may
    have added their own before bundles existed — one name, one permission — and
    that role would otherwise have an EMPTY bundle, which the board reads as
    "nobody holds this" for something several people plainly hold. So each one
    gets an ability of its own, wrapping exactly the permission it already
    carried, named after the role because that is the only honest sentence
    available for it.

    It changes nobody's permissions. It writes down, in the new shape, what the
    old shape already said.
    """
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    Ability = env['biz.access.ability'].sudo().with_context(active_test=False)
    orphans = Role.search(
        [('ability_ids', '=', False), ('group_id', '!=', False)])
    linked = 0
    for profile in orphans:
        key = 'role-%s-%s' % (_slug(profile.name, 'role'), profile.id)
        # Found by its own key and by nothing else. Reusing "an ability that
        # happens to contain this permission" would attach the OTHER
        # permissions in it too, and a migration that widens somebody's access
        # is the one outcome this module refuses everywhere.
        ability = Ability.search([('technical_key', '=', key)], limit=1)
        try:
            if not ability:
                ability = Ability.create({
                    'technical_key': key,
                    'name': profile.name or key,
                    'description': profile.description or '',
                    'area': profile.area,
                    'sequence': profile.sequence or 10,
                    'group_ids': [(6, 0, [profile.group_id.id])],
                })
            profile.write({'ability_ids': [(6, 0, ability.ids)]})
            linked += 1
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'biz_access: the "%s" role could not be given an ability for '
                'the permission it already carried', profile.name,
                exc_info=True)
    if linked:
        _logger.info(
            'biz_access: %s roles outside any seeded catalogue were written '
            'down as bundles of what they already carried', linked)
    return linked


def post_init_hook(env):
    """Odoo 19 hands the hook an `env`. This runs on INSTALL only.

    A hook does NOT fire on an upgrade, so an ability whose permission belongs
    to a module installed later in the same cascade would be missed for good.
    `biz.access.reseed_catalogue()` is the call that closes that gap; it is
    deliberately not a button, because its caller is the platform's own tooling
    straight after it has installed something.
    """
    if not isinstance(env, api.Environment):        # pragma: no cover
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
