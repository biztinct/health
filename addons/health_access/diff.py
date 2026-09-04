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
