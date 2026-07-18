# -*- coding: utf-8 -*-
"""Backfill (condition-spine handover §2.3).

Promote every EXISTING coded-diagnosis sidecar row into ``health.condition``
by replaying the live sync path (``_sync_health_conditions``) — NOT raw SQL —
so recorded_date / recorder / evidence provenance is identical to a fresh
assertion. Idempotent: a re-run creates nothing new (the sync searches first).
"""

import logging

_logger = logging.getLogger(__name__)

_BATCH = 200


def post_init_hook(env):
    Note = env['health.clinical.note'].sudo()
    Condition = env['health.condition'].sudo()
    # Notes that carry at least one ICD-10 code on the sidecar.
    notes = Note.search([('condition_code_ids', '!=', False)])
    before = Condition.search_count([])
    for start in range(0, len(notes), _BATCH):
        notes[start:start + _BATCH]._sync_health_conditions()
    after = Condition.search_count([])
    _logger.info(
        'health_condition backfill: %d coded notes → %d problem-list records '
        'created (%d total now).', len(notes), after - before, after)
