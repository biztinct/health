# -*- coding: utf-8 -*-
{
    'name': 'Care Command — VoIP Bridge',
    'version': '19.0.1.0.1',
    'category': 'Healthcare/CRM',
    'summary': 'Live VoIP call ingestion into the Care Command wall',
    'description': """
Care Command — VoIP Bridge
==========================

A thin auto-installing bridge between ``health_voip24h`` and
``health_care_command``. It exists ONLY when BOTH are installed, so
``health_care_command`` can keep VoIP as a soft (undeclared) dependency and
still install on a server where VoIP is absent.

What it does:

- Adds the live ingestion hook missing from Phase 1: a create-hook on
  ``voip.call.log`` that upserts a ``care.conversation`` for every new call
  (missed/abandoned incoming → ``needs_reply`` + missed-call flag; answered
  incoming → event-only; outgoing → ``waiting``). Mirrors the Phase-1
  ingestion hooks exactly, including the ``cr.savepoint()`` isolation so a
  Care Command bug can never break a VoIP webhook (§5.55).
- Re-runs the existing (already call-aware, idempotent) Care Command backfill
  on install so historic calls surface immediately.

The timeline + backfill in ``health_care_command`` already read
``voip.call.log`` defensively; this module supplies only the live create-hook.
""",
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_care_command',
        'health_voip24h',
    ],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    # Auto-install the moment BOTH parents are present — the bridge should
    # never need a manual install decision.
    'auto_install': True,
    'application': False,
    'sequence': 126,
}
