# -*- coding: utf-8 -*-
"""The proof: nobody lost a screen.

WHY A REPORT AND NOT A TEST. There is a test, and it runs on made-up people
whose access somebody chose. This is the other half: it runs on the REAL
seventy-odd colleagues of a working clinic, against the real menu they will sign
in to tomorrow, and it says for each of them exactly what changed. A rule that is
right about three fabricated users and wrong about one real nurse is a rule that
has failed, and only one of those two can find out.

WHAT IT COMPARES, AND WHY IT IS TWO QUESTIONS.

  * **The left menu.** Before: the previous application's rule alone. After:
    both lanes read as an OR. An OR can only ever add, so the arithmetic says
    this cannot lose anything — and the report proves it rather than asserting
    it, because "cannot" is what everybody says before the first exception.

  * **The top bar.** Before: the previous application's rule alone. After: both
    rules, and here it is the other way round — both SUBTRACT, so the danger is
    real. A screen is lost the moment the new rule hides something the old one
    did not, and that is the one number in this report worth staring at.

AND IT LOOKS ONE STEP FURTHER. A third column says what the top bar would be
with the OLD rule switched off — which is the state the next phase creates. It
is not a pass or fail today; it is the list of what will change on the day that
happens, worked out now while there is time to disagree with it.

IT WRITES NOTHING. Every read is a read. It is safe on a live database, and it
is meant to be run there.
"""

import logging

from odoo.addons.base.models.ir_ui_menu import IrUiMenu as CoreMenu

_logger = logging.getLogger(__name__)


def _drawn(data):
    out = set()
    for section in data or []:
        for item in section.get('items') or []:
            out.add(item['id'])
            for kid in item.get('children') or []:
                out.add(kid['id'])
    return out


def _rail_entry_ids(env, user, legacy_only=False):
    """The left-menu entries this person is DRAWN, as a set of ids.

    "Before" is not a reconstruction: it is the same method, run with the newer
    lane switched off by a context flag that exists for no other purpose. A
    report that rebuilt "before" out of a copy of the rule it is checking would
    be marking its own homework.
    """
    Item = env['cms.sidebar.item'].with_user(user).sudo()
    if legacy_only:
        Item = Item.with_context(health_access_no_biz_lane=True)
    return _drawn(Item.get_sidebar_data())


def _menu_ids(env, user, legacy_only=False):
    """The top-bar menus this person is drawn. Same trick, same reason."""
    Menu = env['ir.ui.menu'].with_user(user).sudo()
    if legacy_only:
        Menu = Menu.with_context(biz_access_no_menu_rule=True)
    return set(Menu._visible_menu_ids(debug=False))


def _new_only_menu_ids(env, user):
    """The top bar with the PREVIOUS application switched off.

    Not a pass or a fail today: it is the list of what changes on the day that
    happens, worked out while there is still time to disagree with it.

    The framework's own answer is asked of the framework's own method, by name,
    so that neither product rule is in the way — and then only this phase's rule
    is subtracted from it.
    """
    Menu = env['ir.ui.menu'].with_user(user).sudo()
    try:
        core = set(CoreMenu._visible_menu_ids(Menu, False))
    except Exception:                                   # noqa: BLE001
        # A forecast that cannot be made is reported as absent, never invented.
        _logger.warning('health_access: the top-bar forecast could not be '
                        'worked out for %s', user.login, exc_info=True)
        return None
    return core - set(Menu._biz_access_hidden_menu_ids())


def build(env):
    """Every active colleague, before and after, for both menus."""
    users = env['res.users'].sudo().search(
        [('active', '=', True), ('share', '=', False)], order='login')
    Menu = env['ir.ui.menu'].sudo()
    names = {}
    rows = []
    lost_rail = lost_menu = 0

    for user in users:
        rail_before = _rail_entry_ids(env, user, legacy_only=True)
        rail_after = _rail_entry_ids(env, user)
        menu_before = _menu_ids(env, user, legacy_only=True)
        menu_after = _menu_ids(env, user)
        menu_next = _new_only_menu_ids(env, user)

        rail_lost = rail_before - rail_after
        rail_gained = rail_after - rail_before
        menu_lost = menu_before - menu_after
        menu_gained = menu_after - menu_before
        next_gained = (menu_next - menu_after) if menu_next is not None else set()
        next_lost = (menu_after - menu_next) if menu_next is not None else set()

        lost_rail += len(rail_lost)
        lost_menu += len(menu_lost)
        for mid in list(menu_gained) + list(next_gained) + list(next_lost):
            if mid not in names:
                names[mid] = Menu.browse(mid).complete_name or str(mid)

        rows.append({
            'login': user.login or '',
            'name': user.name or '',
            'role': (user.access_role_id.name or '')
                    if 'access_role_id' in user._fields else '',
            'rail_before': len(rail_before),
            'rail_after': len(rail_after),
            'rail_lost': sorted(rail_lost),
            'rail_gained': sorted(rail_gained),
            'menu_before': len(menu_before),
            'menu_after': len(menu_after),
            'menu_lost': sorted(menu_lost),
            'menu_gained': sorted(menu_gained),
            'menu_next': (len(menu_next) if menu_next is not None else None),
            'next_gained': sorted(next_gained),
            'next_lost': sorted(next_lost),
        })

    return {'rows': rows, 'names': names, 'users': len(users),
            'lost_rail': lost_rail, 'lost_menu': lost_menu}


def as_markdown(env, result=None):
    """The report, written the way somebody reads it: the verdict first."""
    res = result or build(env)
    rows, names = res['rows'], res['names']
    out = []
    out.append('# Carry-over — before and after, person by person')
    out.append('')
    out.append('Database: `%s`. %s colleague(s) with a login.'
               % (env.cr.dbname, res['users']))
    out.append('')
    out.append('## The verdict')
    out.append('')
    out.append('| | left-menu entries | top-bar screens |')
    out.append('|---|---|---|')
    out.append('| **lost by anybody** | **%s** | **%s** |'
               % (res['lost_rail'], res['lost_menu']))
    out.append('| gained by somebody | %s | %s |'
               % (sum(len(r['rail_gained']) for r in rows),
                  sum(len(r['menu_gained']) for r in rows)))
    out.append('')
    if res['lost_rail'] or res['lost_menu']:
        out.append('> **Somebody lost something.** The rows below name them. '
                   'This is a failed carry-over, not a note.')
    else:
        out.append('> Nobody lost a single entry or a single screen. Every '
                   'person sees at least everything they saw before.')
    out.append('')

    out.append('## Every person')
    out.append('')
    out.append('| Sign-in | Role | Menu before → after | Top bar before → after '
               '| Lost | Gained |')
    out.append('|---|---|---|---|---|---|')
    for r in rows:
        gained = ', '.join(names.get(m, str(m)) for m in r['menu_gained'])
        out.append('| `%s` | %s | %s → %s | %s → %s | %s | %s |' % (
            r['login'], r['role'] or '—',
            r['rail_before'], r['rail_after'],
            r['menu_before'], r['menu_after'],
            (len(r['rail_lost']) + len(r['menu_lost'])) or '0',
            gained or '—'))
    out.append('')

    out.append('## What the next phase would change')
    out.append('')
    out.append('The top bar with the previous application switched off. '
               'Nothing here has happened yet.')
    out.append('')
    out.append('| Sign-in | Role | Top bar now | Then | Would gain | Would lose |')
    out.append('|---|---|---|---|---|---|')
    for r in rows:
        if r['menu_next'] is None:
            continue
        if not r['next_gained'] and not r['next_lost']:
            continue
        out.append('| `%s` | %s | %s | %s | %s | %s |' % (
            r['login'], r['role'] or '—', r['menu_after'], r['menu_next'],
            _few(names, r['next_gained']), _few(names, r['next_lost'])))
    out.append('')
    return '\n'.join(out)


def _few(names, ids, cap=6):
    """A handful of names and a count, never a paragraph of them.

    A column that lists five hundred menu paths is a column nobody reads, and it
    turns a report somebody has to check into a file they scroll past.
    """
    if not ids:
        return '—'
    shown = [names.get(m, str(m)) for m in ids[:cap]]
    if len(ids) > cap:
        shown.append('and %s more' % (len(ids) - cap))
    return ', '.join(shown)


def write(env, path):
    text = as_markdown(env)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    _logger.info('health_access: carry-over diff written to %s', path)
    return path


# =============================================================================
# THE RETIREMENT'S OWN PROOF — a snapshot, and the same snapshot again
#
# The report above compares two answers the SAME database can give at the same
# moment, because both rules were installed side by side. The retirement cannot
# be checked that way: "before" is a database with the old application on it and
# "after" is a database without, and no single moment holds both.
#
# So "before" is written to a file first and read back afterwards. THE SAME
# FUNCTION PRODUCES BOTH SIDES — one file, run twice — because two functions
# that were meant to agree are two functions that eventually do not, and the one
# doing the comparing would be the one deciding what "before" had been.
#
# It writes nothing and reads only what a person could read. Safe on a live
# database and meant to be run on one.
# =============================================================================
def _flags_of(record):
    """The four things the product asks about somebody's job."""
    out = {}
    for name in ('is_doctor_role', 'is_nurse_role', 'is_om_role',
                 'access_role_display'):
        if name in record._fields:
            value = record[name]
            out[name] = value if isinstance(value, bool) else (value or '')
    return out


def _roles_held(env, user):
    """The names of the bundles this person holds IN FULL, sorted.

    Held, not assigned: the two are different numbers and only one of them is
    what somebody can actually do.
    """
    if 'biz.access.role' not in env:
        return []
    held = set(user.sudo().all_group_ids.ids)
    names = []
    for role in env['biz.access.role'].sudo().search([('active', '=', True)]):
        groups = set(role.group_ids.ids)
        if groups and groups <= held:
            names.append(role.name or '')
    return sorted(names)


def snapshot(env):
    """Everything this phase could take away from somebody, per person.

    Keyed by login rather than by id, so the two sides can be compared across a
    restore, and menus are recorded by their full path rather than their id for
    the same reason — an id survives an uninstall, and a menu that is deleted
    and recreated does not.
    """
    Menu = env['ir.ui.menu'].sudo()
    users = env['res.users'].sudo().search(
        [('active', '=', True), ('share', '=', False)], order='login')
    rows = {}
    for user in users:
        menu_ids = env['ir.ui.menu'].with_user(user).sudo()._visible_menu_ids(
            debug=False)
        rail = env['cms.sidebar.item'].with_user(user).sudo().get_sidebar_data()
        rows[user.login or str(user.id)] = {
            'name': user.name or '',
            'rail': sorted(_rail_names(rail)),
            'menus': sorted(
                Menu.browse(list(menu_ids)).mapped('complete_name')),
            'roles_held': _roles_held(env, user),
            'flags': _flags_of(user),
        }
    staff = {}
    Employee = env['hr.employee'].sudo().with_context(active_test=False)
    for emp in Employee.search([]):
        staff['%s|%s' % (emp.id, emp.name or '')] = _flags_of(emp)
    return {'db': env.cr.dbname, 'people': rows, 'staff': staff}


def _rail_names(data):
    """Left-menu entries by NAME, at both levels, as a flat set."""
    out = set()
    for section in data or []:
        for item in section.get('items') or []:
            out.add('%s / %s' % (section.get('name') or '', item['name']))
            for kid in item.get('children') or []:
                out.add('%s / %s / %s' % (section.get('name') or '',
                                          item['name'], kid['name']))
    return out


def write_snapshot(env, path):
    import json                                          # noqa: PLC0415
    data = snapshot(env)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=1, sort_keys=True)
    _logger.info('health_access: snapshot of %s people written to %s',
                 len(data['people']), path)
    return path


def compare_markdown(env, before_path, after=None):
    """The retirement, person by person: what nobody lost, and what changed."""
    import json                                          # noqa: PLC0415
    with open(before_path, encoding='utf-8') as handle:
        before = json.load(handle)
    after = after or snapshot(env)

    out = ['# Retiring the previous access application — before and after', '']
    out.append('Database: `%s` before, `%s` after. %s / %s colleague(s).'
               % (before.get('db'), after.get('db'),
                  len(before['people']), len(after['people'])))
    out.append('')

    lost_rail = lost_roles = flag_changes = 0
    rows = []
    for login, was in sorted(before['people'].items()):
        now = after['people'].get(login)
        if now is None:
            rows.append((login, was['name'], 'GONE', '', '', '', ''))
            continue
        rail_lost = sorted(set(was['rail']) - set(now['rail']))
        rail_gained = sorted(set(now['rail']) - set(was['rail']))
        menu_lost = sorted(set(was['menus']) - set(now['menus']))
        menu_gained = sorted(set(now['menus']) - set(was['menus']))
        roles_lost = sorted(set(was['roles_held']) - set(now['roles_held']))
        flags_same = was['flags'] == now['flags']
        lost_rail += len(rail_lost)
        lost_roles += len(roles_lost)
        flag_changes += 0 if flags_same else 1
        rows.append((login, was['name'],
                     '%s → %s' % (len(was['rail']), len(now['rail'])),
                     '%s → %s' % (len(was['menus']), len(now['menus'])),
                     _few_names(rail_lost) if rail_lost else '—',
                     _few_names(menu_lost) if menu_lost else '—',
                     'same' if flags_same else 'CHANGED'))
        del rail_gained, menu_gained

    staff_changed = [
        key for key, flags in before['staff'].items()
        if key in after['staff'] and after['staff'][key] != flags]

    out.append('## The verdict')
    out.append('')
    out.append('| | count |')
    out.append('|---|---|')
    out.append('| left-menu entries **lost by anybody** | **%s** |' % lost_rail)
    out.append('| roles **no longer held by somebody who held them** | **%s** |'
               % lost_roles)
    out.append('| people whose job flags changed | **%s** |' % flag_changes)
    out.append('| staff records whose job flags changed | **%s** |'
               % len(staff_changed))
    out.append('')
    if lost_rail or lost_roles or flag_changes or staff_changed:
        out.append('> **Something changed that was not meant to.** The rows '
                   'below name it.')
    else:
        out.append('> Nobody lost a left-menu entry, nobody lost a role, and '
                   'every staff record still says the same job it said before.')
    out.append('')
    if staff_changed:
        out.append('Staff records that changed: %s'
                   % ', '.join(staff_changed[:20]))
        out.append('')

    out.append('## Every person')
    out.append('')
    out.append('| Sign-in | Name | Left menu | Top bar | Menu entries lost | '
               'Top-bar screens lost | Job flags |')
    out.append('|---|---|---|---|---|---|---|')
    for row in rows:
        out.append('| `%s` | %s | %s | %s | %s | %s | %s |' % row)
    out.append('')
    return '\n'.join(out)


def _few_names(names, cap=5):
    if not names:
        return '—'
    shown = list(names[:cap])
    if len(names) > cap:
        shown.append('and %s more' % (len(names) - cap))
    return ', '.join(shown)


def write_compare(env, before_path, path):
    text = compare_markdown(env, before_path)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    _logger.info('health_access: retirement diff written to %s', path)
    return path
