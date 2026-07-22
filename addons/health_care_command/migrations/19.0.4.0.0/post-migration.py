# -*- coding: utf-8 -*-
"""Phase-5 "Surface Truth" backfill (§2.5).

Populates the new channel-truth fields on the ~167 existing conversations:
  - has_channel_activity ← True where real traffic already set channel_primary
  - channel_declared     ← derived from the anchored lead's mode_of_contact

The whole logic lives in the unit-tested model method
``care.conversation._backfill_channel_truth`` (idempotent — re-running writes
nothing new and never touches channel_primary/status/unread/owner). This shim
just builds an Environment, calls it, and logs the per-channel breakdown.
``channel_effective`` is a stored compute added when the field was created at
upgrade, so it is already correct for every row; the declared writes here
trigger its recompute via @api.depends.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    res = env["care.conversation"]._backfill_channel_truth()
    _logger.info(
        "care_command Phase-5 backfill: has_channel_activity set on %s rows; "
        "channel_declared derived per channel = %s",
        res.get("activity_set"), res.get("declared"),
    )
