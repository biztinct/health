# -*- coding: utf-8 -*-
{
    'name': 'Health Learn — CareJioX in-app learning',
    'version': '19.0.5.0.0',
    'category': 'Healthcare',
    'summary': 'Guided Journey, bilingual lesson spine and anchor registry for the CRM desk',
    'author': 'Biztinct',
    'description': """
CareJioX Learn — Phase 1: the content spine.
============================================

One content model feeds every learning surface. Phase 1 ships the spine, the
anchor registry and the Guided Journey; the always-on Care Coach (Phase 2) and
the practice missions (Phase 3) add rows to these same tables rather than new
ones.

Design: docs/learn/PHASE1_DESIGN.md
Authoring surface: docs/tutorial_crm/ (the prototype; content is generated from
it, never hand-edited here).
    """,
    'depends': [
        # The sidebar leaf the Journey hangs off, and the menu inventory the
        # content teaches. Pulls health_crm / access_roles transitively.
        'health_cms_sidebar',
        # The two flagship screens. Phase 1 registers anchors in their
        # templates; Phase 2's Coach grounds its answers on them.
        'health_care_command',
        'health_care_command_channels',
        # Web Touchpoints + Lead Analysis are two of the eight CRM stations.
        # Teaching a screen we do not require would leave two dead nodes on the
        # map at any clinic that skipped the module.
        'health_web_leads',
        # --vuf-* design tokens, so the Journey re-themes with the Theme Engine
        # instead of carrying its own copy of the palette.
        'health_theme',
        # The tenant-administrator group. Editing this clinic's override slots
        # is a tenant-admin job, and that group already means exactly that here
        # — declaring a second one would be a role model that drifts.
        'health_user_admin',
    ],
    'data': [
        'security/learn_security.xml',
        'security/ir.model.access.csv',
        # Generated from docs/tutorial_crm/ — see tools/gen_learn_data.py.
        # noupdate="0" throughout: an edited record MUST apply on upgrade.
        'data/learn_strings.xml',
        'data/learn_glossary.xml',
        'data/learn_tenant_slots.xml',
        'data/learn_stations.xml',
        'data/learn_lessons.xml',
        # Phase 2 — the Coach. Intents first: screens reference them.
        'data/learn_intents.xml',
        'data/learn_screens.xml',
        'data/learn_columns.xml',
        # Phase 3 — practice missions. They run on the REPLICA only.
        'data/learn_missions.xml',
        # Hand-written.
        'views/learn_actions.xml',
        'data/learn_sidebar_item.xml',
        'views/learn_content_views.xml',
        'views/learn_override_views.xml',
        'views/learn_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'health_learn/static/src/journey/journey.scss',
            'health_learn/static/src/engine/*.js',
            'health_learn/static/src/journey/journey.js',
            'health_learn/static/src/journey/icons.xml',
            'health_learn/static/src/journey/journey.xml',
            # Phase 2 — the always-on Coach, mounted in the web client
            # shell so it reaches every screen without per-screen work.
            'health_learn/static/src/coach/coach.scss',
            'health_learn/static/src/coach/coach.js',
            'health_learn/static/src/coach/coach.xml',
            'health_learn/static/src/coach/coach_patch.js',
            'health_learn/static/src/coach/coach_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 145,
    'license': 'LGPL-3',
}
