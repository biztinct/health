{
    'name': 'Healthcare Website Security',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Security',
    'summary': 'Locks the public website snippet-filter route to an explicit model allow-list',
    'description': """
Healthcare Website Security
===========================

Closes T-003: the core ``/website/snippet/filters`` route is ``auth='public'``
and, on its single-record path, browses a **caller-supplied** ``res_model`` /
``res_id`` through a ``sudo()`` recordset, guarded only by an assertion on the
template key — not on the model. On a healthcare platform that turns a public
JSON-RPC endpoint into a read oracle over arbitrary models.

This module overrides ``website.snippet.filter._render`` to refuse any
caller-supplied ``res_model`` that is not on an explicit allow-list, BEFORE the
core method reaches the ``sudo()`` browse. Admin-configured filters
(``filter_id`` / ``action_server_id``) are untouched — that path is not
caller-controlled and is the intended dynamic-snippet feature.

The fix lives in an override module, never in a vendored copy of the core
``website`` addon (ledger §5.109).
""",
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
