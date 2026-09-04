# -*- coding: utf-8 -*-
"""What the cockpit needs to know about the product it is running, as REGISTRIES.

THE WHOLE ARGUMENT FOR THIS FILE. This module creates and runs customer
systems. It must not know what those systems are FOR. A cockpit that named a
clinic, a payroll or a bank would be a cockpit that could only ever run one of
them — and the whole reason it was written here rather than inside the product
was so that the next product can have it.

So everything product-shaped arrives through a registration made at import time
by an overlay module, and this file holds the registrations and nothing else.
With nothing registered the cockpit still boots, still lists what is on the box,
and says honestly on screen that nobody has told it what this product is.

EVERY READER TAKES `env` AS AN ARGUMENT (ACCESS F4 / ledger H6). One registry is
loaded once per process and serves every database on the cluster; a helper that
remembered an environment would answer the wrong customer's question the second
time it was called. Nothing here holds one.

AND EVERY ADDRESS IS A SETTING, NEVER A LITERAL. The registration supplies the
DEFAULT; a row in `ir.config_parameter` beats it. The master's own address has
already changed once in the middle of this programme, and it took seventeen
places with it.
"""
import logging

_logger = logging.getLogger(__name__)

# =============================================================================
# 1. WHAT THIS PLATFORM IS CALLED AND WHERE IT LIVES
# =============================================================================
#: The four settings, and the keys they are read from. A product registers the
#: defaults; an operator overrides any of them without a deploy.
P_BRAND = 'biz_tenants.brand'
P_APEX = 'biz_tenants.apex_domain'
P_PREFIX = 'biz_tenants.backend_prefix'
P_TEMPLATE = 'biz_tenants.template_db'

#: Two more the cockpit reads, with defaults in CODE rather than in a
#: `noupdate="1"` record — a shipped record freezes whatever value a test run
#: left behind, because the next upgrade never corrects it.
P_BACKUP_ROOT = 'biz_tenants.backup_root'
P_MEMORY_FLOOR = 'biz_tenants.memory_floor_mb'
P_HEALTH_IGNORE = 'biz_tenants.health_ignore'
P_STATUS_DIR = 'biz_tenants.status_dir'
P_RECOVERY_LOGIN = 'biz_tenants.recovery_login'
P_TEMPLATE_CRONS = 'biz_tenants.template_active_crons'

#: THE CAPACITY GUARD'S TWO NUMBERS, and the first of them is a POLICY rather
#: than a measurement (ledger F34). See `capacity_verdict` for the argument;
#: the short version is that the MEASURED cost of a customer on this machine is
#: about 11 MB of resident memory across the three processes that serve them,
#: and that is not what a customer COSTS — sessions, asset caches and a busy
#: clinic's working set are the rest, and none of them can be measured at rest.
#: So the setting carries the measurement plus a deliberate allowance, and it is
#: a SETTING so it can be re-weighed as customers arrive rather than redeployed.
P_TENANT_COST = 'biz_tenants.tenant_cost_mb'
P_CAPACITY_RESERVE = 'biz_tenants.capacity_reserve_mb'

#: Who the platform would tell, if it could tell anybody. Empty means "every
#: platform administrator with an address", which is the only state in which
#: this matters most: a platform nobody has configured still reaches a human.
P_ALERT_TO = 'biz_tenants.alert_to'
#: How long before a problem says itself again, in hours, by severity.
P_ALERT_EVERY_CRITICAL = 'biz_tenants.alert_every_critical'
P_ALERT_EVERY_WARNING = 'biz_tenants.alert_every_warning'
#: Whose clock the PUBLIC page speaks in. It has no reader to ask (F38), so the
#: zone is named on the page itself and this is where it comes from.
P_STATUS_TZ = 'biz_tenants.status_tz'
#: When somebody last opened the Alerts screen — what "since you were last
#: here" is measured from. With nothing being emailed, that strip is how the
#: owner finds out anything happened at all.
P_ALERTS_SEEN = 'biz_tenants.alerts_seen_at'

#: What a bare install answers before any product has registered anything.
#: DELIBERATELY NOT A PRODUCT NAME: a cockpit that says "the platform" on a
#: database nobody has configured is honest; one that says somebody else's
#: brand is a bug wearing a label.
#
# ⚠ EVERY VALUE HERE IS EMPTY, INCLUDING THE ONE THAT HAS AN OBVIOUS DEFAULT.
# `register_platform` writes a key only when it is still empty — that is what
# makes the FIRST registration win — so a key pre-filled with a plausible
# default silently REFUSES the product's own answer. The backend prefix was
# `/odoo` here, the product registered `/bizapp`, and the registration was
# thrown away without a word. The fallback belongs in the reader.
_PLATFORM = {
    'brand': '',
    'apex': '',
    'backend_prefix': '',
    'template_db': '',
}

_DEFAULTS = {
    P_BACKUP_ROOT: '/odoo/backups/tenants',
    #: Free memory below which provisioning refuses, in MB. A soft floor: the
    #: REAL capacity guard is the next phase's, and this one exists so that
    #: today's cockpit cannot fill a small box by accident.
    P_MEMORY_FLOOR: '400',
    P_HEALTH_IGNORE: '',
    P_STATUS_DIR: '',
    P_RECOVERY_LOGIN: '',
    #: 60 MB is the POLICY (F34). The MEASUREMENT is ~11 MB. They are different
    #: numbers answering different questions and the report says so out loud.
    P_TENANT_COST: '60',
    P_CAPACITY_RESERVE: '400',
    P_ALERT_TO: '',
    P_ALERT_EVERY_CRITICAL: '2',
    P_ALERT_EVERY_WARNING: '6',
    P_STATUS_TZ: '',
    P_ALERTS_SEEN: '',
}


def register_platform(values):
    """A product names itself, its apex domain, its backend prefix, its template.

    Called at import time from an overlay module. The FIRST registration wins
    for each key, so two modules of one product cannot fight over an address.
    """
    for key in ('brand', 'apex', 'backend_prefix', 'template_db'):
        val = (values or {}).get(key)
        if val and not _PLATFORM.get(key):
            _PLATFORM[key] = str(val).strip()
    return dict(_PLATFORM)


def platform_defaults():
    """What the product registered, whatever a setting later says."""
    return dict(_PLATFORM)


def param(env, key, default=None):
    """A setting, with the registered default behind it.

    `get_param` and not `param_raw` here on purpose: for an ADDRESS, "not set"
    and "set to empty" mean the same thing and neither is usable. The places
    where the difference matters read the row themselves (F24) and say so.
    """
    raw = env['ir.config_parameter'].sudo().get_param(key)
    if raw in (None, False, ''):
        return _DEFAULTS.get(key, default)
    return raw


def param_row(env, key):
    """The row's OWN value, `None` when there is no row — ledger F24.

    `get_param` cannot tell "nobody has ever set this" from "somebody cleared
    it on purpose": it answers `False` for a missing key and its body ends in
    `or default`. Any setting where empty is a real answer reads the row.
    """
    row = env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
    return None if not row else (row.value or '')


def brand(env):
    return (param(env, P_BRAND) or _PLATFORM['brand'] or '').strip()


def apex(env):
    return (param(env, P_APEX) or _PLATFORM['apex'] or '').strip()


def backend_prefix(env):
    return (param(env, P_PREFIX) or _PLATFORM['backend_prefix'] or '/odoo').strip()


def template_db(env):
    return (param(env, P_TEMPLATE) or _PLATFORM['template_db'] or '').strip()


def memory_floor_mb(env):
    try:
        return int(str(param(env, P_MEMORY_FLOOR)).strip())
    except (TypeError, ValueError):
        return int(_DEFAULTS[P_MEMORY_FLOOR])


def _number(env, key, fallback):
    try:
        return float(str(param(env, key)).strip())
    except (TypeError, ValueError):
        return float(fallback)


def tenant_cost_mb(env):
    """How much memory ONE customer is allowed. A policy, not a measurement."""
    return _number(env, P_TENANT_COST, _DEFAULTS[P_TENANT_COST])


def capacity_reserve_mb(env):
    """What must stay free for the database and the operating system."""
    return _number(env, P_CAPACITY_RESERVE, _DEFAULTS[P_CAPACITY_RESERVE])


def alert_intervals(env):
    """`(critical_hours, warning_hours)` — how often a problem says itself
    again. Zero or less means "never remind", which is the setting somebody
    wants the week they are already looking at a known problem."""
    return (_number(env, P_ALERT_EVERY_CRITICAL,
                    _DEFAULTS[P_ALERT_EVERY_CRITICAL]),
            _number(env, P_ALERT_EVERY_WARNING,
                    _DEFAULTS[P_ALERT_EVERY_WARNING]))


def health_ignore(env):
    """Substrings that mean "this log line is noise here". ONE PER LINE.

    Read with `param_row` because empty is a real answer (F24): a list parsed
    out of `get_param`'s `False` becomes `["False"]`, which is a filter that
    filters nothing and looks exactly like a working one.

    An ignored line is still RECORDED and still COUNTED — never deleted. A gate
    that cries wolf on every run is a gate the owner learns to click past
    (ledger F25), and a gate that hides what it ignored is worse.
    """
    raw = param_row(env, P_HEALTH_IGNORE)
    if raw is None:
        raw = _DEFAULTS[P_HEALTH_IGNORE]
    return [line.strip().lower() for line in str(raw).split('\n') if line.strip()]


# =============================================================================
# 2. WHAT A CUSTOMER MUST NEVER RECEIVE
#
# THE OWNER'S RULE, AND IT IS THE WHOLE SPEC: everything the master has, every
# customer gets — EXCEPT anything that runs the platform itself or anything that
# could be turned against the platform or against another customer.
#
# So the DEFAULT ANSWER IS YES, and this is the short, argued set of exceptions
# rather than a shortlist of what is allowed. Anything new ships to everybody
# unless somebody writes down here why it must not.
#
# ⚠ A NEVER-LIST IS A STATEMENT ABOUT THE DEPENDENCY GRAPH, NOT ABOUT A SET OF
# NAMES (ledger H57). Naming a module here does not keep it off a customer if
# something else the customer gets DEPENDS on it — the framework pulls a
# declared dependency whatever this list says. Anything added here has to be
# checked against the graph, and the report has to say so when it cannot be
# honoured.
#
# WHY THE LIST LIVES ON THE PLATFORM SIDE. This module is the one a customer's
# system is never allowed to have. A list of "what a customer must never be
# given" that shipped INSIDE a customer's system would be a map of the
# platform's soft spots, in the hands of the people it exists to keep out.
# =============================================================================
#: `{module name: the plain-English reason}`. The reason is shown ON SCREEN
#: beside the module, so it is written for the owner and not for an engineer.
NEVER = {}

#: A module is also held back when its name starts with one of these. A future
#: platform module is then refused BY DEFAULT rather than shipped to every
#: customer on the day it is written.
NEVER_PREFIXES = []

#: The one entry this module owns, because it is a fact about this module.
_OWN_REASON = (
    "The platform cockpit itself. It creates, backs up, restores and removes "
    "every system on this machine — including the master. Inside a customer's "
    "system it would be the controls to everybody else's.")


def register_never(entries=None, prefixes=None):
    """A product names what its customers must never receive.

    `entries` is `{name: reason}` or a bare sequence of names (a name with no
    reason gets a general one). `prefixes` is a sequence of name prefixes.
    """
    if isinstance(entries, dict):
        pairs = entries.items()
    else:
        pairs = [(n, '') for n in (entries or ())]
    for name, reason in pairs:
        if name and name not in NEVER:
            NEVER[name] = reason or never_reason(name)
    for prefix in (prefixes or ()):
        if prefix and prefix not in NEVER_PREFIXES:
            NEVER_PREFIXES.append(prefix)
    return dict(NEVER)


def is_never(name):
    """Is this part of the product one a customer's system never gets? PURE."""
    if not name:
        return False
    if name == 'biz_tenants' or name in NEVER:
        return True
    return name.startswith(tuple(NEVER_PREFIXES)) if NEVER_PREFIXES else False


def never_reason(name):
    """The plain-English reason, for the screen."""
    if name == 'biz_tenants':
        return _OWN_REASON
    if name in NEVER:
        return NEVER[name]
    return ("Reserved for the platform. Parts of the product that run this "
            "machine are never installed on a customer's system.")


def never_list():
    """Everything held back, with its reason, for the screen and for a test."""
    out = {'biz_tenants': _OWN_REASON}
    out.update(NEVER)
    return out


# =============================================================================
# 3. WHAT A CUSTOMER'S USE IS MEASURED IN
#
# The unit a customer is sold is a product decision and it is never one unit:
# one product charges per person in care, another per visit, another per person
# with a login. So the cockpit collects EVERY count every time and lets the
# selling decision be made later, out of numbers that were already gathered.
#
# EVERY METER GUARDS ON ITS OWN TABLE AND COLUMN EXISTING, and answers "not
# available here" rather than raising. A customer who has not been brought in
# step yet does not have every table, and one meter that raises must not take
# the other three with it.
# =============================================================================
#: `[{key, label, unit, sql, table_guard, column_guard}]`, in registration
#: order. The SQL takes `%(start)s` and `%(end)s` and nothing else.
METERS = []


def register_meter(spec):
    """A product says what one of its numbers is, and how to count it."""
    spec = dict(spec or {})
    if not spec.get('key') or not spec.get('sql'):
        raise ValueError("a meter needs a key and a query")
    if any(m['key'] == spec['key'] for m in METERS):
        return list(METERS)
    METERS.append({
        'key': spec['key'],
        'label': spec.get('label') or spec['key'],
        'unit': spec.get('unit') or '',
        'sql': spec['sql'],
        'table_guard': spec.get('table_guard') or '',
        'column_guard': spec.get('column_guard') or '',
        'help': spec.get('help') or '',
    })
    return list(METERS)


def meters():
    return list(METERS)


# =============================================================================
# 4. WHO A CUSTOMER'S OWN ADMINISTRATOR IS
#
# THE ONE ABSOLUTE. The customer's administrator runs their whole system and
# nothing of ours: they never hold `base.group_system`. That is the two-ring
# rule, and provisioning refuses to finish rather than hand over an account
# that still carries it.
#
# WHICH ROLE THEY HOLD IS THE PRODUCT'S TO SAY, by xml-id and never by name —
# the name is the one thing an administrator is invited to change.
# =============================================================================
_TENANT_ADMIN = {'role_xmlid': '', 'group_xmlids': ()}

#: What a customer's administrator must never carry. The same two the access
#: module refuses to put in any role.
PLATFORM_GROUP_XMLIDS = ('base.group_system', 'base.group_erp_manager')


def register_tenant_admin(spec):
    """A product names the role and the groups its own administrator holds."""
    spec = dict(spec or {})
    if spec.get('role_xmlid') and not _TENANT_ADMIN['role_xmlid']:
        _TENANT_ADMIN['role_xmlid'] = spec['role_xmlid']
    if spec.get('group_xmlids') and not _TENANT_ADMIN['group_xmlids']:
        _TENANT_ADMIN['group_xmlids'] = tuple(spec['group_xmlids'])
    return dict(_TENANT_ADMIN)


def tenant_admin():
    return dict(_TENANT_ADMIN)


# =============================================================================
# 5. WHERE A CUSTOMER'S ADMINISTRATOR LANDS
#
# Without a home action the framework drops somebody into the messaging app on
# their first sign-in, which is a poor first impression of any product.
# =============================================================================
_HOME_ACTION = ['']


def register_home_action(xmlid):
    """A product names the screen its administrator opens on."""
    if xmlid and not _HOME_ACTION[0]:
        _HOME_ACTION[0] = xmlid
    return _HOME_ACTION[0]


def home_action():
    return _HOME_ACTION[0]


# =============================================================================
# 6. THE SETTINGS PUSHED ONTO A CUSTOMER'S SYSTEM
#
# Kept as LITERALS here rather than imported from the platform link, because
# this module has to keep working on a master where that one is not installed
# yet. The two lists are asserted equal by a test, which is the only honest way
# to hold two copies of one contract.
# =============================================================================
TENANCY_MODULE = 'biz_tenancy'

T_RELEASE = 'biz_tenancy.release'
T_RELEASE_NOTES = 'biz_tenancy.release_notes'
T_RELEASE_AT = 'biz_tenancy.release_at'
T_RELEASES = 'biz_tenancy.releases'
T_NOTICE = 'biz_tenancy.notice'
T_NOTICE_KIND = 'biz_tenancy.notice_kind'
T_NOTICE_FROM = 'biz_tenancy.notice_from'
T_NOTICE_TO = 'biz_tenancy.notice_to'
T_PUSHED_AT = 'biz_tenancy.pushed_at'
T_PLATFORM_URL = 'biz_tenancy.platform_url'
T_SUPPORT_EMAIL = 'biz_tenancy.support_email'
T_SLUG = 'biz_tenancy.slug'
#: Which parts of the product this customer has. One JSON object, written
#: through the same single door as everything else.
T_FEATURES = 'biz_tenancy.features'
#: Whether this customer allows the platform in at all (SAAS H4c §3.5). Read
#: by the cockpit BEFORE a support link is minted, so the refusal names the
#: customer's own switch rather than failing at the door.
T_SUPPORT_ALLOWED = 'biz_tenancy.support_allowed'


# =============================================================================
# 7. WHICH PARTS OF THE PRODUCT CAN BE SWITCHED OFF
#
# A FEATURE IS NOT A MODULE, and that is the whole reason this is a registry
# rather than a list of module names. "Telehealth" is one thing a clinic buys
# and several parts of the product; "Family" is a portal and a message store.
# What a customer is SOLD is the product's own vocabulary, so the product says
# what the switches are and the cockpit only draws them.
#
# ⚠ AND SWITCHING ONE OFF IS NOT UNINSTALLING ANYTHING. The parts stay where
# they are; the doors to them close. Uninstalling a module from a live system
# takes its data with it, and no sales decision should ever be able to do that.
# =============================================================================
#: `[{key, name, blurb, sequence, default_on}]` in registration order.
#: `blurb` is what a CUSTOMER loses when it is off, written for the customer.
FEATURES = []


def register_features(specs):
    """A product names the parts of itself that can be sold separately."""
    for spec in (specs or ()):
        spec = dict(spec or {})
        key = str(spec.get('key') or '').strip()
        if not key or any(f['key'] == key for f in FEATURES):
            continue
        FEATURES.append({
            'key': key,
            'name': spec.get('name') or key,
            'blurb': spec.get('blurb') or '',
            'sequence': int(spec.get('sequence') or (len(FEATURES) + 1) * 10),
            'default_on': bool(spec.get('default_on', True)),
        })
    return list(FEATURES)


def features():
    return [dict(f) for f in FEATURES]


def feature_keys():
    return [f['key'] for f in FEATURES]


# =============================================================================
# 8. WHAT A CUSTOMER CAN BE PUT ON, AND WHAT IT COSTS
#
# ⚠ THE FIGURES AND THE CURRENCY BELONG TO THE PRODUCT, NOT TO THE COCKPIT
# (rail R11). A cockpit that shipped three plans priced in one country's money
# and named after one industry's customers would put the wrong words and the
# wrong currency in front of the next product on the day it was lifted. So the
# plans are a REGISTRATION, exactly like the features and the meters, and a
# machine where no product has registered any starts with an empty catalogue
# and a screen that says so.
#
# EVERY SEEDED PLAN IS A PLACEHOLDER UNTIL SOMEBODY SAYS OTHERWISE. `placeholder`
# is carried through onto the record and onto the screen, because an invoice
# raised from a figure nobody has looked at is the one mistake billing can make
# that reaches a paying customer.
# =============================================================================
#: `[{code, name, blurb, price_kind, meter_key, price, included, minimum,
#:    tiers, currency_xmlid, vat_rate, seat_limit, trial_days, sequence,
#:    placeholder}]`
PLANS = []


def register_plans(specs):
    """A product names what it sells and what it costs."""
    for spec in (specs or ()):
        spec = dict(spec or {})
        code = str(spec.get('code') or '').strip()
        if not code or any(p['code'] == code for p in PLANS):
            continue
        PLANS.append({
            'code': code,
            'name': spec.get('name') or code,
            'blurb': spec.get('blurb') or '',
            'price_kind': spec.get('price_kind') or 'flat',
            'meter_key': spec.get('meter_key') or '',
            'price': float(spec.get('price') or 0.0),
            'included': int(spec.get('included') or 0),
            'minimum': float(spec.get('minimum') or 0.0),
            'tiers': [dict(t) for t in (spec.get('tiers') or ())],
            'currency_xmlid': spec.get('currency_xmlid') or '',
            'vat_rate': float(spec.get('vat_rate') or 0.0),
            'seat_limit': int(spec.get('seat_limit') or 0),
            'trial_days': int(spec.get('trial_days') or 0),
            'sequence': int(spec.get('sequence') or (len(PLANS) + 1) * 10),
            'placeholder': bool(spec.get('placeholder', True)),
        })
    return list(PLANS)


def plans():
    return [dict(p, tiers=[dict(t) for t in p['tiers']]) for p in PLANS]


# -----------------------------------------------------------------------------
# AND WHAT THE PRODUCT'S OWN MENU LOOKS LIKE, FOR THE PREVIEW BESIDE THE MATRIX.
#
# THE SAME SEAM AS THE RAIL PROVIDER (ledger H6), FOR THE SAME REASON. The
# cockpit must be able to show what a customer's menu will look like with a
# switch off, and it has no idea what a menu is. So the product hands over ONE
# function, it TAKES `env` AS AN ARGUMENT because one registration serves every
# database this process ever loads, and with nothing registered the screen says
# honestly that nobody has told it what this product's menu is rather than
# drawing an empty one that looks like a loss.
# -----------------------------------------------------------------------------
_MENU_PREVIEW = [None]


def register_menu_preview(fn):
    """A product hands over `fn(env, off_keys) -> [sections]`."""
    if fn and _MENU_PREVIEW[0] is None:
        _MENU_PREVIEW[0] = fn
    return _MENU_PREVIEW[0]


def menu_preview(env, off_keys):
    """The miniature, or `None` where no product has said what a menu is."""
    fn = _MENU_PREVIEW[0]
    if not fn:
        return None
    try:
        return fn(env, set(off_keys or ()))
    except Exception:                                        # noqa: BLE001
        _logger.exception("biz_tenants: this product's menu preview raised; "
                          "the matrix is drawn without it.")
        return None
