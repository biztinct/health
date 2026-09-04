# -*- coding: utf-8 -*-
{
    'name': 'Access, for the clinic',
    'summary': "The clinic's own words on the Access home — its areas, what "
               "each role lets somebody do, and the left menu each one opens",
    'description': """
The Access home, speaking this clinic's language.

WHAT THIS MODULE IS. `biz_access` is the home: roles written as bundles of
plain-English abilities, a passport for every person, the left menu drawn as
itself with its gates on it, and hand-overs that take themselves back. It ships
NO vocabulary, because the words on an access board belong to the application and
not to the module that draws them. This is that vocabulary, for this clinic:

  * **Five areas** — clinical care, front desk, operations, finance and
    administration — the words already on the left menu.
  * **An ability for every permission this clinic actually uses**, each one a
    sentence saying what it lets somebody do and what it stops short of. One
    ability per permission, deliberately: it is the only shape in which every
    role that exists today can be written down EXACTLY, with nothing added and
    nothing dropped.
  * **The clinic's roles as bundles**, each with a fixed name of its own, so a
    data file or a later release can point at "the Nurse role" and mean it.
  * **The left menu on the home.** This module tells the Access home how to read
    and write the clinic's own rail — which entries there are, who opens each
    one, and how to change that — and teaches the rail a second kind of gate
    beside the one it already has.
  * **The top bar, by role.** Which applications a role does not see, carried
    over from how the clinic has it set today and now enforced by the product
    itself.
  * **Adding a colleague, from the People lens.** Name, email, role, where they
    work and what they do — the login, the staff record and the role, in one
    form, done by an administrator who does not have the keys to the whole
    system.

TWO GATES, ON PURPOSE, FOR NOW. The clinic's left menu has been gated one way
since it was built. This module adds a second way beside it and reads the two as
an OR, so nobody loses a screen they had yesterday. Nothing is taken away here;
the older gate is retired in its own step, once the two have been proven to
agree, person by person.

WHAT IT NEVER DOES. Nothing here can hand out the system administrator
permission — the models refuse it, over everything a permission implies, and the
home checks again before it writes. Adding a colleague goes through the same
refusals: an administrator of this clinic can give somebody a job, and cannot
give anybody the keys to the box.
""",
    'version': '19.0.1.0.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'website': 'https://www.biztinct.com',
    # NOT `access_roles`, and NOT `health_user_admin`. Every read of either is
    # guarded (`'access.role' in env`, `'access_role_id' in fields`), so this
    # module still installs, upgrades and runs on the day they are gone.
    'depends': [
        'biz_access',
        'health_base',
        'health_cms_sidebar',
        'health_landing',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/cms_sidebar_views.xml',
        'views/new_person_views.xml',
        'data/cms_sidebar_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_access/static/src/js/health_access_palette.js',
        ],
    },
    # Seeds the clinic's vocabulary and carries the old app's data across. Both
    # are idempotent by construction; `biz.access.reseed_catalogue()` re-runs the
    # first and `health.access.migrate_legacy()` the second, because a hook does
    # not fire on an upgrade.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
