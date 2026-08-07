# -*- coding: utf-8 -*-
{
    'name': 'Analytics Hub (CMS)',
    'version': '19.0.1.2.0',
    'category': 'Analytics',
    'summary': 'Puts the BI platform into the /bizapp sidebar and lands CMS '
               'users on a friendly Analytics hub.',
    'description': """
Analytics Hub — the way into BI for CMS users
=============================================

``biz_bi`` ships its own backend application (Home / Explore / Data /
Configuration). A real login on this deployment lands in the ``/bizapp`` CMS
shell, whose app switcher lists only its own apps, so that whole application
is reachable **only by typing a URL** (ledger §5.69, the same trap the
Channel Center and the clinical menus hit).

This glue module closes it:

* a new **ANALYTICS** section and a single **Analytics** leaf in the CMS
  sidebar, role-gated to Owner / Operations Manager / Branch Manager /
  Accountant — written in python, because ``access.role`` rows carry no
  xml-id on this platform;
* the same roles' users are granted ``biz_bi.group_bi_creator``: a sidebar
  item is *visibility*, never permission, and every BI record rule is keyed
  on the BI group ladder;
* an **Analytics Hub** client action (``biz_bi.hub``) — one RPC, a search
  box, a recents strip and a workspace grid listing **every** dashboard the
  user may see;
* a guided **three-step report wizard** behind that hub's "Create Report"
  button — pick a dataset, answer two questions (or ask in your own words
  where an AI provider is configured), preview, save onto a dashboard. It
  writes ordinary ``bi.chart`` rows in the exact ``config_json`` shape
  Explore writes, and "Open in advanced builder" hands the same state to the
  full builder at any point;
* a **Chart | Records list** choice on the wizard's build step, for the
  people who do not want a chart at all: tick the columns you want, keep the
  same date range, look at the rows, download them as a real ``.xlsx``, save
  the list onto a dashboard. It writes ``biz_bi``'s records shape
  (``chart_type: 'table'``, ``mode: 'detail'``, an ordered ``slots.columns``)
  so a wizard-made records report and an Explore-made one are the same row,
  and the export goes through ``biz_bi``'s own server-capped, audit-logged
  ``/bi/export/xlsx`` — record **names** in the cells, never ids.

Both surfaces answer honestly when there is nothing to show: a tenant whose
workspaces hold no dashboard yet gets one first-run card instead of a grid of
empty boxes, the wizard's step-3 list offers only the dashboards the user may
actually WRITE to (the same predicate the dashboard screen publishes as
``can_edit``, rather than the read-scoped list that used to refuse at Save
time), and the recents strip drops dashboards that have been deleted or moved
out of reach since they were viewed.

The existing backend Analytics application is left completely untouched for
power users; the hub is an additional, calmer front door.

Three defects of the old Home are deliberately not inherited: three
sequential awaited RPCs (now one), a single unscoped
``search_read('bi.dashboard', limit=40)`` that made workspaces past the
fortieth dashboard read "No dashboards yet", and a ``window.prompt()``.
    """,
    'author': 'VAFHS Development Team',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'biz_bi',
        'health_cms_sidebar',
    ],
    'data': [
        'views/bi_hub_actions.xml',
        'data/cms_sidebar_analytics.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_bi_cms/static/src/**/*.scss',
            'biz_bi_cms/static/src/**/*.js',
            'biz_bi_cms/static/src/**/*.xml',
        ],
    },
    # `access.role` rows have no xml-id here, so `role_ids` cannot be seeded
    # with ref() — the gating and the BI group grant are written by the hook,
    # exactly as health_cms_coverage does it, and re-applied by the migration
    # script so an upgrade converges with a fresh install.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 146,
}
