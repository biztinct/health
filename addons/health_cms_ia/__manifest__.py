# -*- coding: utf-8 -*-
{
    'name': 'Healthcare CMS — Consolidated Menu',
    'version': '19.0.1.1.0',
    'category': 'Healthcare',
    'summary': 'Regroups the left menu into areas, tabs and the screens inside '
               'each tab, and gives every entry the roles that open it. Data '
               'glue plus one hook — no screen is added or removed.',
    'description': """
The consolidated left menu (MENU IA phase M2)
=============================================

The shell drawn by phase M1 reads a section as a rail entry, a root entry as a
tab and a child as a segment inside the tab. This module fills it: 115 entries
regrouped into nine areas and about fifty tabs, following the table the owner
approved (``docs/handovers/MENU_M2_CONSOLIDATION.md`` §2), and the gate matrix
the owner ruled on (§2b) — no entry is left open to everybody by accident.

WHY A GLUE MODULE THAT LOADS LAST. The rows it moves are seeded by twelve
modules, most of them ``noupdate="1"`` — an upgrade never re-writes those, so
the move has to be WRITTEN, by a hook. It depends on every module that seeds a
row, so it always runs after all of them and nothing can depend back on it (a
dependency loop's symptom is a green "0 of 0 tests", ledger §5.71).

THE SEEDS THAT RE-ASSERT THEMSELVES were edited in their own modules to say the
final place, so a later upgrade of one of them cannot pull a row back where it
was (``biz_bi_cms``, the three Care Command modules, the phone bridge, the
website-leads module, the advertising module).

See ``hooks.py``: every move, rename and gate is a line in a table keyed by the
row's fixed name, and every run says what it changed.
    """,
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        # EVERY module that seeds a left-menu row this module moves, renames
        # or gates. All of them are upstream of this one and none of them
        # depends on it, so no loop is possible (walked transitively, §5.71).
        'health_cms_sidebar',
        'health_cms_coverage',
        'health_cms_clinical',
        'health_access',
        'health_tenancy',
        'biz_bi_cms',
        'health_care_command',
        'health_care_command_channels',
        'health_care_command_voip',
        'health_web_leads',
        'health_google_ads',
        'health_learn',
    ],
    'data': [
        'data/cms_sidebar_tabs.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 142,
}
