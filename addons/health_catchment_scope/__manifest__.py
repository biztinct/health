# -*- coding: utf-8 -*-
{
    'name': 'Healthcare — Catchment Area Scope',
    'version': '19.0.1.1.0',
    'category': 'Healthcare',
    'summary': 'Every list, kanban, calendar and timeline opens filtered to the '
               'user\'s own catchment area, and says so. Owners may switch area.',
    'description': """
Catchment-area scope, made visible
==================================

The data spine for catchment areas already existed before this module: 56
models carry a stored ``catchment_province_id`` and 51 of them carry record
rules comparing it to ``user.catchment_province_id``. What was missing was any
*sign* of it — a user had no way to tell that the short list in front of them
was scoped rather than empty, and an owner had no way to focus on one area.

This module is the engine, and holds no per-model knowledge:

* **A generic search-filter injector** (``ir.ui.view._postprocess_access_rights``)
  that adds a default-on ``My Catchment Area: <name>`` filter to the search view
  of *every* model that has a catchment field. Non-owners get exactly one
  catchment filter and no catchment search field, so no other area's name is
  reachable anywhere in the search UI. Owners additionally get one filter per
  other area, and the field, so they can widen or switch.

* **A province visibility rule** so the operational roles only ever see their
  own area in a Many2one dropdown — a Hanoi receptionist can no longer file a
  client under Ho Chi Minh City and lose it.

* **Helpers on ``res.users``** that the CMS sidebar reads to draw its scope pill.

Two things this module deliberately does NOT do:

* **It is not the security boundary.** Removing the filter facet must never
  reveal another area's records — that is what the record rules are for. The
  facet is a signal. The tests assert both halves separately.

* **It does not fail open.** A non-owner with no catchment area set gets a
  filter that matches nothing, not an unfiltered list. See
  ``action_users_missing_catchment`` for the data-quality list that goes with
  that choice.

Gotcha paid for during the build (ledger-worthy): core's
``_postprocess_access_rights`` **pops** ``model_access_rights`` off the tree
(``ir_ui_view.py:1357``). Any override that calls ``super()`` first and then
reads that attribute gets ``None`` and silently does nothing — which is exactly
the state ``health_field_requirements/models/ir_ui_view.py`` is in. Read the
attribute BEFORE delegating.
    """,
    'author': 'Biztinct',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_base',
    ],
    'data': [
        'security/catchment_scope_security.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 142,
}
