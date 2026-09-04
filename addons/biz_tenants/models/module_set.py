# -*- coding: utf-8 -*-
"""What a customer's system is MADE OF, computed from the product's own
dependencies rather than written down by hand.

THE OWNER'S RULE, IN ONE SENTENCE: *care apps only — but some care apps need a
few core parts as dependencies, and you work that out from the dependencies.*

So there is no list of what a customer gets. There is a rule:

    take every part of the product on the master — everything whose name starts
    with one of the product's own prefixes — follow what each of them declares
    it needs, and follow that, and so on. Add anything the product asked for by
    name that nothing happens to depend on. Everything else the master has is,
    by definition, never given to a customer.

WHY COMPUTED AND NOT LISTED. A list is right on the day it is written and wrong
on the day somebody adds a dependency. The master is also the clinic that runs
today, so it accumulates things — an Inventory app, a Sales app, a spreadsheet
dashboard — that are nothing to do with the product. A hand-written list would
have to be re-checked every time either side moved; a computation is re-checked
by running it.

⚠ AND IT ANSWERS A SECOND QUESTION NOBODY ASKS UNTIL IT BITES (ledger H57): the
framework installs `auto_install` modules on its own the moment their triggers
are all present. A never-list that names one of those is a never-list that will
be quietly broken by the framework. So the computation runs the framework's own
auto-install rule over the answer — inside the master's universe, because the
practical question is "of the parts this master has, which does a customer end
up with" — and reports anything on the never-list that the computation pulls in
anyway. That report is a TEST FAILURE, naming both modules, so the day somebody
makes Inventory load-bearing it is a red test and not a surprise on a nurse's
screen.

NOTHING HERE IMPORTS THE FRAMEWORK (rail R6). Every input is a plain dict, so
the whole rule is reachable from a unit test with no registry, and it cannot
grow a database read by accident.
"""
import logging

from .tenants_common import is_never, never_reason

_logger = logging.getLogger(__name__)

# =============================================================================
# 1. WHAT COUNTS AS "PART OF THE PRODUCT"
#
# The generic core cannot know, so the overlay says. Same shape as every other
# registry in this module: registered at import time by the product, read at
# CALL time so the order two modules load in stops mattering.
# =============================================================================
#: Name prefixes that mark a module as the product's own.
PRODUCT_PREFIXES = []

#: Parts a customer must have that NOTHING in the product depends on. A country
#: chart of accounts is the example that forced this to exist: no clinical
#: module can declare it (the product is sold in more than one country), and yet
#: a clinic in Vietnam without the Vietnamese accounts is not a working clinic.
EXTRAS = []


def register_product_prefixes(prefixes):
    """A product says how its own modules are named."""
    for p in (prefixes or ()):
        p = str(p or '').strip()
        if p and p not in PRODUCT_PREFIXES:
            PRODUCT_PREFIXES.append(p)
    return tuple(PRODUCT_PREFIXES)


def register_extras(names):
    """A product names a part its customers must have that nothing needs."""
    for n in (names or ()):
        n = str(n or '').strip()
        if n and n not in EXTRAS:
            EXTRAS.append(n)
    return tuple(EXTRAS)


def product_prefixes():
    return tuple(PRODUCT_PREFIXES)


def extras():
    return tuple(EXTRAS)


# =============================================================================
# 2. THE COMPUTATION
# =============================================================================
def _manifest(manifests, name):
    """`{'depends': [...], 'auto_install': …}` from either shape of input.

    A manifest map may be `{name: [depends]}` (which is all most callers have)
    or `{name: {'depends': …, 'auto_install': …}}`. Both are accepted because
    the first is what a test wants to write and the second is what the server
    can actually read.
    """
    raw = (manifests or {}).get(name)
    if raw is None:
        return {'depends': [], 'auto_install': None}
    if isinstance(raw, dict):
        return {'depends': [str(d) for d in (raw.get('depends') or ())],
                'auto_install': raw.get('auto_install')}
    return {'depends': [str(d) for d in raw], 'auto_install': None}


def _never_test(never):
    """`never` may be a callable, a set of names, or nothing at all."""
    if never is None:
        return is_never
    if callable(never):
        return never
    names = set(never)
    return lambda n: n in names


def customer_module_set(master_installed, manifests, never=None,
                        prefixes=None, extras_names=None):
    """Everything a customer's system is made of. PURE.

    `master_installed` — the names the master has installed.
    `manifests`        — every module on the machine, `{name: depends}` or
                         `{name: {'depends', 'auto_install'}}`.
    `never`            — a callable or a set of names a customer never gets.
                         Defaults to the registered never-list.
    `prefixes`         — defaults to the registered product prefixes.
    `extras_names`     — defaults to the registered extras.

    Returns a dict:

      * `modules`    — sorted, everything a customer ends up with.
      * `seeds`      — the product's own parts plus the extras, sorted: what
                       the computation started from.
      * `pulled_by`  — `{module: why it is in}`, for the screen.
      * `followers`  — `{module: [the triggers that brought it]}` — the parts
                       the framework installs on its own.
      * `held_back`  — sorted, what the master has and a customer does not.
      * `conflicts`  — `[{module, pulled_by, reason}]` — anything on the
                       never-list that the computation pulls in ANYWAY. Empty
                       is the only acceptable answer; a test asserts it.
    """
    master = set(master_installed or ())
    prefixes = tuple(prefixes if prefixes is not None else product_prefixes())
    wanted_extras = tuple(extras_names if extras_names is not None
                          else extras())
    blocked = _never_test(never)

    seeds = sorted(
        {n for n in master if prefixes and n.startswith(prefixes)
         and not blocked(n)}
        | {n for n in wanted_extras if n in master and not blocked(n)})

    # ---- the declared closure -------------------------------------------
    #
    # ⚠ A NEVER-LISTED MODULE REACHED BY A DEPENDENCY IS FOLLOWED, NOT SKIPPED,
    # AND THAT IS THE WHOLE TRIPWIRE. Skipping it would make the answer LOOK
    # clean while the framework went on installing it anyway — the list would
    # say Inventory is held back and every customer would have Inventory. So
    # the computation follows what the manifests actually say, and anything
    # blocked that it reaches comes back in `conflicts` for somebody to fix.
    # Only the SEEDS are filtered, because a seed is a choice.
    pulled_by = {n: 'seed' for n in seeds}
    modules, stack = set(), list(seeds)
    while stack:
        name = stack.pop()
        if name in modules:
            continue
        modules.add(name)
        for dep in _manifest(manifests, name)['depends']:
            pulled_by.setdefault(dep, name)
            if dep not in modules:
                stack.append(dep)

    # ---- what the framework adds on its own ------------------------------
    #
    # ⚠ INSIDE THE MASTER'S UNIVERSE ON PURPOSE. Every country's chart of
    # accounts on this machine declares `auto_install = ['account']`, and the
    # framework only installs the one matching the company's country — a rule
    # that lives in the framework and not in a manifest. Asking the question of
    # the parts the master ACTUALLY HAS gives the true answer without this file
    # having to know anything about countries.
    followers = {}
    changed = True
    while changed:
        changed = False
        for name in sorted(master - modules):
            man = _manifest(manifests, name)
            auto = man['auto_install']
            if auto in (None, False):
                continue
            triggers = (man['depends'] if auto is True
                        else [str(a) for a in auto])
            if triggers and all(t in modules for t in triggers):
                modules.add(name)
                followers[name] = triggers
                pulled_by.setdefault(
                    name, 'auto:%s' % ','.join(sorted(triggers)))
                changed = True

    conflicts = [
        {'module': n, 'pulled_by': pulled_by.get(n, ''),
         'reason': never_reason(n)}
        for n in sorted(modules) if blocked(n)
    ]
    return {
        'modules': sorted(modules),
        'seeds': seeds,
        'pulled_by': pulled_by,
        'followers': followers,
        'held_back': sorted(master - modules),
        'conflicts': conflicts,
    }


def module_set_rows(answer, labels=None):
    """The held-back half, with a plain reason each, for the screen.

    Same shape as `sync_rules.held_back_rows`, deliberately: the "In step with
    master" screen already draws that shape and this is the same question asked
    of a different list.
    """
    labels = labels or {}
    return [{'module': n, 'label': labels.get(n, n), 'reason': never_reason(n)}
            for n in sorted((answer or {}).get('held_back') or ())]


def dependency_conflicts(answer):
    """The tripwire, as a sentence somebody can act on.

    `[(module, what pulled it in)]`. The day a part of the product declares it
    needs Inventory, this stops being empty — and the message names BOTH, so
    nobody has to go looking for which module changed.
    """
    return [(c['module'], c['pulled_by'])
            for c in (answer or {}).get('conflicts') or ()]
