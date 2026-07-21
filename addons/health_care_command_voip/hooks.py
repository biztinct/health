# -*- coding: utf-8 -*-
"""post_init: re-run the Care Command backfill now that VoIP exists.

The Phase-1 backfill (``health_care_command/hooks.py``) is already call-aware
and idempotent — it reads ``voip.call.log`` behind ``if 'voip.call.log' in
env``. On the original ``health_care_command`` install that guard was False
(VoIP wasn't installed), so no call legs were seeded. Now that this bridge has
pulled ``health_voip24h`` in, re-invoking the SAME helper backfills the historic
calls; re-running creates nothing else new (the upsert keys on anchors).
"""

import logging

from odoo.addons.health_care_command.hooks import post_init_hook as _care_backfill

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _logger.info("care_command_voip: re-running Care Command backfill for calls")
    _care_backfill(env)
